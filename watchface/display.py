"""Screen geometry used for previews.

Values come from the published CMF Watch Pro (1st gen) spec sheet
(1.96" AMOLED, 410 x 502). They have not been read from the device. The
corner radius is an eyeballed approximation for the preview mask only.
The Watch Pro 2 (round 466 x 466) is a different device; don't reuse its values.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayProfile:
    name: str
    width: int
    height: int
    corner_radius: int


WATCH_PRO_1 = DisplayProfile("CMF Watch Pro (1st gen)", 410, 502, 90)
