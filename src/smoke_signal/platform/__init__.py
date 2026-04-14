"""Platform abstraction layer — routes to Windows or macOS implementations."""

from smoke_signal.platform._router import (  # noqa: F401
    apply_window_theme,
    free_gpu_memory,
    is_file_locked,
    open_file,
    open_path,
    send_notification,
)
