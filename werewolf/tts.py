"""Text-to-speech module using pyttsx3 with macOS NSSpeechSynthesizer.

Provides blocking and non-blocking speech synthesis. Falls back gracefully
if pyttsx3 is unavailable — never crashes the game.
"""

import threading
from rich.console import Console

console = Console()

_engine = None
_tts_enabled = False


def init_tts(rate: int = 180):
    """Initialize the pyttsx3 TTS engine.

    Args:
        rate: Speech rate in words per minute (default 180).
    """
    global _engine, _tts_enabled
    try:
        import pyttsx3
        _engine = pyttsx3.init()
        _engine.setProperty("rate", rate)
        _tts_enabled = True
    except Exception as e:
        console.print(f"[dim]TTS unavailable: {e}[/dim]")
        _tts_enabled = False


def speak(text: str):
    """Speak text aloud, blocking until finished.

    Silently skips if TTS is not initialized.
    """
    if not _tts_enabled or _engine is None:
        return
    try:
        _engine.say(text)
        _engine.runAndWait()
    except Exception:
        return


def speak_async(text: str):
    """Speak text in a background thread (non-blocking).

    Silently skips if TTS is not initialized.
    """
    if not _tts_enabled or _engine is None:
        return
    thread = threading.Thread(target=speak, args=(text,), daemon=True)
    thread.start()


def set_voice(voice_id: str):
    """Change the TTS voice by its system identifier.

    On macOS, list available voices with:
        pyttsx3.init().getProperty('voices')
    """
    if not _tts_enabled or _engine is None:
        return
    try:
        _engine.setProperty("voice", voice_id)
    except Exception:
        return


def list_voices() -> list[dict]:
    """Return available system voices as a list of dicts with id and name.

    Returns empty list if TTS is not initialized.
    """
    if not _tts_enabled or _engine is None:
        return []
    try:
        voices = _engine.getProperty("voices")
        return [{"id": v.id, "name": v.name} for v in voices]
    except Exception:
        return []
