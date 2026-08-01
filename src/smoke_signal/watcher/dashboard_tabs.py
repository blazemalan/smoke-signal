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
from smoke_signal.watcher.dashboard_shared import *

logger = logging.getLogger(__name__)

class ActivityTab:
    def build(self, dashboard) -> None:
        container = dashboard._content
        jobs = get_recent_jobs(dashboard.db_path, limit=20)

        if not jobs:
            dashboard._empty_state(container, "No recordings yet", "Drop an audio file in your watch folder to get started.")
            return

        # Scrollable frame
        canvas, scroll_frame = dashboard._make_scrollable(container)

        for job in jobs:
            self._build_job_card(dashboard, scroll_frame, job)


    def _build_job_card(self, dashboard, parent: tk.Frame, job: dict) -> None:
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

        # Action buttons
        if status == "completed" and output_path and Path(output_path).exists():
            dashboard._action_btn(bottom, "Open Transcript", lambda p=output_path: dashboard._open_file(Path(p)))
            if dashboard._summarize_command():
                dashboard._action_btn(bottom, "Summarize", lambda p=output_path: dashboard._summarize_file(Path(p)))
        elif status == "failed":
            dashboard._action_btn(bottom, "Retry", lambda fp=file_path: dashboard._retry_job(fp))


class HeldTab:
    def build(self, dashboard) -> None:
        container = dashboard._content
        held = get_held(dashboard.db_path)

        if not held:
            dashboard._empty_state(
                container, "No held files",
                "Recordings that can't be auto-classified will appear here.\n"
                "Give them a name so Smoke Signal knows what type they are.",
            )
            return

        canvas, scroll_frame = dashboard._make_scrollable(container)

        for item in held:
            self._build_held_card(dashboard, scroll_frame, item)


    def _build_held_card(self, dashboard, parent: tk.Frame, item: dict) -> None:
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
            cat_btn.bind("<Button-1>", lambda e, fp=file_path, v=value: dashboard._quick_classify(fp, v))
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
        entry.bind("<FocusIn>", lambda e, ent=entry: dashboard._clear_placeholder(ent, "Or type"))
        entry.bind("<FocusOut>", lambda e, ent=entry: dashboard._restore_placeholder(ent, "Or type a description..."))
        entry.bind("<Return>", lambda e, fp=file_path: dashboard._process_held(fp))
        entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        dashboard._held_entries[file_path] = entry

        dashboard._action_btn(
            input_row, "Process",
            lambda fp=file_path: dashboard._process_held(fp),
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
        skip_btn.bind("<Button-1>", lambda e, fp=file_path: dashboard._skip_held(fp))
        skip_btn.bind("<Enter>", lambda e: skip_btn.configure(fg=FG_DIM))
        skip_btn.bind("<Leave>", lambda e: skip_btn.configure(fg=FG_MUTED))


class FoldersTab:
    def build(self, dashboard) -> None:
        container = dashboard._content
        config = load_config()
        watcher_cfg = get_watcher_config(config)
        watch_dir = watcher_cfg.get("watch_dir", "Not configured")

        inner = tk.Frame(container, bg=BG)
        inner.pack(fill="both", expand=True, padx=24, pady=16)

        # Watch folder
        self._folder_card(dashboard,
            inner, "Watch Folder",
            _friendly_path(watch_dir), watch_dir,
            subtitle="New recordings are picked up from here",
            on_change=dashboard._change_watch_folder,
        )

        # Transcripts folder
        transcripts_dir = config.get("defaults", {}).get("output_dir", str(DEFAULT_TRANSCRIPTS_DIR))
        self._folder_card(dashboard,
            inner, "Transcripts",
            _friendly_path(transcripts_dir), transcripts_dir,
            subtitle="Finished transcripts are saved here",
            on_change=dashboard._change_transcripts_folder,
        )

        # Stats
        stats_frame = tk.Frame(inner, bg=BG_CARD, padx=16, pady=12)
        stats_frame.pack(fill="x", pady=(12, 0))

        tk.Label(
            stats_frame, text="Summary", font=(FONT[0], 11, "bold"),
            bg=BG_CARD, fg=FG,
        ).pack(anchor="w")

        jobs = get_recent_jobs(dashboard.db_path, limit=500)
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


    def _folder_card(self, dashboard, parent: tk.Frame, title: str, display_path: str,
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
        open_btn.bind("<Button-1>", lambda e, p=raw_path: dashboard._open_path(Path(str(p))))
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

    # -- Speakers tab --


class SpeakersTab:
    def build(self, dashboard) -> None:
        container = dashboard._content
        canvas, scroll = dashboard._make_scrollable(container)
        inner = tk.Frame(scroll, bg=BG)
        inner.pack(fill="both", expand=True, padx=24, pady=16)

        try:
            from smoke_signal.config import DEFAULT_PROFILES_DIR
            from smoke_signal.enrollment.manager import list_profiles
            profiles = list_profiles(DEFAULT_PROFILES_DIR)
        except Exception:
            logger.exception("Could not list speaker profiles")
            profiles = []

        if profiles:
            for prof in profiles:
                self._speaker_card(dashboard, inner, prof)
        else:
            card = tk.Frame(inner, bg=BG_CARD, padx=14, pady=12)
            card.pack(fill="x", pady=(0, 8))
            tk.Label(card, text="No speakers enrolled yet",
                     font=(FONT[0], 10), bg=BG_CARD, fg=FG_DIM).pack(anchor="w")
            tk.Label(card, text="Enroll a voice below and transcripts will name who said what.",
                     font=(FONT[0], 9), bg=BG_CARD, fg=FG_MUTED).pack(anchor="w")

        # Enroll card
        card = tk.Frame(inner, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(8, 0))
        tk.Label(card, text="Enroll a speaker", font=(FONT[0], 10, "bold"),
                 bg=BG_CARD, fg=FG).pack(anchor="w")
        tk.Label(card, text="30–60 seconds of one person talking works best — an old voice memo is perfect.",
                 font=(FONT[0], 9), bg=BG_CARD, fg=FG_MUTED).pack(anchor="w", pady=(2, 6))

        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x")
        tk.Label(row, text="Name", font=(FONT[0], 9),
                 bg=BG_CARD, fg=FG_DIM).pack(side="left")
        dashboard._enroll_name = tk.Entry(row, font=(FONT[0], 9), bg=BG_CARD_HOVER,
                                     fg=FG, insertbackground=FG, relief="flat", width=20)
        dashboard._enroll_name.pack(side="left", padx=(8, 0), ipady=3)

        from smoke_signal.enrollment.service import recording_available
        if recording_available():
            dashboard._action_btn(row, "Record 30s", lambda: self._start_enroll(dashboard, record=True))
        dashboard._action_btn(row, "From Audio File…", lambda: self._start_enroll(dashboard, record=False), accent=True)

        dashboard._enroll_status = tk.Label(card, text=dashboard._enroll_msg or "",
                                       font=(FONT[0], 9), bg=BG_CARD, fg=FG_DIM, anchor="w")
        dashboard._enroll_status.pack(fill="x", pady=(6, 0))


    def _speaker_card(self, dashboard, parent: tk.Frame, prof: dict) -> None:
        card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(0, 6))
        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x")
        tk.Label(row, text=prof.get("name", "?"), font=(FONT[0], 10, "bold"),
                 bg=BG_CARD, fg=FG).pack(side="left")
        dashboard._action_btn(row, "Delete", lambda n=prof.get("name"): self._delete_speaker(dashboard, n))
        samples = prof.get("num_samples", "?")
        updated = (prof.get("updated") or "")[:10]
        tk.Label(card, text=f"{samples} voice sample(s)  ·  updated {updated}",
                 font=(FONT[0], 9), bg=BG_CARD, fg=FG_MUTED, anchor="w").pack(fill="x", pady=(2, 0))


    def _delete_speaker(self, dashboard, name: str) -> None:
        try:
            from smoke_signal.config import DEFAULT_PROFILES_DIR
            from smoke_signal.enrollment.manager import delete_profile
            delete_profile(name, DEFAULT_PROFILES_DIR)
        except Exception:
            logger.exception("Could not delete speaker profile")
        dashboard._switch_tab("speakers")


    def _start_enroll(self, dashboard, record: bool) -> None:
        if dashboard._enroll_thread is not None and dashboard._enroll_thread.is_alive():
            return  # one at a time
        name = dashboard._enroll_name.get().strip()
        if not name:
            dashboard._enroll_msg = "Enter a name first"
            dashboard._enroll_status.configure(text=dashboard._enroll_msg)
            return

        audio_path = None
        if not record:
            picked = filedialog.askopenfilename(
                title="Choose a recording of this person speaking alone",
                filetypes=[("Audio files", "*.m4a *.wav *.mp3 *.flac *.ogg *.aac *.webm *.mp4"),
                           ("All files", "*.*")],
            )
            if not picked:
                return
            audio_path = Path(picked)

        def status_cb(msg: str) -> None:
            dashboard._enroll_msg = msg  # picked up by the 2s refresh loop

        def worker() -> None:
            from smoke_signal.enrollment.service import enroll_from_file, record_clip
            gpu_lock = getattr(dashboard.queue, "gpu_lock", None) if dashboard.queue else None
            path = audio_path
            temp_clip = None
            if record:
                temp_clip = record_clip(30, status_cb)
                if temp_clip is None:
                    return
                path = temp_clip
            try:
                if enroll_from_file(name, path, status_cb, gpu_lock=gpu_lock):
                    dashboard._enroll_done = True
            finally:
                if temp_clip is not None:
                    Path(temp_clip).unlink(missing_ok=True)

        dashboard._enroll_msg = "Starting…"
        dashboard._enroll_status.configure(text=dashboard._enroll_msg)
        dashboard._enroll_thread = threading.Thread(target=worker, daemon=True, name="enroll")
        dashboard._enroll_thread.start()

    # -- Settings tab --

    _MODEL_CHOICES = ["large-v3", "large-v3-turbo", "medium", "small", "base", "tiny"]


class SettingsTab:
    def build(self, dashboard) -> None:
        container = dashboard._content
        config = load_config()
        defaults = config.get("defaults", {}) or {}
        watcher_cfg = get_watcher_config(config) or {}
        integrations = config.get("integrations", {}) or {}

        canvas, scroll = dashboard._make_scrollable(container)
        inner = tk.Frame(scroll, bg=BG)
        inner.pack(fill="both", expand=True, padx=24, pady=16)

        dashboard._settings_widgets = {}

        # --- Transcription card ---
        card = tk.Frame(inner, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text="Transcription", font=(FONT[0], 10, "bold"),
                 bg=BG_CARD, fg=FG).pack(anchor="w")

        model_var = tk.StringVar(value=defaults.get("model", "large-v3-turbo"))
        dashboard._settings_widgets["model"] = model_var
        row = self._settings_row(dashboard, card, "Whisper model")
        opt = tk.OptionMenu(row, model_var, *dashboard._MODEL_CHOICES)
        opt.configure(bg=BG_CARD_HOVER, fg=FG, activebackground=BORDER,
                      activeforeground=FG, highlightthickness=0, bd=0,
                      font=(FONT[0], 9))
        opt["menu"].configure(bg=BG_CARD, fg=FG, font=(FONT[0], 9))
        opt.pack(side="right")

        dashboard._settings_widgets["language"] = self._settings_entry(dashboard,
            card, "Language code ('auto' to detect)", defaults.get("language", "en"))
        dashboard._settings_widgets["speakers"] = self._settings_entry(dashboard,
            card, "Expected speakers (blank = auto)",
            "" if defaults.get("speakers") is None else str(defaults.get("speakers")))

        identify_var = tk.BooleanVar(value=bool(defaults.get("identify", False)))
        dashboard._settings_widgets["identify"] = identify_var
        self._settings_check(dashboard, card, "Identify enrolled speakers", identify_var)

        # --- Watcher card ---
        card = tk.Frame(inner, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text="Watcher", font=(FONT[0], 10, "bold"),
                 bg=BG_CARD, fg=FG).pack(anchor="w")

        notif_var = tk.BooleanVar(value=bool(watcher_cfg.get("enable_notifications", True)))
        dashboard._settings_widgets["notifications"] = notif_var
        self._settings_check(dashboard, card, "Show notifications", notif_var)

        dashboard._settings_widgets["stability"] = self._settings_entry(dashboard,
            card, "Seconds a file must be stable before processing",
            str(watcher_cfg.get("stability_seconds", 30)))
        exts = watcher_cfg.get("extensions") or [".m4a"]
        dashboard._settings_widgets["extensions"] = self._settings_entry(dashboard,
            card, "Audio file types (comma-separated)", ", ".join(exts))

        # --- Integrations card ---
        card = tk.Frame(inner, bg=BG_CARD, padx=14, pady=10)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text="Integrations", font=(FONT[0], 10, "bold"),
                 bg=BG_CARD, fg=FG).pack(anchor="w")
        dashboard._settings_widgets["summarize_command"] = self._settings_entry(dashboard,
            card, "Summarize button command ({file} = transcript path; blank hides the button)",
            integrations.get("summarize_command", "") or "")

        # --- Save row ---
        save_row = tk.Frame(inner, bg=BG)
        save_row.pack(fill="x", pady=(8, 0))
        dashboard._settings_status = tk.Label(
            save_row, text="", font=(FONT[0], 9), bg=BG, fg=FG_MUTED)
        dashboard._settings_status.pack(side="left")
        save_btn = tk.Label(
            save_row, text="Save Settings", font=(FONT[0], 10),
            bg=ACCENT, fg=FG, padx=14, pady=5, cursor="hand2")
        save_btn.pack(side="right")
        save_btn.bind("<Button-1>", lambda e: self._save_settings(dashboard, ))
        save_btn.bind("<Enter>", lambda e: save_btn.configure(bg=ACCENT_GLOW))
        save_btn.bind("<Leave>", lambda e: save_btn.configure(bg=ACCENT))


    def _settings_row(self, dashboard, card: tk.Frame, label: str) -> tk.Frame:
        row = tk.Frame(card, bg=BG_CARD)
        row.pack(fill="x", pady=(6, 0))
        tk.Label(row, text=label, font=(FONT[0], 9),
                 bg=BG_CARD, fg=FG_DIM).pack(side="left")
        return row


    def _settings_entry(self, dashboard, card: tk.Frame, label: str, value: str) -> tk.Entry:
        row = self._settings_row(dashboard, card, label)
        entry = tk.Entry(row, font=(FONT[0], 9), bg=BG_CARD_HOVER, fg=FG,
                         insertbackground=FG, relief="flat", width=28)
        entry.insert(0, value)
        entry.pack(side="right", ipady=3)
        return entry


    def _settings_check(self, dashboard, card: tk.Frame, label: str, var: tk.BooleanVar) -> None:
        row = self._settings_row(dashboard, card, label)
        chk = tk.Checkbutton(
            row, variable=var, bg=BG_CARD, activebackground=BG_CARD,
            selectcolor=BG_CARD_HOVER, highlightthickness=0, bd=0)
        chk.pack(side="right")


    def _save_settings(self, dashboard) -> None:
        w = dashboard._settings_widgets

        # Validate numeric fields before touching the config
        speakers_raw = w["speakers"].get().strip()
        stability_raw = w["stability"].get().strip()
        try:
            speakers = int(speakers_raw) if speakers_raw else None
            if speakers is not None and speakers < 1:
                raise ValueError
        except ValueError:
            dashboard._settings_status.configure(text="Speakers must be a positive number (or blank)", fg="#e06c5c")
            return
        try:
            stability = int(stability_raw)
            if stability < 1:
                raise ValueError
        except ValueError:
            dashboard._settings_status.configure(text="Stability seconds must be a positive number", fg="#e06c5c")
            return

        extensions = []
        for tok in w["extensions"].get().split(","):
            tok = tok.strip().lower()
            if not tok:
                continue
            extensions.append(tok if tok.startswith(".") else "." + tok)

        config = load_config()
        config.setdefault("defaults", {})
        config.setdefault("watcher", {})

        config["defaults"]["model"] = w["model"].get()
        language = w["language"].get().strip() or "en"
        config["defaults"]["language"] = language
        if speakers is None:
            config["defaults"].pop("speakers", None)
        else:
            config["defaults"]["speakers"] = speakers
        config["defaults"]["identify"] = bool(w["identify"].get())

        config["watcher"]["enable_notifications"] = bool(w["notifications"].get())
        config["watcher"]["stability_seconds"] = stability
        if extensions:
            config["watcher"]["extensions"] = extensions

        summarize = w["summarize_command"].get().strip()
        if summarize:
            config.setdefault("integrations", {})["summarize_command"] = summarize
        elif "integrations" in config:
            config["integrations"].pop("summarize_command", None)

        save_config(config)
        dashboard._settings_status.configure(
            text="Saved \u2713  \u2014 file-type and stability changes apply after restart",
            fg=FG_MUTED)

    # -- Helpers --
