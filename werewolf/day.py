"""Day phase: discussion period with countdown timer and optional recording."""

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


def _record_background(
    duration: float,
    result_holder: dict[str, object],
    stop_event: threading.Event,
    mute_event: threading.Event | None = None,
) -> None:
    """
    Record microphone audio in a background thread for the day discussion.

    Uses PortAudio's callback-based streaming API (via sounddevice) rather than
    the simpler sd.rec() because the recording must be stoppable early from the
    main thread when a player ends discussion. The callback is the only clean way
    to receive audio chunks incrementally and signal PortAudio to stop gracefully
    via sd.CallbackStop().

    Audio is captured at 16kHz mono float32 — the format expected by downstream
    STT models (Whisper). Using the system default sample rate / channels would
    require resampling later.

    :param duration: Maximum recording length in seconds.
    :type duration: float
    :param result_holder: Mutable dict written to from this thread. On success,
        populated with 'audio' (np.ndarray) and 'sample_rate' (int).
        On failure, populated with 'error' (str).
    :type result_holder: dict[str, object]
    :param stop_event: Set by the main thread to end recording early.
    :type stop_event: threading.Event
    :param mute_event: When set, the callback writes silence instead of mic
        audio. Used to prevent TTS playback from being captured.
    :type mute_event: threading.Event | None
    """
    try:
        import sounddevice as sd

        sample_rate: int = 16000
        frames_needed: int = int(duration * sample_rate)
        # Pre-allocate the full buffer upfront to avoid growing a list of chunks
        audio: np.ndarray = np.zeros(frames_needed, dtype="float32")
        # Mutable container so the callback (which runs on PortAudio's C thread)
        # can update the write position across invocations
        actual_frames: list[int] = [0]

        def callback(
            indata: np.ndarray,
            frame_count: int,
            _time_info: object,
            _status: sd.CallbackFlags,
        ) -> None:
            """
            Called by PortAudio each time a new chunk of mic samples arrives.

            Copies incoming mono samples into the pre-allocated buffer and
            raises CallbackStop when the buffer is full or stop_event is set.
            When mute_event is set, writes silence (zeros) instead of mic data
            to prevent TTS playback from being captured and re-transcribed.

            :param indata: Incoming audio samples from the microphone.
            :type indata: np.ndarray
            :param frame_count: Number of frames in this chunk.
            :type frame_count: int
            :param _time_info: PortAudio timing metadata (unused).
            :type _time_info: object
            :param _status: Stream status flags (e.g. overflow warnings).
            :type _status: sd.CallbackFlags
            """
            start: int = actual_frames[0]
            end: int = min(start + frame_count, frames_needed)
            count: int = end - start
            if mute_event is not None and mute_event.is_set():
                audio[start:end] = 0.0
            else:
                audio[start:end] = indata[:count, 0]
            actual_frames[0] = end
            if end >= frames_needed or stop_event.is_set():
                # Tells PortAudio to drain remaining samples and stop cleanly
                raise sd.CallbackStop()

        stream: sd.InputStream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,       # mono — stereo adds no value for speech recognition
            dtype="float32",  # native format for numpy and Whisper
            callback=callback,
        )
        stream.start()
        # Block this thread until duration elapses or main thread signals stop
        stop_event.wait(timeout=duration)
        stream.stop()
        stream.close()

        # Trim to only the frames actually written by the callback
        result_holder["audio"] = audio[: actual_frames[0]]
        result_holder["sample_rate"] = sample_rate
    except Exception as e:
        result_holder["error"] = str(e)


def _llm_discussion_loop(
    state: GameState,
    stop_event: threading.Event,
    mute_event: threading.Event,
    ai_segments: list[dict],
    rec_start_time: float,
):
    """Background thread that has the AI speak every AI_SPEAK_INTERVAL seconds.

    Mutes the mic recording while TTS plays to prevent Claude's speech from
    being captured and re-transcribed. Instead, Claude's utterances are tracked
    in ai_segments and merged into the transcript after STT processing.

    :param state: Current game state (for role info and transcript context).
    :param stop_event: Set by the main thread to end the discussion.
    :param mute_event: Set while TTS is playing to silence mic capture.
    :param ai_segments: Mutable list that accumulates Claude's utterances as
        dicts with 'speaker', 'text', 'start', and 'end' keys.
    :param rec_start_time: Wall-clock time when recording started, used to
        compute segment timestamps relative to the audio stream.
    """
    ai_role = state.original_roles.get(AI_PLAYER_NAME, "Unknown")

    while not stop_event.is_set():
        if stop_event.wait(timeout=AI_SPEAK_INTERVAL):
            break

        response = get_day_response(ai_role, state.discussion_transcript)

        start = time.time() - rec_start_time
        mute_event.set()
        speak(response)
        mute_event.clear()
        end = time.time() - rec_start_time

        ai_segments.append({
            "speaker": AI_PLAYER_NAME,
            "text": response,
            "start": start,
            "end": end,
        })


def run_day(state: GameState, enrollments: dict):
    """Run the day discussion period with a countdown timer.

    Players discuss in real life while the timer counts down.
    Pressing Enter pauses the timer and prompts to end early (with confirmation).
    Records and transcribes the discussion with speaker diarization.
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
    mute_event = threading.Event()
    record_result: dict = {}
    ai_segments: list[dict] = []
    rec_start_time = time.time()

    # Start background recording
    console.print("[dim]Recording discussion...[/dim]")
    record_thread = threading.Thread(
        target=_record_background,
        args=(DISCUSSION_TIME, record_result, stop_event, mute_event),
        daemon=True,
    )
    record_thread.start()

    # Start AI discussion thread
    llm_thread = threading.Thread(
        target=_llm_discussion_loop,
        args=(state, stop_event, mute_event, ai_segments, rec_start_time),
        daemon=True,
    )
    llm_thread.start()

    remaining = DISCUSSION_TIME
    while remaining > 0:
        remaining = countdown(remaining, "Discussion time remaining", interruptible=True)
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

    # Stop recording and transcribe
    stop_event.set()
    record_thread.join(timeout=5.0)

    audio = record_result.get("audio")
    if audio is not None and len(audio) > 0:
        try:
            from werewolf.stt import transcribe_and_diarize, format_transcript, Segment

            console.print("\n[dim]Transcribing discussion...[/dim]")
            # Only count human speakers for diarization hints
            human_count = sum(
                1 for p in state.players if not is_ai_player(p)
            )
            segments = transcribe_and_diarize(
                audio,
                enrollments=enrollments,
                min_speakers=max(2, human_count),
                max_speakers=human_count,
            )

            # Merge AI segments (tracked during TTS) into the transcript
            for ai_seg in ai_segments:
                segments.append(Segment(
                    speaker=ai_seg["speaker"],
                    text=ai_seg["text"],
                    start=ai_seg["start"],
                    end=ai_seg["end"],
                ))
            segments.sort(key=lambda s: s.start)

            state.discussion_transcript = [
                {"speaker": s.speaker, "text": s.text, "start": s.start, "end": s.end}
                for s in segments
            ]
            transcript = format_transcript(segments)
            if transcript:
                console.print("\n[bold]Discussion Transcript:[/bold]")
                console.print(transcript)
                console.print()
        except Exception as e:
            console.print(f"[yellow]Transcription failed: {e}[/yellow]")
    elif "error" in record_result:
        console.print(f"[yellow]Recording failed: {record_result['error']}[/yellow]")
