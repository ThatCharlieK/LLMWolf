"""Speech-to-text with speaker diarization using WhisperX and pyannote.

Provides mic recording, transcription, speaker enrollment, and diarization
that maps generic speaker labels to enrolled player names. Runs fully locally.

Requires a free HuggingFace account and token for first-time model download.
Set the HF_TOKEN environment variable or pass it to init functions.
"""

import os
import tempfile
import threading
from dataclasses import dataclass, field

import numpy as np
from rich.console import Console

console = Console()

# Module-level state
_whisper_model = None
_align_model = None
_align_metadata = None
_diarize_pipeline = None
_embedding_inference = None
_device = "cpu"
_stt_enabled = False
_hf_token = None

SAMPLE_RATE = 16000


@dataclass
class Segment:
    """A single transcribed segment with speaker and timing info."""
    speaker: str
    text: str
    start: float
    end: float


def _detect_device() -> str:
    """Detect the best available compute device for inference."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def init_stt(model_size: str = "base", hf_token: str | None = None):
    """Load WhisperX model and diarization pipeline.

    Args:
        model_size: Whisper model size — "tiny", "base", "small", "medium", "large-v2".
                    Smaller models are faster but less accurate.
        hf_token: HuggingFace access token for pyannote model download.
                  Falls back to HF_TOKEN environment variable.
    """
    global _whisper_model, _diarize_pipeline, _embedding_inference
    global _device, _stt_enabled, _hf_token

    _hf_token = hf_token or os.environ.get("HF_TOKEN")
    _device = _detect_device()
    compute_type = "float32" if _device == "cpu" else "float16"

    try:
        import whisperx

        console.print(f"[dim]Loading Whisper model ({model_size}) on {_device}...[/dim]")
        _whisper_model = whisperx.load_model(
            model_size, _device, compute_type=compute_type
        )

        if _hf_token:
            console.print("[dim]Loading diarization pipeline...[/dim]")
            from whisperx.diarize import DiarizationPipeline
            _diarize_pipeline = DiarizationPipeline(
                use_auth_token=_hf_token, device=_device
            )

            console.print("[dim]Loading speaker embedding model...[/dim]")
            from pyannote.audio import Model, Inference
            embed_model = Model.from_pretrained(
                "pyannote/embedding", use_auth_token=_hf_token
            )
            _embedding_inference = Inference(embed_model, window="whole")
        else:
            console.print(
                "[yellow]Warning: No HF_TOKEN set — diarization and speaker "
                "enrollment disabled. Set HF_TOKEN env var or pass hf_token "
                "to init_stt().[/yellow]"
            )

        _stt_enabled = True
        console.print("[dim]STT initialized.[/dim]")

    except Exception as e:
        console.print(f"[yellow]STT unavailable: {e}[/yellow]")
        _stt_enabled = False


def record_audio(duration: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Record audio from the default microphone.

    Args:
        duration: Maximum recording duration in seconds.
        sample_rate: Audio sample rate (default 16000 for Whisper).

    Returns:
        1D numpy float32 array of audio samples.
    """
    import sounddevice as sd

    console.print(f"[bold green]Recording... (up to {duration:.0f}s)[/bold green]")
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    console.print("[dim]Recording finished.[/dim]")
    return audio.flatten()


def record_audio_interruptible(
    max_duration: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Record audio that can be stopped early by pressing Enter.

    Starts recording in a background thread and waits for either the duration
    to elapse or the caller to signal stop via Enter keypress.

    Args:
        max_duration: Maximum recording duration in seconds.
        sample_rate: Audio sample rate.

    Returns:
        1D numpy float32 array of recorded audio (trimmed to actual duration).
    """
    import sounddevice as sd

    frames_needed = int(max_duration * sample_rate)
    audio = np.zeros(frames_needed, dtype="float32")
    stop_event = threading.Event()
    actual_frames = [0]

    def _callback(indata, frame_count, time_info, status):
        """Sounddevice stream callback that fills the buffer."""
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
        callback=_callback,
    )

    console.print(
        f"[bold green]Recording... (up to {max_duration:.0f}s, "
        f"press Enter to stop early)[/bold green]"
    )
    stream.start()

    try:
        # Block until Enter or timeout
        import select
        import sys
        elapsed = 0.0
        while elapsed < max_duration and not stop_event.is_set():
            ready, _, _ = select.select([sys.stdin], [], [], 0.5)
            if ready:
                sys.stdin.readline()
                stop_event.set()
                break
            elapsed += 0.5
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stream.stop()
        stream.close()

    trimmed = audio[: actual_frames[0]]
    console.print(f"[dim]Recorded {len(trimmed) / sample_rate:.1f}s of audio.[/dim]")
    return trimmed


def _save_temp_wav(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
    """Save audio array to a temporary WAV file and return the path."""
    import soundfile as sf

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, sample_rate)
    tmp.close()
    return tmp.name


def _extract_embedding(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Extract a speaker embedding from an audio clip using pyannote.

    Returns a 1D numpy array (the embedding vector).
    """
    wav_path = _save_temp_wav(audio, sample_rate)
    try:
        embedding = _embedding_inference(wav_path)
        return embedding.flatten()
    finally:
        os.unlink(wav_path)


def enroll_speakers(
    players: list[str],
    duration: float = 5.0,
    sample_rate: int = SAMPLE_RATE,
) -> dict[str, np.ndarray]:
    """Voice enrollment: record each player and extract speaker embeddings.

    Prompts each player to speak for a few seconds. Their voice embedding
    is stored for later matching during diarized transcription.

    Args:
        players: List of player names in seating order.
        duration: How many seconds to record each player.
        sample_rate: Audio sample rate.

    Returns:
        Dict mapping player name to their speaker embedding vector.
    """
    if _embedding_inference is None:
        console.print("[yellow]Speaker enrollment skipped (no embedding model).[/yellow]")
        return {}

    enrollments: dict[str, np.ndarray] = {}
    for player in players:
        console.print(
            f"\n[bold]{player}[/bold], please say your name and a short sentence."
        )
        audio = record_audio(duration, sample_rate)

        # Skip silent recordings
        if np.max(np.abs(audio)) < 0.01:
            console.print(f"[yellow]No audio detected for {player}, skipping.[/yellow]")
            continue

        embedding = _extract_embedding(audio, sample_rate)
        enrollments[player] = embedding
        console.print(f"[dim]Enrolled {player}.[/dim]")

    return enrollments


def _match_speaker_to_player(
    speaker_embedding: np.ndarray,
    enrollments: dict[str, np.ndarray],
    threshold: float = 0.6,
) -> str:
    """Match a speaker embedding to the closest enrolled player.

    Args:
        speaker_embedding: Embedding of the unknown speaker.
        enrollments: Dict of player name → embedding from enrollment.
        threshold: Maximum cosine distance to accept a match (0-2 scale).

    Returns:
        Player name if matched, or "Unknown" if no match within threshold.
    """
    from scipy.spatial.distance import cosine

    best_name = "Unknown"
    best_distance = threshold

    for name, enrolled_emb in enrollments.items():
        distance = cosine(speaker_embedding, enrolled_emb)
        if distance < best_distance:
            best_distance = distance
            best_name = name

    return best_name


def transcribe(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> list[Segment]:
    """Transcribe audio without speaker diarization.

    Args:
        audio: 1D float32 numpy array of audio samples.
        sample_rate: Audio sample rate.

    Returns:
        List of Segment objects with speaker set to "Unknown".
    """
    if not _stt_enabled or _whisper_model is None:
        return []

    import whisperx

    wav_path = _save_temp_wav(audio, sample_rate)
    try:
        loaded_audio = whisperx.load_audio(wav_path)
        result = _whisper_model.transcribe(loaded_audio, batch_size=8)
        return [
            Segment(
                speaker="Unknown",
                text=seg.get("text", "").strip(),
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
            )
            for seg in result.get("segments", [])
            if seg.get("text", "").strip()
        ]
    finally:
        os.unlink(wav_path)


def transcribe_and_diarize(
    audio: np.ndarray,
    enrollments: dict[str, np.ndarray] | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    sample_rate: int = SAMPLE_RATE,
) -> list[Segment]:
    """Transcribe audio with speaker diarization, mapping to enrolled players.

    Runs WhisperX transcription, alignment, and pyannote diarization, then
    matches each speaker label to the nearest enrolled player embedding.

    Args:
        audio: 1D float32 numpy array of audio samples.
        enrollments: Speaker enrollment dict from enroll_speakers(). If None,
                     generic SPEAKER_XX labels are used.
        min_speakers: Minimum expected speakers (optional hint for diarization).
        max_speakers: Maximum expected speakers (optional hint for diarization).
        sample_rate: Audio sample rate.

    Returns:
        List of Segment objects with speaker names assigned.
    """
    if not _stt_enabled or _whisper_model is None:
        return []

    if _diarize_pipeline is None:
        console.print("[yellow]Diarization unavailable, falling back to basic transcription.[/yellow]")
        return transcribe(audio, sample_rate)

    import whisperx

    wav_path = _save_temp_wav(audio, sample_rate)
    try:
        loaded_audio = whisperx.load_audio(wav_path)

        # Step 1: Transcribe
        console.print("[dim]Transcribing...[/dim]")
        result = _whisper_model.transcribe(loaded_audio, batch_size=8)

        # Step 2: Align (for word-level timestamps)
        global _align_model, _align_metadata
        if _align_model is None:
            _align_model, _align_metadata = whisperx.load_align_model(
                language_code=result["language"], device=_device
            )
        result = whisperx.align(
            result["segments"], _align_model, _align_metadata,
            loaded_audio, _device, return_char_alignments=False,
        )

        # Step 3: Diarize
        console.print("[dim]Identifying speakers...[/dim]")
        diarize_kwargs = {}
        if min_speakers is not None:
            diarize_kwargs["min_speakers"] = min_speakers
        if max_speakers is not None:
            diarize_kwargs["max_speakers"] = max_speakers

        diarize_segments = _diarize_pipeline(
            loaded_audio, **diarize_kwargs
        )
        result = whisperx.assign_word_speakers(diarize_segments, result)

        # Step 4: Map speaker labels to player names via embeddings
        speaker_label_to_name: dict[str, str] = {}
        if enrollments and _embedding_inference is not None:
            unique_speakers = set()
            for seg in result.get("segments", []):
                spk = seg.get("speaker")
                if spk:
                    unique_speakers.add(spk)

            for spk_label in unique_speakers:
                # Collect audio for this speaker
                spk_segments = [
                    s for s in result["segments"] if s.get("speaker") == spk_label
                ]
                if not spk_segments:
                    continue

                # Use the longest segment for best embedding quality
                longest = max(spk_segments, key=lambda s: s.get("end", 0) - s.get("start", 0))
                start_sample = int(longest["start"] * sample_rate)
                end_sample = int(longest["end"] * sample_rate)
                spk_audio = audio[start_sample:end_sample]

                if len(spk_audio) < sample_rate * 0.5:
                    # Too short for reliable embedding
                    continue

                spk_embedding = _extract_embedding(spk_audio, sample_rate)
                matched_name = _match_speaker_to_player(spk_embedding, enrollments)
                speaker_label_to_name[spk_label] = matched_name

        # Build output segments
        segments = []
        for seg in result.get("segments", []):
            text = seg.get("text", "").strip()
            if not text:
                continue
            raw_speaker = seg.get("speaker", "Unknown")
            speaker = speaker_label_to_name.get(raw_speaker, raw_speaker)
            segments.append(Segment(
                speaker=speaker,
                text=text,
                start=seg.get("start", 0.0),
                end=seg.get("end", 0.0),
            ))

        console.print(f"[dim]Transcribed {len(segments)} segments.[/dim]")
        return segments

    finally:
        os.unlink(wav_path)


def format_transcript(segments: list[Segment]) -> str:
    """Format transcript segments into a readable labeled string.

    Merges consecutive segments from the same speaker.

    Returns:
        Multi-line string like:
            Alice: I think Bob is the werewolf.
            Bob: No way, I'm the Seer!
    """
    if not segments:
        return "(no transcript)"

    lines: list[str] = []
    current_speaker = None
    current_text_parts: list[str] = []

    for seg in segments:
        if seg.speaker == current_speaker:
            current_text_parts.append(seg.text)
        else:
            if current_speaker is not None:
                lines.append(f"{current_speaker}: {' '.join(current_text_parts)}")
            current_speaker = seg.speaker
            current_text_parts = [seg.text]

    if current_speaker is not None:
        lines.append(f"{current_speaker}: {' '.join(current_text_parts)}")

    return "\n".join(lines)
