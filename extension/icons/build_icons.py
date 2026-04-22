"""Generate CtxAnt icons at 16/32/48/128 px.

Run with:   .venv/bin/python extension/icons/build_icons.py

The icon is a purple-to-violet rounded square with a white magic wand
(diagonal stroke + four-point sparkle at the tip). Designed to read at
16px without looking muddy.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw


OUT = Path(__file__).parent
SIZES = [16, 32, 48, 128, 256, 512]  # 256/512 for the store listing


def _bg(size: int) -> Image.Image:
    """Purple→violet diagonal gradient with rounded corners."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # Two-colour diagonal gradient
    top = (138, 92, 246)      # violet-500
    bot = (91, 33, 182)       # violet-800
    grad = Image.new("RGBA", (size, size))
    for y in range(size):
        for x in range(size):
            # diagonal parameter t in [0, 1]
            t = (x + y) / (2 * (size - 1)) if size > 1 else 0
            r = int(top[0] * (1 - t) + bot[0] * t)
            g = int(top[1] * (1 - t) + bot[1] * t)
            b = int(top[2] * (1 - t) + bot[2] * t)
            grad.putpixel((x, y), (r, g, b, 255))
    # Rounded mask
    mask = Image.new("L", (size, size), 0)
    radius = max(2, size // 5)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    img.paste(grad, (0, 0), mask)
    return img


def _draw_sparkle(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float) -> None:
    """Four-point sparkle (two crossing ellipses) centred at (cx, cy)."""
    # Horizontal lobe
    draw.ellipse((cx - r, cy - r * 0.25, cx + r, cy + r * 0.25), fill="white")
    # Vertical lobe
    draw.ellipse((cx - r * 0.25, cy - r, cx + r * 0.25, cy + r), fill="white")


def _wand(img: Image.Image) -> None:
    """Draw a diagonal white wand with a sparkle at the tip."""
    size = img.size[0]
    draw = ImageDraw.Draw(img)

    # Wand geometry: from ~bottom-left (22%,78%) to ~top-right tip (75%,25%)
    x0, y0 = size * 0.22, size * 0.78
    x1, y1 = size * 0.75, size * 0.25
    stroke = max(1, round(size * 0.08))

    # Draw the stick as a thick line with rounded ends
    draw.line((x0, y0, x1, y1), fill="white", width=stroke)
    # Round caps
    cap_r = stroke / 2
    draw.ellipse((x0 - cap_r, y0 - cap_r, x0 + cap_r, y0 + cap_r), fill="white")
    draw.ellipse((x1 - cap_r, y1 - cap_r, x1 + cap_r, y1 + cap_r), fill="white")

    # Main sparkle at the wand tip
    _draw_sparkle(draw, x1, y1, r=size * 0.18)

    # Two smaller sparkles — only on bigger icons (noise at 16px)
    if size >= 48:
        _draw_sparkle(draw, size * 0.82, size * 0.55, r=size * 0.06)
        _draw_sparkle(draw, size * 0.55, size * 0.20, r=size * 0.05)


def build_one(size: int) -> None:
    img = _bg(size)
    _wand(img)
    out = OUT / f"icon-{size}.png"
    img.save(out, "PNG")
    print(f"wrote {out.relative_to(OUT.parent.parent)}")


def main() -> None:
    for s in SIZES:
        build_one(s)


if __name__ == "__main__":
    main()
