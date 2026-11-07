"""Install-ready watch faces for the CMF Watch app's custom photo face.

These static PNGs are what actually goes on the watch (installed by the owner
through the official app). The desktop simulator is a design tool only.

    python -m omnitrix.watch_release                 # omnitrix_home only
    python -m omnitrix.watch_release --all           # home + every alien
    python -m omnitrix.watch_release --theme xlr8    # one theme

Layout rules (target 410 x 502, from the spec sheet; pending calibration):
  * Omnitrix dial centred on the screen and scaled down, leaving two clear
    bands (CLOCK_BANDS) so the watch's own clock never overlaps the artwork,
    whether the app puts it at the top or the bottom.
  * No clock, date or live data baked in: a photo can't update.
AMOLED optimisation:
  * true-black background (unlit pixels: no grey glow around the screen edge,
    lower power), near-black values crushed to 0
  * no 1 px detail at the edges; 24-bit RGB PNG, no alpha
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from omnitrix import screens as S
from omnitrix.aliens import ALIENS, BY_KEY, Alien
from omnitrix.emblems import draw_emblem
from omnitrix.fx import draw_fx
from omnitrix.gfx import H, W, Frame, disc_mask, font, mix, polar, scale, screen_mask

RELEASE_DIR = Path(__file__).resolve().parents[1] / "watch_faces"
CENTER = (W // 2, H // 2)  # (205, 251)
DIAL_SCALE = 0.76
_CROP_R = 200  # dial + glow radius at full scale
DIAL_OUTER = round((S.R_RING + 8) * DIAL_SCALE)  # ring + glow edge at release scale
CLOCK_BANDS = {"top": (0, CENTER[1] - DIAL_OUTER - 4), "bottom": (CENTER[1] + DIAL_OUTER + 4, H)}
T = 1.1  # frozen animation time
BLACK_CRUSH = 6  # luminance below this becomes true black
BACKDROP_WASH = 0.12  # faint tint behind the dial; the simulator uses 0.55
FX_IN_BANDS = 0.12  # effects/grid brightness left inside the clock bands
BADGE_X, BADGE_R = 40, 21  # alien side badges (left centre x, hex radius)


def file_name(alien: Alien | None) -> str:
    return "omnitrix_home.png" if alien is None else f"{alien.key}.png"


def _dial_layer(color, rim, style: S.Style) -> Image.Image:
    """The Omnitrix dial rendered on pure black at the simulator's normal size."""
    f = Frame(bg="#000000")
    S.draw_ring(f, style, color, T, bg="#000000")
    S.draw_meter(f, style, color, 100, T, bg="#000000")  # decorative: a photo can't show live battery
    S.draw_bezel(f, style, color, T)
    S.draw_core(f, color, T, glow_k=0.6, rim=rim)
    return f.finish(style.glow)


def _band_mask(ramp: int = 26) -> Image.Image:
    """L mask: 255 between the clock bands, fading to FX_IN_BANDS*255 inside them."""
    top_end, bot_start = CLOCK_BANDS["top"][1], CLOCK_BANDS["bottom"][0]
    col = Image.new("L", (1, H))
    for y in range(H):
        if y < top_end:
            u = max(0.0, 1 - (top_end - y) / ramp)
        elif y > bot_start:
            u = max(0.0, 1 - (y - bot_start) / ramp)
        else:
            u = 1.0
        col.putpixel((0, y), int(255 * u))
    return col.resize((W, H))


def _side_badges(f: Frame, alien: Alien) -> None:
    """Alien emblem in a hex badge on both sides of the dial, so same-coloured aliens stay distinguishable."""
    fill = mix("#000000", alien.accent, 0.06)
    ring_edge = round((S.R_RING + 4) * DIAL_SCALE)
    for side in (-1, 1):
        c = (CENTER[0] + side * (CENTER[0] - BADGE_X), CENTER[1])
        f.polygon([polar(c, BADGE_R, a) for a in range(-90, 270, 60)], fill=fill, outline=alien.accent, width=1.6,
                  glow=scale(alien.accent, 0.7))
        draw_emblem(f, alien.emblem, c, BADGE_R * 0.56, alien.accent, alien.secondary, fill)
        x0 = c[0] - side * BADGE_R * 0.87
        f.line([(x0, c[1]), (CENTER[0] + side * ring_edge, c[1])], mix("#000000", alien.accent, 0.6), 1.5)


def _crush_blacks(img: Image.Image) -> Image.Image:
    dark = img.convert("L").point(lambda v: 255 if v < BLACK_CRUSH else 0)
    out = img.copy()
    out.paste((0, 0, 0), mask=dark)
    return out


def render(alien: Alien | None = None, style: S.Style | None = None) -> Image.Image:
    style = style or S.Style(background="#000000", hex_grid=0.22)
    color = alien.accent if alien else style.omni_green
    rim = style.omni_green if alien else None

    back = Frame(S.background("#000000", color, style.hex_grid, CENTER, wash=BACKDROP_WASH))
    if alien:
        draw_fx(back, alien, T, 0.45, CENTER)
    backdrop = back.finish(style.glow)
    # effects and grid fade out where the watch draws its clock
    backdrop = Image.composite(backdrop, backdrop.point(lambda v: int(v * FX_IN_BANDS)), _band_mask())
    if alien:
        badges = Frame(bg="#000000")
        _side_badges(badges, alien)
        backdrop = ImageChops.lighter(backdrop, badges.finish(style.glow))

    dial = _dial_layer(color, rim, style)
    cx, cy = S.C
    size = round(2 * _CROP_R * DIAL_SCALE)
    dial = dial.crop((cx - _CROP_R, cy - _CROP_R, cx + _CROP_R, cy + _CROP_R)).resize((size, size), Image.LANCZOS)
    layer = Image.new("RGB", (W, H))
    origin = (CENTER[0] - size // 2, CENTER[1] - size // 2)
    layer.paste(dial, origin)

    # glow adds onto the backdrop; inside the ring the dial fully covers the hex grid
    out = ImageChops.screen(backdrop, layer)
    r_in = round((S.R_RING + style.ring_width / 2) * DIAL_SCALE)
    m = Image.new("L", (W, H), 0)
    m.paste(disc_mask(r_in), (CENTER[0] - r_in, CENTER[1] - r_in))
    out = Image.composite(layer, out, m)

    # No fx.POST (e.g. Upgrade's slice glitch): on a static face it reads as a corrupted image.
    out = Image.composite(out, Image.new("RGB", (W, H)), screen_mask())
    return _crush_blacks(out)


def save(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, optimize=True)
    return path


# ---- preview -------------------------------------------------------------------
def _watch_body(face: Image.Image, clock: str | None, label: str) -> Image.Image:
    pad, top = 34, 30
    w, h = W + 2 * pad, H + 2 * pad
    canvas = Image.new("RGB", (w + 30, h + top + 40), "#161616")
    d = ImageDraw.Draw(canvas)
    ox, oy = 10, top
    d.rounded_rectangle([ox + w - 6, oy + 150, ox + w + 12, oy + 230], radius=6, fill="#3a3a3a")  # side button
    d.rounded_rectangle([ox, oy, ox + w, oy + h], radius=118, fill="#2a2c2a", outline="#4a4d4a", width=3)
    d.rounded_rectangle([ox + pad - 8, oy + pad - 8, ox + pad + W + 7, oy + pad + H + 7], radius=96, fill="#000000")
    screen = face.copy()
    if clock:
        sd = ImageDraw.Draw(screen)
        y0, y1 = CLOCK_BANDS[clock]
        yc = (y0 + y1) / 2 + (6 if clock == "top" else -10)
        sd.text((W / 2, yc), "10:09", font=font("bahnschrift.ttf", 72, "SemiBold"), fill="#ffffff", anchor="mm")
    canvas.paste(screen, (ox + pad, oy + pad), screen_mask())
    d.text((ox + w / 2, 14), label, font=font("bahnschrift.ttf", 15, "SemiBold"), fill="#9fb09f", anchor="mm")
    d.text((ox + w / 2, oy + h + 22), "clock drawn by the watch (simulated)" if clock else "image as installed (410 x 502)",
           font=font("bahnschrift.ttf", 12), fill="#6f7a6f", anchor="mm")
    return canvas


def preview(face: Image.Image, title: str) -> Image.Image:
    panels = [_watch_body(face, None, "PNG"), _watch_body(face, "top", "APP CLOCK AT TOP"),
              _watch_body(face, "bottom", "APP CLOCK AT BOTTOM")]
    pw, ph = panels[0].size
    sheet = Image.new("RGB", (pw * 3, ph + 46), "#161616")
    ImageDraw.Draw(sheet).text((sheet.width / 2, 24), title, font=font("bahnschrift.ttf", 20, "Bold"), fill="#39ff14", anchor="mm")
    for i, p in enumerate(panels):
        sheet.paste(p, (i * pw, 46))
    return sheet


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="home + every alien")
    g.add_argument("--theme", choices=["home", *BY_KEY], help="a single theme")
    args = ap.parse_args(argv)

    if args.all:
        themes = [None, *ALIENS]
    elif args.theme and args.theme != "home":
        themes = [BY_KEY[args.theme]]
    else:
        themes = [None]

    for alien in themes:
        img = render(alien)
        p = save(img, RELEASE_DIR / file_name(alien))
        name = alien.name if alien else "OMNITRIX HOME"
        save(preview(img, f"{name}  -  CMF WATCH PRO 1 (D395)  -  410 x 502"), RELEASE_DIR / "previews" / p.name)
        print(f"{p}  ({p.stat().st_size // 1024} KB)")
    print(f"clock bands kept free: top y<{CLOCK_BANDS['top'][1]}, bottom y>{CLOCK_BANDS['bottom'][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
