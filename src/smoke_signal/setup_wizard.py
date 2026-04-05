"""First-run setup wizard for Smoke Signal.

A polished tkinter wizard that guides new users through:
1. Welcome + system check
2. HuggingFace token setup
3. Watch folder selection
4. Completion

Design language matches cinder.works — dark, minimal, ember aesthetic.
"""

import math
import os
import random
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path


# === Cinder Design System ===

# Colors
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
ACCENT_DARK = "#a83415"
LINK = "#6eb5ff"
SUCCESS = "#4ecca3"
ERROR = "#e74c3c"
BORDER = "#383838"
BORDER_ACCENT = "#3a2018"

# Typography
FONT = "Inter"
FONT_FALLBACK = ("Inter", "Segoe UI", "SF Pro Display", "-apple-system", "sans-serif")
FONT_MONO = ("JetBrains Mono", "Consolas", "Courier New", "monospace")

# Dimensions
RADIUS = 12
WINDOW_W = 640
WINDOW_H = 540
PAD_X = 40
PAD_Y = 30


class EmberCanvas:
    """Floating ember particles on a canvas background."""

    def __init__(self, parent, width, height):
        self.canvas = tk.Canvas(
            parent, width=width, height=height,
            bg=BG_DEEP, highlightthickness=0, bd=0,
        )
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.width = width
        self.height = height
        self.embers = []
        self._init_embers(20)
        self._animate()

    def _init_embers(self, count):
        for _ in range(count):
            self.embers.append({
                "x": random.uniform(0, self.width),
                "y": random.uniform(0, self.height),
                "size": random.uniform(1.5, 4),
                "speed": random.uniform(0.3, 1.2),
                "drift": random.uniform(-0.3, 0.3),
                "opacity": random.uniform(0.15, 0.6),
                "phase": random.uniform(0, math.pi * 2),
            })

    def _animate(self):
        self.canvas.delete("ember")
        for e in self.embers:
            e["y"] -= e["speed"]
            e["x"] += e["drift"] + math.sin(e["phase"]) * 0.3
            e["phase"] += 0.02

            # Flicker
            alpha = e["opacity"] * (0.7 + 0.3 * math.sin(e["phase"] * 3))

            # Reset if off screen
            if e["y"] < -10:
                e["y"] = self.height + 10
                e["x"] = random.uniform(0, self.width)

            # Map alpha to color intensity
            r = int(212 * alpha + 10 * (1 - alpha))
            g = int(69 * alpha + 10 * (1 - alpha))
            b = int(26 * alpha + 10 * (1 - alpha))
            color = f"#{r:02x}{g:02x}{b:02x}"

            s = e["size"]
            self.canvas.create_oval(
                e["x"] - s, e["y"] - s,
                e["x"] + s, e["y"] + s,
                fill=color, outline="", tags="ember",
            )

        self.canvas.after(50, self._animate)


class StepIndicator:
    """Minimal step progress dots."""

    def __init__(self, parent, total_steps):
        self.frame = tk.Frame(parent, bg=BG_DEEP)
        self.total = total_steps
        self.dots = []
        for i in range(total_steps):
            dot = tk.Canvas(
                self.frame, width=8, height=8,
                bg=BG_DEEP, highlightthickness=0,
            )
            dot.pack(side="left", padx=4)
            self.dots.append(dot)

    def set_step(self, step):
        for i, dot in enumerate(self.dots):
            dot.delete("all")
            if i == step:
                dot.create_oval(0, 0, 8, 8, fill=ACCENT, outline="")
            elif i < step:
                dot.create_oval(1, 1, 7, 7, fill=FG_DIM, outline="")
            else:
                dot.create_oval(2, 2, 6, 6, fill=FG_MUTED, outline="")


class SetupWizard:
    """Multi-step setup wizard with cinder.works aesthetic."""

    def __init__(self):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

        self.root = tk.Tk()
        self.root.title("Smoke Signal")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DEEP)

        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value),
            )
        except Exception:
            pass

        # Center on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - WINDOW_W) // 2
        y = (self.root.winfo_screenheight() - WINDOW_H) // 2
        self.root.geometry(f"+{x}+{y}")

        # Set window icon
        self._set_icon()

        # Results
        self.hf_token = ""
        self.watch_dir = ""
        self.completed = False

        # Steps
        self._step = 0
        self._steps = [
            self._build_welcome,
            self._build_token_step,
            self._build_watch_step,
            self._build_done_step,
        ]

        # Ember background
        self._embers = EmberCanvas(self.root, WINDOW_W, WINDOW_H)

        # Main content frame (floats above embers)
        self._main = tk.Frame(self.root, bg=BG_DEEP)
        self._main.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Step indicator
        self._step_indicator = StepIndicator(self._main, len(self._steps))
        self._step_indicator.frame.pack(pady=(PAD_Y, 0))

        # Content container
        self._container = tk.Frame(self._main, bg=BG_DEEP)
        self._container.pack(fill="both", expand=True, padx=PAD_X, pady=(15, PAD_Y))

        self._show_step()

    def _set_icon(self):
        """Set window icon from the app's icon generator."""
        try:
            from smoke_signal.icon import create_app_icon
            import io
            from PIL import ImageTk
            icon_img = create_app_icon(32)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    def run(self) -> bool:
        """Run the wizard. Returns True if setup was completed."""
        self.root.mainloop()
        return self.completed

    def _clear(self):
        for widget in self._container.winfo_children():
            widget.destroy()

    def _show_step(self):
        self._clear()
        self._step_indicator.set_step(self._step)
        self._steps[self._step]()

    def _next(self):
        self._step += 1
        if self._step < len(self._steps):
            self._show_step()

    # === UI Components ===

    def _make_title(self, text):
        tk.Label(
            self._container, text=text,
            font=(FONT, 22, "bold"), fg=FG, bg=BG_DEEP,
        ).pack(anchor="w", pady=(0, 4))

    def _make_subtitle(self, text):
        tk.Label(
            self._container, text=text,
            font=(FONT, 10), fg=FG_DIM, bg=BG_DEEP,
            wraplength=WINDOW_W - PAD_X * 2, justify="left",
        ).pack(anchor="w", pady=(0, 16))

    def _make_card(self, parent=None):
        parent = parent or self._container
        card = tk.Frame(
            parent, bg=BG_CARD,
            highlightbackground=BORDER, highlightthickness=1,
            padx=20, pady=16,
        )
        return card

    def _make_button(self, parent, text, command, primary=False, icon=None):
        display = f"{icon}  {text}" if icon else text
        bg = ACCENT if primary else BG_CARD
        hover_bg = ACCENT_GLOW if primary else BG_CARD_HOVER
        border = ACCENT_DARK if primary else BORDER

        btn = tk.Button(
            parent, text=display, command=command,
            font=(FONT, 10, "bold" if primary else "normal"),
            bg=bg, fg="white" if primary else FG,
            activebackground=hover_bg,
            activeforeground="white",
            relief="flat", padx=24, pady=10,
            cursor="hand2",
            highlightbackground=border, highlightthickness=1,
        )

        # Hover effects
        def on_enter(e):
            btn.configure(bg=hover_bg)

        def on_leave(e):
            btn.configure(bg=bg)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        return btn

    def _make_label(self, text, parent=None, bold=False, dim=False, size=10):
        parent = parent or self._container
        fg = FG_DIM if dim else FG
        weight = "bold" if bold else "normal"
        return tk.Label(
            parent, text=text,
            font=(FONT, size, weight), fg=fg, bg=parent.cget("bg"),
            wraplength=WINDOW_W - PAD_X * 2 - 40, justify="left",
        )

    # === Step 1: Welcome ===

    def _build_welcome(self):
        # Smoke Signal branding
        brand_frame = tk.Frame(self._container, bg=BG_DEEP)
        brand_frame.pack(anchor="w", pady=(10, 0))

        # Fire icon character
        tk.Label(
            brand_frame, text="\U0001f525",
            font=(FONT, 28), bg=BG_DEEP,
        ).pack(side="left", padx=(0, 12))

        title_block = tk.Frame(brand_frame, bg=BG_DEEP)
        title_block.pack(side="left")
        tk.Label(
            title_block, text="Smoke Signal",
            font=(FONT, 24, "bold"), fg=FG, bg=BG_DEEP,
        ).pack(anchor="w")
        tk.Label(
            title_block, text="Local-first audio transcription",
            font=(FONT, 10), fg=FG_DIM, bg=BG_DEEP,
        ).pack(anchor="w")

        # Spacer
        tk.Frame(self._container, bg=BG_DEEP, height=20).pack(fill="x")

        # System check card
        card = self._make_card()
        card.pack(fill="x", pady=(0, 10))

        tk.Label(
            card, text="SYSTEM CHECK",
            font=(FONT, 9, "bold"), fg=FG_MUTED, bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 12))

        checks = self._run_system_check()
        for label, status, detail in checks:
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", pady=3)

            # Status dot
            dot_canvas = tk.Canvas(
                row, width=10, height=10,
                bg=BG_CARD, highlightthickness=0,
            )
            dot_canvas.pack(side="left", padx=(0, 10), pady=2)
            color = SUCCESS if status else ERROR
            dot_canvas.create_oval(1, 1, 9, 9, fill=color, outline="")

            tk.Label(
                row, text=label,
                font=(FONT, 10, "bold"), fg=FG, bg=BG_CARD,
                width=8, anchor="w",
            ).pack(side="left")
            tk.Label(
                row, text=detail,
                font=(FONT, 10), fg=FG_DIM, bg=BG_CARD,
            ).pack(side="left", padx=(4, 0))

        # Navigation
        btn_frame = tk.Frame(self._container, bg=BG_DEEP)
        btn_frame.pack(side="bottom", fill="x")
        self._make_button(
            btn_frame, "Get Started", self._next, primary=True, icon="\u2192"
        ).pack(side="right")

    def _run_system_check(self):
        checks = []
        import sys
        checks.append(("Python", True, f"{sys.version.split()[0]}"))

        try:
            from smoke_signal.gpu import check_gpu
            gpu = check_gpu()
            if gpu["available"]:
                checks.append(("GPU", True, f"{gpu['name']} ({gpu['vram_total_mb']} MB)"))
            else:
                checks.append(("GPU", False, "No NVIDIA GPU \u2014 CPU mode (slow)"))
        except Exception:
            checks.append(("GPU", False, "Could not detect GPU"))

        import subprocess
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            checks.append(("ffmpeg", r.returncode == 0, "Installed" if r.returncode == 0 else "Not working"))
        except FileNotFoundError:
            checks.append(("ffmpeg", False, "Not found"))

        return checks

    # === Step 2: HuggingFace Token ===

    def _build_token_step(self):
        self._make_title("Connect HuggingFace")
        self._make_subtitle(
            "Speaker identification uses AI models hosted on HuggingFace. "
            "You need a free account and access token to download them."
        )

        # Steps card
        card = self._make_card()
        card.pack(fill="x", pady=(0, 16))

        steps = [
            ("\u2460", "Create a free account", "https://huggingface.co/join"),
            ("\u2461", "Accept speaker model terms", "https://huggingface.co/pyannote/speaker-diarization-3.1"),
            ("\u2462", "Accept segmentation terms", "https://huggingface.co/pyannote/segmentation-3.0"),
            ("\u2463", "Create an access token", "https://huggingface.co/settings/tokens"),
        ]

        for icon, label, url in steps:
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", pady=4)
            tk.Label(
                row, text=icon, font=(FONT, 12),
                fg=ACCENT, bg=BG_CARD,
            ).pack(side="left", padx=(0, 12))
            link = tk.Label(
                row, text=label, font=(FONT, 10),
                fg=LINK, bg=BG_CARD, cursor="hand2",
            )
            link.pack(side="left")
            link.bind("<Button-1>", lambda e, u=url: self._open_url(u))
            # Underline on hover
            link.bind("<Enter>", lambda e, l=link: l.configure(font=(FONT, 10, "underline")))
            link.bind("<Leave>", lambda e, l=link: l.configure(font=(FONT, 10)))

        # Token input
        input_label = self._make_label("Access Token", bold=True, size=9)
        input_label.configure(fg=FG_MUTED)
        input_label.pack(anchor="w", pady=(4, 6))

        input_frame = tk.Frame(
            self._container, bg=BG_INPUT,
            highlightbackground=BORDER, highlightthickness=1,
        )
        input_frame.pack(fill="x")

        self._token_var = tk.StringVar()
        entry = tk.Entry(
            input_frame, textvariable=self._token_var,
            font=(FONT_MONO[0], 11), bg=BG_INPUT, fg=FG,
            insertbackground=ACCENT, relief="flat", bd=8,
        )
        entry.pack(fill="x")

        # Focus highlight
        def on_focus_in(e):
            input_frame.configure(highlightbackground=ACCENT)

        def on_focus_out(e):
            input_frame.configure(highlightbackground=BORDER)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

        # Status
        self._token_status = tk.Label(
            self._container, text="",
            font=(FONT, 10), fg=FG_DIM, bg=BG_DEEP,
        )
        self._token_status.pack(anchor="w", pady=(8, 0))

        # Buttons
        btn_frame = tk.Frame(self._container, bg=BG_DEEP)
        btn_frame.pack(side="bottom", fill="x")

        self._make_button(btn_frame, "Verify", self._verify_token).pack(side="left")
        self._make_button(btn_frame, "Skip", self._next).pack(side="right", padx=(0, 10))

        self._token_next_btn = self._make_button(
            btn_frame, "Continue", self._save_token_and_next, primary=True, icon="\u2192"
        )
        self._token_next_btn.pack(side="right")
        self._token_next_btn.configure(state="disabled")

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def _verify_token(self):
        token = self._token_var.get().strip()
        if not token:
            self._token_status.configure(text="\u2717  Paste a token first", fg=ERROR)
            return

        self._token_status.configure(text="\u2022  Verifying...", fg=FG_DIM)
        self.root.update()

        try:
            from huggingface_hub import HfApi
            api = HfApi()
            info = api.whoami(token=token)
            username = info.get("name", "Unknown")
            self._token_status.configure(
                text=f"\u2713  Connected as {username}", fg=SUCCESS
            )
            self.hf_token = token
            self._token_next_btn.configure(state="normal")
        except Exception as e:
            err = str(e)[:60]
            self._token_status.configure(
                text=f"\u2717  {err}", fg=ERROR
            )

    def _save_token_and_next(self):
        self._next()

    # === Step 3: Watch Folder ===

    def _build_watch_step(self):
        self._make_title("Watch Folder")
        self._make_subtitle(
            "Choose the folder where your voice recordings appear. "
            "This is usually a folder that syncs from your phone "
            "(iCloud Drive, OneDrive, Google Drive)."
        )

        # Folder illustration
        card = self._make_card()
        card.pack(fill="x", pady=(0, 16))

        tk.Label(
            card, text="\U0001f4c1",
            font=(FONT, 24), bg=BG_CARD,
        ).pack(pady=(0, 8))

        self._watch_var = tk.StringVar()
        self._watch_display = tk.Label(
            card, text="No folder selected",
            font=(FONT, 10), fg=FG_MUTED, bg=BG_CARD,
        )
        self._watch_display.pack(pady=(0, 12))

        self._make_button(
            card, "Browse...", self._browse_folder, icon="\U0001f4c2"
        ).pack()

        # Manual path input
        input_label = self._make_label("Or paste a path:", bold=False, size=9)
        input_label.configure(fg=FG_MUTED)
        input_label.pack(anchor="w", pady=(16, 6))

        input_frame = tk.Frame(
            self._container, bg=BG_INPUT,
            highlightbackground=BORDER, highlightthickness=1,
        )
        input_frame.pack(fill="x")

        entry = tk.Entry(
            input_frame, textvariable=self._watch_var,
            font=(FONT, 10), bg=BG_INPUT, fg=FG,
            insertbackground=ACCENT, relief="flat", bd=8,
        )
        entry.pack(fill="x")

        # Update display when typing
        def on_change(*_):
            val = self._watch_var.get().strip()
            if val:
                self._watch_display.configure(text=val, fg=FG)
            else:
                self._watch_display.configure(text="No folder selected", fg=FG_MUTED)

        self._watch_var.trace_add("write", on_change)

        # Buttons
        btn_frame = tk.Frame(self._container, bg=BG_DEEP)
        btn_frame.pack(side="bottom", fill="x")

        self._make_button(btn_frame, "Skip", self._next).pack(side="left")
        self._make_button(
            btn_frame, "Continue", self._save_watch_and_next, primary=True, icon="\u2192"
        ).pack(side="right")

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select recording folder")
        if folder:
            self._watch_var.set(folder)

    def _save_watch_and_next(self):
        self.watch_dir = self._watch_var.get().strip()
        self._next()

    # === Step 4: Done ===

    def _build_done_step(self):
        # Save everything
        self._save_all()

        # Success header
        tk.Frame(self._container, bg=BG_DEEP, height=20).pack()

        tk.Label(
            self._container, text="\u2713",
            font=(FONT, 36), fg=SUCCESS, bg=BG_DEEP,
        ).pack(pady=(0, 8))

        tk.Label(
            self._container, text="You're all set",
            font=(FONT, 22, "bold"), fg=FG, bg=BG_DEEP,
        ).pack(pady=(0, 20))

        # Summary card
        card = self._make_card()
        card.pack(fill="x", pady=(0, 10))

        if self.hf_token:
            self._status_row(card, True, "HuggingFace connected")
        else:
            self._status_row(card, False, "No HuggingFace token \u2014 add one later in settings")

        if self.watch_dir:
            # Shorten long paths
            display = self.watch_dir
            if len(display) > 45:
                display = "..." + display[-42:]
            self._status_row(card, True, f"Watching: {display}")
        else:
            self._status_row(card, False, "No watch folder \u2014 manual transcription only")

        # Info
        tk.Label(
            self._container,
            text="First transcription will download AI models (~1.75 GB)",
            font=(FONT, 9), fg=FG_MUTED, bg=BG_DEEP,
        ).pack(pady=(16, 0))

        # Launch button
        btn_frame = tk.Frame(self._container, bg=BG_DEEP)
        btn_frame.pack(side="bottom", fill="x")

        self._make_button(
            btn_frame, "Launch Smoke Signal", self._finish, primary=True, icon="\U0001f525"
        ).pack(side="right")

    def _status_row(self, parent, ok, text):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=3)
        dot = tk.Canvas(row, width=10, height=10, bg=BG_CARD, highlightthickness=0)
        dot.pack(side="left", padx=(0, 10), pady=2)
        dot.create_oval(1, 1, 9, 9, fill=SUCCESS if ok else FG_MUTED, outline="")
        tk.Label(
            row, text=text,
            font=(FONT, 10), fg=FG if ok else FG_DIM, bg=BG_CARD,
        ).pack(side="left")

    def _save_all(self):
        """Write HF token to .env and watch_dir to config.yaml."""
        from smoke_signal.config import (
            DATA_DIR,
            DEFAULT_CONFIG_PATH,
            DEFAULT_ENV_PATH,
            load_config,
            save_config,
        )

        if self.hf_token:
            DEFAULT_ENV_PATH.write_text(f"HF_TOKEN={self.hf_token}\n", encoding="utf-8")

        if self.watch_dir:
            config = load_config()
            if "watcher" not in config:
                config["watcher"] = {}
            config["watcher"]["watch_dir"] = self.watch_dir
            save_config(config)

    def _finish(self):
        self.completed = True
        self.root.destroy()


def run_wizard() -> bool:
    """Run the setup wizard. Returns True if setup completed."""
    wizard = SetupWizard()
    return wizard.run()
