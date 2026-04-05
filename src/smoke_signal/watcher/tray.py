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
    ):
        self.db_path = db_path
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_quit = on_quit
        self.on_open_dashboard = on_open_dashboard
        self._paused = False
        self._status_text = "Idle"
        self._icon: pystray.Icon | None = None

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
                lambda _: f"Smoke Signal — {self._status_text}",
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
                lambda _: "Resume" if self._paused else "Pause",
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
        self._paused = not self._paused
        if self._paused:
            self._status_text = "Paused"
            self.on_pause()
        else:
            self._status_text = "Watching"
            self.on_resume()

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
