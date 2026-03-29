"""Sequential GPU processing queue with file-based locking."""

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from smoke_signal.watcher.state import get_pending, update_status

logger = logging.getLogger(__name__)


class GpuLock:
    """File-based GPU lock to prevent concurrent transcriptions."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 300) -> bool:
        """Try to acquire the GPU lock. Returns True if acquired."""
        start = time.time()
        while True:
            with self._lock:
                if not self.lock_path.exists():
                    self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                    self.lock_path.write_text(str(time.time()))
                    return True

                # Check for stale lock (older than 30 minutes = crashed job)
                try:
                    lock_time = float(self.lock_path.read_text().strip())
                    if time.time() - lock_time > 1800:
                        logger.warning("Stale GPU lock detected, breaking it")
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except (ValueError, OSError):
                    self.lock_path.unlink(missing_ok=True)
                    continue

            if time.time() - start > timeout:
                return False

            time.sleep(5)

    def release(self) -> None:
        """Release the GPU lock."""
        with self._lock:
            self.lock_path.unlink(missing_ok=True)

    @property
    def is_locked(self) -> bool:
        return self.lock_path.exists()


class ProcessingQueue:
    """Sequential queue for GPU transcription jobs."""

    def __init__(
        self,
        db_path: Path,
        process_fn: Callable[[dict], None],
        gpu_lock: GpuLock,
    ):
        self.db_path = db_path
        self.process_fn = process_fn
        self.gpu_lock = gpu_lock
        self._wake_event = threading.Event()
        self._running = True
        self._current_file: str | None = None

    def enqueue_wake(self) -> None:
        """Signal that new items may be available."""
        self._wake_event.set()

    def run_loop(self) -> None:
        """Block forever, processing queued items as they arrive."""
        logger.info("Processing queue started")
        while self._running:
            self._wake_event.clear()

            while self._running:
                pending = get_pending(self.db_path)
                if not pending:
                    break

                job = pending[0]
                self._current_file = Path(job["file_path"]).name

                if not self.gpu_lock.acquire(timeout=600):
                    logger.error("Could not acquire GPU lock after 10 minutes")
                    break

                try:
                    file_path = Path(job["file_path"])
                    update_status(self.db_path, file_path, "processing")
                    logger.info(f"Processing: {file_path.name}")
                    self.process_fn(job)
                except Exception as e:
                    logger.error(f"Job failed: {e}")
                    update_status(
                        self.db_path,
                        Path(job["file_path"]),
                        "failed",
                        error_message=str(e)[:500],
                    )
                finally:
                    self.gpu_lock.release()
                    self._current_file = None

            # Wait for new items or timeout
            self._wake_event.wait(timeout=30)

        logger.info("Processing queue stopped")

    def stop(self) -> None:
        """Signal the queue to stop."""
        self._running = False
        self._wake_event.set()

    @property
    def current_file(self) -> str | None:
        return self._current_file

    @property
    def is_busy(self) -> bool:
        return self._current_file is not None

    @property
    def queue_depth(self) -> int:
        return len(get_pending(self.db_path))
