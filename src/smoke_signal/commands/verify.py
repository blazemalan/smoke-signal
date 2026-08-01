import sys
import subprocess
import click

from smoke_signal.config import get_hf_token


@click.command("verify")
def verify():
    """Verify GPU, dependencies, and configuration."""
    click.echo("=== Smoke Signal System Check ===\n")

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
