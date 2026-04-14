"""File system monitoring for iCloud Drive with stability detection."""

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from smoke_signal.watcher.state import is_processed

logger = logging.getLogger(__name__)

# Defaults (overridable via config)
DEFAULT_STABILITY_INTERVAL = 5    # seconds between size checks
DEFAULT_STABILITY_THRESHOLD = 30  # seconds of stable size = done syncing
DEFAULT_MIN_FILE_SIZE = 50_000    # 50KB minimum (skip stubs)


class ICloudFileHandler(FileSystemEventHandler):
    """Watches for new .m4a files and validates they are fully synced."""

    def __init__(
        self,
        on_file_ready: Callable[[Path], None],
        db_path: Path,
        stability_interval: int = DEFAULT_STABILITY_INTERVAL,
        stability_threshold: int = DEFAULT_STABILITY_THRESHOLD,
        min_file_size: int = DEFAULT_MIN_FILE_SIZE,
    ):
        super().__init__()
        self.on_file_ready = on_file_ready
        self.db_path = db_path
        self.stability_interval = stability_interval
        self.stability_threshold = stability_threshold
        self.min_file_size = min_file_size
        self._tracking: dict[str, dict] = {}  # path -> {size, stable_since}
        self._lock = threading.Lock()

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_file(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle_file(Path(event.src_path))

    def _handle_file(self, file_path: Path) -> None:
        """Start tracking a file if it's a valid .m4a we haven't processed."""
        if file_path.suffix.lower() != ".m4a":
            return

        if is_processed(self.db_path, file_path):
            return

        with self._lock:
            path_str = str(file_path)
            if path_str not in self._tracking:
                logger.info(f"New file detected: {file_path.name}")
                self._tracking[path_str] = {
                    "size": -1,
                    "stable_since": None,
                }

    def check_stability(self) -> None:
        """Check all tracked files for sync completion. Call periodically."""
        with self._lock:
            to_remove = []

            for path_str, info in self._tracking.items():
                file_path = Path(path_str)

                # File disappeared during sync
                if not file_path.exists():
                    logger.debug(f"File disappeared: {file_path.name}")
                    to_remove.append(path_str)
                    continue

                current_size = file_path.stat().st_size

                # Too small (stub or accidental recording)
                if current_size < self.min_file_size:
                    continue

                # File is locked by another process (iCloud still writing)
                if _is_file_locked(file_path):
                    info["stable_since"] = None
                    continue

                # Size changed — reset stability timer
                if current_size != info["size"]:
                    info["size"] = current_size
                    info["stable_since"] = time.time()
                    continue

                # Size is stable — check if threshold reached
                if info["stable_since"] is not None:
                    elapsed = time.time() - info["stable_since"]
                    if elapsed >= self.stability_threshold:
                        logger.info(
                            f"File ready: {file_path.name} "
                            f"({current_size / 1024 / 1024:.1f} MB)"
                        )
                        to_remove.append(path_str)
                        self.on_file_ready(file_path)

            for path_str in to_remove:
                del self._tracking[path_str]

    @property
    def tracking_count(self) -> int:
        with self._lock:
            return len(self._tracking)


def scan_existing(
    watch_dir: Path,
    db_path: Path,
    min_file_size: int = DEFAULT_MIN_FILE_SIZE,
) -> list[Path]:
    """Find .m4a files in the watch directory that aren't in the database.

    Returns list of new file paths (not yet processed).
    """
    new_files = []
    if not watch_dir.exists():
        logger.warning(f"Watch directory does not exist: {watch_dir}")
        return new_files

    for m4a in watch_dir.rglob("*.m4a"):
        if m4a.stat().st_size < min_file_size:
            continue
        if not is_processed(db_path, m4a):
            new_files.append(m4a)

    new_files.sort(key=lambda p: p.stat().st_mtime)
    return new_files


def start_observer(
    watch_dir: Path,
    handler: ICloudFileHandler,
) -> Observer:
    """Start the watchdog observer on the given directory."""
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info(f"Watching: {watch_dir}")
    return observer


def _is_file_locked(file_path: Path) -> bool:
    """Check if a file is locked by another process."""
    from smoke_signal.platform import is_file_locked
    return is_file_locked(file_path)
