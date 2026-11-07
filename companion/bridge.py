"""Omnitrix flavour on top of the watch's existing features (offline planning).

The Pro 1 can't run our UI, but a companion app can borrow features it already has:
  * show the selected alien's name as a notification / music line,
  * read the watch's media buttons as "turn the dial / select",
  * buzz (find-watch) as transformation feedback,
  * switch to an already-installed alien face.

Each action returns a PLAN: an ordered list of Steps. Building a plan does no I/O, so it is fully testable.
The client (client.py) is what turns a plan into packets, and only sends in live mode.
"""

from __future__ import annotations

from dataclasses import dataclass

from omnitrix.aliens import ALIENS, BY_KEY, Alien

from companion import commands

NOTIF_APP_ID = 0x00A1  # arbitrary non-call app id for our notifications


@dataclass(frozen=True)
class Step:
    describe: str
    cmd: commands.Cmd
    payload: bytes


def select_alien(alien: Alien) -> list[Step]:
    """Announce the chosen alien using the music line + a notification."""
    c1, p1 = commands.music_info(alien.name, f"OMNITRIX / {alien.klass}", playing=True)
    c2, p2 = commands.notification(NOTIF_APP_ID, "OMNITRIX", f"{alien.name} selected")
    return [Step(f"music line -> {alien.name}", c1, p1),
            Step(f"notify -> {alien.name} selected", c2, p2)]


def transform(alien: Alien, face_index: int | None = None) -> list[Step]:
    """Transformation feedback: buzz, announce, and optionally switch to the alien's face."""
    steps = [Step("find-watch buzz (transform)", *commands.find_watch())]
    c, p = commands.notification(NOTIF_APP_ID, "OMNITRIX", f"Transformed: {alien.name}")
    steps.append(Step(f"notify -> transformed {alien.name}", c, p))
    if face_index is not None:
        steps.append(Step(f"switch to face #{face_index} (UNVERIFIED on Pro 1)", *commands.switch_face(face_index)))
    return steps


# Media-button codes the watch sends (MUSIC_BUTTON), mapped to Omnitrix dial actions.
BUTTON_ACTIONS = {
    0x0102: "dial +1 (next)",
    0x0002: "dial -1 (previous)",
    0x0101: "select / confirm (play-pause)",
}


def button_to_action(code: int) -> str | None:
    """Translate a watch media-button code into an Omnitrix dial action (for the incoming direction)."""
    return BUTTON_ACTIONS.get(code)


def alien_at(index: int) -> Alien:
    return ALIENS[index % len(ALIENS)]


def demo_plan() -> list[Step]:
    """A short scripted sequence for a dry-run: select XLR8, then transform into it."""
    xlr8 = BY_KEY["xlr8"]
    return select_alien(xlr8) + transform(xlr8, face_index=ALIENS.index(xlr8) + 1)
