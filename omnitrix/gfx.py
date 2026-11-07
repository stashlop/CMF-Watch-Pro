"""Drawing primitives for the Omnitrix renderer.

A ``Frame`` holds two layers at SS x supersampling:
  * ``img``  - the normal picture
  * ``glow`` - shapes that should bloom; it is downscaled, blurred and added on top
All public coordinates are in 1x screen pixels (410 x 502).
"""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from watchface.display import WATCH_PRO_1

W, H = WATCH_PRO_1.width, WATCH_PRO_1.height
SS = 2

RGB = tuple[int, int, int]


def rgb(c) -> RGB:
    if isinstance(c, tuple):
        return c
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t: float) -> RGB:
    a, b = rgb(a), rgb(b)
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def scale(c, k: float) -> RGB:
    return tuple(max(0, min(255, int(v * k))) for v in rgb(c))


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out_cubic(x: float) -> float:
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = clamp01(x)
    return 4 * x**3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x: float) -> float:
    x = clamp01(x)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def phase(t: float, start: float, end: float) -> float:
    """0..1 progress of t through [start, end]."""
    return clamp01((t - start) / (end - start))


def polar(c, r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


@lru_cache(maxsize=256)
def font(name: str, size: int, variation: str | None = None):
    try:
        f = ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default(size=size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except (OSError, ValueError):
            pass
    return f


@lru_cache(maxsize=4)
def screen_mask() -> Image.Image:
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, W - 1, H - 1], radius=WATCH_PRO_1.corner_radius, fill=255)
    return m


@lru_cache(maxsize=32)
def disc_mask(r_px: int) -> Image.Image:
    m = Image.new("L", (2 * r_px, 2 * r_px), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 2 * r_px - 1, 2 * r_px - 1], fill=255)
    return m


class Frame:
    def __init__(self, background: Image.Image | None = None, bg="#000000") -> None:
        self.img = background.copy() if background is not None else Image.new("RGB", (W * SS, H * SS), rgb(bg))
        self.glow = Image.new("RGB", (W * SS, H * SS), (0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.g = ImageDraw.Draw(self.glow)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def pts(points) -> list[tuple[float, float]]:
        return [(x * SS, y * SS) for x, y in points]

    @staticmethod
    def box(c, r: float) -> list[float]:
        return [(c[0] - r) * SS, (c[1] - r) * SS, (c[0] + r) * SS, (c[1] + r) * SS]

    def _glow(self, glow, color):
        if glow is None or glow is False:
            return None
        return rgb(color) if glow is True else rgb(glow)

    # -- shapes --------------------------------------------------------------
    def circle(self, c, r, fill=None, outline=None, width=1.0, glow=None):
        w = max(1, int(width * SS))
        self.d.ellipse(self.box(c, r), fill=fill and rgb(fill), outline=outline and rgb(outline), width=w)
        g = self._glow(glow, outline or fill)
        if g:  # outlined shapes glow along the outline only
            self.g.ellipse(self.box(c, r), fill=None if outline else g, outline=g if outline else None, width=w)

    def ring(self, c, r, color, width, glow=None):
        """Circle stroke centred on radius r."""
        self.circle(c, r + width / 2, outline=color, width=width, glow=glow)

    def arc(self, c, r, start, end, color, width, glow=None):
        """Arc stroke centred on radius r; angles in degrees, 0 = 3 o'clock, clockwise."""
        b = self.box(c, r + width / 2)
        w = max(1, int(width * SS))
        self.d.arc(b, start, end, fill=rgb(color), width=w)
        g = self._glow(glow, color)
        if g:
            self.g.arc(b, start, end, fill=g, width=w)

    def polygon(self, points, fill=None, outline=None, width=1.0, glow=None):
        p = self.pts(points)
        w = max(1, int(width * SS))
        self.d.polygon(p, fill=fill and rgb(fill), outline=outline and rgb(outline), width=w)
        g = self._glow(glow, outline or fill)
        if g:
            self.g.polygon(p, fill=None if outline else g, outline=g if outline else None, width=w)

    def line(self, points, color, width=1.0, glow=None):
        p = self.pts(points)
        w = max(1, int(width * SS))
        self.d.line(p, fill=rgb(color), width=w, joint="curve")
        g = self._glow(glow, color)
        if g:
            self.g.line(p, fill=g, width=w, joint="curve")

    def rect(self, xy, fill=None, outline=None, width=1.0, radius=0, glow=None):
        b = [v * SS for v in xy]
        w = max(1, int(width * SS))
        self.d.rounded_rectangle(b, radius=radius * SS, fill=fill and rgb(fill), outline=outline and rgb(outline), width=w)
        g = self._glow(glow, outline or fill)
        if g:
            self.g.rounded_rectangle(b, radius=radius * SS, fill=None if outline else g, outline=g if outline else None, width=w)

    def text(self, xy, s, size, color, font_name="bahnschrift.ttf", variation=None, anchor="mm", glow=None, spacing=0):
        f = font(font_name, int(size * SS), variation)
        x, y = xy[0] * SS, xy[1] * SS
        if spacing:
            # manual letter spacing for the "tech" look
            widths = [f.getlength(ch) + spacing * SS for ch in s]
            total = sum(widths) - spacing * SS
            x0 = x - total / 2 if anchor[0] == "m" else x - total if anchor[0] == "r" else x
            for ch, cw in zip(s, widths):
                self.d.text((x0, y), ch, font=f, fill=rgb(color), anchor="l" + anchor[1])
                g = self._glow(glow, color)
                if g:
                    self.g.text((x0, y), ch, font=f, fill=g, anchor="l" + anchor[1])
                x0 += cw
            return
        self.d.text((x, y), s, font=f, fill=rgb(color), anchor=anchor)
        g = self._glow(glow, color)
        if g:
            self.g.text((x, y), s, font=f, fill=g, anchor=anchor)

    def paste_disc(self, c, tile: Image.Image):
        """Paste a square SS-resolution tile clipped to a circle centred at c."""
        r_px = tile.width // 2
        self.img.paste(tile, (int(c[0] * SS - r_px), int(c[1] * SS - r_px)), disc_mask(r_px))

    # -- output --------------------------------------------------------------
    def finish(self, glow: float = 1.0, fade: float = 1.0, post=None) -> Image.Image:
        out = self.img.reduce(SS)
        if glow > 0:
            g = self.glow.reduce(SS * 2)
            wide = g.filter(ImageFilter.GaussianBlur(7))
            tight = g.filter(ImageFilter.GaussianBlur(2))
            g = ImageChops.add(wide, tight)
            if glow != 1.0:
                g = g.point(lambda v: min(255, int(v * glow)))
            out = ImageChops.add(out, g.resize((W, H), Image.BILINEAR))
        if post is not None:
            out = post(out)
        if fade < 1.0:
            out = Image.blend(Image.new("RGB", out.size, (0, 0, 0)), out, clamp01(fade))
        return Image.composite(out, Image.new("RGB", out.size, (0, 0, 0)), screen_mask())
