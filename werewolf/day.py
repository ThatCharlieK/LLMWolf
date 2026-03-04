"""Day phase: discussion period with countdown timer and optional recording."""

import threading

import numpy as np
import questionary
from rich.console import Console

from werewolf.state import GameState
from werewolf.ui import clear_screen, show_panel, show_big_text, countdown, ROLE_COLORS

console = Console()

# Default discussion time in seconds (5 minutes)
DISCUSSION_TIME = 300


def _record_background(duration: float, result_holder: dict, stop_event: threading.Event):
    """Record audio in a background thread, storing result in result_holder['audio'].

    Runs until duration elapses or stop_event is set.
    """
    try:
        import sounddevice as sd

        sample_rate = 16000
        frames_needed = int(duration * sample_rate)
        audio = np.zeros(frames_needed, dtype="float32")
        actual_frames = [0]

        def callback(indata, frame_count, time_info, status):
            """Sounddevice callback that fills the audio buffer."""
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

        result_holder["audio"] = audio[: actual_frames[0]]
        result_holder["sample_rate"] = sample_rate
    except Exception as e:
        result_holder["error"] = str(e)


def run_day(state: GameState, enrollments: dict | None = None):
    """Run the day discussion period with a countdown timer.

    Players discuss in real life while the timer counts down.
    Pressing Enter pauses the timer and prompts to end early (with confirmation).
    If enrollments are provided, records and transcribes the discussion.
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

    # Start background recording if enrollments available
    recording_active = bool(enrollments)
    stop_event = threading.Event()
    record_result: dict = {}
    record_thread = None

    if recording_active:
        console.print("[dim]Recording discussion...[/dim]")
        record_thread = threading.Thread(
            target=_record_background,
            args=(DISCUSSION_TIME, record_result, stop_event),
            daemon=True,
        )
        record_thread.start()

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
    if recording_active and record_thread is not None:
        stop_event.set()
        record_thread.join(timeout=5.0)

        audio = record_result.get("audio")
        if audio is not None and len(audio) > 0:
            try:
                from werewolf.stt import transcribe_and_diarize, format_transcript

                console.print("\n[dim]Transcribing discussion...[/dim]")
                segments = transcribe_and_diarize(
                    audio,
                    enrollments=enrollments,
                    min_speakers=2,
                    max_speakers=len(state.players),
                )
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
