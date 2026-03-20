"""Speaker profile management — embedding extraction, storage, CRUD."""

import json
from datetime import datetime
from pathlib import Path

import click
import numpy as np
import torch


def enroll_speaker(
    name: str,
    audio_path: Path,
    profiles_dir: Path,
    hf_token: str,
    append: bool = False,
    device: str = "cuda",
) -> Path:
    """Enroll a speaker by extracting voice embeddings from an audio file.

    For best results, use a recording of solo speech (30-60 seconds minimum).
    """
    from pyannote.audio import Model, Inference
    from scribe.audio import preprocess_audio, validate_audio_file

    validate_audio_file(audio_path)
    profiles_dir.mkdir(parents=True, exist_ok=True)

    # Preprocess to 16kHz mono WAV
    click.echo("Preprocessing audio...")
    wav_path = preprocess_audio(audio_path)

    try:
        # Load the embedding model
        click.echo("Loading speaker embedding model...")
        model = Model.from_pretrained(
            "pyannote/embedding", use_auth_token=hf_token,
        )
        inference = Inference(model, window="whole", device=torch.device(device))

        # Extract embedding
        click.echo("Extracting speaker embedding...")
        embedding = inference(str(wav_path))
        embedding_vec = embedding.data.flatten()

        # L2-normalize
        norm = np.linalg.norm(embedding_vec)
        if norm > 0:
            embedding_vec = embedding_vec / norm
    finally:
        wav_path.unlink(missing_ok=True)
        del model, inference
        torch.cuda.empty_cache()

    # Load or create profile
    profile_path = profiles_dir / f"{name.lower()}.json"
    if append and profile_path.exists():
        profile = _load_profile(profile_path)
        old_embedding = np.array(profile["embedding"])
        old_count = profile["num_samples"]

        # Weighted average
        new_embedding = (old_embedding * old_count + embedding_vec) / (old_count + 1)
        new_embedding = new_embedding / np.linalg.norm(new_embedding)

        profile["embedding"] = new_embedding.tolist()
        profile["num_samples"] = old_count + 1
        profile["updated"] = datetime.now().isoformat()
        profile["sample_sources"].append(str(audio_path.name))
        click.echo(f"Updated profile '{name}' ({profile['num_samples']} samples).")
    else:
        profile = {
            "name": name,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "num_samples": 1,
            "embedding": embedding_vec.tolist(),
            "embedding_model": "pyannote/embedding",
            "sample_sources": [str(audio_path.name)],
        }
        click.echo(f"Created profile '{name}'.")

    _save_profile(profile_path, profile)
    return profile_path


def list_profiles(profiles_dir: Path) -> list[dict]:
    """List all speaker profiles."""
    profiles = []
    if not profiles_dir.exists():
        return profiles
    for path in sorted(profiles_dir.glob("*.json")):
        profile = _load_profile(path)
        profiles.append({
            "name": profile["name"],
            "num_samples": profile["num_samples"],
            "created": profile["created"],
            "updated": profile["updated"],
            "sources": profile.get("sample_sources", []),
        })
    return profiles


def delete_profile(name: str, profiles_dir: Path) -> bool:
    path = profiles_dir / f"{name.lower()}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def load_all_embeddings(profiles_dir: Path) -> dict[str, np.ndarray]:
    """Load all speaker profile embeddings. Returns {name: embedding_vector}."""
    embeddings = {}
    if not profiles_dir.exists():
        return embeddings
    for path in profiles_dir.glob("*.json"):
        profile = _load_profile(path)
        embeddings[profile["name"]] = np.array(profile["embedding"])
    return embeddings


def _load_profile(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _save_profile(path: Path, profile: dict) -> None:
    with open(path, "w") as f:
        json.dump(profile, f, indent=2)
