"""Smoke Signal app icon generator.

Modern app icon: dark rounded square with a smooth gradient flame
and soft smoke. Designed to match the quality of icons like Obsidian, CapCut.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def create_app_icon(size: int = 256) -> Image.Image:
    """Generate a modern app icon with smooth flame on dark background."""
    # Render at 4x for quality anti-aliasing
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # === Rounded square background ===
    corner = int(s * 0.22)  # iOS-style roundrect
    _rounded_rect(draw, 0, 0, s - 1, s - 1, corner, fill=(22, 22, 22, 255))

    # Subtle inner gradient (slightly lighter at top)
    for y in range(s):
        t = y / s
        overlay_alpha = int(12 * (1 - t))
        if overlay_alpha > 0:
            draw.line([(0, y), (s, y)], fill=(255, 255, 255, overlay_alpha))

    cx = s // 2

    # === Soft background glow (orange, behind everything) ===
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_cx = cx
    glow_cy = int(s * 0.55)
    glow_r = int(s * 0.30)
    for i in range(glow_r, 0, -1):
        t = i / glow_r
        a = int(40 * (1 - t) * (1 - t))
        glow_draw.ellipse(
            [glow_cx - i, glow_cy - int(i * 0.7), glow_cx + i, glow_cy + int(i * 0.7)],
            fill=(212, 69, 26, a),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=int(s * 0.04)))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # === Smoke ===
    smoke = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    smoke_draw = ImageDraw.Draw(smoke)

    smoke_base_y = int(s * 0.38)
    puffs = [
        (cx + int(s * 0.01), int(s * 0.10), int(s * 0.08), 35),
        (cx - int(s * 0.02), int(s * 0.17), int(s * 0.10), 45),
        (cx + int(s * 0.01), int(s * 0.26), int(s * 0.12), 55),
        (cx - int(s * 0.01), int(s * 0.34), int(s * 0.13), 60),
    ]
    for px, py, pr, alpha in puffs:
        smoke_draw.ellipse(
            [px - pr, py - pr, px + pr, py + pr],
            fill=(200, 200, 205, alpha),
        )

    smoke = smoke.filter(ImageFilter.GaussianBlur(radius=int(s * 0.035)))
    img = Image.alpha_composite(img, smoke)
    draw = ImageDraw.Draw(img)

    # === Flame ===
    flame = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    flame_draw = ImageDraw.Draw(flame)

    flame_bottom = int(s * 0.78)
    flame_top = int(s * 0.30)
    flame_w = int(s * 0.20)

    # Outer flame — brand orange
    _draw_smooth_flame(flame_draw, cx, flame_bottom, flame_top, flame_w,
                       (212, 69, 26, 255))

    # Mid flame
    _draw_smooth_flame(flame_draw, cx, flame_bottom - int(s * 0.02),
                       flame_top + int(s * 0.08), int(flame_w * 0.68),
                       (255, 140, 50, 255))

    # Inner flame
    _draw_smooth_flame(flame_draw, cx, flame_bottom - int(s * 0.04),
                       flame_top + int(s * 0.16), int(flame_w * 0.40),
                       (255, 210, 80, 255))

    # Core
    _draw_smooth_flame(flame_draw, cx, flame_bottom - int(s * 0.06),
                       flame_top + int(s * 0.24), int(flame_w * 0.18),
                       (255, 245, 215, 230))

    # Slight flame glow
    flame_glow = flame.copy().filter(ImageFilter.GaussianBlur(radius=int(s * 0.015)))
    img = Image.alpha_composite(img, flame_glow)
    img = Image.alpha_composite(img, flame)

    # === Wood logs ===
    draw = ImageDraw.Draw(img)
    log_y = int(s * 0.78)
    log_h = int(s * 0.035)

    # Left log
    _draw_log(draw, cx - int(s * 0.22), log_y + int(s * 0.02),
              cx + int(s * 0.05), log_y + log_h + int(s * 0.04),
              angle=-12, s=s)
    # Right log
    _draw_log(draw, cx - int(s * 0.05), log_y + int(s * 0.02),
              cx + int(s * 0.22), log_y + log_h + int(s * 0.04),
              angle=12, s=s)

    # Downsample with high-quality resampling
    img = img.resize((size, size), Image.LANCZOS)
    return img


def _rounded_rect(draw, x1, y1, x2, y2, r, fill):
    """Draw a rounded rectangle."""
    draw.rectangle([x1 + r, y1, x2 - r, y2], fill=fill)
    draw.rectangle([x1, y1 + r, x2, y2 - r], fill=fill)
    draw.pieslice([x1, y1, x1 + 2 * r, y1 + 2 * r], 180, 270, fill=fill)
    draw.pieslice([x2 - 2 * r, y1, x2, y1 + 2 * r], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - 2 * r, x1 + 2 * r, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - 2 * r, y2 - 2 * r, x2, y2], 0, 90, fill=fill)


def _draw_smooth_flame(draw, cx, bottom_y, top_y, half_width, color):
    """Draw a smooth flame shape with organic curves."""
    points = []
    steps = 60

    for i in range(steps + 1):
        t = i / steps
        y = bottom_y + (top_y - bottom_y) * t

        # Organic width profile
        base = 1 - t
        belly = 0.12 * math.sin(t * math.pi * 0.85)
        taper = 1 - t ** 0.65

        w = half_width * taper * (base + belly)
        w = max(w, 0)

        wobble = math.sin(t * math.pi * 2.2) * half_width * 0.025
        points.append((cx - w + wobble, y))

    for i in range(steps, -1, -1):
        t = i / steps
        y = bottom_y + (top_y - bottom_y) * t

        base = 1 - t
        belly = 0.12 * math.sin(t * math.pi * 0.85)
        taper = 1 - t ** 0.65

        w = half_width * taper * (base + belly)
        w = max(w, 0)

        wobble = math.sin(t * math.pi * 2.2) * half_width * 0.025
        points.append((cx + w - wobble, y))

    if len(points) >= 3:
        draw.polygon(points, fill=color)


def _draw_log(draw, x1, y1, x2, y2, angle, s):
    """Draw a simple wood log."""
    draw.rounded_rectangle(
        [x1, y1, x2, y2],
        radius=int(s * 0.01),
        fill=(90, 55, 30, 255),
    )
    # Highlight
    draw.rounded_rectangle(
        [x1 + 2, y1, x2 - 2, y1 + int(s * 0.008)],
        radius=int(s * 0.005),
        fill=(130, 80, 45, 255),
    )


def create_tray_icon(size: int = 64) -> Image.Image:
    """Create icon for system tray."""
    return create_app_icon(size)


def save_ico(output_path: Path, sizes: list[int] | None = None) -> None:
    """Save a multi-size .ico file for Windows."""
    if sizes is None:
        sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [create_app_icon(s) for s in sizes]
    # Save from the largest image, append the rest
    images[-1].save(
        str(output_path), format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )


def save_icns(output_path: Path) -> None:
    """Save an .icns file for macOS."""
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    images = [create_app_icon(s) for s in sizes]
    images[-1].save(str(output_path), format="ICNS", append_images=images[:-1])


if __name__ == "__main__":
    assets = Path(__file__).resolve().parent.parent.parent / "assets"
    assets.mkdir(exist_ok=True)

    icon = create_app_icon(512)
    icon.save(str(assets / "smoke-signal.png"))
    print(f"Saved: {assets / 'smoke-signal.png'}")

    save_ico(assets / "smoke-signal.ico")
    print(f"Saved: {assets / 'smoke-signal.ico'}")

    tray = create_tray_icon(64)
    tray.save(str(assets / "tray-icon.png"))
    print(f"Saved: {assets / 'tray-icon.png'}")
