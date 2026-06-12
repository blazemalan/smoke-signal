"""Smoke Signal CLI — local-first audio transcription with speaker diarization."""

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")

from pathlib import Path

import click

from smoke_signal.config import (
    DEFAULT_PROFILES_DIR,
    DEFAULT_TRANSCRIPTS_DIR,
    get_hf_token,
    get_profile,
    load_config,
    load_env,
)


@click.group()
def main():
    """Smoke Signal — local-first audio transcription with speaker diarization."""
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
@click.option("--no-align", is_flag=True, default=False, help="Skip word-level alignment (faster)")
@click.option("--format", "format_type", type=click.Choice(["markdown", "json", "csv"]), default="markdown", help="Output format (markdown, json, csv)")
def transcribe(audio_file, model, language, speakers, identify, output, compute_type, profile, vault, batch_size, no_align, format_type):
    """Transcribe an audio file with speaker diarization."""
    from smoke_signal.commands.transcribe import do_transcribe

    do_transcribe(
        audio_file, model, language, speakers, identify, output,
        compute_type, profile, vault, batch_size, no_align, format_type
    )


@main.command()
@click.argument("name")
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.option("--append", is_flag=True, help="Add to existing profile instead of replacing")
def enroll(name, audio_file, append):
    """Enroll a speaker from an audio file for future identification.

    Provide 30-60 seconds of solo speech for best results.
    """
    from smoke_signal.commands.profiles import do_enroll
    do_enroll(name, audio_file, append)


@main.group()
def profiles():
    """Manage speaker profiles."""
    pass


@profiles.command("list")
def profiles_list():
    """List all enrolled speaker profiles."""
    from smoke_signal.commands.profiles import do_profiles_list
    do_profiles_list()


@profiles.command("delete")
@click.argument("name")
def profiles_delete(name):
    """Delete a speaker profile."""
    from smoke_signal.commands.profiles import do_profiles_delete
    do_profiles_delete(name)


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
            from smoke_signal.gpu import check_gpu
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


@main.command()
@click.option("--once", is_flag=True, help="Check for new files once and exit (no daemon)")
@click.option("--scan-days", default=7, help="How many days back to scan for unprocessed files")
@click.option("--backfill", type=int, default=None, help="Process unprocessed files from last N days")
@click.option("--no-tray", is_flag=True, help="Run headless without system tray icon")
def watch(once, scan_days, backfill, no_tray):
    """Start the file watcher daemon to auto-transcribe new recordings."""
    from smoke_signal.commands.watcher import do_watch
    do_watch(once, scan_days, backfill, no_tray)


@main.command("classify")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.argument("description")
def classify_file(file_path, description):
    """Manually classify a held recording and trigger processing."""
    from smoke_signal.commands.watcher import do_classify_file
    do_classify_file(file_path, description)


@main.command()
def status():
    """Show watcher status: queue depth, recent jobs, held files."""
    from smoke_signal.commands.watcher import do_status
    do_status()


@main.command()
def setup():
    """Run the first-time setup wizard."""
    from smoke_signal.setup_wizard import run_wizard

    completed = run_wizard()
    if completed:
        click.echo("Setup complete!")
    else:
        click.echo("Setup cancelled.")


if __name__ == "__main__":
    main()
