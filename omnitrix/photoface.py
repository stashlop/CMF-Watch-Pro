"""Static images for the CMF Watch app's custom photo watch face.

The official app installs these; nothing here talks to the watch. A photo face
can't animate or show live data, so these are the Omnitrix *look* only: no date,
no clock (the watch draws its own on top), and a purely decorative energy meter.

    python -m omnitrix.photoface            # writes data/exports/omnitrix/phone/

Outputs:
  calibration.png              upload this first: shows crop/scale/black level on the watch
  <theme>_clock-<pos>.png/.jpg one per theme (omnitrix + 10 aliens) x clock position
                               top / center / bottom = where the app draws its clock
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from omnitrix import screens as S
from omnitrix.aliens import ALIENS, Alien
from omnitrix.export import EXPORT_DIR
from omnitrix.fx import draw_fx, post_for
from omnitrix.gfx import H, W, Frame, font, mix

PHONE_DIR = EXPORT_DIR / "phone"
PLACEMENTS = ("top", "center", "bottom")
T = 1.1  # frozen animation time for the still image
SHIFT_FOR_TOP = H - 2 * S.C[1]  # mirror the dial into the lower part (74 px down)


# ---- calibration -----------------------------------------------------------------
def calibration() -> Image.Image:
    img = Image.new("RGB", (W, H), "black")
    d = ImageDraw.Draw(img)
    f_small, f_mid, f_big = font("bahnschrift.ttf", 11), font("bahnschrift.ttf", 14), font("bahnschrift.ttf", 22, "Bold")

    # nested borders: whichever is the outermost one still visible tells the crop in px
    for inset, col in ((0, "#ff2a2a"), (4, "#ff9a1f"), (8, "#ffe81f"), (16, "#39ff14"), (32, "#1fa2ff")):
        d.rectangle([inset, inset, W - 1 - inset, H - 1 - inset], outline=col, width=2)
    d.text((W // 2, 82), "OUTERMOST VISIBLE BORDER (px)", font=f_small, fill="#9a9a9a", anchor="mm")
    for i, (inset, col) in enumerate(((0, "#ff2a2a"), (4, "#ff9a1f"), (8, "#ffe81f"), (16, "#39ff14"), (32, "#1fa2ff"))):
        d.text((W // 2 + (i - 2) * 40, 101), str(inset), font=f_mid, fill=col, anchor="mm")

    # rulers every 10 px, labelled every 50
    for x in range(0, W, 10):
        ln = 12 if x % 50 == 0 else 6
        d.line([(x, 34), (x, 34 + ln)], fill="#9a9a9a")
        if x % 50 == 0 and 0 < x < W:
            d.text((x, 52), str(x), font=f_small, fill="#9a9a9a", anchor="mm")
    for y in range(0, H, 10):
        ln = 12 if y % 50 == 0 else 6
        d.line([(34, y), (34 + ln, y)], fill="#9a9a9a")
        if y % 50 == 0 and 50 < y < H - 20:
            d.text((54, y), str(y), font=f_small, fill="#9a9a9a", anchor="lm")

    # expected rounded screen corners (radius from the preview profile)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=90, outline="#555555", width=1)

    # centre cross + circle for aspect-ratio / scaling checks
    cx, cy = W // 2, H // 2
    d.line([(cx - 60, cy), (cx + 60, cy)], fill="#ffffff")
    d.line([(cx, cy - 60), (cx, cy + 60)], fill="#ffffff")
    d.ellipse([cx - 100, cy - 100, cx + 100, cy + 100], outline="#39ff14", width=2)
    d.text((cx, cy - 125), "410 x 502 TEST", font=f_big, fill="#ffffff", anchor="mm")
    d.text((cx, cy + 122), "circle should look round", font=f_mid, fill="#39ff14", anchor="mm")

    # black-level steps: on AMOLED the first patches should be distinguishable from pure black
    levels = (0, 4, 8, 16, 32, 64, 128, 255)
    sw = 34
    x0 = cx - len(levels) * sw // 2
    for i, v in enumerate(levels):
        d.rectangle([x0 + i * sw, cy + 145, x0 + (i + 1) * sw - 2, cy + 175], fill=(v, v, v))
        d.text((x0 + i * sw + sw // 2 - 1, cy + 186), str(v), font=f_small, fill="#9a9a9a", anchor="mm")

    # 1-px detail lines to check if the app downsamples
    for i in range(6):
        d.line([(cx + 120, cy - 30 + i * 2), (cx + 170, cy - 30 + i * 2)], fill="#ffffff")
    d.text((cx + 145, cy - 42), "1px lines", font=f_small, fill="#9a9a9a", anchor="mm")
    return img


# ---- themed backgrounds ------------------------------------------------------------
def _theme(alien: Alien | None, style: S.Style):
    if alien is None:
        return style.omni_green, style.background
    return alien.accent, alien.bg_tint


def _dial(alien: Alien | None, style: S.Style, dim_core: bool, c=S.C) -> Image.Image:
    color, bg = _theme(alien, style)
    f = Frame(S.background(bg, color, style.hex_grid, c))
    if alien:
        draw_fx(f, alien, T, 0.55, c)
    S.draw_ring(f, style, color, T, bg=bg, c=c)
    S.draw_meter(f, style, color, 100, T, bg=bg, c=c)
    S.draw_bezel(f, style, color, T, c=c)
    core = mix(bg, color, 0.28) if dim_core else color
    S.draw_core(f, core, T, glow_k=0.12 if dim_core else 0.6, rim=style.omni_green if alien else None, c=c)
    return f.finish(style.glow, post=post_for(alien, T, 0.4) if alien else None)


def photo_face(alien: Alien | None, placement: str, style: S.Style | None = None) -> Image.Image:
    """top / center / bottom = where the watch app draws its clock."""
    style = style or S.Style()
    if placement == "bottom":  # dial in its usual place; plate area stays empty for the clock
        return _dial(alien, style, dim_core=False)
    if placement == "center":  # dimmed core so a centred clock stays readable
        return _dial(alien, style, dim_core=True)
    if placement == "top":  # dial lowered; top band empty
        return _dial(alien, style, dim_core=False, c=(S.C[0], S.C[1] + SHIFT_FOR_TOP))
    raise ValueError(f"placement must be one of {PLACEMENTS}")


def export_phone_pack(out: Path = PHONE_DIR, style: S.Style | None = None) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = [out / "calibration.png"]
    calibration().save(written[0])
    for alien in [None, *ALIENS]:
        name = alien.key if alien else "omnitrix"
        for pos in PLACEMENTS:
            img = photo_face(alien, pos, style)
            for ext, kw in ((".png", {}), (".jpg", {"quality": 95, "subsampling": 0})):
                p = out / f"{name}_clock-{pos}{ext}"
                img.save(p, **kw)
                written.append(p)
    return written


def main(argv=None) -> int:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    files = export_phone_pack()
    print(f"{len(files)} files in {PHONE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
