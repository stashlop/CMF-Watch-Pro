"""Watch-face preview: live Tkinter window or headless PNG export.

    python -m watchface.preview                                  # GUI
    python -m watchface.preview --list
    python -m watchface.preview --face activity_rings --export out.png [--time 10:09:30]

The GUI re-reads the selected face JSON whenever the file changes on disk, so
you can edit faces in an editor and watch the preview update.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from watchface.display import WATCH_PRO_1
from watchface.render import WatchState, load_face, render

FACES_DIR = Path(__file__).resolve().parent / "faces"
PREVIEW_DIR = Path(__file__).resolve().parents[1] / "data" / "previews"


def list_faces() -> dict[str, Path]:
    return {p.stem: p for p in sorted(FACES_DIR.glob("*.json"))}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    t = datetime.strptime(value, "%H:%M:%S" if value.count(":") == 2 else "%H:%M").time()
    return datetime.combine(datetime.now().date(), t)


class PreviewApp:
    def __init__(self, root, faces: dict[str, Path], initial: str, fixed_time: datetime | None) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.root, self.faces = tk, root, faces
        self.fixed_time = fixed_time
        self._face, self._face_mtime, self._photo = None, None, None

        root.title(f"Watch Face Preview - {WATCH_PRO_1.name}")
        root.configure(bg="#1b1b1b")

        self.canvas = tk.Canvas(root, width=WATCH_PRO_1.width + 40, height=WATCH_PRO_1.height + 40,
                                bg="#1b1b1b", highlightthickness=0)
        self.canvas.grid(row=0, column=0, padx=10, pady=10)

        panel = ttk.Frame(root, padding=10)
        panel.grid(row=0, column=1, sticky="ns")

        ttk.Label(panel, text="Face").pack(anchor="w")
        self.face_var = tk.StringVar(value=initial)
        ttk.Combobox(panel, textvariable=self.face_var, values=list(faces), state="readonly").pack(fill="x", pady=(0, 12))
        self.face_var.trace_add("write", lambda *_: self._invalidate())

        self.battery = self._slider(panel, "Battery %", 0, 100, 76)
        self.steps = self._slider(panel, "Steps", 0, 15000, 6420)
        self.heart = self._slider(panel, "Heart rate", 40, 200, 72)

        ttk.Button(panel, text="Export PNG", command=self.export).pack(fill="x", pady=(16, 4))
        self.status = ttk.Label(panel, text="", wraplength=200, foreground="#777")
        self.status.pack(anchor="w")

        self.tick()

    def _slider(self, parent, label, lo, hi, init):
        from tkinter import ttk

        var = self.tk.IntVar(value=init)
        ttk.Label(parent, text=label).pack(anchor="w")
        ttk.Scale(parent, from_=lo, to=hi, variable=var, command=lambda v: var.set(int(float(v)))).pack(fill="x")
        ttk.Label(parent, textvariable=var).pack(anchor="e", pady=(0, 8))
        return var

    def _invalidate(self) -> None:
        self._face_mtime = None

    def state(self) -> WatchState:
        return WatchState(now=self.fixed_time or datetime.now(), battery=self.battery.get(),
                          steps=self.steps.get(), heart_rate=self.heart.get())

    def current_face(self) -> dict:
        path = self.faces[self.face_var.get()]
        mtime = path.stat().st_mtime
        if mtime != self._face_mtime:
            try:
                self._face, self._face_mtime = load_face(path), mtime
                self.status.config(text=f"Loaded {path.name}")
            except ValueError as exc:  # bad JSON while mid-edit: keep the last good face
                self.status.config(text=f"{path.name}: {exc}")
        return self._face

    def tick(self) -> None:
        from PIL import ImageTk

        face = self.current_face()
        if face is not None:
            try:
                img = render(face, self.state())
                self._photo = ImageTk.PhotoImage(img)
                self.canvas.delete("all")
                self.canvas.create_image(20, 20, anchor="nw", image=self._photo)
            except Exception as exc:
                self.status.config(text=f"Render error: {exc}")
        self.root.after(500, self.tick)

    def export(self) -> None:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        out = PREVIEW_DIR / f"{self.face_var.get()}_{datetime.now():%Y%m%d_%H%M%S}.png"
        render(self.current_face(), self.state()).save(out)
        self.status.config(text=f"Saved {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--face", default="minimal_digital", help="face name (file stem in watchface/faces)")
    parser.add_argument("--export", type=Path, help="render once to this PNG and exit (no GUI)")
    parser.add_argument("--time", help="freeze clock at HH:MM[:SS]")
    parser.add_argument("--list", action="store_true", help="list available faces")
    args = parser.parse_args(argv)

    faces = list_faces()
    if args.list:
        print("\n".join(faces))
        return 0
    if args.face not in faces:
        parser.error(f"unknown face '{args.face}'. Available: {', '.join(faces)}")

    fixed = _parse_time(args.time)
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        render(load_face(faces[args.face]), WatchState(now=fixed or datetime.now())).save(args.export)
        print(f"Saved {args.export}")
        return 0

    import tkinter as tk

    root = tk.Tk()
    PreviewApp(root, faces, args.face, fixed)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
