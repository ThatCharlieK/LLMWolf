"""Day phase: discussion period with countdown timer and chunked recording."""

import threading
import time

import numpy as np
import questionary
from rich.console import Console

from werewolf.state import GameState
from werewolf.llm import get_day_response, is_ai_player, AI_PLAYER_NAME
from werewolf.ui import clear_screen, show_panel, show_big_text, countdown, ROLE_COLORS, speak

console = Console()

# Default discussion time in seconds (5 minutes)
DISCUSSION_TIME = 300

# How often (seconds) the AI speaks during discussion
AI_SPEAK_INTERVAL = 30


def _record_chunk(
    duration: float,
    stop_event: threading.Event,
    sample_rate: int = 16000,
) -> tuple[np.ndarray | None, int]:
    """Record a chunk of microphone audio, stoppable early via stop_event.

    Uses PortAudio callback streaming at 16kHz mono float32 (Whisper format).
    Returns the captured audio trimmed to actual length.

    :param duration: Maximum recording length in seconds.
    :param stop_event: Set externally to end recording early.
    :param sample_rate: Audio sample rate (default 16kHz for Whisper).
    :returns: Tuple of (audio array or None on error, sample rate).
    """
    try:
        import sounddevice as sd

        frames_needed = int(duration * sample_rate)
        audio = np.zeros(frames_needed, dtype="float32")
        actual_frames = [0]

        def callback(indata, frame_count, _time_info, _status):
            start = actual_frames[0]
            end = min(start + frame_count, frames_needed)
            count = end - start
            audio[start:end] = indata[:count, 0]
            actual_frames[0] = end
            if end >= frames_needed or stop_event.is_set():
                raise sd.CallbackStop()

        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        stream.start()
        stop_event.wait(timeout=duration)
        stream.stop()
        stream.close()

        return audio[: actual_frames[0]], sample_rate
    except Exception as e:
        console.print(f"[dim]Recording error: {e}[/dim]")
        return None, sample_rate


def _discussion_loop(
    state: GameState,
    stop_event: threading.Event,
    timer_pause: threading.Event,
    enrollments: dict,
) -> None:
    """Background thread: record → transcribe → AI response → TTS, repeating.

    Each cycle records a chunk of audio, transcribes it with speaker
    diarization, appends the new segments to state.discussion_transcript,
    then has the AI respond based on the accumulated transcript.
    The timer is paused during transcription/LLM/TTS so players don't
    lose discussion time while the AI is processing.

    :param state: Current game state (transcript is mutated in place).
    :param stop_event: Set by the main thread to end the discussion.
    :param timer_pause: Set to pause the countdown timer, cleared to resume.
    :param enrollments: Speaker enrollment embeddings for diarization.
    """
    from werewolf.stt import transcribe_and_diarize

    ai_role = state.original_roles.get(AI_PLAYER_NAME, "Unknown")
    human_count = sum(1 for p in state.players if not is_ai_player(p))
    discussion_start = time.time()

    while not stop_event.is_set():
        # 1. Record a chunk (timer runs — players are talking)
        time_offset = time.time() - discussion_start
        console.print("[dim]Recording...[/dim]")
        audio, sr = _record_chunk(AI_SPEAK_INTERVAL, stop_event)

        # 2. Pause the timer while we process
        timer_pause.set()

        # 3. Transcribe the chunk
        if audio is not None and len(audio) >= sr * 0.5:
            try:
                console.print("[dim]Transcribing...[/dim]")
                segments = transcribe_and_diarize(
                    audio,
                    enrollments=enrollments,
                    min_speakers=1,
                    max_speakers=max(1, human_count),
                )
                for seg in segments:
                    state.discussion_transcript.append({
                        "speaker": seg.speaker,
                        "text": seg.text,
                        "start": seg.start + time_offset,
                        "end": seg.end + time_offset,
                    })
            except Exception as e:
                console.print(f"[dim]Transcription error: {e}[/dim]")

        # 4. If discussion ended during recording/transcription, stop
        if stop_event.is_set():
            timer_pause.clear()
            break

        # 5. Get AI response with the accumulated transcript
        response = get_day_response(ai_role, state.discussion_transcript)

        if stop_event.is_set():
            timer_pause.clear()
            break

        # 6. Speak via TTS (blocking — no recording happening, so no mic feedback)
        tts_start = time.time() - discussion_start
        speak(response)
        tts_end = time.time() - discussion_start

        # 7. Add AI utterance to the running transcript
        state.discussion_transcript.append({
            "speaker": AI_PLAYER_NAME,
            "text": response,
            "start": tts_start,
            "end": tts_end,
        })

        # 8. Resume the timer — back to recording
        timer_pause.clear()


def run_day(state: GameState, enrollments: dict):
    """Run the day discussion period with a countdown timer.

    Players discuss in real life while the timer counts down.
    Pressing Enter pauses the timer and prompts to end early (with confirmation).
    Records and transcribes the discussion in 30-second chunks so the AI can
    hear and respond to what players actually say.
    """
    clear_screen()
    show_big_text("DAY PHASE", style="bold yellow")

    show_panel(
        "Discussion Time",
        "Everyone, open your eyes!\n\n"
        "Discuss! Try to figure out who the werewolves are.\n"
        "Anyone can say anything — including lying.",
        style="yellow",
    )

    player_list = "  ".join(
        f"[bold]{name}[/bold]" for name in state.players
    )
    console.print(f"\nPlayers: {player_list}\n")
    console.print("[dim]Press Enter to end discussion early[/dim]\n")

    stop_event = threading.Event()
    timer_pause = threading.Event()

    # Start the unified discussion loop (record → transcribe → AI → TTS)
    discussion_thread = threading.Thread(
        target=_discussion_loop,
        args=(state, stop_event, timer_pause, enrollments),
        daemon=True,
    )
    discussion_thread.start()

    remaining = DISCUSSION_TIME
    while remaining > 0:
        remaining = countdown(remaining, "Discussion time remaining", interruptible=True, pause_event=timer_pause)
        if remaining > 0:
            confirm = questionary.confirm(
                "Are you sure you want to end discussion early?",
                default=False,
            ).ask()
            if confirm:
                break
            # Not confirmed — resume timer
            clear_screen()
            show_big_text("DAY PHASE", style="bold yellow")
            console.print(f"\nPlayers: {player_list}\n")
            console.print("[dim]Press Enter to end discussion early[/dim]\n")

    # Stop discussion and wait for thread to finish
    stop_event.set()
    discussion_thread.join(timeout=30.0)

    # Display the accumulated transcript
    if state.discussion_transcript:
        from werewolf.stt import format_transcript, Segment

        segments = [
            Segment(
                speaker=d["speaker"],
                text=d["text"],
                start=d["start"],
                end=d["end"],
            )
            for d in state.discussion_transcript
        ]
        transcript = format_transcript(segments)
        if transcript:
            console.print("\n[bold]Discussion Transcript:[/bold]")
            console.print(transcript)
            console.print()
    else:
        console.print("[dim]No discussion was transcribed.[/dim]")
