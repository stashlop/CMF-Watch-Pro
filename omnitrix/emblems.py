"""Original geometric emblems, one per alien. Defined in unit space (-1..1, y down)."""

from __future__ import annotations

import math

from omnitrix.gfx import Frame


def _map(c, s, pts, rot_deg: float = 0.0):
    a = math.radians(rot_deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + s * (x * ca - y * sa), c[1] + s * (x * sa + y * ca)) for x, y in pts]


def _ellipse(cx, cy, rx, ry, rot=0.0, n=28):
    a = math.radians(rot)
    out = []
    for i in range(n):
        u = 2 * math.pi * i / n
        x, y = rx * math.cos(u), ry * math.sin(u)
        out.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    return out


def _slash(x0, y0, x1, y1, bow, wmax, n=18):
    """Tapered curved stroke as a polygon."""
    mx, my = (x0 + x1) / 2 + bow, (y0 + y1) / 2
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t**2 * x1
        y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t**2 * y1
        dx = 2 * (1 - t) * (mx - x0) + 2 * t * (x1 - mx)
        dy = 2 * (1 - t) * (my - y0) + 2 * t * (y1 - my)
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        w = wmax * math.sin(math.pi * t)
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def flame(f: Frame, c, s, col, sec, dark, glow):
    outer = [(0, -1.0), (0.22, -0.52), (0.48, -0.78), (0.5, -0.22), (0.64, 0.12), (0.58, 0.52), (0.32, 0.84),
             (0, 0.95), (-0.32, 0.84), (-0.58, 0.52), (-0.64, 0.12), (-0.5, -0.28), (-0.42, -0.66), (-0.18, -0.42)]
    f.polygon(_map(c, s, outer), fill=col, glow=glow)
    f.polygon(_map(c, s, [(0, -0.22), (0.22, 0.2), (0.27, 0.5), (0, 0.74), (-0.27, 0.5), (-0.22, 0.2)]), fill=dark)
    f.polygon(_map(c, s, [(0, 0.12), (0.11, 0.4), (0, 0.58), (-0.11, 0.4)]), fill=sec, glow=glow and sec)


def four_arms(f: Frame, c, s, col, sec, dark, glow):
    arm = [(0.34, -0.1), (0.74, -0.1), (0.74, -0.19), (1.0, -0.19), (1.0, 0.19), (0.74, 0.19), (0.74, 0.1), (0.34, 0.1)]
    for ang in (-38, 38, 142, 218):
        f.polygon(_map(c, s, arm, ang), fill=col, glow=glow)
    hexa = [(0.4 * math.cos(math.radians(a)), 0.4 * math.sin(math.radians(a))) for a in range(30, 390, 60)]
    f.polygon(_map(c, s, hexa), fill=col, glow=glow)
    f.polygon(_map(c, s, [(-0.2, -0.08), (0, 0.12), (0.2, -0.08), (0.2, 0.06), (0, 0.26), (-0.2, 0.06)]), fill=dark)


def bolt(f: Frame, c, s, col, sec, dark, glow):
    f.polygon(_map(c, s, [(0.3, -1.0), (-0.32, 0.08), (0.04, 0.08), (-0.22, 1.0), (0.56, -0.22), (0.16, -0.22), (0.5, -1.0)]),
              fill=col, glow=glow)
    for y, x0 in ((-0.42, -0.95), (0.0, -1.0), (0.42, -0.9)):
        f.line(_map(c, s, [(x0, y), (x0 + 0.42, y)]), sec, width=max(1.0, s * 0.09), glow=glow and sec)


def crystal(f: Frame, c, s, col, sec, dark, glow):
    f.polygon(_map(c, s, [(-0.55, -0.6), (0.55, -0.6), (0.95, -0.12), (0, 1.0), (-0.95, -0.12)]), fill=col, glow=glow)
    w = max(1.0, s * 0.05)
    f.line(_map(c, s, [(-0.95, -0.12), (0.95, -0.12)]), dark, w)
    f.line(_map(c, s, [(-0.55, -0.6), (-0.3, -0.12), (0, -0.6), (0.3, -0.12), (0.55, -0.6)]), dark, w)
    f.line(_map(c, s, [(-0.3, -0.12), (0, 1.0), (0.3, -0.12)]), dark, w)
    f.polygon(_map(c, s, [(-0.45, -0.52), (-0.2, -0.52), (-0.32, -0.2)]), fill=sec)


def claws(f: Frame, c, s, col, sec, dark, glow):
    for k in (-1, 0, 1):
        x = k * 0.44
        f.polygon(_map(c, s, _slash(x + 0.28, -0.95 + abs(k) * 0.12, x - 0.28, 0.95 - abs(k) * 0.12, 0.18, 0.16)),
                  fill=col, glow=glow)


def circuit(f: Frame, c, s, col, sec, dark, glow):
    f.ring(c, s * 0.86, col, max(1.5, s * 0.12), glow=glow)
    w = max(1.0, s * 0.09)
    traces = [[(0, -0.22), (0, -0.5), (0.36, -0.5)], [(-0.19, 0.11), (-0.45, 0.26), (-0.45, 0.52)], [(0.19, 0.11), (0.5, 0.11)]]
    for tr in traces:
        f.line(_map(c, s, tr), col, w, glow=glow)
        end = _map(c, s, [tr[-1]])[0]
        f.circle(end, s * 0.1, fill=sec, glow=glow and sec)
    f.circle(c, s * 0.24, fill=col, glow=glow)
    f.circle(c, s * 0.1, fill=dark)


def ghost(f: Frame, c, s, col, sec, dark, glow):
    pts = [(0.62 * math.cos(math.radians(a)), -0.25 + 0.62 * math.sin(math.radians(a))) for a in range(180, 361, 15)]
    pts += [(0.62, 0.5), (0.42, 0.88), (0.22, 0.6), (0, 0.95), (-0.22, 0.6), (-0.42, 0.88), (-0.62, 0.5)]
    f.polygon(_map(c, s, pts), fill=col, glow=glow)
    eye = _map(c, s, [(0, -0.18)])[0]
    f.circle(eye, s * 0.27, fill=dark)
    f.circle(eye, s * 0.1, fill=sec, glow=glow and sec)


def sphere(f: Frame, c, s, col, sec, dark, glow):
    f.circle(c, s * 0.95, fill=col, glow=glow)
    w = max(1.0, s * 0.07)
    for side in (-1, 1):
        f.line(_map(c, s, [(side * 0.42 * math.sin(math.pi * u / 10), -0.93 + 1.86 * u / 10) for u in range(11)]), dark, w)
    f.line(_map(c, s, [(-0.93, 0.0), (-0.42, 0.06), (0.42, 0.06), (0.93, 0.0)]), dark, w)
    f.circle(c, s * 0.22, fill=dark)
    f.circle(c, s * 0.1, fill=sec)


def wings(f: Frame, c, s, col, sec, dark, glow):
    for side in (-1, 1):
        f.polygon(_map(c, s, _ellipse(side * 0.48, -0.2, 0.5, 0.2, side * -30)), fill=col, glow=glow)
        f.polygon(_map(c, s, _ellipse(side * 0.42, 0.3, 0.4, 0.15, side * 25)), fill=col, glow=glow)
        f.line(_map(c, s, [(side * 0.05, -0.5), (side * 0.28, -0.92)]), col, max(1.0, s * 0.06))
        f.circle(_map(c, s, [(side * 0.28, -0.92)])[0], s * 0.1, fill=sec, glow=glow and sec)
    f.polygon(_map(c, s, _ellipse(0, 0.05, 0.13, 0.6)), fill=sec)


def fin(f: Frame, c, s, col, sec, dark, glow):
    f.polygon(_map(c, s, [(-0.85, 0.2), (-0.2, -0.35), (0.1, -0.98), (0.3, -0.45), (0.85, 0.2)]), fill=col, glow=glow)
    f.polygon(_map(c, s, [(-0.9, 0.32), (0.9, 0.32), (0.9, 0.42), (-0.9, 0.42)]), fill=col, glow=glow)
    n, x0, w = 6, -0.84, 0.28
    for i in range(n):
        x = x0 + i * w
        f.polygon(_map(c, s, [(x, 0.42), (x + w * 0.9, 0.42), (x + w * 0.45, 0.88)]), fill=sec, glow=glow and sec)


DRAWERS = {fn.__name__: fn for fn in (flame, four_arms, bolt, crystal, claws, circuit, ghost, sphere, wings, fin)}


def draw_emblem(f: Frame, name: str, c, size: float, color, secondary, dark="#000000", glow: bool = True) -> None:
    DRAWERS[name](f, c, size, color, secondary, dark, glow)
