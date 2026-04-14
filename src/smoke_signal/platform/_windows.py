"""Windows platform implementations."""

from __future__ import annotations

import ctypes
import logging
import os
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
    """Send a Windows toast notification via winotify."""
    from winotify import Notification

    # winotify requires .ico — swap .png for .ico if available
    icon = icon_path
    if icon and icon.endswith(".png"):
        ico_path = icon.rsplit(".", 1)[0] + ".ico"
        if Path(ico_path).exists():
            icon = ico_path
    icon = icon if icon and Path(icon).exists() else ""
    toast = Notification(
        app_id="Smoke Signal",
        title=title,
        msg=body,
        icon=icon,
    )
    for label, launch_uri in actions or []:
        toast.add_actions(label=label, launch=launch_uri)
    toast.show()


def is_file_locked(file_path: Path) -> bool:
    """Check if a file is locked by another process using kernel32."""
    try:
        GENERIC_READ = 0x80000000
        FILE_SHARE_NONE = 0
        OPEN_EXISTING = 3
        INVALID_HANDLE = ctypes.c_void_p(-1).value

        handle = ctypes.windll.kernel32.CreateFileW(
            str(file_path),
            GENERIC_READ,
            FILE_SHARE_NONE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle == INVALID_HANDLE:
            return True
        ctypes.windll.kernel32.CloseHandle(handle)
        return False
    except (OSError, AttributeError):
        return False


def open_path(path: Path) -> None:
    """Open a folder in Explorer."""
    target = path if path.is_dir() else path.parent
    try:
        os.startfile(str(target))
    except Exception:
        logger.warning(f"Could not open: {target}")


def open_file(path: Path) -> None:
    """Open a file with its default application."""
    try:
        os.startfile(str(path))
    except Exception:
        logger.warning(f"Could not open file: {path}")


def apply_window_theme(tk_root=None) -> None:
    """Apply high-DPI awareness and dark title bar on Windows.

    Call with tk_root=None before creating the Tk window (for DPI awareness).
    Call again with the Tk root after creation (for dark title bar).
    """
    # DPI awareness — safe to call multiple times
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    # Dark title bar on Windows 11 — needs a window handle
    if tk_root is not None:
        try:
            hwnd = ctypes.windll.user32.GetParent(tk_root.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value),
            )
        except Exception:
            pass


def free_gpu_memory() -> None:
    """Free GPU memory (CUDA)."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
