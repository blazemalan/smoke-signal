"""First-run setup wizard for Smoke Signal.

A simple tkinter wizard that guides new users through:
1. Welcome + system check
2. HuggingFace token setup
3. Watch folder selection
4. Completion
"""

import os
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path


# Colors
BG = "#1a1a2e"
FG = "#e0e0e0"
ACCENT = "#ff7800"
ACCENT_HOVER = "#ff9933"
SUCCESS = "#4ecca3"
ERROR = "#e74c3c"
CARD_BG = "#16213e"
ENTRY_BG = "#0f3460"


class SetupWizard:
    """Multi-step setup wizard using tkinter."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Smoke Signal — Setup")
        self.root.geometry("600x480")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Results
        self.hf_token = ""
        self.watch_dir = ""
        self.completed = False

        # Current step
        self._step = 0
        self._steps = [
            self._build_welcome,
            self._build_token_step,
            self._build_watch_step,
            self._build_done_step,
        ]

        # Container
        self._container = tk.Frame(self.root, bg=BG)
        self._container.pack(fill="both", expand=True, padx=30, pady=20)

        self._show_step()

    def run(self) -> bool:
        """Run the wizard. Returns True if setup was completed."""
        self.root.mainloop()
        return self.completed

    def _clear(self):
        for widget in self._container.winfo_children():
            widget.destroy()

    def _show_step(self):
        self._clear()
        self._steps[self._step]()

    def _next(self):
        self._step += 1
        if self._step < len(self._steps):
            self._show_step()

    def _make_title(self, text):
        tk.Label(
            self._container, text=text,
            font=("Segoe UI", 18, "bold"), fg=ACCENT, bg=BG,
        ).pack(anchor="w", pady=(0, 10))

    def _make_text(self, text):
        tk.Label(
            self._container, text=text,
            font=("Segoe UI", 10), fg=FG, bg=BG,
            wraplength=540, justify="left",
        ).pack(anchor="w", pady=(0, 8))

    def _make_button(self, parent, text, command, primary=False):
        btn = tk.Button(
            parent, text=text, command=command,
            font=("Segoe UI", 10, "bold" if primary else "normal"),
            bg=ACCENT if primary else CARD_BG,
            fg="white",
            activebackground=ACCENT_HOVER if primary else ENTRY_BG,
            activeforeground="white",
            relief="flat", padx=20, pady=8,
            cursor="hand2",
        )
        return btn

    # --- Step 1: Welcome ---

    def _build_welcome(self):
        self._make_title("Welcome to Smoke Signal")
        self._make_text(
            "Smoke Signal auto-transcribes your voice recordings using AI "
            "running on your computer. No cloud services, everything stays local."
        )

        # System check
        card = tk.Frame(self._container, bg=CARD_BG, padx=15, pady=12)
        card.pack(fill="x", pady=(10, 0))

        tk.Label(
            card, text="System Check",
            font=("Segoe UI", 11, "bold"), fg=FG, bg=CARD_BG,
        ).pack(anchor="w", pady=(0, 8))

        checks = self._run_system_check()
        for label, status, detail in checks:
            row = tk.Frame(card, bg=CARD_BG)
            row.pack(fill="x", pady=1)
            icon = "\u2713" if status else "\u2717"
            color = SUCCESS if status else ERROR
            tk.Label(
                row, text=icon, font=("Segoe UI", 10), fg=color, bg=CARD_BG,
                width=2,
            ).pack(side="left")
            tk.Label(
                row, text=f"{label}: {detail}",
                font=("Segoe UI", 10), fg=FG, bg=CARD_BG,
            ).pack(side="left")

        # Next button
        btn_frame = tk.Frame(self._container, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))
        self._make_button(btn_frame, "Next  \u2192", self._next, primary=True).pack(side="right")

    def _run_system_check(self):
        checks = []

        # Python
        import sys
        checks.append(("Python", True, f"{sys.version.split()[0]}"))

        # GPU
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram = getattr(props, 'total_memory', getattr(props, 'total_mem', 0)) // (1024 * 1024)
                checks.append(("GPU", True, f"{name} ({vram} MB VRAM)"))
            else:
                checks.append(("GPU", False, "No NVIDIA GPU — will use CPU (slow)"))
        except ImportError:
            checks.append(("GPU", False, "PyTorch not installed"))

        # ffmpeg
        import subprocess
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            if r.returncode == 0:
                checks.append(("ffmpeg", True, "Installed"))
            else:
                checks.append(("ffmpeg", False, "Not working"))
        except FileNotFoundError:
            checks.append(("ffmpeg", False, "Not found — required for audio processing"))

        return checks

    # --- Step 2: HuggingFace Token ---

    def _build_token_step(self):
        self._make_title("HuggingFace Account")
        self._make_text(
            "Speaker identification requires models from HuggingFace. "
            "You need a free account and access token."
        )

        # Instructions card
        card = tk.Frame(self._container, bg=CARD_BG, padx=15, pady=12)
        card.pack(fill="x", pady=(5, 0))

        steps = [
            ("1.", "Create a free account", "https://huggingface.co/join"),
            ("2.", "Accept speaker model terms", "https://huggingface.co/pyannote/speaker-diarization-3.1"),
            ("3.", "Accept segmentation model terms", "https://huggingface.co/pyannote/segmentation-3.0"),
            ("4.", "Create an access token", "https://huggingface.co/settings/tokens"),
        ]

        for num, label, url in steps:
            row = tk.Frame(card, bg=CARD_BG)
            row.pack(fill="x", pady=2)
            tk.Label(
                row, text=num, font=("Segoe UI", 10, "bold"),
                fg=ACCENT, bg=CARD_BG, width=3,
            ).pack(side="left")
            link = tk.Label(
                row, text=label, font=("Segoe UI", 10, "underline"),
                fg="#6eb5ff", bg=CARD_BG, cursor="hand2",
            )
            link.pack(side="left")
            link.bind("<Button-1>", lambda e, u=url: self._open_url(u))

        # Token input
        tk.Label(
            self._container, text="Paste your token here:",
            font=("Segoe UI", 10), fg=FG, bg=BG,
        ).pack(anchor="w", pady=(15, 4))

        token_frame = tk.Frame(self._container, bg=BG)
        token_frame.pack(fill="x")

        self._token_var = tk.StringVar()
        entry = tk.Entry(
            token_frame, textvariable=self._token_var,
            font=("Consolas", 11), bg=ENTRY_BG, fg=FG,
            insertbackground=FG, relief="flat",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6)

        # Status label
        self._token_status = tk.Label(
            self._container, text="",
            font=("Segoe UI", 10), fg=FG, bg=BG,
        )
        self._token_status.pack(anchor="w", pady=(6, 0))

        # Buttons
        btn_frame = tk.Frame(self._container, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))

        verify_btn = self._make_button(btn_frame, "Verify Token", self._verify_token)
        verify_btn.pack(side="left")

        self._token_next_btn = self._make_button(btn_frame, "Next  \u2192", self._save_token_and_next, primary=True)
        self._token_next_btn.pack(side="right")
        self._token_next_btn.configure(state="disabled")

        skip_btn = self._make_button(btn_frame, "Skip", self._next)
        skip_btn.pack(side="right", padx=(0, 10))

    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def _verify_token(self):
        token = self._token_var.get().strip()
        if not token:
            self._token_status.configure(text="\u2717 Please paste a token", fg=ERROR)
            return

        self._token_status.configure(text="Verifying...", fg=FG)
        self.root.update()

        try:
            from huggingface_hub import HfApi
            api = HfApi()
            info = api.whoami(token=token)
            username = info.get("name", "Unknown")
            self._token_status.configure(
                text=f"\u2713 Verified — logged in as {username}", fg=SUCCESS
            )
            self.hf_token = token
            self._token_next_btn.configure(state="normal")
        except Exception as e:
            self._token_status.configure(
                text=f"\u2717 Invalid token: {e}", fg=ERROR
            )

    def _save_token_and_next(self):
        self._next()

    # --- Step 3: Watch Folder ---

    def _build_watch_step(self):
        self._make_title("Recording Folder")
        self._make_text(
            "Where do your voice recordings appear? This is usually a folder "
            "that syncs from your phone (iCloud Drive, OneDrive, Google Drive, etc.)."
        )
        self._make_text(
            "Smoke Signal will watch this folder and auto-transcribe new recordings."
        )

        # Folder picker
        picker_frame = tk.Frame(self._container, bg=BG)
        picker_frame.pack(fill="x", pady=(15, 0))

        self._watch_var = tk.StringVar()
        entry = tk.Entry(
            picker_frame, textvariable=self._watch_var,
            font=("Segoe UI", 10), bg=ENTRY_BG, fg=FG,
            insertbackground=FG, relief="flat",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6)

        browse_btn = self._make_button(picker_frame, "Browse...", self._browse_folder)
        browse_btn.pack(side="right", padx=(10, 0))

        # Buttons
        btn_frame = tk.Frame(self._container, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))

        self._make_button(btn_frame, "Skip", self._next).pack(side="left")
        self._make_button(btn_frame, "Next  \u2192", self._save_watch_and_next, primary=True).pack(side="right")

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select recording folder")
        if folder:
            self._watch_var.set(folder)

    def _save_watch_and_next(self):
        self.watch_dir = self._watch_var.get().strip()
        self._next()

    # --- Step 4: Done ---

    def _build_done_step(self):
        self._make_title("Setup Complete!")

        # Save everything
        self._save_all()

        if self.hf_token:
            self._make_text("\u2713  HuggingFace token saved")
        else:
            self._make_text(
                "\u2717  No HuggingFace token set — speaker identification won't work "
                "until you add one. You can re-run setup from the tray menu."
            )

        if self.watch_dir:
            self._make_text(f"\u2713  Watching: {self.watch_dir}")
        else:
            self._make_text(
                "\u2717  No watch folder set — auto-transcription is disabled. "
                "You can still transcribe files manually."
            )

        self._make_text("")
        self._make_text(
            "The first transcription will download AI models (~1.75 GB). "
            "This is a one-time download."
        )

        # Finish button
        btn_frame = tk.Frame(self._container, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(20, 0))

        self._make_button(
            btn_frame, "Launch Smoke Signal  \u2192", self._finish, primary=True
        ).pack(side="right")

    def _save_all(self):
        """Write HF token to .env and watch_dir to config.yaml."""
        from smoke_signal.config import (
            DATA_DIR,
            DEFAULT_CONFIG_PATH,
            DEFAULT_ENV_PATH,
            load_config,
            save_config,
        )

        # Save HF token
        if self.hf_token:
            env_path = DEFAULT_ENV_PATH
            env_path.write_text(f"HF_TOKEN={self.hf_token}\n", encoding="utf-8")

        # Save watch_dir
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
