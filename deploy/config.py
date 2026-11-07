"""What 'a CMF Watch Pro 1' looks like, and what the faces must satisfy.

Every value says where it came from. Values observed on this project's watch are in
docs/protocol-notes.md.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACES_DIR = ROOT / "watch_faces"
DEPLOY_DATA = ROOT / "data" / "deploy"  # gitignored via data/*

# Identity, observed on this watch over read-only GATT (2026-11-07)
EXPECTED_GAP_NAME = "Watch Pro"  # 0x2A00 Device Name
EXPECTED_MODEL_NUMBER = "lark"  # 0x2A24 Model Number String
ADV_SERVICE = "0000efe7-0000-1000-8000-00805f9b34fb"  # advertised service on this watch

# Firmware: not exposed through standard GATT on this watch (no 0x2A26/0x2A28).
# Gadgetbridge lists the D395 as tested on 11.0.0.50, which is informational only.
GADGETBRIDGE_TESTED_FIRMWARE = "11.0.0.50"

# Faces (install order: home first)
FACE_FILES = [
    "omnitrix_home.png", "heatblast.png", "four_arms.png", "xlr8.png", "diamondhead.png", "wildmutt.png",
    "upgrade.png", "ghostfreak.png", "cannonbolt.png", "ripjaws.png", "stinkfly.png",
]

# 410 x 502 is the spec-sheet resolution. CMF's support page only says "AMOLED".
# The calibration photo face will confirm or correct this.
DISPLAY_SIZE = (410, 502)
DISPLAY_SIZE_VERIFIED = False

# CMF documents no size limit. 1 MB is a conservative self-imposed ceiling (faces are ~100-150 KB).
MAX_FACE_BYTES = 1_000_000

# Where ADB copies the faces on the phone (shows up in the gallery / photo picker)
PHONE_DIR = "/sdcard/Pictures/Omnitrix"

OFFICIAL_METHOD = (
    "CMF Watch app > My tab > Customize Watch Face > choose a background and style > download "
    "(support.cmf.tech, 'How do I customize the watch face?', Watch Pro)"
)
