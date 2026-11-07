"""Export Omnitrix assets to data/exports/omnitrix/.

    python -m omnitrix.export                 # everything
    python -m omnitrix.export --only faces|backgrounds|gifs|screens

Everything is 410 x 502 (the CMF Watch Pro 1 spec-sheet resolution). Whether the
CMF Watch app accepts these as photo faces is NOT verified yet; see
docs/hardware-capabilities.md. "backgrounds" leave the clock area empty for that use.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from omnitrix import screens as S
from omnitrix.aliens import ALIENS, Alien

EXPORT_DIR = Path(__file__).resolve().parents[1] / "data" / "exports" / "omnitrix"


def transform_gif(alien: Alien, path: Path, style: S.Style | None = None, data: S.WatchData | None = None,
                  fps: int = 20, hold: float = 1.0) -> Path:
    frames = []
    n = int((S.TRANSFORM_DURATION + hold) * fps)
    for i in range(n):
        t = i / fps
        frames.append(S.transform(t, alien, data, style) if t <= S.TRANSFORM_DURATION else S.alien_face(t, alien, data, style))
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=False)
    return path


def selector_gif(path: Path, style=None, data=None, fps: int = 20) -> Path:
    """Dial turning through every alien, with a confirm burst on the last one."""
    frames, t = [], 0.0
    for i in range(len(ALIENS)):
        for k in range(12):  # turn
            u = k / 12
            frames.append(S.selector(t, i + S.ease_in_out(u) if i < len(ALIENS) - 1 else float(i), data, style))
            t += 1 / fps
    for k in range(int(S.CONFIRM_DURATION * fps)):
        frames.append(S.select_confirm(t, k / (S.CONFIRM_DURATION * fps), len(ALIENS) - 1, data, style))
        t += 1 / fps
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
    return path


def export_all(only: str | None = None, out: Path = EXPORT_DIR, style=None, data=None, log=print) -> list[Path]:
    style, data = style or S.Style(), data or S.WatchData()
    written: list[Path] = []
    out.mkdir(parents=True, exist_ok=True)
    if only in (None, "screens"):
        for name, img in (("home", S.home(1.3, data, style)), ("selector", S.selector(1.3, 0.0, data, style))):
            p = out / f"{name}.png"
            img.save(p)
            written.append(p)
        for a in ALIENS:
            p = out / "info" / f"{a.key}.png"
            p.parent.mkdir(exist_ok=True)
            S.info(1.0, a, data, style).save(p)
            written.append(p)
    if only in (None, "faces"):
        (out / "faces").mkdir(exist_ok=True)
        for a in ALIENS:
            p = out / "faces" / f"{a.key}.png"
            S.alien_face(1.1, a, data, style).save(p)
            written.append(p)
    if only in (None, "backgrounds"):
        (out / "backgrounds").mkdir(exist_ok=True)
        p = out / "backgrounds" / "omnitrix_home.png"
        S.home_background(1.3, style).save(p)
        written.append(p)
        for a in ALIENS:
            p = out / "backgrounds" / f"{a.key}.png"
            S.alien_face(1.1, a, data, style, show_clock=False).save(p)
            written.append(p)
    if only in (None, "gifs"):
        for a in ALIENS:
            log(f"rendering transformation: {a.name}")
            written.append(transform_gif(a, out / "transform" / f"{a.key}.gif", style, data))
        written.append(selector_gif(out / "selector_dial.gif", style, data))
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=("faces", "backgrounds", "gifs", "screens"))
    ap.add_argument("--time", help="clock time HH:MM for the exported faces")
    args = ap.parse_args(argv)
    data = S.WatchData()
    if args.time:
        data.now = datetime.combine(datetime.now().date(), datetime.strptime(args.time, "%H:%M").time())
    files = export_all(args.only, data=data)
    print(f"{len(files)} files in {EXPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
