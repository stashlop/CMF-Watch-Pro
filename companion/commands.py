"""Documented CMF commands and payload builders for the Omnitrix companion layer.

Command IDs (cmd1, cmd2) are from Gadgetbridge's ``CmfCommand`` enum (AGPLv3). Only a safe subset is
exposed here: the ones this prototype uses to add Omnitrix flavour with the watch's existing features.

DESTRUCTIVE commands are intentionally NOT builders and are listed in ``BLOCKED`` so the client can refuse
them even if asked: firmware transfer, the factory shell, and factory reset.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

ENC = "utf-8"


@dataclass(frozen=True)
class Cmd:
    name: str
    cmd1: int
    cmd2: int
    encrypted: bool = True  # all non-auth app commands are AES-encrypted


# --- the Omnitrix-relevant, non-destructive commands we build -----------------------------
APP_NOTIFICATION = Cmd("APP_NOTIFICATION", 0x0065, 0x0001)
MUSIC_INFO_SET = Cmd("MUSIC_INFO_SET", 0xFFFF, 0x905C)
FIND_WATCH = Cmd("FIND_WATCH", 0x005D, 0x0001)
WATCHFACE = Cmd("WATCHFACE", 0x009F, 0x0001)  # switch the active (already-installed) face

ALLOWED = {c.name: c for c in (APP_NOTIFICATION, MUSIC_INFO_SET, FIND_WATCH, WATCHFACE)}

# Commands this prototype must never emit (destructive / out of scope / undocumented effect).
BLOCKED = {
    "FACTORY_RESET": (0x009A, 0x0001),
    "DATA_CHUNK_WRITE_FIRMWARE": (0xFFFF, 0x9042),
    "DATA_TRANSFER_FIRMWARE_INIT_1_REQUEST": (0xFFFF, 0x9052),
}


# --- payload builders (byte layouts mirror Gadgetbridge; unverified on this watch) ----------
def notification(app_id: int, title: str, body: str) -> tuple[Cmd, bytes]:
    """A phone-style notification. Used to show an alien's name on the watch."""
    t = title.encode(ENC)[:20]
    b = body.encode(ENC)[:120]
    buf = bytearray()
    buf += struct.pack(">H", app_id)
    buf += struct.pack(">H", len(t)) + t
    buf += struct.pack(">H", len(b)) + b
    return APP_NOTIFICATION, bytes(buf)


def music_info(track: str, artist: str, playing: bool = True) -> tuple[Cmd, bytes]:
    """Set the music-screen text. Used to show the selected alien as the 'now playing' line."""
    tr = track.encode(ENC)[:60]
    ar = artist.encode(ENC)[:60]
    buf = bytearray()
    buf.append(0x01 if playing else 0x00)
    buf += struct.pack(">H", len(tr)) + tr
    buf += struct.pack(">H", len(ar)) + ar
    return MUSIC_INFO_SET, bytes(buf)


def find_watch() -> tuple[Cmd, bytes]:
    """Trigger the watch's find-device vibration/animation. Used as transformation feedback."""
    return FIND_WATCH, b"\xa5"


def switch_face(index: int) -> tuple[Cmd, bytes]:
    """Switch to an already-installed face by index. Effect on the Pro 1 is UNVERIFIED."""
    return WATCHFACE, struct.pack(">B", index & 0xFF)
