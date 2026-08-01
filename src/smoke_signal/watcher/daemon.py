"""Main watcher daemon — wires all components together."""

import logging
import logging.handlers
import signal
import sys
import threading
import time
import warnings
from pathlib import Path

# Suppress noisy third-party warnings
warnings.filterwarnings("ignore", message=".*automatically upgraded your loaded checkpoint.*")
warnings.filterwarnings("ignore", message=".*was deprecated, redirecting.*")
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
warnings.filterwarnings("ignore", message=".*multiple.*ModelCheckpoint.*")
warnings.filterwarnings("ignore", message=".*not in the model state dict.*")

from smoke_signal.config import (
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_LOGS_DIR,
    load_config,
)
from smoke_signal.watcher.classifier import classify, classify_from_description
from smoke_signal.watcher.job import run_job
from smoke_signal.watcher.monitor import (
    ICloudFileHandler,
    scan_existing,
    start_observer,
)
from smoke_signal.watcher.notifier import notify_error, notify_held
from smoke_signal.watcher.queue import GpuLock, ProcessingQueue
from smoke_signal.watcher.single_instance import SingleInstance
from smoke_signal.watcher.state import (
    init_db,
    is_processed,
    mark_existing_as_seen,
    record_file,
    reset_stale_processing,
    update_status,
)
from send2trash import send2trash

logger = logging.getLogger("smoke_signal.watcher")


def setup_logging(log_dir: Path) -> None:
    """Configure file + console logging with daily rotation."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "watcher.log"

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path, when="midnight", backupCount=14, encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    )

    root_logger = logging.getLogger("smoke_signal")
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def _on_file_ready(
    file_path: Path,
    db_path: Path,
    queue: ProcessingQueue,
    watcher_config: dict,
) -> None:
    """Callback when a file passes stability checks."""
    if is_processed(db_path, file_path):
        return

    categories = watcher_config.get("categories")
    classification = classify(file_path, categories=categories)

    if classification.meeting_type == "unknown":
        # Hold the file and notify
        record_file(
            db_path,
            file_path,
            file_size=file_path.stat().st_size,
            recording_date=classification.recording_date,
            recording_time=classification.recording_time,
            status="held",
            meeting_type="unknown",
        )
        if watcher_config.get("enable_notifications", True):
            notify_held(file_path, classification.recording_date)
        logger.info(f"Held: {file_path.name} (no classification match)")
        return

    # Record and enqueue
    record_file(
        db_path,
        file_path,
        file_size=file_path.stat().st_size,
        recording_date=classification.recording_date,
        recording_time=classification.recording_time,
        status="pending",
        meeting_type=classification.meeting_type,
        description=classification.description,
        profile=classification.profile,
    )
    logger.info(
        f"Queued: {file_path.name} → {classification.meeting_type} "
        f"(profile={classification.profile}, confidence={classification.confidence})"
    )
    queue.enqueue_wake()


def run_daemon(
    watch_dir: Path | None = None,
    scan_days: int = 7,
    use_tray: bool = True,
) -> None:
    """Main daemon entry point. Sets up all components and runs."""
    # Single-instance guard: if a watcher is already running, pop its
    # dashboard window instead of starting a second copy.
    instance = SingleInstance()
    if not instance.acquire():
        instance.notify_existing()
        print("Smoke Signal is already running — showing its window instead.")
        return

    config = load_config()
    watcher_config = config.get("watcher", {})

    if watch_dir is None:
        configured = watcher_config.get("watch_dir", "")
        if not configured:
            logger.error("No watch_dir configured in config.yaml.")
            notify_error(
                Path("config.yaml"),
                "No watch folder configured. Open Smoke Signal settings to set a watch folder.",
            )
            return
        watch_dir = Path(configured)

    # Setup
    setup_logging(DEFAULT_LOGS_DIR)
    db_path = DEFAULT_DB_PATH
    init_db(db_path)

    # Crash recovery
    recovered = reset_stale_processing(db_path)
    if recovered:
        logger.info(f"Recovered {recovered} interrupted job(s)")

    # GPU lock — clear stale lock from previous crash on startup
    gpu_lock_path = DEFAULT_DATA_DIR / "gpu.lock"
    if gpu_lock_path.exists():
        logger.info("Clearing stale GPU lock from previous session")
        gpu_lock_path.unlink(missing_ok=True)
    gpu_lock = GpuLock(gpu_lock_path)

    # Processing queue
    def process_fn(job: dict) -> None:
        run_job(job, db_path)
        if watcher_config.get("trash_after_processing"):
            file_path = Path(job["file_path"])
            send2trash(file_path)
            logger.info(f"Trashed original file: {file_path.name}")

    queue = ProcessingQueue(db_path, process_fn, gpu_lock)

    # File handler
    stability_seconds = watcher_config.get("stability_seconds", 30)
    min_size = watcher_config.get("min_file_size_bytes", 50_000)
    extensions = watcher_config.get("extensions", [".m4a"])

    handler = ICloudFileHandler(
        on_file_ready=lambda fp: _on_file_ready(fp, db_path, queue, watcher_config),
        db_path=db_path,
        stability_threshold=stability_seconds,
        min_file_size=min_size,
        extensions=extensions,
    )

    if not watch_dir.exists():
        logger.error(f"Watch directory does not exist: {watch_dir}")
        notify_error(
            Path(str(watch_dir)),
            f"Watch folder not found: {watch_dir}\nOpen Smoke Signal settings to fix.",
        )
        return

    # First-run: seed existing files as "seen"
    if not DEFAULT_DB_PATH.exists() or _is_first_run(db_path):
        logger.info("First run detected — marking existing files as seen")
        existing = scan_existing(watch_dir, db_path, min_file_size=min_size, extensions=extensions)
        if existing:
            marked = mark_existing_as_seen(db_path, existing)
            logger.info(f"Marked {marked} existing files as seen")

    # Scan for new files since last run
    new_files = scan_existing(watch_dir, db_path, min_file_size=min_size, extensions=extensions)
    for fp in new_files:
        _on_file_ready(fp, db_path, queue, watcher_config)

    # Start observer
    observer = start_observer(watch_dir, handler)

    # Stability checker thread
    def stability_loop():
        while observer.is_alive():
            try:
                handler.check_stability()
            except Exception:
                logger.exception("Stability check crashed; continuing")
            time.sleep(handler.stability_interval)

    stability_thread = threading.Thread(target=stability_loop, daemon=True)
    stability_thread.start()

    # Processing queue thread
    queue_thread = threading.Thread(target=queue.run_loop, daemon=True)
    queue_thread.start()

    logger.info(f"Smoke Signal watcher running — monitoring {watch_dir}")

    # Run tray or block on signals
    if use_tray:
        try:
            from smoke_signal.watcher.tray import SmokeSignalTray
            from smoke_signal.watcher.dashboard import DashboardWindow

            def _refresh_tray():
                t = tray_holder.get("tray")
                if t is not None:
                    t.refresh_menu()

            def on_pause():
                queue.pause()
                _refresh_tray()
                logger.info("Paused — current job will finish; no new jobs will start")

            def on_resume():
                queue.resume()
                _refresh_tray()
                logger.info("Resumed")

            tray_holder: dict = {}

            dashboard = DashboardWindow(db_path, queue, on_pause, on_resume)

            def on_quit():
                logger.info("Shutting down...")
                dashboard.stop()
                queue.stop()
                observer.stop()

            tray = SmokeSignalTray(
                db_path, on_pause, on_resume, on_quit,
                on_open_dashboard=dashboard.request_show,
                is_paused_fn=lambda: queue.is_paused,
            )
            tray_holder["tray"] = tray
            tray.set_status("Watching")

            # Second launches signal us to pop the dashboard; also show it
            # on this first launch so double-clicking the icon opens a window.
            instance.listen(dashboard.request_show)
            dashboard.request_show()

            if sys.platform == "darwin":
                # macOS: Cocoa requires the tray on the main thread, so the
                # dashboard runs on a secondary thread (legacy path).
                dashboard.start()
                tray.run()  # blocks main thread
            else:
                # Windows/Linux: Tkinter must own the main thread, otherwise the
                # Tcl interpreter is finalized on the wrong thread at exit and
                # aborts with "Tcl_AsyncDelete: async handler deleted by the
                # wrong thread" (STATUS_BREAKPOINT / 0x80000003). Run the tray on
                # a background thread and the dashboard on the main thread.
                tray_thread = threading.Thread(target=tray.run, daemon=True, name="tray")
                tray_thread.start()
                dashboard.run_main()  # blocks main thread until quit
                tray.stop()
        except ImportError:
            logger.warning("pystray not available, running headless")
            instance.listen(lambda: None)
            _block_until_signal(observer, queue)
    else:
        instance.listen(lambda: None)
        _block_until_signal(observer, queue)

    observer.join(timeout=5)
    instance.release()
    logger.info("Smoke Signal watcher stopped")


def run_once(watch_dir: Path | None = None) -> None:
    """Check for new files once, process them, then exit."""
    config = load_config()
    watcher_config = config.get("watcher", {})

    if watch_dir is None:
        configured = watcher_config.get("watch_dir", "")
        if not configured:
            print("Error: No watch_dir configured in config.yaml.")
            return
        watch_dir = Path(configured)

    setup_logging(DEFAULT_LOGS_DIR)
    db_path = DEFAULT_DB_PATH
    init_db(db_path)
    reset_stale_processing(db_path)

    gpu_lock = GpuLock(DEFAULT_DATA_DIR / "gpu.lock")
    min_size = watcher_config.get("min_file_size_bytes", 50_000)
    extensions = watcher_config.get("extensions", [".m4a"])

    # First-run: seed existing files as "seen"
    if _is_first_run(db_path):
        logger.info("First run detected — marking existing files as seen")
        existing = scan_existing(watch_dir, db_path, min_file_size=min_size, extensions=extensions)
        if existing:
            marked = mark_existing_as_seen(db_path, existing)
            logger.info(f"Marked {marked} existing files as seen")

    new_files = scan_existing(watch_dir, db_path, min_file_size=min_size, extensions=extensions)
    if not new_files:
        logger.info("No new files to process")
        return

    logger.info(f"Found {len(new_files)} new file(s)")
    categories = watcher_config.get("categories")

    for fp in new_files:
        classification = classify(fp, categories=categories)

        if classification.meeting_type == "unknown":
            record_file(
                db_path, fp, file_size=fp.stat().st_size,
                recording_date=classification.recording_date,
                status="held", meeting_type="unknown",
            )
            logger.info(f"Held: {fp.name}")
            continue

        record_file(
            db_path, fp, file_size=fp.stat().st_size,
            recording_date=classification.recording_date,
            recording_time=classification.recording_time,
            status="pending",
            meeting_type=classification.meeting_type,
            description=classification.description,
            profile=classification.profile,
        )

        if not gpu_lock.acquire(timeout=600):
            logger.error("Could not acquire GPU lock")
            break

        try:
            job = {
                "file_path": str(fp),
                "profile": classification.profile,
                "meeting_type": classification.meeting_type,
                "recording_date": classification.recording_date,
            }
            update_status(db_path, fp, "processing")
            run_job(job, db_path)
            if watcher_config.get("trash_after_processing"):
                send2trash(fp)
                logger.info(f"Trashed original file: {fp.name}")
        except Exception as e:
            logger.error(f"Failed: {fp.name} — {e}")
            update_status(db_path, fp, "failed", error_message=str(e)[:500])
        finally:
            gpu_lock.release()


def _is_first_run(db_path: Path) -> bool:
    """Check if the database has any records."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
    conn.close()
    return count == 0


def _block_until_signal(observer, queue) -> None:
    """Block until SIGINT/SIGTERM, then clean up."""
    stop_event = threading.Event()

    def handler(signum, frame):
        logger.info("Signal received, shutting down...")
        queue.stop()
        observer.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    stop_event.wait()
