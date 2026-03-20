"""Scribe CLI — local-first audio transcription with speaker diarization."""

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")

from pathlib import Path

import click

from scribe.config import (
    DEFAULT_PROFILES_DIR,
    DEFAULT_TRANSCRIPTS_DIR,
    get_hf_token,
    get_profile,
    load_config,
    load_env,
)


@click.group()
def main():
    """Scribe — local-first audio transcription with speaker diarization."""
    load_env()


@main.command()
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option("--model", "-m", default=None, help="Whisper model (large-v3, large-v3-turbo, medium, small, base, tiny)")
@click.option("--language", "-l", default=None, help="Language code or 'auto' for detection")
@click.option("--speakers", "-s", type=int, default=None, help="Expected number of speakers")
@click.option("--identify", "-i", is_flag=True, default=None, help="Match speakers against enrolled profiles")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output file path")
@click.option("--compute-type", default=None, help="Compute type: float16 (default), float32")
@click.option("--profile", "-p", default=None, help="Named config profile (therapy, work, etc.)")
@click.option("--vault", is_flag=True, default=False, help="Output in vault meeting-note format")
@click.option("--batch-size", type=int, default=16, help="Whisper batch size (lower = less VRAM)")
def transcribe(audio_file, model, language, speakers, identify, output, compute_type, profile, vault, batch_size):
    """Transcribe an audio file with speaker diarization."""
    from scribe.gpu import check_gpu, check_vram_sufficient
    from scribe.output.markdown import format_transcript, get_output_path
    from scribe.pipeline.local import transcribe as run_transcribe

    # Load config and merge with profile
    config = load_config()
    if profile:
        prof = get_profile(config, profile)
    else:
        prof = config.get("defaults", {})

    # CLI args override profile/defaults
    model = model or prof.get("model", "large-v3")
    language = language or prof.get("language", "auto")
    compute_type = compute_type or prof.get("compute_type", "float16")
    speakers = speakers if speakers is not None else prof.get("speakers")
    if identify is None:
        identify = prof.get("identify", False)

    # GPU check
    gpu_info = check_gpu()
    if gpu_info["available"]:
        click.echo(f"GPU: {gpu_info['name']} ({gpu_info['vram_total_mb']}MB VRAM, CUDA {gpu_info['cuda_version']})")
    else:
        click.echo("Warning: No CUDA GPU detected. Running on CPU (will be slow).")

    ok, msg = check_vram_sufficient(model, compute_type, gpu_info)
    if not ok:
        click.echo(f"Warning: {msg}")
        if not click.confirm("Continue anyway?"):
            return

    device = gpu_info["device"]

    # Run transcription
    result = run_transcribe(
        audio_path=audio_file,
        model_name=model,
        compute_type=compute_type,
        language=language if language != "auto" else None,
        num_speakers=speakers,
        device=device,
        batch_size=batch_size,
    )

    # Speaker identification
    if identify:
        from scribe.enrollment.matcher import identify_speakers
        hf_token = get_hf_token()
        result = identify_speakers(
            result, audio_file, DEFAULT_PROFILES_DIR, hf_token, device,
        )

    # Format and write output
    markdown = format_transcript(result, vault_mode=vault)

    output_dir = DEFAULT_TRANSCRIPTS_DIR
    if vault:
        # Try to find celerity-notes meeting-notes dir
        vault_path = Path.home() / "OneDrive" / "Documents" / "celerity-notes" / "meeting-notes"
        if vault_path.exists():
            output_dir = vault_path

    output_dir.mkdir(parents=True, exist_ok=True)

    if output is None:
        output = get_output_path(audio_file, output_dir, vault_mode=vault)

    output.write_text(markdown, encoding="utf-8")
    click.echo(f"Transcript saved to: {output}")


@main.command()
@click.argument("name")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option("--append", is_flag=True, help="Add to existing profile instead of replacing")
def enroll(name, audio_file, append):
    """Enroll a speaker from an audio file for future identification.

    Provide 30-60 seconds of solo speech for best results.
    """
    from scribe.enrollment.manager import enroll_speaker
    from scribe.gpu import check_gpu

    gpu_info = check_gpu()
    device = gpu_info["device"]
    hf_token = get_hf_token()

    DEFAULT_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    profile_path = enroll_speaker(
        name=name,
        audio_path=audio_file,
        profiles_dir=DEFAULT_PROFILES_DIR,
        hf_token=hf_token,
        append=append,
        device=device,
    )
    click.echo(f"Profile saved: {profile_path}")


@main.group()
def profiles():
    """Manage speaker profiles."""
    pass


@profiles.command("list")
def profiles_list():
    """List all enrolled speaker profiles."""
    from scribe.enrollment.manager import list_profiles

    profs = list_profiles(DEFAULT_PROFILES_DIR)
    if not profs:
        click.echo("No speaker profiles found.")
        click.echo(f"Enroll a speaker: scribe enroll <name> <audio_file>")
        return

    click.echo(f"{'Name':<15} {'Samples':<10} {'Created':<12} {'Updated':<12}")
    click.echo("-" * 50)
    for p in profs:
        created = p["created"][:10]
        updated = p["updated"][:10]
        click.echo(f"{p['name']:<15} {p['num_samples']:<10} {created:<12} {updated:<12}")


@profiles.command("delete")
@click.argument("name")
def profiles_delete(name):
    """Delete a speaker profile."""
    from scribe.enrollment.manager import delete_profile

    if delete_profile(name, DEFAULT_PROFILES_DIR):
        click.echo(f"Deleted profile '{name}'.")
    else:
        click.echo(f"Profile '{name}' not found.")


@main.command()
def verify():
    """Verify GPU, dependencies, and configuration."""
    import sys

    click.echo("=== Scribe System Check ===\n")

    # Python
    click.echo(f"Python: {sys.version.split()[0]}")

    # PyTorch + CUDA
    try:
        import torch
        click.echo(f"PyTorch: {torch.__version__}")
        click.echo(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            from scribe.gpu import check_gpu
            gpu = check_gpu()
            click.echo(f"GPU: {gpu['name']}")
            click.echo(f"VRAM: {gpu['vram_total_mb']}MB")
            click.echo(f"CUDA version: {gpu['cuda_version']}")
            click.echo(f"Compute capability: {gpu['compute_capability']}")
        else:
            click.echo("GPU: Not available (will use CPU)")
    except ImportError:
        click.echo("PyTorch: NOT INSTALLED")

    click.echo()

    # WhisperX
    try:
        import whisperx  # noqa: F401
        click.echo("WhisperX: OK")
    except ImportError as e:
        click.echo(f"WhisperX: FAILED ({e})")

    # pyannote
    try:
        import pyannote.audio
        click.echo(f"pyannote.audio: {pyannote.audio.__version__}")
    except ImportError as e:
        click.echo(f"pyannote.audio: FAILED ({e})")

    # ffmpeg
    import subprocess
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        version = r.stdout.split("\n")[0] if r.returncode == 0 else "FAILED"
        click.echo(f"ffmpeg: {version}")
    except FileNotFoundError:
        click.echo("ffmpeg: NOT FOUND (required for audio preprocessing)")

    click.echo()

    # HuggingFace token
    try:
        token = get_hf_token()
        masked = token[:8] + "..." + token[-4:]
        click.echo(f"HF_TOKEN: {masked}")
    except ValueError as e:
        click.echo(f"HF_TOKEN: NOT SET — {e}")

    click.echo()
    click.echo("=== Check Complete ===")


if __name__ == "__main__":
    main()
