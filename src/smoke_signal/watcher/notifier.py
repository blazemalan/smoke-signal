"""Cross-platform notifications for the Smoke Signal watcher."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_ICON_PATH = str(Path(__file__).resolve().parents[3] / "assets" / "smoke-signal.png")


def notify_success(
    meeting_type: str,
    recording_date: str,
    output_path: Path,
    duration_str: str,
) -> None:
    """Send a toast notification on successful transcription."""
    title = "Transcription complete"
    body = (
        f"{meeting_type.title()} recording ({recording_date})\n"
        f"Duration: {duration_str}\n"
        f"Saved to: {output_path.name}"
    )
    file_uri = output_path.resolve().as_uri()
    _send_toast(title, body, actions=[("Open Transcript", file_uri)])


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
        f"Open Smoke Signal to classify this recording."
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


def _send_toast(
    title: str,
    body: str,
    actions: list[tuple[str, str]] | None = None,
) -> None:
    """Send a platform-native notification.

    Args:
        title: Notification heading.
        body: Notification message text.
        actions: Optional list of (label, launch_uri) button pairs.
                 Supported on Windows; ignored on macOS.
    """
    try:
        from smoke_signal.platform import send_notification
        send_notification(title, body, icon_path=_ICON_PATH, actions=actions)
        logger.debug(f"Notification sent: {title}")
    except Exception as e:
        logger.warning(f"Failed to send notification: {e}")
