from __future__ import annotations
import tkinter as tk
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageTk

BG_DEEP = "#000000"
BG = "#1c1c1c"
BG_CARD = "#242424"
BG_CARD_HOVER = "#2e2e2e"
BG_INPUT = "#1e1e1e"
FG = "#e5e5e5"
FG_DIM = "#999999"
FG_MUTED = "#666666"
ACCENT = "#d4451a"
ACCENT_GLOW = "#ff6b3d"
SUCCESS = "#4ecca3"
ERROR = "#e74c3c"
BORDER = "#383838"

FONT = ("Inter", "Segoe UI", "SF Pro Display", "sans-serif")
FONT_MONO = ("JetBrains Mono", "Consolas", "Courier New", "monospace")

WIN_W = 800
WIN_H = 560

STATUS_LABELS = {
    "completed": "Done",
    "failed": "Failed",
    "processing": "Processing",
    "pending": "Queued",
    "held": "Needs info",
    "seen": "Skipped",
}

CATEGORY_PICKS = [
    ("Meeting", "meeting"),
    ("Interview", "interview"),
    ("Lecture", "lecture"),
    ("Personal", "personal note"),
]

def _friendly_path(raw: str) -> str:
    p = Path(str(raw))
    parts = p.parts
    try:
        home_parts = Path.home().parts
        if parts[: len(home_parts)] == home_parts:
            parts = parts[len(home_parts) :]
    except Exception:
        pass
    cleaned = []
    for part in parts:
        if "~" in part and part.startswith("iCloud~"):
            cleaned.append(part.split("~")[-1])
        else:
            cleaned.append(part)
    return " > ".join(cleaned) if cleaned else str(raw)

def _time_ago(iso_str: str | None) -> str:
    if not iso_str:
        return ""
    raw = str(iso_str)
    try:
        if "T" in iso_str:
            dt = datetime.fromisoformat(iso_str)
        else:
            dt = datetime.strptime(iso_str, "%Y-%m-%d")
        delta = datetime.now() - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            m = seconds // 60
            return f"{m}m ago"
        if seconds < 86400:
            h = seconds // 3600
            return f"{h}h ago"
        if seconds < 172800:
            return "yesterday"
        d = seconds // 86400
        return f"{d}d ago"
    except Exception:
        return raw
