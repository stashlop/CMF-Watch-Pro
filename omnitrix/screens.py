"""Omnitrix screens. Every function returns a 410 x 502 RGB image for time ``t``.

Screens: home, selector, select_confirm, info, alien_face, transform.
``Style`` holds the user-customisable look (Design Studio controls).
"""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw

from omnitrix.aliens import ALIENS, Alien
from omnitrix.emblems import draw_emblem
from omnitrix.fx import draw_fx, post_for
from omnitrix.gfx import (
    H, SS, W, Frame, clamp01, ease_in_out, ease_out_back, ease_out_cubic, mix, phase, polar, rgb, scale,
)

# ---- layout (1x pixels) ------------------------------------------------------
C = (205, 214)
R_RING = 160
R_TICK = (142, 151)
R_METER = 132
R_BEZEL = 118
R_CORE = 104
R_ORBIT = 138
PLATE = (62, 392, 348, 472)

TRANSFORM_DURATION = 4.2
CONFIRM_DURATION = 1.0


@dataclass
class Style:
    background: str = "#000000"
    omni_green: str = "#39FF14"
    ring_width: float = 6.0
    glow: float = 1.0
    hex_grid: float = 0.35
    font: str = "bahnschrift.ttf"
    clock_24h: bool = True


@dataclass
class WatchData:
    now: datetime = field(default_factory=datetime.now)
    battery: int = 76


# ---- cached layers -----------------------------------------------------------
@lru_cache(maxsize=32)
def background(bg: str, tint: str, hex_amount: float, center: tuple = C, wash: float = 0.55) -> Image.Image:
    """Cached backdrop: radial tint wash (strength ``wash``) + hex grid fading from ``center``."""
    size = (W * SS, H * SS)
    base = Image.new("RGB", size, rgb(bg))

    radial = Image.radial_gradient("L").resize((int(620 * SS), int(620 * SS)))
    radial = ImageChops.invert(radial)
    falloff = Image.new("L", size, 0)
    falloff.paste(radial, (int((center[0] - 310) * SS), int((center[1] - 310) * SS)))

    base = Image.composite(Image.new("RGB", size, mix(bg, tint, 0.16)), base, falloff.point(lambda v: v * wash))

    if hex_amount > 0:
        hexes = Image.new("L", size, 0)
        d = ImageDraw.Draw(hexes)
        r = 17 * SS
        dx, dy = 1.5 * r, math.sqrt(3) * r
        col = 0
        x = -r
        while x < size[0] + r:
            y = -dy if col % 2 == 0 else -dy / 2
            while y < size[1] + dy:
                pts = [(x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a))) for a in range(0, 360, 60)]
                d.polygon(pts, outline=255, width=max(1, SS))
                y += dy
            x += dx
            col += 1
        hexes = ImageChops.multiply(hexes, falloff.point(lambda v: int(v * hex_amount)))
        base = Image.composite(Image.new("RGB", size, mix(bg, tint, 0.55)), base, hexes)
    return base


@lru_cache(maxsize=64)
def core_tile(radius: int, color: str, dark: str = "#000000") -> Image.Image:
    """The Omnitrix hourglass faceplate (supersampled square tile)."""
    n = 2 * radius * SS
    grad = ImageChops.invert(Image.radial_gradient("L").resize((n, n)))
    face = Image.composite(Image.new("RGB", (n, n), mix(color, "#ffffff", 0.12)),
                           Image.new("RGB", (n, n), scale(color, 0.45)), grad)
    d = ImageDraw.Draw(face)
    r, cx, cy, g = n / 2, n / 2, n / 2, n * 0.035
    for side in (-1, 1):
        d.polygon([(cx + side * 1.08 * r, cy - 1.42 * r), (cx + side * 1.08 * r, cy + 1.42 * r), (cx + side * g, cy)],
                  fill=rgb(dark))
    return face


@lru_cache(maxsize=16)
def holo_tile(radius: int, accent: str) -> Image.Image:
    n = 2 * radius * SS
    grad = ImageChops.invert(Image.radial_gradient("L").resize((n, n))).point(lambda v: v * 0.6)
    tile = Image.composite(Image.new("RGB", (n, n), mix("#000000", accent, 0.22)), Image.new("RGB", (n, n), (2, 6, 2)), grad)
    d = ImageDraw.Draw(tile)
    for y in range(0, n, 5 * SS):
        d.line([(0, y), (n, y)], fill=mix("#000000", accent, 0.08), width=SS)
    return tile


# ---- building blocks -----------------------------------------------------------
def _hourglass_glow(f: Frame, c, r, color, k):
    for sgn in (-1, 1):
        pts = [(c[0], c[1])] + [polar(c, r, a) for a in range(-90 - 37 + (sgn > 0) * 180, -90 + 38 + (sgn > 0) * 180, 6)]
        f.g.polygon(f.pts(pts), fill=scale(color, k))


def draw_ring(f: Frame, style: Style, color, t: float, rot: float = 0.0, brightness: float = 1.0, ticks: bool = True,
              sweep: bool = True, bg=None, c=C):
    bg = bg or style.background
    col = mix(bg, color, brightness)
    f.ring(c, R_RING, col, style.ring_width, glow=scale(color, brightness))
    f.ring(c, R_RING - 9, mix(bg, color, 0.25 * brightness), 1.2)
    if not ticks:
        return
    sweep_a = (t * 120) % 360
    for i in range(72):
        a = rot + t * 6 + i * 5
        d = abs((a - sweep_a + 180) % 360 - 180)
        b = (0.22 + 0.78 * max(0.0, 1 - d / 45)) if sweep else 0.35
        b *= brightness
        r0 = R_TICK[0] - (4 if i % 6 == 0 else 0)
        tc = mix(bg, color, b)
        f.line([polar(c, r0, a), polar(c, R_TICK[1], a)], tc, 2.2 if i % 6 == 0 else 1.4, glow=tc if b > 0.6 else None)


def draw_meter(f: Frame, style: Style, color, battery: int, t: float, bg=None, c=C):
    bg = bg or style.background
    segs = 16
    lit = round(clamp01(battery / 100) * segs)
    col = "#FF3B30" if battery <= 20 else color
    for i in range(segs):
        a0 = 133 + i * 6
        on = i < lit
        sc = col if on else mix(bg, col, 0.13)
        f.arc(c, R_METER, a0, a0 + 4.4, sc, 9, glow=sc if on else None)
    for i in range(12):  # right-side energy flow
        a0 = -46 + (11 - i) * 8
        b = 0.15 + 0.85 * max(0.0, math.sin(i * 0.55 - t * 5)) ** 3
        sc = mix(bg, color, b)
        f.arc(c, R_METER, a0, a0 + 5, sc, 6, glow=sc if b > 0.5 else None)


def draw_bezel(f: Frame, style: Style, color, t: float, rot: float = 0.0, c=C):
    f.ring(c, R_BEZEL - 6.5, "#161b16", 13)
    f.ring(c, R_BEZEL + 6.5, "#2c352c", 1)
    f.ring(c, R_BEZEL - 6.5, "#3b473b", 1)
    pulse = 0.55 + 0.45 * math.sin(t * 3)
    for a in (45, 135, 225, 315):
        p = polar(c, R_BEZEL, a + rot)
        hexa = [polar(p, 8, a + rot + k) for k in range(0, 360, 60)]
        f.polygon(hexa, fill="#0d120d", outline="#56645a", width=1.2)
        f.circle(p, 2.6, fill=mix("#000000", color, pulse), glow=scale(color, pulse))


def draw_core(f: Frame, color, t: float, scale_k: float = 1.0, rot: float = 0.0, glow_k: float = None, rim=None, c=C):
    r = max(4, int(R_CORE * scale_k))
    tile = core_tile(r, color)
    if rot:
        tile = tile.rotate(-rot, resample=Image.BICUBIC)
    f.paste_disc(c, tile)
    k = (0.55 + 0.25 * math.sin(t * 2.2)) if glow_k is None else glow_k
    _hourglass_glow(f, c, r, color, k * 0.6)
    f.ring(c, r, rim or "#9aa69a", 3.5 * scale_k)


def draw_plate(f: Frame, color, bg, chamfer=14, glow=True):
    x0, y0, x1, y1 = PLATE
    c = chamfer
    pts = [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]
    f.polygon(pts, fill=mix(bg, color, 0.05), outline=color, width=2, glow=color if glow else None)
    f.line([(x0 + c + 6, y0 + 5), (x0 + c + 40, y0 + 5)], mix(bg, color, 0.6), 1.5)
    f.line([(x1 - c - 40, y1 - 5), (x1 - c - 6, y1 - 5)], mix(bg, color, 0.6), 1.5)
    for x in (190, 220):  # struts to the dial
        f.line([(x, C[1] + R_RING + 2), (x, y0)], mix(bg, color, 0.7), 2, glow=color if glow else None)


def mini_hourglass(f: Frame, c, s, color):
    f.circle(c, s, fill=color, glow=color)
    for side in (-1, 1):
        f.polygon([(c[0] + side * 1.08 * s, c[1] - 1.42 * s), (c[0] + side * 1.08 * s, c[1] + 1.42 * s), (c[0] + side * s * 0.08, c[1])],
                  fill="#000000")
    f.ring(c, s, "#9aa69a", 1)


def _time_str(style: Style, now: datetime) -> str:
    return now.strftime("%H:%M") if style.clock_24h else now.strftime("%I:%M").lstrip("0")


def draw_clock(f: Frame, style: Style, data: WatchData, color, variation="SemiBold Condensed"):
    f.text((205, 430), _time_str(style, data.now), 70, mix(color, "#ffffff", 0.82), style.font, variation, glow=scale(color, 0.8))
    f.text((316, 446), data.now.strftime("%S"), 20, color, style.font, "SemiBold", anchor="rs")
    if not style.clock_24h:
        f.text((316, 418), data.now.strftime("%p"), 13, mix(style.background, color, 0.7), style.font, "SemiBold", anchor="rs")


def draw_date(f: Frame, style: Style, data: WatchData, color, bg):
    dim = mix(bg, color, 0.5)
    f.text((205, 31), data.now.strftime("%a  %d %b").upper(), 18, mix(color, "#ffffff", 0.55), style.font, "SemiBold", spacing=2)
    for sgn in (-1, 1):
        x0, x1 = 205 + sgn * 78, 205 + sgn * 140
        f.line([(x0, 31), (x1, 31)], dim, 1.5)
        f.polygon([(x1, 27), (x1 + sgn * 5, 31), (x1, 35), (x1 - sgn * 5, 31)], fill=color, glow=color)


def _bottom_label(f: Frame, style: Style, s: str, color):
    f.text((205, 488), s, 12, color, style.font, "SemiBold", spacing=2)


# ---- screens ---------------------------------------------------------------------
def home(t: float, data: WatchData | None = None, style: Style | None = None) -> Image.Image:
    style, data = style or Style(), data or WatchData()
    g, bg = style.omni_green, style.background
    f = Frame(background(bg, g, style.hex_grid))
    draw_date(f, style, data, g, bg)
    draw_ring(f, style, g, t)
    draw_meter(f, style, g, data.battery, t)
    draw_bezel(f, style, g, t)
    draw_core(f, g, t)
    draw_plate(f, g, bg)
    mini_hourglass(f, (96, 432), 13, g)
    draw_clock(f, style, data, g)
    _bottom_label(f, style, f"ENERGY {data.battery}%", mix(bg, g, 0.6))
    return f.finish(style.glow)


def home_background(t: float, style: Style | None = None) -> Image.Image:
    """Home screen without clock/date, for use behind a watch-drawn clock."""
    style = style or Style()
    g, bg = style.omni_green, style.background
    f = Frame(background(bg, g, style.hex_grid))
    draw_ring(f, style, g, t)
    draw_meter(f, style, g, 100, t)
    draw_bezel(f, style, g, t)
    draw_core(f, g, t)
    return f.finish(style.glow)


def _wrapdist(i: float, j: float, n: int) -> float:
    return abs((i - j + n / 2) % n - n / 2)


def selector(t: float, sel: float = 0.0, data: WatchData | None = None, style: Style | None = None,
             burst: float = 0.0) -> Image.Image:
    """Alien dial. ``sel`` may be fractional while the dial is turning."""
    style, data = style or Style(), data or WatchData()
    g, bg = style.omni_green, style.background
    n = len(ALIENS)
    idx = int(round(sel)) % n
    alien = ALIENS[idx]
    f = Frame(background(bg, g, style.hex_grid))

    f.text((205, 31), "SELECT  ALIEN", 15, mix(bg, g, 0.85), style.font, "SemiBold", spacing=3)
    draw_ring(f, style, g, t, ticks=False)
    f.ring(C, R_ORBIT, mix(bg, g, 0.18), 1.2)

    for i, a in enumerate(ALIENS):
        s = clamp01(1 - _wrapdist(i, sel, n))
        p = polar(C, R_ORBIT, -90 + (i - sel) * (360 / n))
        f.circle(p, 15 + 3 * s, fill=mix(bg, a.accent, 0.08 + 0.14 * s),
                 outline=mix(mix(bg, a.accent, 0.4), g, s), width=1.4 + 1.6 * s, glow=g if s > 0.5 else None)
        draw_emblem(f, a.emblem, p, 9 + 3 * s, mix(scale(a.accent, 0.5), a.accent, s), a.secondary, mix(bg, a.accent, 0.08),
                    glow=s > 0.5)

    f.paste_disc(C, holo_tile(R_CORE, alien.accent))
    pulse = 0.7 + 0.3 * math.sin(t * 4)
    f.ring(C, R_CORE, g, 5 + 6 * burst, glow=scale(g, pulse + burst))
    for k in range(3):
        s0 = t * 70 + k * 120
        f.arc(C, R_CORE - 10, s0, s0 + 50, mix(bg, g, 0.55), 2, glow=scale(g, 0.5))
    bob = 2.5 * math.sin(t * 2)
    size = 54 * (1 + 0.22 * math.sin(math.pi * burst)) * (1 - 0.35 * min(1.0, _wrapdist(sel, idx, n) * 2))
    draw_emblem(f, alien.emblem, (C[0], C[1] + bob), size, alien.accent, alien.secondary, (4, 8, 4))

    if burst > 0:
        b = math.sin(math.pi * clamp01(burst))
        draw_fx(f, alien, t, max(0.05, b), C)
        f.ring(C, R_CORE + ease_out_cubic(burst) * 130, mix(bg, alien.accent, 1 - burst), 3 + 8 * (1 - burst),
               glow=scale(alien.accent, 1 - burst))

    draw_plate(f, g, bg)
    f.text((205, 424), alien.name, 40, alien.accent, style.font, "SemiBold Condensed", glow=scale(alien.accent, 0.5), spacing=1)
    f.text((205, 456), f"{alien.klass}    {idx + 1:02d}/{n}", 13, mix(bg, g, 0.7), style.font, "SemiBold", spacing=2)
    _bottom_label(f, style, "TAP SELECT  /  HOLD TRANSFORM", mix(bg, g, 0.45))
    post = post_for(alien, t, b) if burst > 0 else None
    return f.finish(style.glow * (1 + 0.6 * math.sin(math.pi * clamp01(burst))), post=post)


def select_confirm(t: float, p: float, sel: int, data=None, style=None) -> Image.Image:
    """Selection confirmation burst, p = 0..1 over CONFIRM_DURATION."""
    return selector(t, float(sel), data, style, burst=clamp01(p))


def info(t: float, alien: Alien, data: WatchData | None = None, style: Style | None = None) -> Image.Image:
    style, data = style or Style(), data or WatchData()
    g, bg = style.omni_green, style.background
    f = Frame(background(bg, alien.accent, style.hex_grid * 0.8))
    hc = (205, 118)
    f.polygon([polar(hc, 66, a) for a in range(-90, 270, 60)], outline=alien.accent, width=3, glow=alien.accent)
    f.polygon([polar(hc, 57, a) for a in range(-90, 270, 60)], fill=mix(bg, alien.accent, 0.08))
    draw_emblem(f, alien.emblem, (hc[0], hc[1] + 1.5 * math.sin(t * 2)), 38, alien.accent, alien.secondary, mix(bg, alien.accent, 0.08))
    f.text((205, 216), alien.name, 40, alien.accent, style.font, "SemiBold Condensed", glow=scale(alien.accent, 0.5), spacing=2)
    f.text((205, 248), alien.klass, 14, mix(bg, alien.secondary, 0.75), style.font, "SemiBold", spacing=4)
    for i, line in enumerate(textwrap.wrap(alien.tagline, 30)[:3]):
        f.text((205, 282 + i * 22), line, 16, "#c9cfc9", style.font, "Regular")
    for row, (label, val) in enumerate(zip(("POWER", "SPEED", "DEFENSE"), alien.stats)):
        y = 356 + row * 30
        f.text((70, y), label, 13, mix(bg, g, 0.7), style.font, "SemiBold", anchor="lm", spacing=2)
        for s in range(10):
            x = 160 + s * 18
            on = s < val
            col = alien.accent if on else mix(bg, alien.accent, 0.14)
            f.polygon([(x + 4, y - 6), (x + 16, y - 6), (x + 12, y + 6), (x, y + 6)], fill=col, glow=col if on else None)
    pulse = 0.55 + 0.45 * math.sin(t * 3)
    mini_hourglass(f, (118, 470), 9, g)
    f.text((138, 470), "HOLD TO TRANSFORM", 13, mix(bg, g, pulse), style.font, "SemiBold", anchor="lm", spacing=2)
    return f.finish(style.glow)


def alien_face(t: float, alien: Alien, data: WatchData | None = None, style: Style | None = None,
               show_clock: bool = True) -> Image.Image:
    """The alien's themed watch face. The hourglass core keeps the Omnitrix recognisable."""
    style, data = style or Style(), data or WatchData()
    g, bg, ac = style.omni_green, alien.bg_tint, alien.accent
    f = Frame(background(bg, ac, style.hex_grid))
    draw_fx(f, alien, t, 0.55, C)
    draw_date(f, style, data, ac, bg)
    draw_ring(f, style, ac, t, bg=bg)
    draw_meter(f, style, ac, data.battery, t, bg=bg)
    draw_bezel(f, style, ac, t)
    draw_core(f, ac, t, rim=g)
    if show_clock:
        draw_plate(f, ac, bg)
        draw_emblem(f, alien.emblem, (96, 432), 15, ac, alien.secondary, mix(bg, ac, 0.05))
        draw_clock(f, style, data, ac, alien.time_variation)
        _bottom_label(f, style, f"{alien.name}  /  ENERGY {data.battery}%", mix(bg, ac, 0.6))
    return f.finish(style.glow, post=post_for(alien, t, 0.5))


def transform(t: float, alien: Alien, data: WatchData | None = None, style: Style | None = None) -> Image.Image:
    """Transformation sequence, t = 0..TRANSFORM_DURATION seconds.

    wake -> symbol -> dial rotates -> ring lights -> alien appears -> name -> confirm flash -> alien face
    """
    style, data = style or Style(), data or WatchData()
    g, bg = style.omni_green, style.background
    wake, sym, rot = phase(t, 0, 0.35), phase(t, 0.35, 0.9), phase(t, 0.9, 1.6)
    lit, appear, name = phase(t, 1.6, 2.0), phase(t, 2.0, 2.5), phase(t, 2.5, 3.0)
    conf, ret = phase(t, 3.0, 3.7), phase(t, 3.7, TRANSFORM_DURATION)

    f = Frame(background(bg, g, style.hex_grid * (0.3 + 0.7 * lit)))
    ang = ease_in_out(rot) * 180

    draw_ring(f, style, g, t, rot=ang * 2, brightness=0.2 + 0.8 * lit, sweep=lit >= 1)
    if 0 < lit < 1:
        f.arc(C, R_RING, -90, -90 + 360 * ease_out_cubic(lit), mix(g, "#ffffff", 0.4), style.ring_width + 3,
              glow=mix(g, "#ffffff", 0.3))
    draw_bezel(f, style, g, t, rot=ang)

    if sym > 0:
        s = 0.12 + 0.88 * ease_out_back(sym)
        r = max(4, int(R_CORE * s))
        tile = core_tile(r, g)
        if appear > 0:
            tile = Image.blend(tile, holo_tile(r, alien.accent), ease_out_cubic(appear))
        if ang:
            tile = tile.rotate(-ang, resample=Image.BICUBIC)
        f.paste_disc(C, tile)
        f.ring(C, r, "#9aa69a" if appear < 0.5 else g, 3.5 * s, glow=g if appear >= 0.5 else None)
        if appear < 1:
            _hourglass_glow(f, C, r, g, (0.4 + 0.8 * lit) * (1 - appear))

    if appear > 0:
        f.ring(C, R_CORE, g, 5, glow=scale(g, 1.2))
        draw_emblem(f, alien.emblem, C, 54 * ease_out_back(appear), alien.accent, alien.secondary, (4, 8, 4))

    if name > 0:
        draw_plate(f, alien.accent, bg)
        shown = alien.name[: max(1, int(round(len(alien.name) * ease_out_cubic(name))))]
        f.text((205, 430), shown, 42, alien.accent, style.font, "SemiBold Condensed", glow=scale(alien.accent, 0.6), spacing=2)

    if conf > 0:
        draw_fx(f, alien, t, max(0.05, math.sin(math.pi * conf)), C)
        f.ring(C, R_CORE + ease_out_cubic(conf) * 320, mix(bg, g, 1 - conf), 14 * (1 - conf) + 1, glow=scale(g, 1 - conf))

    if wake < 1:
        y = H * ease_out_cubic(wake)
        f.line([(0, y), (W, y)], g, 3, glow=g)

    flash = (1 - conf) ** 2 * 0.85 if conf > 0 else 0.0

    def post(img):
        if flash > 0.01:
            img = Image.blend(img, Image.new("RGB", img.size, mix(g, "#ffffff", 0.55)), flash)
        return img

    frame = f.finish(style.glow * (1 + 0.5 * lit * (1 - ret)), fade=0.1 + 0.9 * ease_out_cubic(wake), post=post)
    if ret > 0:
        frame = Image.blend(frame, alien_face(t, alien, data, style), ease_in_out(ret))
    return frame
