"""Scribe CLI — local-first audio transcription with speaker diarization."""

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
def transcribe(audio_file, model, language, speakers, identify, output, compute_type, profile, vault, batch_size):
    """Transcribe an audio file with speaker diarization."""
    from smoke_signal.gpu import check_gpu, check_vram_sufficient
    from smoke_signal.output.markdown import format_transcript, get_output_path
    from smoke_signal.pipeline.local import transcribe as run_transcribe

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
        from smoke_signal.enrollment.matcher import identify_speakers
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
    from smoke_signal.enrollment.manager import enroll_speaker
    from smoke_signal.gpu import check_gpu

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
    from smoke_signal.enrollment.manager import list_profiles

    profs = list_profiles(DEFAULT_PROFILES_DIR)
    if not profs:
        click.echo("No speaker profiles found.")
        click.echo(f"Enroll a speaker: smoke-signal enroll <name> <audio_file>")
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
    from smoke_signal.enrollment.manager import delete_profile

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
    from smoke_signal.watcher.daemon import run_daemon, run_once

    if once:
        run_once()
    else:
        run_daemon(scan_days=scan_days, use_tray=not no_tray)


@main.command("classify")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.argument("description")
def classify_file(file_path, description):
    """Manually classify a held recording and trigger processing."""
    from smoke_signal.config import DEFAULT_DATA_DIR, DEFAULT_DB_PATH
    from smoke_signal.watcher.classifier import classify_from_description
    from smoke_signal.watcher.job import run_job
    from smoke_signal.watcher.queue import GpuLock
    from smoke_signal.watcher.state import init_db, record_file, update_status

    init_db(DEFAULT_DB_PATH)

    classification = classify_from_description(file_path, description)
    click.echo(
        f"Classified as: {classification.meeting_type} "
        f"(profile={classification.profile})"
    )

    # Update or insert record
    record_file(
        DEFAULT_DB_PATH,
        file_path,
        file_size=file_path.stat().st_size,
        recording_date=classification.recording_date,
        recording_time=classification.recording_time,
        status="pending",
        meeting_type=classification.meeting_type,
        description=description,
        profile=classification.profile,
    )

    # Acquire GPU lock and process
    gpu_lock = GpuLock(DEFAULT_DATA_DIR / "gpu.lock")
    if not gpu_lock.acquire(timeout=60):
        click.echo("GPU is busy (watcher is processing). Queued for later.")
        return

    try:
        update_status(DEFAULT_DB_PATH, file_path, "processing")
        job = {
            "file_path": str(file_path),
            "profile": classification.profile,
            "meeting_type": classification.meeting_type,
            "recording_date": classification.recording_date,
        }
        run_job(job, DEFAULT_DB_PATH)
        click.echo("Done!")
    except Exception as e:
        update_status(DEFAULT_DB_PATH, file_path, "failed", error_message=str(e)[:500])
        click.echo(f"Failed: {e}")
    finally:
        gpu_lock.release()


@main.command()
def status():
    """Show watcher status: queue depth, recent jobs, held files."""
    from smoke_signal.config import DEFAULT_DATA_DIR, DEFAULT_DB_PATH
    from smoke_signal.watcher.queue import GpuLock
    from smoke_signal.watcher.state import get_held, get_pending, get_recent_jobs, init_db

    if not DEFAULT_DB_PATH.exists():
        click.echo("Watcher has not been run yet. Start with: smoke-signal watch")
        return

    init_db(DEFAULT_DB_PATH)

    gpu_lock = GpuLock(DEFAULT_DATA_DIR / "gpu.lock")
    gpu_status = "busy" if gpu_lock.is_locked else "idle"

    pending = get_pending(DEFAULT_DB_PATH)
    held = get_held(DEFAULT_DB_PATH)
    recent = get_recent_jobs(DEFAULT_DB_PATH, limit=10)

    click.echo(f"GPU: {gpu_status}")
    click.echo(f"Queue: {len(pending)} pending")
    click.echo(f"Held: {len(held)} awaiting classification")
    click.echo()

    if held:
        click.echo("=== Held Files ===")
        for h in held:
            name = Path(h["file_path"]).name
            date = h.get("recording_date", "?")
            click.echo(f"  {name} ({date})")
        click.echo()

    if recent:
        click.echo("=== Recent Jobs ===")
        click.echo(f"{'Status':<12} {'File':<30} {'Type':<12} {'Time'}")
        click.echo("-" * 70)
        for job in recent:
            status_icon = {
                "completed": "✓",
                "failed": "✗",
                "processing": "…",
                "pending": "○",
                "held": "?",
                "seen": "—",
            }.get(job["status"], " ")
            name = Path(job["file_path"]).name[:28]
            mtype = (job.get("meeting_type") or "")[:10]
            ptime = ""
            if job.get("processing_time_seconds"):
                ptime = f"{job['processing_time_seconds']:.0f}s"
            click.echo(f"  {status_icon} {job['status']:<9} {name:<30} {mtype:<12} {ptime}")


if __name__ == "__main__":
    main()
