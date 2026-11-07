"""Per-alien effects.

Each effect is ``fn(f, alien, t, k, c)``: draw onto Frame ``f`` at time ``t`` seconds,
intensity ``k`` (about 0.5 = ambient on the alien's watch face, 1.0 = selection burst),
``c`` = dial centre. ``POST`` holds optional whole-image post-processing.
"""

from __future__ import annotations

import math
import random

from PIL import Image, ImageChops

from omnitrix.emblems import _slash
from omnitrix.gfx import H, SS, W, Frame, clamp01, mix, rgb, scale


def _table(seed: int, n: int, fn):
    r = random.Random(seed)
    return [fn(r) for _ in range(n)]


def _glow_ellipse(f: Frame, cx, cy, rx, ry, color):
    f.g.ellipse([(cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS], fill=rgb(color))


_EMBERS = _table(1, 46, lambda r: (r.uniform(20, W - 20), r.uniform(30, 90), r.uniform(1.2, 3.0), r.uniform(5, 16), r.uniform(0, 6.3), r.random()))


def embers(f, a, t, k, c):
    for i in range(8):  # stacked ellipses -> soft heat gradient after blur
        u = 1 - i / 8
        _glow_ellipse(f, W / 2, H + 60, 280 * u, 170 * u, scale(a.accent, 0.06 * k * (i + 1)))
    for i, (x0, spd, size, sway, ph, hue) in enumerate(_EMBERS[: int(len(_EMBERS) * k)]):
        y = H + 10 - ((t * spd + ph * 80) % (H + 40))
        x = x0 + sway * math.sin(t * 1.7 + ph)
        b = clamp01(y / H) * 0.9 + 0.1
        col = mix(a.accent, a.secondary, hue)
        f.circle((x, y), size, fill=mix(a.bg_tint, col, b), glow=scale(col, b))


def shock(f, a, t, k, c):
    period = 1.6
    for n in range(3):
        p = ((t / period) + n / 3) % 1
        alpha = (1 - p) * k
        f.ring(c, 105 + p * 250, mix(a.bg_tint, a.accent, alpha), 2 + 7 * (1 - p), glow=scale(a.accent, alpha) if alpha > 0.15 else None)


_STREAKS = _table(2, 26, lambda r: (r.uniform(10, H - 10), r.uniform(40, 150), r.uniform(450, 950), r.uniform(0, 1000), r.uniform(1.0, 3.0)))


def speed(f, a, t, k, c):
    for y, ln, spd, off, w in _STREAKS[: int(len(_STREAKS) * k)]:
        x = ((t * spd + off) % (W + 320)) - 160
        col = mix(a.bg_tint, mix(a.accent, a.secondary, 0.3), 0.35 + 0.55 * k)
        f.line([(x, y), (x + ln, y - ln * 0.08)], col, w, glow=col if w > 1.8 else None)


def _shard_table(r):
    while True:
        x, y = r.uniform(10, W - 10), r.uniform(10, H - 10)
        if math.hypot(x - 205, y - 214) > 175 and not (55 < x < 355 and 385 < y < 480):
            break
    s, rot = r.uniform(14, 36), r.uniform(0, 360)
    pts = [(x + s * math.cos(math.radians(rot + d)), y + s * math.sin(math.radians(rot + d))) for d in (0, 115, 230)]
    return pts, r.uniform(0, 6.3), r.uniform(1.2, 2.6)


_SHARDS = _table(3, 18, _shard_table)


def crystal(f, a, t, k, c):
    for pts, ph, spd in _SHARDS:
        b = (0.25 + 0.75 * max(0.0, math.sin(t * spd + ph)) ** 4) * k
        f.polygon(pts, fill=mix(a.bg_tint, a.accent, b * 0.35), outline=mix(a.bg_tint, a.secondary, b), width=1.2,
                  glow=scale(a.accent, b) if b > 0.45 else None)


def claws(f, a, t, k, c):
    period = 2.4
    cyc, p = divmod(t / period, 1)
    spots = [(320, 110, 1), (95, 330, -1), (310, 340, 1), (100, 100, -1)]
    x, y, side = spots[int(cyc) % len(spots)]
    grow = clamp01(p / 0.18)
    fade = 1 - clamp01((p - 0.18) / 0.8)
    alpha = fade * k
    if alpha <= 0:
        return
    for j in (-1, 0, 1):
        x0, y0 = x + j * 22 + side * 40, y - 70
        x1, y1 = x + j * 22 - side * 40, y + 70
        xe, ye = x0 + (x1 - x0) * grow, y0 + (y1 - y0) * grow
        col = mix(a.bg_tint, a.accent, alpha)
        f.polygon(_slash(x0, y0, xe, ye, side * 10, 6), fill=col, glow=scale(a.accent, alpha))


def _trace(r):
    x, y = r.randrange(0, W, 24), r.randrange(0, H, 24)
    pts = [(x, y)]
    for _ in range(r.randint(3, 6)):
        if r.random() < 0.5:
            x += r.choice((-1, 1)) * r.randint(2, 5) * 24
        else:
            y += r.choice((-1, 1)) * r.randint(2, 5) * 24
        pts.append((x, y))
    return pts, r.uniform(0, 1)


_TRACES = _table(4, 14, _trace)


def glitch(f, a, t, k, c):
    for pts, off in _TRACES:
        f.line(pts, mix(a.bg_tint, a.accent, 0.18 * k + 0.05), 1.5)
        segs = list(zip(pts, pts[1:]))
        p = ((t * 0.5 + off) % 1) * len(segs)
        i = int(p)
        (x0, y0), (x1, y1) = segs[i]
        u = p - i
        f.circle((x0 + (x1 - x0) * u, y0 + (y1 - y0) * u), 2.5, fill=a.secondary, glow=scale(a.accent, k))


def glitch_post(img: Image.Image, t: float, k: float) -> Image.Image:
    r = random.Random(int(t * 9))
    if r.random() > 0.35 * k + 0.05:
        return img
    out = img.copy()
    for _ in range(r.randint(1, 3)):
        y, h, dx = r.randrange(0, H - 20), r.randint(4, 18), r.choice((-1, 1)) * r.randint(4, 16)
        band = img.crop((0, y, W, y + h))
        out.paste(ImageChops.offset(band, dx, 0), (0, y))
    rch, gch, bch = out.split()
    return Image.merge("RGB", (ImageChops.offset(rch, 3, 0), gch, bch))


_BLOBS = _table(5, 7, lambda r: (r.uniform(40, W - 40), r.uniform(40, H - 40), r.uniform(50, 110), r.uniform(0.15, 0.4), r.uniform(0, 6.3)))


def mist(f, a, t, k, c):
    for x, y, rad, spd, ph in _BLOBS:
        cx = x + 40 * math.sin(t * spd + ph)
        cy = y + 25 * math.cos(t * spd * 0.8 + ph)
        for i in range(6):  # soft wisp: brighter towards the middle, glow layer only
            u = 1 - i / 6
            _glow_ellipse(f, cx, cy, rad * u, rad * 0.6 * u, scale(a.accent, 0.035 * k * (i + 1)))


def roll(f, a, t, k, c):
    rot = t * 110 * (0.4 + k)
    col = mix(a.bg_tint, a.accent, 0.35 + 0.5 * k)
    for i in range(6):
        s = rot + i * 60
        f.arc(c, 182, s, s + 38, col, 6, glow=col)
    dim = mix(a.bg_tint, a.secondary, 0.3 * k + 0.1)
    for i in range(24):
        s = -rot * 0.6 + i * 15
        f.arc(c, 193, s, s + 6, dim, 2.5)


_FLIES = _table(6, 22, lambda r: (r.uniform(168, 240), r.uniform(0, 360), r.uniform(-1.2, 1.2), r.uniform(0, 6.3), r.uniform(1.3, 2.6)))


def buzz(f, a, t, k, c):
    for rad, th, w, ph, size in _FLIES[: int(len(_FLIES) * k) or 1]:
        rr = rad + 9 * math.sin(t * 13 + ph)
        ang = math.radians(th + t * w * 60 + 6 * math.sin(t * 17 + ph))
        p = (c[0] + rr * math.cos(ang), c[1] + rr * math.sin(ang))
        f.circle(p, size, fill=a.secondary, glow=scale(a.accent, k))


_BUBBLES = _table(7, 16, lambda r: (r.uniform(20, W - 20), r.uniform(20, 55), r.uniform(2, 5), r.uniform(0, 6.3)))


def ripple(f, a, t, k, c):
    for j in range(3):
        y0 = H - 30 - j * 16
        col = mix(a.bg_tint, a.accent, (0.65 - j * 0.17) * k)
        pts = [(x, y0 + 6 * math.sin(x / 34 + t * 2.2 + j)) for x in range(0, W + 10, 10)]
        f.line(pts, col, 2, glow=col if j == 0 else None)
    for x0, spd, size, ph in _BUBBLES[: int(len(_BUBBLES) * k) or 1]:
        y = H - ((t * spd + ph * 70) % (H + 20))
        f.circle((x0 + 5 * math.sin(t * 2 + ph), y), size, outline=mix(a.bg_tint, a.secondary, 0.7 * k), width=1.2)


EFFECTS = {fn.__name__: fn for fn in (embers, shock, speed, crystal, claws, glitch, mist, roll, buzz, ripple)}
POST = {"glitch": glitch_post}


def draw_fx(f: Frame, alien, t: float, k: float, c) -> None:
    EFFECTS[alien.fx](f, alien, t, k, c)


def post_for(alien, t: float, k: float):
    fn = POST.get(alien.fx)
    return (lambda img: fn(img, t, k)) if fn else None
