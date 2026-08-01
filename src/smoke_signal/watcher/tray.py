"""System tray app for the Smoke Signal watcher."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw
import pystray

from smoke_signal.icon import create_tray_icon
from smoke_signal.watcher.state import get_held, get_recent_jobs

logger = logging.getLogger(__name__)


class SmokeSignalTray:
    """System tray icon with status and controls."""

    def __init__(
        self,
        db_path: Path,
        on_pause: Callable,
        on_resume: Callable,
        on_quit: Callable,
        on_open_dashboard: Callable | None = None,
        is_paused_fn: Callable[[], bool] | None = None,
    ):
        self.db_path = db_path
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_quit = on_quit
        self.on_open_dashboard = on_open_dashboard
        self.is_paused_fn = is_paused_fn
        self._paused = False
        self._status_text = "Idle"
        self._icon: pystray.Icon | None = None

    def _is_paused(self) -> bool:
        """True paused state — reads the queue when available so the tray
        mirrors pauses triggered from the dashboard (and vice versa)."""
        if self.is_paused_fn is not None:
            try:
                return bool(self.is_paused_fn())
            except Exception:
                return self._paused
        return self._paused

    def _open_dashboard(self, icon, item) -> None:
        if self.on_open_dashboard:
            self.on_open_dashboard()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Dashboard",
                self._open_dashboard,
                default=True,
            ),
            pystray.MenuItem(
                lambda _: f"Smoke Signal — {'Paused' if self._is_paused() else self._status_text}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Recent Jobs",
                pystray.Menu(lambda: self._recent_items()),
            ),
            pystray.MenuItem(
                lambda _: f"Held Files ({len(get_held(self.db_path))})",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _: "Resume Watcher" if self._is_paused() else "Pause Watcher",
                self._toggle_pause,
            ),
            pystray.MenuItem("Quit", self._quit),
        )

    def _recent_items(self) -> list[pystray.MenuItem]:
        jobs = get_recent_jobs(self.db_path, limit=5)
        if not jobs:
            return [pystray.MenuItem("No recent jobs", None, enabled=False)]
        items = []
        for job in jobs:
            name = Path(job["file_path"]).name
            status = job["status"]
            label = f"{'✓' if status == 'completed' else '✗' if status == 'failed' else '…'} {name}"
            items.append(pystray.MenuItem(label, None, enabled=False))
        return items

    def _toggle_pause(self, icon, item) -> None:
        # _status_text deliberately untouched: the menu label derives
        # 'Paused' live from _is_paused(), so it can't go stale when the
        # pause comes from the dashboard instead of the tray.
        if self._is_paused():
            self._paused = False
            self.on_resume()
        else:
            self._paused = True
            self.on_pause()

    def refresh_menu(self) -> None:
        """Re-render the tray menu (call after external state changes)."""
        if self._icon is not None:
            try:
                self._icon.update_menu()
            except Exception:
                logger.debug("Tray menu refresh failed", exc_info=True)

    def _quit(self, icon, item) -> None:
        self._status_text = "Stopping..."
        self.on_quit()
        if self._icon:
            self._icon.stop()

    def set_status(self, text: str) -> None:
        self._status_text = text

    def run(self) -> None:
        """Start the tray icon. Blocks the calling thread."""
        icon_image = create_tray_icon()
        self._icon = pystray.Icon(
            "smoke-signal",
            icon_image,
            "Smoke Signal",
            menu=self._build_menu(),
        )
        logger.info("System tray started")
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
