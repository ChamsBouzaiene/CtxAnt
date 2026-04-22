"""Turn the two source ant PNGs into the bundled assets CtxAnt actually uses.

Inputs (expected in ~/Downloads, dropped there from the brand kit):
    favicon.png   — blue gradient rounded square with white ant silhouette.
                    Used anywhere we want the full-colour brand mark.
    menu_mac.png  — solid black ant silhouette on a white field.
                    Used as the macOS menu-bar template image.

Outputs:
    backend/assets/appicon.png        — full-res blue square (kept for dashboard)
    backend/assets/menubar.png        — 88×88 template PNG, black on transparent
    web/assets/favicon.png            — 128×128 favicon for ctxant.com
    web/assets/app-icon.png           — 512×512 for landing hero / share previews
    extension/icons/icon-{N}.png      — replaced at 16/32/48/128/256/512 so the
                                        Chrome extension matches the website.

Why the template-image conversion matters: rumps passes `template=True` to
NSImage, which tells macOS "tint me to match the menu bar text colour." For
that to work the image has to be *black pixels on transparency*, not black
on white — otherwise the white background gets tinted too and you end up
with a chunky white blob in the status bar. This script does the threshold
+ alpha derivation.

Run with:  .venv/bin/python scripts/process_brand_assets.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path.home() / "Downloads"

SRC_BLUE = DOWNLOADS / "favicon.png"       # blue rounded-square ant
SRC_BLACK = DOWNLOADS / "menu_mac.png"     # black-on-white silhouette

# Tolerance used when flood-filling the near-white background of the colour
# source. ChatGPT-exported "transparent" PNGs aren't actually transparent —
# they're RGB with a near-white (254,254,254) field that looks like a
# checkerboard only because the viewer renders one on top. Corner-flood with
# a wide tolerance reliably strips that field; we can afford a generous
# threshold because the ant *inside* the blue square is fully enclosed by
# blue pixels (values like (9,171,254)), which are far from white and stop
# the flood cold — so bumping tolerance doesn't risk leaking into the ant.
# Threshold ~90 gets past the subtle drop-shadow halo ChatGPT bakes around
# the rounded-square corner where antialiased grey-ish pixels would otherwise
# stop a tighter flood.
_BG_FLOOD_THRESH = 90


# ── Menu-bar template: black on transparent ──────────────────────────────────

def build_menubar_template(src: Path, out: Path, size: int = 88) -> None:
    """Convert black-on-white to black-on-alpha.

    Strategy: luminance drives alpha. Pure white → 0 alpha, pure black →
    255 alpha, antialiased edge pixels get a proportional alpha so the
    curve stays smooth at the menu-bar render size.

    Output is square, sized for 2× retina (44pt × 2 = 88px).
    """
    im = Image.open(src).convert("L")  # luminance, 0 (black) – 255 (white)
    # Square-crop to the smaller dimension before resizing so the ant doesn't
    # get squashed if the source isn't perfectly square (it is today, but
    # brand assets have a way of drifting).
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side))
    im = im.resize((size, size), Image.LANCZOS)

    # Compose black image with alpha = 255 - luminance.
    black = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    alpha = im.point(lambda v: 255 - v)
    black.putalpha(alpha)
    # Also set RGB channels to black where alpha > 0 (Pillow defaults to 0s
    # already from the Image.new above, but be explicit).
    out.parent.mkdir(parents=True, exist_ok=True)
    black.save(out, "PNG")
    print(f"  menubar → {out.relative_to(ROOT)}  ({size}×{size})")


# ── Colour app icon at various sizes ─────────────────────────────────────────

def _strip_bg(im: Image.Image) -> Image.Image:
    """Flood-fill near-white corners with full transparency.

    The blue rounded-square body of the icon is opaque-blue so it can't be
    reached by a flood starting outside it; the white ant inside the square
    is fully enclosed by blue, so it can't either. Only the outer white
    field gets wiped. Done on the full-resolution source so the alpha edge
    benefits from Lanczos downscaling afterwards.
    """
    im = im.convert("RGBA")
    w, h = im.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        # floodfill edits in-place; value=(0,0,0,0) is a fully transparent
        # pixel. thresh is per-channel max-distance for "same colour".
        ImageDraw.floodfill(im, xy=corner, value=(0, 0, 0, 0),
                            thresh=_BG_FLOOD_THRESH)
    return im


def build_colour_icon(src: Path, out: Path, size: int,
                      strip_bg: bool = True) -> None:
    im = Image.open(src)
    if strip_bg:
        im = _strip_bg(im)
    else:
        im = im.convert("RGBA")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    im = im.crop((left, top, left + side, top + side))
    im = im.resize((size, size), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG", optimize=True)
    print(f"  colour → {out.relative_to(ROOT)}  ({size}×{size})")


# ── Entry ─────────────────────────────────────────────────────────────────────

def main() -> None:
    for p in (SRC_BLUE, SRC_BLACK):
        if not p.exists():
            raise SystemExit(f"Missing source: {p}")

    print("Writing assets:")

    # Menu bar (template — black on transparent)
    build_menubar_template(SRC_BLACK, ROOT / "backend" / "assets" / "menubar.png")

    # Dashboard / backend-bundled full-colour icon
    build_colour_icon(SRC_BLUE, ROOT / "backend" / "assets" / "appicon.png", size=512)

    # Website
    build_colour_icon(SRC_BLUE, ROOT / "web" / "assets" / "favicon.png", size=128)
    build_colour_icon(SRC_BLUE, ROOT / "web" / "assets" / "app-icon.png", size=512)

    # Chrome extension — overwrite every size so the store listing gets the
    # new mark when we re-upload.
    for sz in (16, 32, 48, 128, 256, 512):
        build_colour_icon(
            SRC_BLUE,
            ROOT / "extension" / "icons" / f"icon-{sz}.png",
            size=sz,
        )

    print("Done.")


if __name__ == "__main__":
    main()
