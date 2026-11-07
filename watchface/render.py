"""Render a face definition (JSON) to a Pillow image. Pure: no I/O besides fonts.

Face JSON:
    {"name": "...", "background": "#000000", "elements": [ ... ]}

Element types (coordinates are screen pixels):
    rect    {"xy": [x0,y0,x1,y1], "fill", "outline", "width", "radius"}
    circle  {"center": [x,y], "r", "fill", "outline", "width"}
    line    {"xy": [x0,y0,x1,y1], "fill", "width"}
    text    {"text": "{now:%H:%M}", "xy": [x,y], "anchor": "mm", "font": "segoeuib.ttf", "size", "fill"}
    arc     {"box": [x0,y0,x1,y1], "progress": "steps"|"battery", "width", "fill", "track"}

Text is a str.format template over WatchState fields: now (datetime, supports
strftime specs), battery, steps, steps_goal, heart_rate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from watchface.display import WATCH_PRO_1, DisplayProfile


@dataclass
class WatchState:
    now: datetime = field(default_factory=datetime.now)
    battery: int = 76
    steps: int = 6420
    steps_goal: int = 10000
    heart_rate: int = 72

    def fields(self) -> dict:
        return {
            "now": self.now,
            "battery": self.battery,
            "steps": self.steps,
            "steps_goal": self.steps_goal,
            "heart_rate": self.heart_rate,
        }

    def progress(self, key: str) -> float:
        if key == "steps":
            value = self.steps / self.steps_goal if self.steps_goal else 0.0
        elif key == "battery":
            value = self.battery / 100
        else:
            raise ValueError(f"unknown progress source '{key}'")
        return max(0.0, min(1.0, value))


@lru_cache(maxsize=64)
def load_font(name: str | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if name:
        try:
            return ImageFont.truetype(name, size)  # searches C:\Windows\Fonts on Windows
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def load_face(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _draw_element(draw: ImageDraw.ImageDraw, el: dict, state: WatchState) -> None:
    kind = el["type"]
    if kind == "rect":
        draw.rounded_rectangle(
            el["xy"], radius=el.get("radius", 0), fill=el.get("fill"), outline=el.get("outline"), width=el.get("width", 1)
        )
    elif kind == "circle":
        x, y = el["center"]
        r = el["r"]
        draw.ellipse([x - r, y - r, x + r, y + r], fill=el.get("fill"), outline=el.get("outline"), width=el.get("width", 1))
    elif kind == "line":
        draw.line(el["xy"], fill=el.get("fill", "#ffffff"), width=el.get("width", 1))
    elif kind == "text":
        text = el["text"].format(**state.fields())
        font = load_font(el.get("font"), el.get("size", 24))
        draw.text(tuple(el["xy"]), text, fill=el.get("fill", "#ffffff"), font=font, anchor=el.get("anchor", "la"))
    elif kind == "arc":
        width = el.get("width", 10)
        if el.get("track"):
            draw.arc(el["box"], 0, 360, fill=el["track"], width=width)
        frac = state.progress(el["progress"])
        if frac > 0:
            draw.arc(el["box"], -90, -90 + 360 * frac, fill=el.get("fill", "#ffffff"), width=width)
    else:
        raise ValueError(f"unknown element type '{kind}'")


def render(face: dict, state: WatchState | None = None, profile: DisplayProfile = WATCH_PRO_1) -> Image.Image:
    state = state or WatchState()
    img = Image.new("RGB", (profile.width, profile.height), face.get("background", "#000000"))
    draw = ImageDraw.Draw(img)
    for el in face.get("elements", []):
        _draw_element(draw, el, state)

    # Black out the area outside the rounded screen so previews show real clipping.
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, profile.width - 1, profile.height - 1], radius=profile.corner_radius, fill=255)
    return Image.composite(img, Image.new("RGB", img.size, "#000000"), mask)
