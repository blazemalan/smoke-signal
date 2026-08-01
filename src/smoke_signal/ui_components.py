import math
import random
import tkinter as tk

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
