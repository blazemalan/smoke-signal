"""macOS platform implementations."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = [
    "send_notification",
    "is_file_locked",
    "open_path",
    "open_file",
    "apply_window_theme",
    "free_gpu_memory",
]


def send_notification(
    title: str,
    body: str,
    icon_path: str = "",
    actions: list[tuple[str, str]] | None = None,
) -> None:
    """Send a macOS notification via osascript.

    Action buttons are not supported in basic AppleScript notifications,
    so the actions parameter is accepted but ignored.
    """
    try:
        subprocess.run(
            [
                "osascript",
                "-e", "on run argv",
                "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                "-e", "end run",
                title,
                body,
            ],
            capture_output=True, timeout=5,
        )
    except Exception as e:
        logger.warning(f"Failed to send notification: {e}")


def is_file_locked(file_path: Path) -> bool:
    """Check if a file is locked by another process using fcntl."""
    import fcntl

    try:
        with open(file_path, "rb") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return False
    except (IOError, OSError):
        return True


def open_path(path: Path) -> None:
    """Open a folder in Finder."""
    target = path if path.is_dir() else path.parent
    try:
        subprocess.run(["open", str(target)], check=False)
    except Exception:
        logger.warning(f"Could not open: {target}")


def open_file(path: Path) -> None:
    """Open a file with its default application."""
    try:
        subprocess.run(["open", str(path)], check=False)
    except Exception:
        logger.warning(f"Could not open file: {path}")


def apply_window_theme(tk_root=None) -> None:
    """No-op on macOS.

    macOS Tk handles Retina scaling natively, and the app paints its own
    dark colors via the Cinder design system.
    """
    pass


def free_gpu_memory() -> None:
    """Free GPU memory (MPS or CUDA fallback)."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif hasattr(torch, "mps") and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass
