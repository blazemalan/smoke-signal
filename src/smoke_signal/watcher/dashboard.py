"""Dashboard window for Smoke Signal — tkinter UI on a dedicated thread."""

from __future__ import annotations

import logging
import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from pathlib import Path

from PIL import Image, ImageTk

from smoke_signal.config import (
    DATA_DIR,
    DEFAULT_LOGS_DIR,
    DEFAULT_TRANSCRIPTS_DIR,
    load_config,
    get_watcher_config,
    save_config,
)
from smoke_signal.watcher.classifier import classify_from_description
from smoke_signal.watcher.state import (
    get_held,
    get_pending,
    get_recent_jobs,
    update_status,
)

logger = logging.getLogger(__name__)

# === Cinder Design System ===

BG_DEEP = "#161616"
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

# Status labels — friendly names instead of raw DB values
STATUS_LABELS = {
    "completed": "Done",
    "failed": "Failed",
    "processing": "Processing",
    "pending": "Queued",
    "held": "Needs info",
    "seen": "Skipped",
}

# Category quick-pick buttons for held files
CATEGORY_PICKS = [
    ("Meeting", "meeting"),
    ("Interview", "interview"),
    ("Lecture", "lecture"),
    ("Personal", "personal note"),
]


def _friendly_path(raw: str) -> str:
    """Shorten a path to something readable.

    C:\\Users\\you\\iCloudDrive\\iCloud~com~openplanetsoftware~just-press-record
    → iCloudDrive > just-press-record
    """
    p = Path(str(raw))
    parts = p.parts
    # Drop drive + Users + username prefix if present
    try:
        home_parts = Path.home().parts
        if parts[: len(home_parts)] == home_parts:
            parts = parts[len(home_parts) :]
    except Exception:
        pass
    # Clean up iCloud bundle IDs
    cleaned = []
    for part in parts:
        if "~" in part and part.startswith("iCloud~"):
            # iCloud~com~openplanetsoftware~just-press-record → just-press-record
            cleaned.append(part.split("~")[-1])
        else:
            cleaned.append(part)
    return " > ".join(cleaned) if cleaned else str(raw)


def _time_ago(iso_str: str | None) -> str:
    """Convert an ISO timestamp or YYYY-MM-DD date to a relative string."""
    if not iso_str:
        return ""
    try:
        # Handle both full ISO and date-only
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
        days = seconds // 86400
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"
        return iso_str  # fall back to raw date for very old
    except Exception:
        return iso_str or ""


class DashboardWindow:
    """Tkinter dashboard running on its own daemon thread."""

    def __init__(
        self,
        db_path: Path,
        queue,
        on_pause: callable,
        on_resume: callable,
    ):
        self.db_path = db_path
        self.queue = queue
        self.on_pause = on_pause
        self.on_resume = on_resume
        self._show_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._root: tk.Tk | None = None
        self._paused = False
        self._active_tab = "activity"
        self._held_entries: dict[str, tk.Entry] = {}
        self._last_job_snapshot: str = ""  # detect changes for auto-refresh

    # -- Public API (called from other threads) --

    def start(self) -> None:
        """Launch the UI thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="dashboard")
        self._thread.start()

    def request_show(self) -> None:
        """Ask the window to show itself (thread-safe)."""
        self._show_event.set()

    def stop(self) -> None:
        """Ask the window to destroy itself."""
        self._stop_event.set()

    # -- Tkinter thread --

    def _run(self) -> None:
        from smoke_signal.platform import apply_window_theme

        # DPI + dark title bar (Windows); no-op on macOS
        apply_window_theme(None)  # call before Tk() for DPI awareness

        self._root = tk.Tk()
        self._root.title("Smoke Signal")
        self._root.geometry(f"{WIN_W}x{WIN_H}")
        self._root.configure(bg=BG)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.withdraw()  # start hidden

        apply_window_theme(self._root)  # dark title bar (needs window handle)

        # Set window icon (campfire, not tkinter feather)
        try:
            assets = Path(__file__).resolve().parents[3] / "assets"
            png = assets / "smoke-signal.png"
            if png.exists():
                img = Image.open(png)
                icons = [ImageTk.PhotoImage(img.resize((s, s), Image.LANCZOS)) for s in (16, 32, 48, 64)]
                self._icon_refs = icons  # prevent GC
                self._root.iconphoto(True, *icons)
            if sys.platform == "win32":
                ico = assets / "smoke-signal.ico"
                if ico.exists():
                    self._root.iconbitmap(str(ico))
        except Exception:
            pass

        self._build_ui()
        self._poll_signals()
        self._refresh()
        self._root.mainloop()

    def _poll_signals(self) -> None:
        """Check for show/stop requests from other threads."""
        if self._stop_event.is_set():
            self._root.destroy()
            return
        if self._show_event.is_set():
            self._show_event.clear()
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
        self._root.after(100, self._poll_signals)

    def _on_close(self) -> None:
        self._root.withdraw()

    # -- UI Building --

    def _build_ui(self) -> None:
        root = self._root

        # Header
        header = tk.Frame(root, bg=BG_DEEP, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        title = tk.Label(
            header, text="Smoke Signal", font=(FONT[0], 15, "bold"),
            bg=BG_DEEP, fg=FG,
        )
        title.pack(side="left", padx=(20, 0), pady=12)

        self._status_label = tk.Label(
            header, text="Watching for recordings", font=(FONT[0], 10),
            bg=BG_DEEP, fg=FG_DIM,
        )
        self._status_label.pack(side="right", padx=(0, 20), pady=12)

        self._queue_label = tk.Label(
            header, text="", font=(FONT[0], 10),
            bg=BG_DEEP, fg=ACCENT,
        )
        self._queue_label.pack(side="right", padx=(0, 12), pady=12)

        # Tab bar
        tab_bar = tk.Frame(root, bg=BG, height=40)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._tab_buttons = {}
        for tab_id, label in [("activity", "Activity"), ("held", "Held Files"), ("folders", "Folders")]:
            btn = tk.Label(
                tab_bar, text=label, font=(FONT[0], 10),
                bg=BG, fg=FG_DIM, padx=16, pady=8, cursor="hand2",
            )
            btn.pack(side="left", padx=(4, 0))
            btn.bind("<Button-1>", lambda e, t=tab_id: self._switch_tab(t))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(fg=FG))
            btn.bind("<Leave>", lambda e, b=btn, t=tab_id: b.configure(
                fg=ACCENT if t == self._active_tab else FG_DIM
            ))
            self._tab_buttons[tab_id] = btn

        # Separator under tabs
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")

        # Content area
        self._content = tk.Frame(root, bg=BG)
        self._content.pack(fill="both", expand=True)

        # Footer
        tk.Frame(root, bg=BORDER, height=1).pack(fill="x")
        footer = tk.Frame(root, bg=BG_DEEP, height=44)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self._pause_btn = tk.Label(
            footer, text="Pause Watcher", font=(FONT[0], 10),
            bg=BG_CARD, fg=FG, padx=14, pady=6, cursor="hand2",
        )
        self._pause_btn.pack(side="left", padx=(16, 0), pady=8)
        self._pause_btn.bind("<Button-1>", lambda e: self._toggle_pause())
        self._pause_btn.bind("<Enter>", lambda e: self._pause_btn.configure(bg=BG_CARD_HOVER))
        self._pause_btn.bind("<Leave>", lambda e: self._pause_btn.configure(bg=BG_CARD))

        summarize_btn = tk.Label(
            footer, text="Summarize", font=(FONT[0], 10),
            bg=ACCENT, fg=FG, padx=14, pady=6, cursor="hand2",
        )
        summarize_btn.pack(side="left", padx=(10, 0), pady=8)
        summarize_btn.bind("<Button-1>", lambda e: self._launch_transcribe())
        summarize_btn.bind("<Enter>", lambda e: summarize_btn.configure(bg=ACCENT_GLOW))
        summarize_btn.bind("<Leave>", lambda e: summarize_btn.configure(bg=ACCENT))

        logs_btn = tk.Label(
            footer, text="Logs", font=(FONT[0], 9),
            bg=BG_DEEP, fg=FG_MUTED, padx=8, pady=6, cursor="hand2",
        )
        logs_btn.pack(side="right", padx=(0, 16), pady=8)
        logs_btn.bind("<Button-1>", lambda e: self._open_path(DEFAULT_LOGS_DIR))
        logs_btn.bind("<Enter>", lambda e: logs_btn.configure(fg=FG_DIM))
        logs_btn.bind("<Leave>", lambda e: logs_btn.configure(fg=FG_MUTED))

        self._switch_tab("activity")

    # -- Tabs --

    def _switch_tab(self, tab_id: str) -> None:
        self._active_tab = tab_id
        for tid, btn in self._tab_buttons.items():
            btn.configure(fg=ACCENT if tid == tab_id else FG_DIM)

        # Clear content
        for child in self._content.winfo_children():
            child.destroy()
        self._held_entries.clear()

        if tab_id == "activity":
            self._build_activity_tab()
        elif tab_id == "held":
            self._build_held_tab()
        elif tab_id == "folders":
            self._build_folders_tab()

    def _build_activity_tab(self) -> None:
        container = self._content
        jobs = get_recent_jobs(self.db_path, limit=20)

        if not jobs:
            self._empty_state(container, "No recordings yet", "Drop an audio file in your watch folder to get started.")
            return

        # Scrollable frame
        canvas, scroll_frame = self._make_scrollable(container)

        for job in jobs:
            self._build_job_card(scroll_frame, job)

    def _build_job_card(self, parent: tk.Frame, job: dict) -> None:
        status = job.get("status", "")
        file_path = job.get("file_path", "")
        filename = Path(file_path).name if file_path else "Unknown"
        meeting_type = job.get("meeting_type", "")
        proc_time = job.get("processing_time_seconds")
        output_path = job.get("output_path", "")
        error_msg = job.get("error_message", "")

        # Use completed_at if available, fall back to recording_date, then created_at
        timestamp = job.get("completed_at") or job.get("created_at") or job.get("recording_date")

        # Status color + friendly label
        color = {
            "completed": SUCCESS, "failed": ERROR, "processing": ACCENT,
            "pending": FG_MUTED, "held": FG_DIM, "seen": FG_MUTED,
        }.get(status, FG_MUTED)
        status_text = STATUS_LABELS.get(status, status)

        card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", padx=16, pady=(6, 0))

        # Top row: status dot + label + filename + meeting type
        top = tk.Frame(card, bg=BG_CARD)
        top.pack(fill="x")

        dot = tk.Canvas(top, width=10, height=10, bg=BG_CARD, highlightthickness=0)
        dot.create_oval(1, 1, 9, 9, fill=color, outline="")
        dot.pack(side="left", padx=(0, 4), pady=3)

        tk.Label(
            top, text=status_text, font=(FONT[0], 9),
            bg=BG_CARD, fg=color,
        ).pack(side="left", padx=(0, 10))

        name_text = filename if len(filename) <= 40 else filename[:37] + "..."
        tk.Label(
            top, text=name_text, font=(FONT[0], 10),
            bg=BG_CARD, fg=FG, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        if meeting_type and meeting_type not in ("unknown",):
            tk.Label(
                top, text=meeting_type, font=(FONT[0], 9),
                bg=BG_CARD, fg=FG_DIM,
            ).pack(side="right")

        # Bottom row: time ago, processing time, action button
        bottom = tk.Frame(card, bg=BG_CARD)
        bottom.pack(fill="x", pady=(4, 0))

        detail_parts = []
        ago = _time_ago(timestamp)
        if ago:
            detail_parts.append(ago)
        if proc_time:
            mins = int(proc_time // 60)
            secs = int(proc_time % 60)
            detail_parts.append(f"took {mins}m {secs}s" if mins else f"took {secs}s")
        if status == "failed" and error_msg:
            short_err = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg
            detail_parts.append(short_err)

        tk.Label(
            bottom, text="  ·  ".join(detail_parts), font=(FONT[0], 9),
            bg=BG_CARD, fg=FG_DIM, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Action button
        if status == "completed" and output_path and Path(output_path).exists():
            self._action_btn(bottom, "Open Transcript", lambda p=output_path: self._open_file(Path(p)))
        elif status == "failed":
            self._action_btn(bottom, "Retry", lambda fp=file_path: self._retry_job(fp))

    def _build_held_tab(self) -> None:
        container = self._content
        held = get_held(self.db_path)

        if not held:
            self._empty_state(
                container, "No held files",
                "Recordings that can't be auto-classified will appear here.\n"
                "Give them a name so Smoke Signal knows what type they are.",
            )
            return

        canvas, scroll_frame = self._make_scrollable(container)

        for item in held:
            self._build_held_card(scroll_frame, item)

    def _build_held_card(self, parent: tk.Frame, item: dict) -> None:
        file_path = item.get("file_path", "")
        filename = Path(file_path).name if file_path else "Unknown"
        rec_date = item.get("recording_date", "")

        card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", padx=16, pady=(6, 0))

        # Filename + time ago
        top = tk.Frame(card, bg=BG_CARD)
        top.pack(fill="x")

        tk.Label(
            top, text=filename, font=(FONT[0], 10),
            bg=BG_CARD, fg=FG, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ago = _time_ago(rec_date)
        if ago:
            tk.Label(
                top, text=ago, font=(FONT[0], 9),
                bg=BG_CARD, fg=FG_DIM,
            ).pack(side="right")

        # Quick-pick category buttons
        pick_row = tk.Frame(card, bg=BG_CARD)
        pick_row.pack(fill="x", pady=(8, 0))

        tk.Label(
            pick_row, text="What is this?", font=(FONT[0], 9),
            bg=BG_CARD, fg=FG_MUTED,
        ).pack(side="left", padx=(0, 10))

        for label, value in CATEGORY_PICKS:
            cat_btn = tk.Label(
                pick_row, text=label, font=(FONT[0], 9),
                bg=BG_CARD_HOVER, fg=FG_DIM, padx=10, pady=3, cursor="hand2",
            )
            cat_btn.pack(side="left", padx=(0, 4))
            cat_btn.bind("<Button-1>", lambda e, fp=file_path, v=value: self._quick_classify(fp, v))
            cat_btn.bind("<Enter>", lambda e, b=cat_btn: b.configure(bg=BORDER, fg=FG))
            cat_btn.bind("<Leave>", lambda e, b=cat_btn: b.configure(bg=BG_CARD_HOVER, fg=FG_DIM))

        # Custom description input row
        input_row = tk.Frame(card, bg=BG_CARD)
        input_row.pack(fill="x", pady=(6, 0))

        entry = tk.Entry(
            input_row, font=(FONT[0], 10),
            bg=BG_INPUT, fg=FG, insertbackground=FG,
            relief="flat", highlightthickness=1,
            highlightcolor=ACCENT, highlightbackground=BORDER,
        )
        entry.insert(0, "Or type a description...")
        entry.configure(fg=FG_MUTED)
        entry.bind("<FocusIn>", lambda e, ent=entry: self._clear_placeholder(ent, "Or type"))
        entry.bind("<FocusOut>", lambda e, ent=entry: self._restore_placeholder(ent, "Or type a description..."))
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        self._held_entries[file_path] = entry

        self._action_btn(
            input_row, "Process",
            lambda fp=file_path: self._process_held(fp),
            accent=True,
        )

        # Skip button at the end
        skip_row = tk.Frame(card, bg=BG_CARD)
        skip_row.pack(fill="x", pady=(6, 0))

        skip_btn = tk.Label(
            skip_row, text="Skip this file", font=(FONT[0], 9),
            bg=BG_CARD, fg=FG_MUTED, cursor="hand2",
        )
        skip_btn.pack(side="right")
        skip_btn.bind("<Button-1>", lambda e, fp=file_path: self._skip_held(fp))
        skip_btn.bind("<Enter>", lambda e: skip_btn.configure(fg=FG_DIM))
        skip_btn.bind("<Leave>", lambda e: skip_btn.configure(fg=FG_MUTED))

    def _build_folders_tab(self) -> None:
        container = self._content
        config = load_config()
        watcher_cfg = get_watcher_config(config)
        watch_dir = watcher_cfg.get("watch_dir", "Not configured")

        inner = tk.Frame(container, bg=BG)
        inner.pack(fill="both", expand=True, padx=24, pady=16)

        # Watch folder
        self._folder_card(
            inner, "Watch Folder",
            _friendly_path(watch_dir), watch_dir,
            subtitle="New recordings are picked up from here",
            on_change=self._change_watch_folder,
        )

        # Transcripts folder
        transcripts_dir = config.get("defaults", {}).get("output_dir", str(DEFAULT_TRANSCRIPTS_DIR))
        self._folder_card(
            inner, "Transcripts",
            _friendly_path(transcripts_dir), transcripts_dir,
            subtitle="Finished transcripts are saved here",
            on_change=self._change_transcripts_folder,
        )

        # Stats
        stats_frame = tk.Frame(inner, bg=BG_CARD, padx=16, pady=12)
        stats_frame.pack(fill="x", pady=(12, 0))

        tk.Label(
            stats_frame, text="Summary", font=(FONT[0], 11, "bold"),
            bg=BG_CARD, fg=FG,
        ).pack(anchor="w")

        jobs = get_recent_jobs(self.db_path, limit=500)
        counts = {}
        for j in jobs:
            s = j.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1

        total = counts.get("completed", 0)
        failed = counts.get("failed", 0)
        held = counts.get("held", 0)
        queued = counts.get("pending", 0)

        stats_text = f"{total} transcribed    {failed} failed    {held} need attention    {queued} in queue"
        tk.Label(
            stats_frame, text=stats_text, font=(FONT[0], 10),
            bg=BG_CARD, fg=FG_DIM,
        ).pack(anchor="w", pady=(4, 0))

    def _folder_card(self, parent: tk.Frame, title: str, display_path: str,
                     raw_path, subtitle: str = "", on_change: callable = None) -> None:
        card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(0, 8))

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x")

        tk.Label(
            row, text=title, font=(FONT[0], 10, "bold"),
            bg=BG_CARD, fg=FG,
        ).pack(side="left")

        # Buttons (right-aligned, right to left)
        open_btn = tk.Label(
            row, text="Open", font=(FONT[0], 9),
            bg=BG_CARD, fg=ACCENT, cursor="hand2",
        )
        open_btn.pack(side="right")
        open_btn.bind("<Button-1>", lambda e, p=raw_path: self._open_path(Path(str(p))))
        open_btn.bind("<Enter>", lambda e: open_btn.configure(fg=ACCENT_GLOW))
        open_btn.bind("<Leave>", lambda e: open_btn.configure(fg=ACCENT))

        if on_change:
            change_btn = tk.Label(
                row, text="Change", font=(FONT[0], 9),
                bg=BG_CARD, fg=FG_DIM, cursor="hand2", padx=8,
            )
            change_btn.pack(side="right")
            change_btn.bind("<Button-1>", lambda e: on_change())
            change_btn.bind("<Enter>", lambda e: change_btn.configure(fg=FG))
            change_btn.bind("<Leave>", lambda e: change_btn.configure(fg=FG_DIM))

        # Friendly path
        tk.Label(
            card, text=display_path, font=(FONT[0], 9),
            bg=BG_CARD, fg=FG_DIM, anchor="w",
        ).pack(fill="x", pady=(4, 0))

        # Subtitle
        if subtitle:
            tk.Label(
                card, text=subtitle, font=(FONT[0], 9),
                bg=BG_CARD, fg=FG_MUTED, anchor="w",
            ).pack(fill="x")

    # -- Helpers --

    def _make_scrollable(self, container: tk.Frame) -> tuple[tk.Canvas, tk.Frame]:
        canvas = tk.Canvas(container, bg=BG, highlightthickness=0, bd=0)
        scroll_frame = tk.Frame(canvas, bg=BG)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=WIN_W - 2)
        canvas.pack(fill="both", expand=True)

        # Mousewheel scrolling (no visible scrollbar — cleaner look)
        def _on_mousewheel(event):
            if sys.platform == "darwin":
                canvas.yview_scroll(int(-1 * event.delta), "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        return canvas, scroll_frame

    def _action_btn(self, parent, text, command, accent=False) -> None:
        bg = ACCENT if accent else BG_CARD_HOVER
        fg_c = FG if accent else FG_DIM
        hover_bg = ACCENT_GLOW if accent else BORDER

        btn = tk.Label(
            parent, text=text, font=(FONT[0], 9),
            bg=bg, fg=fg_c, padx=10, pady=3, cursor="hand2",
        )
        btn.pack(side="right", padx=(4, 0))
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))

    def _empty_state(self, parent, title: str, subtitle: str) -> None:
        frame = tk.Frame(parent, bg=BG)
        frame.pack(expand=True)
        tk.Label(
            frame, text=title, font=(FONT[0], 13),
            bg=BG, fg=FG_DIM,
        ).pack(pady=(0, 4))
        tk.Label(
            frame, text=subtitle, font=(FONT[0], 10),
            bg=BG, fg=FG_MUTED,
        ).pack()

    def _clear_placeholder(self, entry: tk.Entry, prefix: str) -> None:
        if entry.get().startswith(prefix):
            entry.delete(0, "end")
            entry.configure(fg=FG)

    def _restore_placeholder(self, entry: tk.Entry, placeholder: str) -> None:
        if not entry.get().strip():
            entry.insert(0, placeholder)
            entry.configure(fg=FG_MUTED)

    def _open_path(self, path: Path) -> None:
        from smoke_signal.platform import open_path
        open_path(path)

    def _open_file(self, path: Path) -> None:
        """Open a specific file (e.g. a transcript) with the default app."""
        from smoke_signal.platform import open_file
        open_file(path)

    # -- Actions --

    def _retry_job(self, file_path: str) -> None:
        update_status(self.db_path, Path(file_path), "pending")
        if self.queue:
            self.queue.enqueue_wake()
        self._switch_tab("activity")

    def _quick_classify(self, file_path: str, description: str) -> None:
        """Classify a held file using a quick-pick category."""
        config = load_config()
        categories = get_watcher_config(config).get("categories")
        classification = classify_from_description(
            Path(file_path), description, categories=categories,
        )
        update_status(
            self.db_path, Path(file_path), "pending",
            meeting_type=classification.meeting_type,
            description=classification.description,
            profile=classification.profile,
        )
        if self.queue:
            self.queue.enqueue_wake()
        self._switch_tab("held")

    def _process_held(self, file_path: str) -> None:
        entry = self._held_entries.get(file_path)
        if not entry:
            return
        description = entry.get().strip()
        if not description or description.startswith("Or type"):
            entry.configure(highlightbackground=ERROR, highlightcolor=ERROR)
            self._root.after(1500, lambda: entry.configure(
                highlightbackground=BORDER, highlightcolor=ACCENT
            ))
            return
        self._quick_classify(file_path, description)

    def _skip_held(self, file_path: str) -> None:
        update_status(self.db_path, Path(file_path), "seen")
        self._switch_tab("held")

    def _change_watch_folder(self) -> None:
        new_dir = filedialog.askdirectory(
            title="Choose Watch Folder",
            parent=self._root,
        )
        if not new_dir:
            return
        config = load_config()
        if "watcher" not in config:
            config["watcher"] = {}
        config["watcher"]["watch_dir"] = new_dir
        save_config(config)
        self._switch_tab("folders")

    def _change_transcripts_folder(self) -> None:
        new_dir = filedialog.askdirectory(
            title="Choose Transcripts Folder",
            parent=self._root,
        )
        if not new_dir:
            return
        config = load_config()
        if "defaults" not in config:
            config["defaults"] = {}
        config["defaults"]["output_dir"] = new_dir
        save_config(config)
        self._switch_tab("folders")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.configure(text="Resume Watcher")
            self.on_pause()
        else:
            self._pause_btn.configure(text="Pause Watcher")
            self.on_resume()

    def _launch_transcribe(self) -> None:
        """Open a terminal running claude with /transcribe."""
        import subprocess
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    'start cmd /k claude "/transcribe"',
                    shell=True,
                )
            elif sys.platform == "darwin":
                script = 'tell app "Terminal" to do script "claude \\"/transcribe\\""'
                subprocess.Popen(["osascript", "-e", script])
            else:
                subprocess.Popen(["x-terminal-emulator", "-e", "claude", "/transcribe"])
        except Exception as e:
            logger.warning(f"Could not launch Claude: {e}")

    # -- Refresh loop --

    def _refresh(self) -> None:
        """Update status bar and auto-refresh active tab every 2 seconds."""
        if self._stop_event.is_set():
            return

        try:
            # Update header status
            if self._paused:
                status = "Paused"
            elif self.queue and self.queue.is_busy:
                current = self.queue.current_file or "..."
                name = current if len(current) <= 25 else current[:22] + "..."
                status = f"Processing {name}"
            else:
                status = "Watching for recordings"
            self._status_label.configure(text=status)

            depth = self.queue.queue_depth if self.queue else 0
            held_count = len(get_held(self.db_path))
            parts = []
            if depth > 0:
                parts.append(f"{depth} queued")
            if held_count > 0:
                parts.append(f"{held_count} need attention")
            self._queue_label.configure(text="  ·  ".join(parts))

            held_btn = self._tab_buttons.get("held")
            if held_btn:
                held_text = f"Held Files ({held_count})" if held_count else "Held Files"
                held_btn.configure(text=held_text)

            # Auto-refresh active tab when data changes
            jobs = get_recent_jobs(self.db_path, limit=20)
            snapshot = "|".join(f"{j['file_path']}:{j['status']}" for j in jobs)
            if snapshot != self._last_job_snapshot:
                self._last_job_snapshot = snapshot
                if self._active_tab == "activity":
                    self._switch_tab("activity")
                elif self._active_tab == "held":
                    self._switch_tab("held")

        except Exception:
            pass

        self._root.after(2000, self._refresh)
