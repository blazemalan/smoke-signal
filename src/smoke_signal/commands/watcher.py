from pathlib import Path

import click


def do_watch(once, scan_days, backfill, no_tray):
    from smoke_signal.watcher.daemon import run_daemon, run_once

    if once:
        run_once()
    else:
        run_daemon(scan_days=scan_days, use_tray=not no_tray)


def do_classify_file(file_path, description):
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


def do_status():
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
