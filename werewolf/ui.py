"""Shared UI helpers for terminal display and sound playback."""

import os
import select
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live

console = Console()

ROLE_COLORS = {
    "Werewolf": "red",
    "Seer": "cyan",
    "Robber": "yellow",
    "Troublemaker": "magenta",
    "Villager": "green",
    "Tanner": "dark_orange",
    "Witch": "purple",
}

# Resolve sounds directory relative to this file's package
_SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"
_sound_enabled = False


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def init_sound():
    """Initialize the pygame mixer for sound playback."""
    global _sound_enabled
    try:
        import pygame
        pygame.mixer.init()
        _sound_enabled = True
    except Exception:
        _sound_enabled = False


def play_sound(filename: str):
    """Play an mp3 from the sounds/ directory. Blocks until finished.

    Silently skips if sound is not initialized or files are missing.
    """
    if not _sound_enabled:
        return
    filepath = _SOUNDS_DIR / filename
    if not filepath.exists():
        return
    try:
        import pygame
        pygame.mixer.music.load(str(filepath))
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
    except Exception:
        return


def show_panel(title: str, body: str, style: str = "blue"):
    """Display a rich Panel with the given title and body, centered."""
    panel = Panel(body, title=title, border_style=style, expand=False)
    console.print(panel, justify="center")


def show_big_text(text: str, style: str = "bold white"):
    """Display large, prominent text for phase announcements."""
    console.print()
    console.print(Text(f"  {text}  ", style=style), justify="center")
    console.print()


def countdown(seconds: int, label: str, interruptible: bool = False) -> int:
    """Show a live countdown timer in the terminal.

    Displays like: "Discussion time remaining: 3:24"
    When interruptible=True, pressing Enter breaks out early.
    Returns remaining seconds (0 if completed normally, >0 if interrupted).
    """
    with Live(console=console, refresh_per_second=2) as live:
        for remaining in range(seconds, 0, -1):
            mins, secs = divmod(remaining, 60)
            live.update(
                Text(f"{label}: {mins}:{secs:02d}", style="bold cyan"),
            )
            if interruptible:
                ready, _, _ = select.select([sys.stdin], [], [], 1.0)
                if ready:
                    sys.stdin.readline()  # consume the input
                    return remaining
            else:
                time.sleep(1)
    play_sound("vote.mp3")
    console.print()
    show_panel("Time's Up!", "Discussion period is over.", style="red")
    return 0


def pause(seconds: float):
    """Sleep for the given duration."""
    time.sleep(seconds)


def wait_for_enter(prompt: str = "Press Enter to continue..."):
    """Display a prompt and wait for the user to press Enter."""
    console.print(f"\n[dim]{prompt}[/dim]")
    input()


# --- TTS convenience wrapper ---

_tts_enabled = False


def init_tts_ui():
    """Initialize TTS for use via the speak() UI helper."""
    global _tts_enabled
    try:
        from werewolf.tts import init_tts
        init_tts()
        _tts_enabled = True
    except Exception:
        _tts_enabled = False


def speak(text: str):
    """Speak text aloud via TTS. Silently skips if unavailable."""
    if not _tts_enabled:
        return
    try:
        from werewolf.tts import speak as tts_speak
        tts_speak(text)
    except Exception:
        return
