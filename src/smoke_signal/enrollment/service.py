"""UI-agnostic enrollment helpers used by the dashboard.

All functions report progress through a status callback and never raise —
they are designed to run on a background thread behind a Tk UI.
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

StatusCb = Callable[[str], None]


def enroll_from_file(name: str, audio_path: Path, status_cb: StatusCb,
                     gpu_lock=None) -> bool:
    """Enroll (or extend) a speaker profile from an audio file.

    Respects the watcher's GPU lock so enrollment never runs concurrently
    with a transcription job. Returns True on success.
    """
    from smoke_signal.config import DEFAULT_PROFILES_DIR, get_hf_token

    try:
        token = get_hf_token()
    except ValueError:
        status_cb("HF_TOKEN not set — run setup or add it in your data folder's .env")
        return False

    acquired = False
    if gpu_lock is not None:
        status_cb("Waiting for GPU…")
        acquired = gpu_lock.acquire(timeout=15)
        if not acquired:
            status_cb("GPU is busy transcribing — try again after the current job")
            return False

    try:
        from smoke_signal.gpu import check_gpu
        from smoke_signal.enrollment.manager import enroll_speaker, list_profiles

        device = check_gpu()["device"]
        append = any(p.get("name") == name for p in list_profiles(DEFAULT_PROFILES_DIR))

        status_cb(f"Enrolling {name}… (loading voice model)")
        enroll_speaker(
            name=name,
            audio_path=Path(audio_path),
            profiles_dir=DEFAULT_PROFILES_DIR,
            hf_token=token,
            append=append,
            device=device,
        )
        suffix = " (added to existing profile)" if append else ""
        status_cb(f"✓ Enrolled {name}{suffix}")
        return True
    except Exception as e:
        logger.exception("Enrollment failed")
        status_cb(f"Enrollment failed: {str(e)[:120]}")
        return False
    finally:
        if acquired:
            gpu_lock.release()


def recording_available() -> bool:
    """True if in-app mic recording is available (sounddevice installed)."""
    try:
        import sounddevice  # noqa: F401
        return True
    except Exception:
        return False


def record_clip(seconds: int, status_cb: StatusCb, samplerate: int = 16000) -> Path | None:
    """Record a mono WAV clip from the default microphone.

    Returns the temp file path, or None on failure.
    """
    try:
        import sounddevice as sd
        import soundfile as sf

        status_cb(f"Recording {seconds}s — speak naturally…")
        frames = sd.rec(int(seconds * samplerate), samplerate=samplerate,
                        channels=1, dtype="float32")
        start = time.time()
        while time.time() - start < seconds:
            left = max(0, seconds - int(time.time() - start))
            status_cb(f"Recording… {left}s left (keep talking)")
            time.sleep(1)
        sd.wait()

        out = Path(tempfile.mktemp(suffix=".wav"))
        sf.write(str(out), frames, samplerate)
        return out
    except Exception as e:
        logger.exception("Recording failed")
        status_cb(f"Recording failed: {str(e)[:120]} — is a microphone connected?")
        return None
