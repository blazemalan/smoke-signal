"""System tray app for the Smoke Signal watcher."""

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pystray

from smoke_signal.watcher.state import get_held, get_recent_jobs

logger = logging.getLogger(__name__)


def create_icon(size: int = 64) -> Image.Image:
    """Generate a smoke signal icon — fire at bottom, smoke wisps rising."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size / 64  # scale factor
    cx = size // 2

    # Smoke wisps (grey, rising from fire) — drawn first so fire overlaps
    smoke_color = (180, 180, 190, 140)
    smoke_light = (200, 200, 210, 100)

    # Left wisp
    draw.ellipse([
        int((cx - 12) * s), int(6 * s),
        int((cx - 2) * s), int(18 * s),
    ], fill=smoke_light)

    # Center wisp (larger)
    draw.ellipse([
        int((cx - 7) * s), int(2 * s),
        int((cx + 7) * s), int(16 * s),
    ], fill=smoke_color)

    # Right wisp
    draw.ellipse([
        int((cx + 2) * s), int(8 * s),
        int((cx + 12) * s), int(20 * s),
    ], fill=smoke_light)

    # Mid smoke connection
    draw.ellipse([
        int((cx - 9) * s), int(14 * s),
        int((cx + 9) * s), int(28 * s),
    ], fill=smoke_color)

    # Fire base (orange)
    fire_outer = [
        (cx, int(24 * s)),                  # tip
        (int(cx + 14 * s), int(40 * s)),    # right
        (int(cx + 12 * s), int(56 * s)),    # right base
        (int(cx - 12 * s), int(56 * s)),    # left base
        (int(cx - 14 * s), int(40 * s)),    # left
    ]
    draw.polygon(fire_outer, fill=(255, 120, 0, 255))

    # Fire inner (yellow)
    fire_inner = [
        (cx, int(30 * s)),
        (int(cx + 8 * s), int(42 * s)),
        (int(cx + 6 * s), int(52 * s)),
        (int(cx - 6 * s), int(52 * s)),
        (int(cx - 8 * s), int(42 * s)),
    ]
    draw.polygon(fire_inner, fill=(255, 200, 50, 255))

    # Fire core (white-hot)
    fire_core = [
        (cx, int(36 * s)),
        (int(cx + 3 * s), int(44 * s)),
        (int(cx + 2 * s), int(52 * s)),
        (int(cx - 2 * s), int(52 * s)),
        (int(cx - 3 * s), int(44 * s)),
    ]
    draw.polygon(fire_core, fill=(255, 255, 220, 255))

    return img


class SmokeSignalTray:
    """System tray icon with status and controls."""

    def __init__(
        self,
        db_path: Path,
        on_pause: callable,
        on_resume: callable,
        on_quit: callable,
    ):
        self.db_path = db_path
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_quit = on_quit
        self._paused = False
        self._status_text = "Idle"
        self._icon: pystray.Icon | None = None

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
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
        icon_image = create_icon()
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
