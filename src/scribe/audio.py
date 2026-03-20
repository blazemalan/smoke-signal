"""Audio preprocessing via ffmpeg."""

import subprocess
import tempfile
from pathlib import Path

SUPPORTED_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".wma", ".aac", ".webm", ".mp4"}


def validate_audio_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format: {path.suffix}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def get_audio_duration(path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def preprocess_audio(input_path: Path, output_path: Path | None = None) -> Path:
    """Convert audio to 16kHz mono WAV for pyannote/whisper compatibility.

    If the input is already a 16kHz mono WAV, returns the input path unchanged.
    Otherwise, converts and returns the output path.
    """
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".wav"))

    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(output_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")

    return output_path
