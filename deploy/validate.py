"""Check every exported face against the watch's (known) requirements."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageStat

from deploy import config


def _clock_bands():
    from omnitrix.watch_release import CLOCK_BANDS  # single source of truth for the layout

    return CLOCK_BANDS


def check_face(path: Path) -> dict:
    out: dict = {"file": path.name, "ok": False, "problems": []}
    if not path.exists():
        out["problems"].append("missing (run: python -m omnitrix.watch_release --all)")
        return out
    raw = path.read_bytes()
    out["bytes"] = len(raw)
    out["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:
        out["problems"].append(f"not a readable image: {exc}")
        return out

    p = out["problems"]
    if img.format != "PNG":
        p.append(f"format {img.format}, expected PNG")
    if img.size != config.DISPLAY_SIZE:
        p.append(f"size {img.size}, expected {config.DISPLAY_SIZE}")
    if img.mode != "RGB":
        p.append(f"mode {img.mode}, expected RGB without alpha")
    if len(raw) > config.MAX_FACE_BYTES:
        p.append(f"{len(raw)} bytes > {config.MAX_FACE_BYTES} self-imposed limit")

    if img.size == config.DISPLAY_SIZE:
        lum = img.convert("L")
        hist = lum.histogram()
        out["true_black_pct"] = round(100 * hist[0] / sum(hist), 1)
        if out["true_black_pct"] < 50:
            p.append(f"only {out['true_black_pct']}% true black (AMOLED target >= 50%)")
        for name, (y0, y1) in _clock_bands().items():
            mean = ImageStat.Stat(lum.crop((60, y0, 350, y1))).mean[0]
            out[f"{name}_band_mean"] = round(mean, 1)
            if mean >= 6:
                p.append(f"{name} clock band not dark (mean {mean:.1f})")
    out["ok"] = not p
    return out


def validate_all(faces_dir: Path = config.FACES_DIR) -> list[dict]:
    return [check_face(faces_dir / name) for name in config.FACE_FILES]
