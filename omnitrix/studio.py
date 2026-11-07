"""Omnitrix Design Studio: live, interactive simulator of the Omnitrix on the
CMF Watch Pro 1 screen, with customisation and asset export.

    python -m omnitrix.studio

Simulated controls (the real watch does NOT support these; see docs/hardware-capabilities.md):
    B / Space / "Side button"   open the alien dial (or close it)
    Mouse wheel, drag, arrows    turn the dial
    Click the core / Enter       select the alien (confirm animation, then info screen)
    Click an orbit icon          jump to that alien
    Hold the mouse 0.6 s / T     transform
    Right-click / Esc            back
"""

from __future__ import annotations

import math
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import colorchooser, ttk

from PIL import Image, ImageDraw, ImageTk

from omnitrix import screens as S
from omnitrix.aliens import ALIENS
from omnitrix.export import EXPORT_DIR, export_all, transform_gif
from omnitrix.gfx import H, W

FONTS = ["bahnschrift.ttf", "AGENCYB.TTF", "OCRAEXT.TTF", "consolab.ttf", "segoeuib.ttf"]
HOLD_SECONDS = 0.6
PAD = 32  # bezel around the screen in the preview
BG = "#141414"


def _bezel_image() -> Image.Image:
    w, h = W + 2 * PAD, H + 2 * PAD
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, w - 3, h - 3], radius=120, fill="#232623", outline="#3a403a", width=3)
    d.rounded_rectangle([PAD - 8, PAD - 8, w - PAD + 7, h - PAD + 7], radius=98, fill="#050505", outline="#101210", width=2)
    return img


class Studio:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.style = S.Style()
        self.data = S.WatchData()
        self.t0 = time.perf_counter()
        self.mode = "home"
        self.mode_t = 0.0
        self.sel_target = 0.0
        self.sel_anim = 0.0
        self.active = None  # alien currently "transformed into"
        self.press = None  # (x, y, time) of mouse down
        self.drag_x = None
        self.frames = []

        root.title("Omnitrix Design Studio - CMF Watch Pro 1 (desktop simulator)")
        root.configure(bg=BG)
        self._ttk_style()

        left = tk.Frame(root, bg=BG)
        left.grid(row=0, column=0, padx=12, pady=12)
        self.canvas = tk.Canvas(left, width=W + 2 * PAD, height=H + 2 * PAD, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self._bezel = ImageTk.PhotoImage(_bezel_image())
        self.canvas.create_image(0, 0, anchor="nw", image=self._bezel)
        self.screen_item = self.canvas.create_image(PAD, PAD, anchor="nw")
        self.hold_item = self.canvas.create_arc(0, 0, 0, 0, start=90, extent=0, style="arc", outline="#39FF14", width=4)
        self.status = tk.Label(left, text="", bg=BG, fg="#7f8a7f", font=("Bahnschrift", 10), anchor="w", justify="left")
        self.status.pack(fill="x", pady=(6, 0))

        nb = ttk.Notebook(root)
        nb.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=12)
        nb.add(self._watch_tab(nb), text="Watch")
        nb.add(self._custom_tab(nb), text="Customise")
        nb.add(self._export_tab(nb), text="Export")

        c = self.canvas
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", lambda e: self.back())
        c.bind("<MouseWheel>", lambda e: self.turn(-1 if e.delta > 0 else 1))
        for key, fn in {"<b>": self.side_button, "<space>": self.side_button, "<Escape>": self.back,
                        "<Left>": lambda: self.turn(-1), "<Right>": lambda: self.turn(1),
                        "<Return>": self.enter, "<t>": self.transform}.items():
            root.bind(key, lambda e, fn=fn: fn())

        self.set_mode("home")
        self.tick()

    # ---- UI construction -----------------------------------------------------
    def _ttk_style(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.configure(".", background=BG, foreground="#d6e6d6", fieldbackground="#202420", font=("Bahnschrift", 10))
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background="#1d211d", foreground="#9fb09f", padding=(12, 6))
        st.map("TNotebook.Tab", background=[("selected", "#2a3a2a")], foreground=[("selected", "#39FF14")])
        st.configure("TButton", background="#1f2a1f", foreground="#d6ffd0", borderwidth=1, padding=6)
        st.map("TButton", background=[("active", "#2d4a2d")])
        st.configure("Accent.TButton", background="#1d5a12", foreground="#ffffff")
        st.configure("TLabelframe", background=BG, foreground="#39FF14")
        st.configure("TLabelframe.Label", background=BG, foreground="#39FF14")
        st.configure("TCheckbutton", background=BG)
        st.configure("Horizontal.TScale", background=BG)

    def _watch_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        hw = ttk.LabelFrame(f, text="Simulated controls", padding=8)
        hw.pack(fill="x")
        ttk.Button(hw, text="Side button  (B)", command=self.side_button).pack(fill="x", pady=2)
        ttk.Button(hw, text="Back  (Esc / right-click)", command=self.back).pack(fill="x", pady=2)
        ttk.Button(hw, text="Transform  (hold / T)", style="Accent.TButton", command=self.transform).pack(fill="x", pady=2)

        sc = ttk.LabelFrame(f, text="Screen", padding=8)
        sc.pack(fill="x", pady=(10, 0))
        for label, mode in (("Omnitrix home", "home"), ("Alien dial", "select"), ("Alien info", "info"), ("Alien watch face", "face")):
            ttk.Button(sc, text=label, command=lambda m=mode: self.goto(m)).pack(fill="x", pady=1)

        al = ttk.LabelFrame(f, text="Alien", padding=8)
        al.pack(fill="x", pady=(10, 0))
        self.alien_var = tk.StringVar(value=ALIENS[0].name)
        cb = ttk.Combobox(al, textvariable=self.alien_var, values=[a.name for a in ALIENS], state="readonly")
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", lambda e: self.pick_alien(cb.current()))

        dv = ttk.LabelFrame(f, text="Simulated data", padding=8)
        dv.pack(fill="x", pady=(10, 0))
        self.batt = tk.IntVar(value=self.data.battery)
        ttk.Label(dv, text="Battery %").pack(anchor="w")
        ttk.Scale(dv, from_=0, to=100, variable=self.batt, command=lambda v: self.batt.set(int(float(v)))).pack(fill="x")
        self.h24 = tk.BooleanVar(value=True)
        ttk.Checkbutton(dv, text="24-hour clock", variable=self.h24).pack(anchor="w", pady=(6, 0))
        self.freeze = tk.BooleanVar(value=False)
        ttk.Checkbutton(dv, text="Freeze time at 10:09:30", variable=self.freeze).pack(anchor="w")

        tk.Label(f, text=__doc__.split("Simulated controls")[1].split("\n", 1)[1].strip(), bg=BG, fg="#6f7a6f",
                 justify="left", font=("Consolas", 8)).pack(anchor="w", pady=(12, 0))
        return f

    def _custom_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        col = ttk.LabelFrame(f, text="Colours", padding=8)
        col.pack(fill="x")
        self.swatches = {}
        for label, attr in (("Background", "background"), ("Omnitrix green", "omni_green")):
            row = ttk.Frame(col)
            row.pack(fill="x", pady=2)
            sw = tk.Label(row, width=3, bg=getattr(self.style, attr), relief="solid", bd=1)
            sw.pack(side="left")
            ttk.Button(row, text=label, command=lambda a=attr: self.pick_colour(a)).pack(side="left", fill="x", expand=True, padx=(6, 0))
            self.swatches[attr] = sw

        ring = ttk.LabelFrame(f, text="Omnitrix ring", padding=8)
        ring.pack(fill="x", pady=(10, 0))
        self.ring_w = self._slider(ring, "Ring width", 2, 14, self.style.ring_width)
        self.glow = self._slider(ring, "Glow", 0, 2, self.style.glow)
        self.hexg = self._slider(ring, "Hex grid", 0, 1, self.style.hex_grid)

        ty = ttk.LabelFrame(f, text="Typography", padding=8)
        ty.pack(fill="x", pady=(10, 0))
        self.font_var = tk.StringVar(value=self.style.font)
        ttk.Combobox(ty, textvariable=self.font_var, values=FONTS, state="readonly").pack(fill="x")
        ttk.Label(ty, text="Bahnschrift supports the per-alien\nweights; other fonts use one weight.", foreground="#6f7a6f").pack(anchor="w", pady=(4, 0))

        ttk.Button(f, text="Reset to Omnitrix default", command=self.reset_style).pack(fill="x", pady=(12, 0))
        return f

    def _export_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        for label, fn in (("Current screen  ->  PNG", self.export_current),
                          ("Transformation (current alien)  ->  GIF", self.export_gif),
                          ("All watch faces  ->  PNG", lambda: self.export_bg("faces")),
                          ("Photo-face backgrounds (no clock)  ->  PNG", lambda: self.export_bg("backgrounds")),
                          ("Everything (incl. 10 GIFs, slow)", lambda: self.export_bg(None))):
            ttk.Button(f, text=label, command=fn).pack(fill="x", pady=3)
        ttk.Label(f, text=f"Saved to:\n{EXPORT_DIR}", foreground="#7f8a7f", wraplength=260).pack(anchor="w", pady=(10, 0))
        ttk.Label(f, text="All assets are 410 x 502. Whether the CMF Watch\napp accepts them is not verified yet.",
                  foreground="#c9a227").pack(anchor="w", pady=(10, 0))
        return f

    def _slider(self, parent, label, lo, hi, init):
        var = tk.DoubleVar(value=init)
        ttk.Label(parent, text=label).pack(anchor="w")
        ttk.Scale(parent, from_=lo, to=hi, variable=var).pack(fill="x", pady=(0, 6))
        return var

    # ---- state ---------------------------------------------------------------
    @property
    def now(self) -> float:
        return time.perf_counter() - self.t0

    @property
    def sel_index(self) -> int:
        return int(round(self.sel_target)) % len(ALIENS)

    @property
    def current_alien(self):
        return ALIENS[self.sel_index]

    def set_mode(self, mode: str, msg: str = "") -> None:
        self.mode, self.mode_t = mode, self.now
        names = {"home": "Omnitrix home", "select": "Alien dial", "confirm": "Alien selected",
                 "info": "Alien info", "transform": "Transforming...", "face": "Alien watch face"}
        self.status.config(text=f"{names[mode]}   {msg}")

    def goto(self, mode: str) -> None:
        if mode == "face":
            self.active = self.current_alien
        self.set_mode(mode)

    def pick_alien(self, i: int) -> None:
        self.sel_target = self.sel_anim = float(i)
        if self.mode == "face":
            self.active = self.current_alien

    def side_button(self) -> None:
        if self.mode in ("home", "face", "info"):
            self.set_mode("select")
        elif self.mode == "select":
            self.set_mode("face" if self.active else "home")

    def back(self) -> None:
        if self.mode == "select":
            self.set_mode("face" if self.active else "home")
        elif self.mode == "info":
            self.set_mode("select")
        elif self.mode == "face":
            self.active = None
            self.set_mode("home", "(Omnitrix timed out)")

    def turn(self, step: int) -> None:
        if self.mode == "select":
            self.sel_target += step
            self.alien_var.set(self.current_alien.name)

    def enter(self) -> None:
        if self.mode == "select":
            self.set_mode("confirm")
        elif self.mode == "info":
            self.transform()

    def transform(self) -> None:
        if self.mode != "transform":
            self.sel_anim = self.sel_target
            self.set_mode("transform", self.current_alien.name)

    # ---- pointer -------------------------------------------------------------
    def _screen_xy(self, e):
        return e.x - PAD, e.y - PAD

    def on_press(self, e) -> None:
        self.press = (e.x, e.y, self.now)
        self.drag_x = e.x

    def on_drag(self, e) -> None:
        if self.mode == "select" and self.drag_x is not None and abs(e.x - self.drag_x) > 40:
            self.turn(-1 if e.x > self.drag_x else 1)
            self.drag_x = e.x

    def on_release(self, e) -> None:
        if not self.press:
            return
        px, py, pt = self.press
        self.press = None
        moved = math.hypot(e.x - px, e.y - py) > 12
        if moved or self.now - pt >= HOLD_SECONDS:
            return
        x, y = self._screen_xy(e)
        r = math.hypot(x - S.C[0], y - S.C[1])
        if self.mode in ("home", "face") and r < S.R_RING:
            self.set_mode("select")
        elif self.mode == "select":
            if r < S.R_CORE:
                self.set_mode("confirm")
            elif abs(r - S.R_ORBIT) < 22:
                ang = math.degrees(math.atan2(y - S.C[1], x - S.C[0])) + 90
                step = round(((ang + 180) % 360 - 180) / (360 / len(ALIENS)))
                self.turn(step)

    def _check_hold(self) -> None:
        c = self.canvas
        if self.press and self.mode in ("select", "info"):
            px, py, pt = self.press
            p = (self.now - pt) / HOLD_SECONDS
            c.coords(self.hold_item, px - 30, py - 30, px + 30, py + 30)
            c.itemconfigure(self.hold_item, extent=-360 * min(p, 0.999))
            if p >= 1:
                self.press = None
                self.transform()
        else:
            c.itemconfigure(self.hold_item, extent=0)

    # ---- customisation / export ---------------------------------------------
    def pick_colour(self, attr: str) -> None:
        rgb, hexv = colorchooser.askcolor(getattr(self.style, attr), title=attr)
        if hexv:
            setattr(self.style, attr, hexv)
            self.swatches[attr].config(bg=hexv)

    def reset_style(self) -> None:
        self.style = S.Style()
        for v, val in ((self.ring_w, self.style.ring_width), (self.glow, self.style.glow), (self.hexg, self.style.hex_grid)):
            v.set(val)
        self.font_var.set(self.style.font)
        for attr, sw in self.swatches.items():
            sw.config(bg=getattr(self.style, attr))

    def _sync(self) -> None:
        st = self.style
        st.ring_width = round(self.ring_w.get(), 1)
        st.glow = round(self.glow.get(), 2)
        st.hex_grid = round(self.hexg.get(), 1)  # coarse steps: each value builds a cached background
        st.font = self.font_var.get()
        st.clock_24h = self.h24.get()
        self.data.battery = self.batt.get()
        self.data.now = datetime.now().replace(hour=10, minute=9, second=30) if self.freeze.get() else datetime.now()

    def _snapshot(self):
        return S.Style(**vars(self.style)), S.WatchData(now=self.data.now, battery=self.data.battery)

    def _bg(self, work, done_msg) -> None:
        self.status.config(text="Exporting...")

        def run():
            try:
                res = work()
                msg = done_msg(res)
            except Exception as exc:  # report, keep the app alive
                msg = f"Export failed: {exc}"
            self.root.after(0, lambda: self.status.config(text=msg))

        threading.Thread(target=run, daemon=True).start()

    def export_current(self) -> None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        p = EXPORT_DIR / f"screen_{self.mode}_{datetime.now():%Y%m%d_%H%M%S}.png"
        self.last_img.save(p)
        self.status.config(text=f"Saved {p}")

    def export_gif(self) -> None:
        a = self.current_alien
        style, data = self._snapshot()
        self._bg(lambda: transform_gif(a, EXPORT_DIR / "transform" / f"{a.key}.gif", style, data), lambda p: f"Saved {p}")

    def export_bg(self, only) -> None:
        style, data = self._snapshot()
        self._bg(lambda: export_all(only, style=style, data=data, log=lambda m: None), lambda files: f"Saved {len(files)} files to {EXPORT_DIR}")

    # ---- frame loop ----------------------------------------------------------
    def render(self, t: float) -> Image.Image:
        st, d = self.style, self.data
        lt = t - self.mode_t
        if self.mode == "home":
            return S.home(t, d, st)
        if self.mode == "select":
            self.sel_anim += (self.sel_target - self.sel_anim) * 0.28
            return S.selector(t, self.sel_anim, d, st)
        if self.mode == "confirm":
            p = lt / S.CONFIRM_DURATION
            if p >= 1:
                self.set_mode("info", self.current_alien.name)
                return S.info(t, self.current_alien, d, st)
            return S.select_confirm(t, p, self.sel_index, d, st)
        if self.mode == "info":
            return S.info(t, self.current_alien, d, st)
        if self.mode == "transform":
            if lt >= S.TRANSFORM_DURATION:
                self.active = self.current_alien
                self.set_mode("face", self.active.name)
                return S.alien_face(t, self.active, d, st)
            return S.transform(lt, self.current_alien, d, st)
        return S.alien_face(t, self.active or self.current_alien, d, st)

    def tick(self) -> None:
        start = time.perf_counter()
        self._sync()
        self._check_hold()
        self.last_img = self.render(self.now)
        self._photo = ImageTk.PhotoImage(self.last_img)
        self.canvas.itemconfigure(self.screen_item, image=self._photo)
        spent = (time.perf_counter() - start) * 1000
        self.root.after(max(1, int(33 - spent)), self.tick)


def main() -> int:
    root = tk.Tk()
    Studio(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
