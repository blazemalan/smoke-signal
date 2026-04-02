"""Smoke Signal app icon generator.

Pixel art campfire with big puffs of smoke rising.
"""

from pathlib import Path

from PIL import Image


# Palette
TRANSPARENT = (0, 0, 0, 0)
WOOD_DARK = (80, 45, 20, 255)
WOOD_MID = (120, 65, 30, 255)
WOOD_LIGHT = (155, 90, 45, 255)
EMBER = (200, 60, 20, 255)
FIRE_OUTER = (212, 69, 26, 255)      # brand orange #d4451a
FIRE_MID = (255, 140, 50, 255)
FIRE_INNER = (255, 210, 80, 255)
FIRE_CORE = (255, 245, 200, 255)
SMOKE_1 = (180, 180, 185, 200)
SMOKE_2 = (155, 155, 162, 170)
SMOKE_3 = (130, 130, 138, 140)
SMOKE_4 = (110, 110, 118, 100)
ASH = (90, 85, 80, 255)


def create_app_icon(size: int = 256) -> Image.Image:
    """Generate a pixel art campfire icon, then scale to requested size."""
    # Design on a 32x32 pixel grid
    grid = 32
    img = Image.new("RGBA", (grid, grid), TRANSPARENT)

    # Draw pixel by pixel
    def px(x, y, color):
        if 0 <= x < grid and 0 <= y < grid:
            img.putpixel((x, y), color)

    def hline(x1, x2, y, color):
        for x in range(x1, x2 + 1):
            px(x, y, color)

    # === SMOKE PUFFS (top) ===

    # Top puff (smallest, faintest)
    for x, y in [(14, 1), (15, 1), (16, 1), (17, 1),
                 (13, 2), (14, 2), (15, 2), (16, 2), (17, 2), (18, 2),
                 (14, 3), (15, 3), (16, 3), (17, 3)]:
        px(x, y, SMOKE_4)

    # Upper-mid puff
    for x, y in [(13, 4), (14, 4), (15, 4), (16, 4),
                 (12, 5), (13, 5), (14, 5), (15, 5), (16, 5), (17, 5),
                 (11, 6), (12, 6), (13, 6), (14, 6), (15, 6), (16, 6), (17, 6), (18, 6),
                 (12, 7), (13, 7), (14, 7), (15, 7), (16, 7), (17, 7),
                 (13, 8), (14, 8), (15, 8), (16, 8)]:
        px(x, y, SMOKE_3)

    # Mid puff (bigger)
    for x, y in [(14, 9), (15, 9), (16, 9), (17, 9), (18, 9),
                 (13, 10), (14, 10), (15, 10), (16, 10), (17, 10), (18, 10), (19, 10),
                 (12, 11), (13, 11), (14, 11), (15, 11), (16, 11), (17, 11), (18, 11), (19, 11), (20, 11),
                 (12, 12), (13, 12), (14, 12), (15, 12), (16, 12), (17, 12), (18, 12), (19, 12),
                 (13, 13), (14, 13), (15, 13), (16, 13), (17, 13), (18, 13)]:
        px(x, y, SMOKE_2)

    # Lower puff (largest, closest to fire, brightest)
    for x, y in [(14, 14), (15, 14), (16, 14), (17, 14),
                 (12, 15), (13, 15), (14, 15), (15, 15), (16, 15), (17, 15), (18, 15), (19, 15),
                 (11, 16), (12, 16), (13, 16), (14, 16), (15, 16), (16, 16), (17, 16), (18, 16), (19, 16), (20, 16),
                 (11, 17), (12, 17), (13, 17), (14, 17), (15, 17), (16, 17), (17, 17), (18, 17), (19, 17), (20, 17),
                 (12, 18), (13, 18), (14, 18), (15, 18), (16, 18), (17, 18), (18, 18), (19, 18),
                 (13, 19), (14, 19), (15, 19), (16, 19), (17, 19), (18, 19)]:
        px(x, y, SMOKE_1)

    # === FIRE ===

    # Flame tip
    px(15, 17, FIRE_OUTER)
    px(16, 17, FIRE_OUTER)

    # Flame upper
    hline(14, 17, 18, FIRE_OUTER)
    hline(14, 17, 19, FIRE_MID)
    px(15, 19, FIRE_INNER)
    px(16, 19, FIRE_INNER)

    # Flame body
    hline(13, 18, 20, FIRE_OUTER)
    hline(14, 17, 20, FIRE_MID)
    px(15, 20, FIRE_INNER)
    px(16, 20, FIRE_INNER)

    hline(12, 19, 21, FIRE_OUTER)
    hline(13, 18, 21, FIRE_MID)
    hline(14, 17, 21, FIRE_INNER)
    px(15, 21, FIRE_CORE)
    px(16, 21, FIRE_CORE)

    # Flame base (wider)
    hline(11, 20, 22, FIRE_OUTER)
    hline(12, 19, 22, FIRE_MID)
    hline(14, 17, 22, FIRE_INNER)

    hline(11, 20, 23, EMBER)
    hline(12, 19, 23, FIRE_OUTER)
    hline(14, 17, 23, FIRE_MID)

    # === EMBERS / ASH LINE ===
    hline(10, 21, 24, ASH)
    for x in [11, 13, 16, 19]:
        px(x, 24, EMBER)

    # === WOOD LOGS ===

    # Left log (diagonal \)
    for i in range(8):
        x = 8 + i
        y = 25 + (i // 2)
        px(x, y, WOOD_DARK)
        px(x, y - 1, WOOD_MID) if y > 25 else None
        if i % 3 == 0:
            px(x, y, WOOD_LIGHT)

    # Right log (diagonal /)
    for i in range(8):
        x = 23 - i
        y = 25 + (i // 2)
        px(x, y, WOOD_DARK)
        px(x, y - 1, WOOD_MID) if y > 25 else None
        if i % 3 == 1:
            px(x, y, WOOD_LIGHT)

    # Cross log (horizontal)
    hline(10, 21, 26, WOOD_DARK)
    hline(11, 20, 27, WOOD_MID)
    for x in [12, 15, 18]:
        px(x, 26, WOOD_LIGHT)
    for x in [13, 17]:
        px(x, 27, WOOD_LIGHT)

    # Bottom detail logs
    hline(9, 22, 28, WOOD_DARK)
    for x in [10, 14, 19, 21]:
        px(x, 28, WOOD_MID)

    # Ground stones
    for x, y in [(8, 29), (9, 29), (22, 29), (23, 29),
                 (11, 29), (12, 29), (19, 29), (20, 29)]:
        px(x, y, ASH)

    # Scale up with nearest-neighbor to preserve pixel art crispness
    img = img.resize((size, size), Image.NEAREST)
    return img


def create_tray_icon(size: int = 64) -> Image.Image:
    """Create icon for system tray."""
    return create_app_icon(size)


def save_ico(output_path: Path, sizes: list[int] | None = None) -> None:
    """Save a multi-size .ico file for Windows."""
    if sizes is None:
        sizes = [16, 24, 32, 48, 64, 128, 256]

    images = [create_app_icon(s) for s in sizes]
    images[0].save(
        str(output_path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


def save_icns(output_path: Path) -> None:
    """Save an .icns file for macOS."""
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    images = [create_app_icon(s) for s in sizes]
    images[-1].save(
        str(output_path),
        format="ICNS",
        append_images=images[:-1],
    )


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
