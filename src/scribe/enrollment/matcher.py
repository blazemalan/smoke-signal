"""Speaker identification via cosine similarity against enrolled profiles."""

from pathlib import Path

import click
import numpy as np
import torch

from scribe.enrollment.manager import load_all_embeddings
from scribe.models import TranscriptResult


SIMILARITY_THRESHOLD = 0.70


def identify_speakers(
    result: TranscriptResult,
    audio_path: Path,
    profiles_dir: Path,
    hf_token: str,
    device: str = "cuda",
) -> TranscriptResult:
    """Replace generic speaker labels (SPEAKER_00, etc.) with enrolled names."""
    profile_embeddings = load_all_embeddings(profiles_dir)
    if not profile_embeddings:
        click.echo("No speaker profiles found. Skipping identification.")
        return result

    click.echo(f"Matching against {len(profile_embeddings)} enrolled speaker(s)...")

    # Extract embeddings for each diarized speaker from the audio
    speaker_embeddings = _extract_speaker_embeddings(
        result, audio_path, hf_token, device
    )

    if not speaker_embeddings:
        click.echo("Could not extract speaker embeddings. Skipping identification.")
        return result

    # Match via cosine similarity
    mapping = _match_speakers(speaker_embeddings, profile_embeddings)

    if not mapping:
        click.echo("No speakers matched above threshold.")
        return result

    click.echo(f"Identified: {', '.join(f'{k} → {v}' for k, v in mapping.items())}")

    # Apply mapping to segments
    for seg in result.segments:
        if seg.speaker in mapping:
            seg.speaker = mapping[seg.speaker]
        for word in seg.words:
            if word.speaker in mapping:
                word.speaker = mapping[word.speaker]

    # Update speakers list
    result.speakers = sorted({
        mapping.get(s, s) for s in result.speakers
    })

    return result


def _extract_speaker_embeddings(
    result: TranscriptResult,
    audio_path: Path,
    hf_token: str,
    device: str,
) -> dict[str, np.ndarray]:
    """Extract a representative embedding for each diarized speaker."""
    from pyannote.audio import Model, Inference
    from scribe.audio import preprocess_audio

    wav_path = preprocess_audio(audio_path)

    try:
        model = Model.from_pretrained(
            "pyannote/embedding", use_auth_token=hf_token,
        )
        inference = Inference(model, window="sliding", duration=3.0, step=1.5, device=torch.device(device))

        # Group segments by speaker
        speaker_segments: dict[str, list[tuple[float, float]]] = {}
        for seg in result.segments:
            if seg.speaker:
                speaker_segments.setdefault(seg.speaker, []).append((seg.start, seg.end))

        speaker_embeddings = {}
        import torchaudio

        waveform, sr = torchaudio.load(str(wav_path))
        if sr != 16000:
            waveform = torchaudio.functional.resample(waveform, sr, 16000)
            sr = 16000

        for speaker, time_ranges in speaker_segments.items():
            # Collect audio chunks for this speaker
            chunks = []
            for start, end in time_ranges[:10]:  # Use up to 10 segments
                start_sample = int(start * sr)
                end_sample = int(end * sr)
                if end_sample > waveform.shape[1]:
                    end_sample = waveform.shape[1]
                if start_sample < end_sample:
                    chunks.append(waveform[:, start_sample:end_sample])

            if not chunks:
                continue

            # Concatenate and extract embedding
            speaker_audio = torch.cat(chunks, dim=1)
            # Ensure at least 1 second of audio
            if speaker_audio.shape[1] < sr:
                continue

            # Use "whole" inference on the concatenated chunk
            speaker_embedding = inference({"waveform": speaker_audio, "sample_rate": sr})
            vec = speaker_embedding.data.flatten()
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            speaker_embeddings[speaker] = vec

        return speaker_embeddings
    finally:
        wav_path.unlink(missing_ok=True)
        del model, inference
        torch.cuda.empty_cache()


def _match_speakers(
    speaker_embeddings: dict[str, np.ndarray],
    profile_embeddings: dict[str, np.ndarray],
) -> dict[str, str]:
    """Match diarized speakers to enrolled profiles via cosine similarity."""
    # Build similarity matrix
    scores = {}
    for spk_label, spk_emb in speaker_embeddings.items():
        for prof_name, prof_emb in profile_embeddings.items():
            sim = float(np.dot(spk_emb, prof_emb))
            scores[(spk_label, prof_name)] = sim

    # Greedy assignment: highest similarity first, no duplicate assignments
    mapping = {}
    used_profiles = set()

    for (spk_label, prof_name), sim in sorted(scores.items(), key=lambda x: -x[1]):
        if sim < SIMILARITY_THRESHOLD:
            break
        if spk_label in mapping or prof_name in used_profiles:
            continue
        mapping[spk_label] = prof_name
        used_profiles.add(prof_name)

    return mapping
