"""Windows toast notifications for the Scribe watcher."""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

APP_ID = "Smoke Signal"


def notify_success(
    meeting_type: str,
    recording_date: str,
    output_path: Path,
    duration_str: str,
) -> None:
    """Send a toast notification on successful transcription."""
    title = f"Transcription complete"
    body = (
        f"{meeting_type.title()} recording ({recording_date})\n"
        f"Duration: {duration_str}\n"
        f"Saved to: {output_path.name}"
    )
    _send_toast(title, body)


def notify_error(file_path: Path, error_message: str) -> None:
    """Send a toast notification on transcription failure."""
    title = "Transcription failed"
    body = f"{file_path.name}\n{error_message[:200]}"
    _send_toast(title, body)


def notify_held(file_path: Path, recording_date: str) -> None:
    """Send a notification for unclassified recordings."""
    title = "New recording detected"
    body = (
        f"{file_path.name} ({recording_date})\n"
        f"No auto-classification match.\n"
        f"Run: smoke-signal classify \"{file_path}\" \"<description>\""
    )
    _send_toast(title, body)


def notify_queue(queue_depth: int, current_file: str | None = None) -> None:
    """Notify about queue state when multiple files arrive."""
    title = "Processing queue"
    if current_file:
        body = f"Processing: {current_file}\n{queue_depth} remaining in queue"
    else:
        body = f"{queue_depth} recordings queued for transcription"
    _send_toast(title, body)


def _send_toast(title: str, body: str) -> None:
    """Send a Windows toast notification."""
    try:
        from winotify import Notification

        toast = Notification(
            app_id=APP_ID,
            title=title,
            msg=body,
        )
        toast.show()
        logger.debug(f"Toast sent: {title}")
    except Exception as e:
        logger.warning(f"Failed to send toast notification: {e}")
