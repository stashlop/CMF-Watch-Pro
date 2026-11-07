"""Build the Omnitrix asset pack for the ESP32-S3-Touch-AMOLED-2.06 firmware.

    python -m esp32.assets [--quality 82] [--fps 10] [--preview]

Everything is rendered by the same ``omnitrix`` code as the Design Studio, then split into:

* static bases (home + 10 alien faces) as JPEG, with the clock/date/label left out,
* battery-meter crops (raw RGB565), so the firmware lights 0-16 segments without 17 copies of each face,
* glyph sprites per theme (RGB565, added onto the background), so the firmware draws the live clock in the
  Omnitrix style,
* frame sequences (JPEG) for the alien dial, the selection burst, the info cards and the transformation.

Outputs go to ``esp32/firmware/data`` (the LittleFS image) and ``esp32/firmware/src/assets_manifest.h``.
``compose()`` reproduces what the firmware draws, so the result can be checked on the PC (``--preview``).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import math
import shutil
import struct
import sys
import zlib
from array import array
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from omnitrix import screens as S
from omnitrix.aliens import ALIENS, Alien
from omnitrix.emblems import draw_emblem
from omnitrix.fx import draw_fx
from omnitrix.gfx import SS, H, W, Frame, font, mix, rgb, scale

ROOT = Path(__file__).resolve().parent
FW_DIR = ROOT / "firmware"
DATA_DIR = FW_DIR / "data"
MANIFEST = FW_DIR / "src" / "assets_manifest.h"
PREVIEW_DIR = ROOT.parent / "data" / "exports" / "esp32"

T = 1.0  # frozen ambient animation time for static screens
SEGS = 16  # battery meter segments (screens.draw_meter)
SEL_SUB = 3  # selector frames per alien step (dial turning animation)
CONFIRM_FRAMES = 8
XF_SHARED_END = 2.0  # transform() is alien-independent before this time
XF_END = 3.7  # after this the firmware cross-fades to the live face itself
FADE_MS = 500
LOW_BATTERY = 20  # draw_meter turns red at or below this
LOW_RED = "#FF3B30"
FLASH_BUDGET = 0xCF0000 - 200_000  # LittleFS partition (partitions.csv) minus filesystem overhead

DIGITS = "0123456789"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ---- themes and text spots -------------------------------------------------------
@dataclass(frozen=True)
class Theme:
    index: int
    key: str
    name: str
    color: str  # accent
    bg: str
    clock_variation: str
    alien: Alien | None

    def label(self, battery: int) -> str:
        return f"ENERGY {battery}%" if self.alien is None else f"{self.alien.name}  /  ENERGY {battery}%"


def themes(style: S.Style | None = None) -> list[Theme]:
    style = style or S.Style()
    out = [Theme(0, "home", "OMNITRIX", style.omni_green, style.background, "SemiBold Condensed", None)]
    for i, a in enumerate(ALIENS, start=1):
        out.append(Theme(i, a.key, a.name, a.accent, a.bg_tint, a.time_variation, a))
    return out


@dataclass(frozen=True)
class TextSpot:
    """Where screens.py draws a live string. anchor: 'mm' (centre/middle) or 'rs' (right/baseline)."""

    key: str
    x: int
    y: int
    size: int
    spacing: int
    anchor: str
    charset: str


SPOTS = {
    "clock": TextSpot("clock", 205, 430, 70, 0, "mm", DIGITS + ":"),  # draw_clock
    "sec": TextSpot("sec", 316, 446, 20, 0, "rs", DIGITS),
    "date": TextSpot("date", 205, 31, 18, 2, "mm", UPPER + DIGITS + " "),  # draw_date
    "label": TextSpot("label", 205, 488, 12, 2, "mm", UPPER + DIGITS + " /%"),  # _bottom_label
}


def spot_style(th: Theme, spot: str, style: S.Style):
    """(colour, glow colour or None, font variation) exactly as screens.py uses them."""
    c = th.color
    if spot == "clock":
        return mix(c, "#ffffff", 0.82), scale(c, 0.8), th.clock_variation
    if spot == "sec":
        return rgb(c), None, "SemiBold"
    if spot == "date":
        return mix(c, "#ffffff", 0.55), None, "SemiBold"
    return mix(th.bg, c, 0.6), None, "SemiBold"


def date_text(now: datetime) -> str:
    return now.strftime("%a  %d %b").upper()


# ---- static bases ------------------------------------------------------------------
def _date_decor(f: Frame, color, bg):
    """draw_date without its text."""
    dim = mix(bg, color, 0.5)
    for sgn in (-1, 1):
        x0, x1 = 205 + sgn * 78, 205 + sgn * 140
        f.line([(x0, 31), (x1, 31)], dim, 1.5)
        f.polygon([(x1, 27), (x1 + sgn * 5, 31), (x1, 35), (x1 - sgn * 5, 31)], fill=color, glow=color)


def _meter(f: Frame, color, seg_color, lit: int, t: float, bg):
    """screens.draw_meter with the segment colour and lit count given explicitly."""
    for i in range(SEGS):
        a0 = 133 + i * 6
        on = i < lit
        sc = seg_color if on else mix(bg, seg_color, 0.13)
        f.arc(S.C, S.R_METER, a0, a0 + 4.4, sc, 9, glow=sc if on else None)
    for i in range(12):
        a0 = -46 + (11 - i) * 8
        b = 0.15 + 0.85 * max(0.0, math.sin(i * 0.55 - t * 5)) ** 3
        sc = mix(bg, color, b)
        f.arc(S.C, S.R_METER, a0, a0 + 5, sc, 6, glow=sc if b > 0.5 else None)


def base(th: Theme, lit: int, red: bool, style: S.Style | None = None, t: float = T) -> Image.Image:
    """Home / alien face without the clock, seconds, date text and bottom label."""
    style = style or S.Style()
    c, bg, g = th.color, th.bg, style.omni_green
    seg = LOW_RED if red else c
    f = Frame(S.background(bg, c, style.hex_grid))
    if th.alien is None:
        _date_decor(f, c, bg)
        S.draw_ring(f, style, c, t)
        _meter(f, c, seg, lit, t, bg)
        S.draw_bezel(f, style, c, t)
        S.draw_core(f, c, t)
        S.draw_plate(f, c, bg)
        S.mini_hourglass(f, (96, 432), 13, c)
    else:
        a = th.alien
        draw_fx(f, a, t, 0.55, S.C)
        _date_decor(f, c, bg)
        S.draw_ring(f, style, c, t, bg=bg)
        _meter(f, c, seg, lit, t, bg)
        S.draw_bezel(f, style, c, t)
        S.draw_core(f, c, t, rim=g)
        S.draw_plate(f, c, bg)
        draw_emblem(f, a.emblem, (96, 432), 15, c, a.secondary, mix(bg, c, 0.05))
    return f.finish(style.glow)  # no whole-image post (Upgrade's glitch would shift a static face)


def battery_lit(battery: int) -> tuple[int, bool]:
    """Lit segments and red flag, as draw_meter computes them (no .5 ties occur for integer percentages)."""
    battery = max(0, min(100, battery))
    return (battery * SEGS + 50) // 100, battery <= LOW_BATTERY


RED_MAX_LIT = battery_lit(LOW_BATTERY)[0]  # the meter is red only up to this many segments


# ---- binary encoders -----------------------------------------------------------------
def rgb565(img: Image.Image) -> bytes:
    raw = img.convert("RGB").tobytes()
    px = array("H", (((raw[i] >> 3) << 11) | ((raw[i + 1] >> 2) << 5) | (raw[i + 2] >> 3) for i in range(0, len(raw), 3)))
    if sys.byteorder != "little":
        px.byteswap()
    return px.tobytes()


def from565(v: int) -> tuple[int, int, int]:
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def jpeg(img: Image.Image, quality: int, full_chroma: bool) -> bytes:
    """Baseline JPEG. Static screens keep 4:4:4 (clean thin glows); animation frames use 4:2:0 to fit the flash."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality, subsampling=0 if full_chroma else 2, optimize=True)
    return buf.getvalue()


ZMAGIC = b"OZ1\0"


def deflate(data: bytes) -> bytes:
    """'OZ1\\0', u32 raw length, zlib stream (the firmware inflates it with the ROM's miniz)."""
    return ZMAGIC + struct.pack("<I", len(data)) + zlib.compress(data, 9)


def inflate(data: bytes) -> bytes:
    if data[:4] != ZMAGIC:
        return data
    raw = zlib.decompress(data[8:])
    assert len(raw) == struct.unpack_from("<I", data, 4)[0]
    return raw


def _changed_box(a: Image.Image, b: Image.Image):
    """Bounding box of the pixels where any channel differs (None if identical)."""
    return ImageChops.difference(a, b).getbbox()


def _patch(img: Image.Image, box) -> bytes:
    x0, y0, x1, y1 = box
    return struct.pack("<4H", x0, y0, x1 - x0, y1 - y0) + rgb565(img.crop(box))


def meter_pack(th: Theme, style: S.Style) -> tuple[bytes, Image.Image]:
    """(meter file, unlit base image).

    The meter is stored as a chain of patches. Patch k holds image(k lit) inside the box where it differs from
    image(k-1 lit), so pasting patches 1..n over the unlit base gives image(n lit) exactly, glow included.
    File: 'OMT2', u8 normal count (16), u8 red count, u16 0, then patches (x, y, w, h u16 + RGB565 pixels):
    normal 1..16, then red 0 (unlit red over the unlit base), red 1..RED_MAX_LIT.
    """
    normal = [base(th, k, False, style) for k in range(SEGS + 1)]
    red = [base(th, k, True, style) for k in range(RED_MAX_LIT + 1)]
    patches = []
    for chain, first_prev in ((normal, None), (red, normal[0])):
        prev = first_prev
        for k, img in enumerate(chain):
            if prev is not None:
                box = _changed_box(prev, img) or (0, 0, 1, 1)
                patches.append(_patch(img, box))
            prev = img
    head = b"OMT2" + struct.pack("<BBH", SEGS, RED_MAX_LIT + 1, 0)
    return head + b"".join(patches), normal[0]


def glyph(ch: str, size: int, variation: str, color, glow, style: S.Style):
    """One character rendered like Frame.text + Frame.finish. Returns (image, xoff, yoff, advance)."""
    f = font(style.font, int(size * SS), variation)
    adv = f.getlength(ch) / SS
    l, t, r, b = f.getbbox(ch, anchor="ls")
    if r <= l or b <= t:
        return None, 0, 0, adv
    pad = 18 if glow else 2
    x0, y0 = math.floor(l / SS) - pad, math.floor(t / SS) - pad
    x1, y1 = math.ceil(r / SS) + pad, math.ceil(b / SS) + pad
    w, h = x1 - x0, y1 - y0
    w, h = w + (w % 2), h + (h % 2)  # glow pass reduces by 2*SS
    img = Image.new("RGB", (w * SS, h * SS), (0, 0, 0))
    from PIL import ImageDraw

    ImageDraw.Draw(img).text((-x0 * SS, -y0 * SS), ch, font=f, fill=rgb(color), anchor="ls")
    out = img.reduce(SS)
    if glow:
        gl = Image.new("RGB", img.size, (0, 0, 0))
        ImageDraw.Draw(gl).text((-x0 * SS, -y0 * SS), ch, font=f, fill=rgb(glow), anchor="ls")
        g = gl.reduce(SS * 2)
        g = ImageChops.add(g.filter(ImageFilter.GaussianBlur(7)), g.filter(ImageFilter.GaussianBlur(2)))
        if style.glow != 1.0:
            g = g.point(lambda v: min(255, int(v * style.glow)))
        out = ImageChops.add(out, g.resize((w, h), Image.BILINEAR))
    bb = out.getbbox()
    if bb is None:
        return None, 0, 0, adv
    return out.crop(bb), x0 + bb[0], y0 + bb[1], adv


def mid_offset(size: int, variation: str, style: S.Style) -> float:
    """Baseline offset below y for Pillow's vertical 'm' anchor."""
    asc, desc = font(style.font, int(size * SS), variation).getmetrics()
    return (asc - desc) / 2 / SS


def font_pack(th: Theme, spot: TextSpot, style: S.Style) -> bytes:
    """'OFN1', u16 count, i16 mid_q4, u16 0, u16 0, then 16-byte glyph records, then RGB565 pixels."""
    color, glow, var = spot_style(th, spot.key, style)
    recs, blob = [], bytearray()
    for ch in spot.charset:
        img, xo, yo, adv = glyph(ch, spot.size, var, color, glow, style)
        recs.append((ch, adv, xo, yo, img))
    header = 4 + 8 + 16 * len(recs)
    table = bytearray()
    for ch, adv, xo, yo, img in recs:
        w, h = (img.size if img else (0, 0))
        table += struct.pack("<BBhhhHHI", ord(ch), 0, round(adv * 16), xo, yo, w, h, header + len(blob))
        if img:
            blob += rgb565(img)
    mid = round(mid_offset(spot.size, var, style) * 16)
    return b"OFN1" + struct.pack("<HhHH", len(recs), mid, 0, 0) + bytes(table) + bytes(blob)


# ---- reading packs back (PC-side model of the firmware compositor) -----------------
def parse_font(data: bytes) -> dict:
    data = inflate(data)
    n, mid, _ = struct.unpack_from("<HhH", data, 4)
    glyphs = {}
    for i in range(n):
        ch, _, adv, xo, yo, w, h, off = struct.unpack_from("<BBhhhHHI", data, 12 + 16 * i)
        img = None
        if w and h:
            px = struct.unpack_from(f"<{w * h}H", data, off)
            img = Image.new("RGB", (w, h))
            img.putdata([from565(v) for v in px])
        glyphs[chr(ch)] = (adv, xo, yo, img)  # advance in 1/16 px
    return {"mid_q4": mid, "glyphs": glyphs}


def parse_meter(data: bytes) -> dict:
    data = inflate(data)
    n_normal, n_red, _ = struct.unpack_from("<BBH", data, 4)
    off, patches = 8, []
    for _ in range(n_normal + n_red):
        x, y, w, h = struct.unpack_from("<4H", data, off)
        px = struct.unpack_from(f"<{w * h}H", data, off + 8)
        img = Image.new("RGB", (w, h))
        img.putdata([from565(v) for v in px])
        patches.append((x, y, img))
        off += 8 + 2 * w * h
    return {"normal": patches[:n_normal], "red": patches[n_normal:]}


def text_layout(fnt: dict, spot: TextSpot, s: str) -> list[tuple[int, int, Image.Image]]:
    """Glyph positions, in the firmware's integer 1/16-pixel arithmetic (text.cpp: omniTextLayout)."""
    sp = spot.spacing * 16
    total = sum(fnt["glyphs"][ch][0] + sp for ch in s) - (sp if s else 0)
    x = spot.x * 16 - (total // 2 if spot.anchor[0] == "m" else total)
    by = (spot.y * 16 + fnt["mid_q4"] + 8) >> 4 if spot.anchor[1] == "m" else spot.y
    out = []
    for ch in s:
        adv, xo, yo, g = fnt["glyphs"][ch]
        if g:
            out.append(((x >> 4) + xo, by + yo, g))
        x += adv + sp
    return out


def draw_text(img: Image.Image, fnt: dict, spot: TextSpot, s: str) -> None:
    """Additive glyph blit, as the firmware does it (per-channel add with saturation)."""
    for px, py, g in text_layout(fnt, spot, s):
        region = img.crop((px, py, px + g.width, py + g.height))
        img.paste(ImageChops.add(region, g), (px, py))


def apply_meter(img: Image.Image, m: dict, battery: int) -> None:
    lit, red = battery_lit(battery)
    chain = m["red"][: lit + 1] if red else m["normal"][:lit]
    for x, y, p in chain:
        img.paste(p, (x, y))


def compose(theme_index: int, now: datetime, battery: int, data_dir: Path = DATA_DIR) -> Image.Image:
    """What the firmware shows on the home (theme 0) or an alien face."""
    th = themes()[theme_index]
    img = Image.open(data_dir / "f" / f"{theme_index}.jpg").convert("RGB")
    apply_meter(img, parse_meter((data_dir / "m" / f"{theme_index}.mtr").read_bytes()), battery)
    for key, s in (("date", date_text(now)), ("clock", now.strftime("%H:%M")), ("sec", now.strftime("%S")),
                   ("label", th.label(battery))):
        draw_text(img, parse_font((data_dir / "t" / f"{theme_index}_{key}.fnt").read_bytes()), SPOTS[key], s)
    return img


# ---- build -------------------------------------------------------------------------
def _write(path: Path, data: bytes, sizes: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    sizes[path.parts[-2]] = sizes.get(path.parts[-2], 0) + len(data)


def build(quality: int = 82, fps: int = 10, out: Path = DATA_DIR, manifest: Path = MANIFEST, log=print) -> dict:
    style = S.Style()
    if out.exists():
        shutil.rmtree(out)
    sizes: dict = {}
    ths = themes(style)

    log("faces + meters + fonts")
    for th in ths:
        mtr, unlit = meter_pack(th, style)
        _write(out / "m" / f"{th.index}.mtr", deflate(mtr), sizes)
        _write(out / "f" / f"{th.index}.jpg", jpeg(unlit, quality, True), sizes)
        for key, spot in SPOTS.items():
            _write(out / "t" / f"{th.index}_{key}.fnt", deflate(font_pack(th, spot, style)), sizes)

    log("alien dial")
    n = len(ALIENS)
    for i in range(n):
        for k in range(SEL_SUB):
            _write(out / "s" / f"{i}_{k}.jpg", jpeg(S.selector(T, i + k / SEL_SUB, style=style), quality, False), sizes)

    log("selection burst + info cards")
    for i, a in enumerate(ALIENS):
        for k in range(CONFIRM_FRAMES):
            p = k / (CONFIRM_FRAMES - 1)
            img = S.select_confirm(T + p * S.CONFIRM_DURATION, p, i, style=style)
            _write(out / "c" / f"{i}_{k}.jpg", jpeg(img, quality, False), sizes)
        _write(out / "i" / f"{i}.jpg", jpeg(S.info(T, a, style=style), quality, True), sizes)

    log("transformation")
    n_shared = int(round(XF_SHARED_END * fps))
    n_total = int(round(XF_END * fps))
    for k in range(n_shared):
        _write(out / "x" / f"s_{k}.jpg", jpeg(S.transform(k / fps, ALIENS[0], style=style), quality, False), sizes)
    for i, a in enumerate(ALIENS):
        for k in range(n_shared, n_total):
            _write(out / "x" / f"{i}_{k - n_shared}.jpg", jpeg(S.transform(k / fps, a, style=style), quality, False), sizes)

    total = sum(sizes.values())
    build_id = hashlib.sha1(f"{datetime.now().isoformat()}{total}".encode()).hexdigest()[:10]
    (out / "build.txt").write_text(build_id, encoding="ascii")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(_manifest(build_id, fps, n_shared, n_total - n_shared, ths, style), encoding="ascii")
    log(f"total {total / 1e6:.2f} MB of {FLASH_BUDGET / 1e6:.1f} MB  " +
        "  ".join(f"{k}:{v / 1e6:.2f}" for k, v in sorted(sizes.items())))
    if total > FLASH_BUDGET:
        raise SystemExit(f"asset pack {total} bytes exceeds the LittleFS partition ({FLASH_BUDGET}); lower --quality/--fps")
    return {"build_id": build_id, "bytes": total, "sizes": sizes}


def _manifest(build_id: str, fps: int, n_shared: int, n_alien: int, ths: list[Theme], style: S.Style) -> str:
    names = ", ".join(f'"{t.name}"' for t in ths)
    spots = "\n".join(
        f"static const OmniSpot OMNI_SPOT_{k.upper()} = {{{s.x}, {s.y}, {s.spacing}, '{s.anchor[0]}', '{s.anchor[1]}'}};"
        for k, s in SPOTS.items())
    return f"""// Generated by `python -m esp32.assets`. Do not edit; rebuild the assets instead.
#pragma once
#include <stdint.h>

#define OMNI_BUILD_ID "{build_id}"
#define OMNI_N_ALIENS {len(ALIENS)}
#define OMNI_N_THEMES {len(ths)}
#define OMNI_SEGS {SEGS}
#define OMNI_LOW_BATTERY {LOW_BATTERY}
#define OMNI_SEL_SUB {SEL_SUB}
#define OMNI_CONFIRM_FRAMES {CONFIRM_FRAMES}
#define OMNI_CONFIRM_MS {int(S.CONFIRM_DURATION * 1000)}
#define OMNI_XF_FPS {fps}
#define OMNI_XF_SHARED {n_shared}
#define OMNI_XF_ALIEN {n_alien}
#define OMNI_FADE_MS {FADE_MS}

// layout from omnitrix/screens.py (1x pixels), used for touch hit-testing
#define OMNI_CX {S.C[0]}
#define OMNI_CY {S.C[1]}
#define OMNI_R_RING {S.R_RING}
#define OMNI_R_ORBIT {S.R_ORBIT}
#define OMNI_R_CORE {S.R_CORE}

struct OmniSpot {{ int16_t x, y; int8_t spacing; char h, v; }};  // h: 'm' centre / 'r' right, v: 'm' middle / 's' baseline
{spots}

// theme 0 = Omnitrix home, 1..{len(ALIENS)} = aliens in dial order
static const char *const OMNI_THEME_NAMES[OMNI_N_THEMES] = {{{names}}};
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--fps", type=int, default=10, help="transformation frame rate")
    ap.add_argument("--preview", action="store_true", help="also write PC previews of the composed faces")
    args = ap.parse_args(argv)
    res = build(args.quality, args.fps)
    if args.preview:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime(2026, 11, 7, 10, 9, 30)
        for th in themes():
            compose(th.index, now, 76).save(PREVIEW_DIR / f"face_{th.index}_{th.key}.png")
        print(f"previews in {PREVIEW_DIR}")
    print(f"build {res['build_id']}: {res['bytes'] / 1e6:.2f} MB -> {DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
