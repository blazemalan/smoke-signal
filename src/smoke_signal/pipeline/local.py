"""WhisperX local transcription + diarization pipeline."""

import gc
import time
from pathlib import Path
from typing import Callable

import click
import numpy as np
import torch
import whisperx
from whisperx.diarize import DiarizationPipeline

from smoke_signal.audio import get_audio_duration, preprocess_audio, validate_audio_file
from smoke_signal.config import get_hf_token
from smoke_signal.models import Segment, TranscriptResult, Word


def transcribe(
    audio_path: Path,
    model_name: str = "large-v3",
    compute_type: str = "float16",
    language: str | None = None,
    num_speakers: int | None = None,
    device: str = "cuda",
    batch_size: int = 16,
    align: bool = True,
    log_fn: Callable[[str], None] = click.echo,
) -> tuple[TranscriptResult, "np.ndarray"]:
    """Run the full WhisperX pipeline: transcribe → align → diarize.

    Returns (TranscriptResult, audio_array) where audio_array is the 16kHz
    mono numpy array that can be reused for speaker identification.
    """
    start_time = time.time()
    validate_audio_file(audio_path)

    duration = get_audio_duration(audio_path)
    log_fn(f"Audio duration: {_format_duration(duration)}")

    # Step 1: Preprocess audio to 16kHz mono WAV
    log_fn("Preprocessing audio...")
    wav_path = preprocess_audio(audio_path)

    try:
        audio = whisperx.load_audio(str(wav_path))
    finally:
        # Clean up temp WAV if we created one
        if wav_path != audio_path:
            wav_path.unlink(missing_ok=True)

    # Step 2: Transcribe with WhisperX
    lang = None if language == "auto" else language
    log_fn(f"Loading Whisper model ({model_name}, {compute_type})...")
    model = whisperx.load_model(
        model_name,
        device=device,
        compute_type=compute_type,
        language=lang,
    )

    log_fn("Transcribing...")
    result = model.transcribe(audio, batch_size=batch_size, language=lang)
    detected_language = result.get("language", "en")
    log_fn(f"Detected language: {detected_language}")

    # Step 3: Align (word-level timestamps) — optional
    if align:
        log_fn("Aligning timestamps...")
        try:
            align_model, align_metadata = whisperx.load_align_model(
                language_code=detected_language, device=device
            )
            result = whisperx.align(
                result["segments"], align_model, align_metadata, audio, device,
                return_char_alignments=False,
            )
            del align_model
        except Exception as e:
            log_fn(f"Warning: Alignment failed ({e}), continuing without word-level timestamps.")

    # Step 4: Unload Whisper to free VRAM
    del model
    gc.collect()
    torch.cuda.empty_cache()
    log_fn("Whisper model unloaded, VRAM freed.")

    # Step 5: Diarize
    log_fn("Running speaker diarization...")
    hf_token = get_hf_token()
    diarize_model = DiarizationPipeline(
        use_auth_token=hf_token, device=torch.device(device),
    )

    diarize_kwargs = {}
    if num_speakers is not None:
        diarize_kwargs["min_speakers"] = num_speakers
        diarize_kwargs["max_speakers"] = num_speakers

    diarize_segments = diarize_model(audio, **diarize_kwargs)

    # Step 6: Assign speakers to segments
    result = whisperx.assign_word_speakers(diarize_segments, result)

    # Step 7: Unload diarization model
    del diarize_model
    gc.collect()
    torch.cuda.empty_cache()

    # Step 8: Build result
    segments = _build_segments(result.get("segments", []))
    speakers = sorted({s.speaker for s in segments if s.speaker})

    processing_time = time.time() - start_time
    log_fn(f"Done in {_format_duration(processing_time)}. Found {len(speakers)} speaker(s).")

    from datetime import datetime

    return TranscriptResult(
        segments=segments,
        speakers=speakers,
        language=detected_language,
        duration=duration,
        model=model_name,
        pipeline="local",
        processing_time=processing_time,
        audio_file=str(audio_path.name),
        date=datetime.now(),
    ), audio


def _build_segments(raw_segments: list[dict]) -> list[Segment]:
    """Convert WhisperX raw segments to our Segment model."""
    segments = []
    for seg in raw_segments:
        words = []
        for w in seg.get("words", []):
            if "start" not in w or "end" not in w:
                continue
            words.append(Word(
                text=w.get("word", ""),
                start=w["start"],
                end=w["end"],
                confidence=w.get("score"),
                speaker=w.get("speaker"),
            ))

        segments.append(Segment(
            text=seg.get("text", "").strip(),
            start=seg.get("start", 0.0),
            end=seg.get("end", 0.0),
            speaker=seg.get("speaker"),
            words=words,
        ))

    return segments


def _format_duration(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
