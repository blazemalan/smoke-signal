"""Windowless entry point for the Smoke Signal watcher tray app.

Registered as a gui_scripts entry point, which uses pythonw.exe on Windows —
no console window appears. On Mac/Linux, behaves identically to the CLI.
"""

import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pyannote")


def main():
    try:
        from smoke_signal.config import DEFAULT_LOGS_DIR, load_env
        from smoke_signal.watcher.daemon import run_daemon

        load_env()
        run_daemon(use_tray=True)
    except Exception:
        # With pythonw.exe, stderr is detached — write crashes to a fallback log
        import traceback

        from smoke_signal.config import DEFAULT_LOGS_DIR

        DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(DEFAULT_LOGS_DIR / "tray_crash.log", "a") as f:
            traceback.print_exc(file=f)
        sys.exit(1)


if __name__ == "__main__":
    main()
