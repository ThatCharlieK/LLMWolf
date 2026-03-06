"""Text-to-speech module using macOS built-in `say` command.

Provides blocking and non-blocking speech synthesis. Falls back gracefully
if `say` is unavailable — never crashes the game.
"""

import shutil
import subprocess
from rich.console import Console

console = Console()

_tts_enabled = False


def init_tts():
    """Initialize TTS by verifying the macOS `say` command is available."""
    global _tts_enabled
    _tts_enabled = shutil.which("say") is not None
    if not _tts_enabled:
        console.print("[dim]TTS unavailable: 'say' command not found[/dim]")


def speak(text: str):
    """Speak text aloud using macOS `say`, blocking until finished.

    Silently skips if TTS is not initialized.
    """
    if not _tts_enabled:
        return
    try:
        subprocess.run(["say", text], check=False)
    except Exception:
        return


def speak_async(text: str):
    """Speak text in the background (non-blocking).

    Silently skips if TTS is not initialized.
    """
    if not _tts_enabled:
        return
    try:
        subprocess.Popen(["say", text])
    except Exception:
        return
