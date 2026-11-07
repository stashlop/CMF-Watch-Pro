"""Heuristics for picking a CMF Watch Pro (1st gen) out of a BLE scan.

Observed on this project's watch (see docs/protocol-notes.md):
  * its advertisement carries NO name; the GAP Device Name read over GATT is "Watch Pro"
  * it advertises 16-bit service 0xEFE7
  * its manufacturer data embeds its own address: the 2-byte "company ID"
    (little-endian) + first 4 payload bytes == the 6 address bytes
The fingerprint rule is built from one unit; confirm on others before relying on it.
Names with a generation digit ("Watch Pro 2", "Watch 3 Pro") are always excluded.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# A digit right after "watch" or "pro" signals a different generation.
_OTHER_GENERATION = re.compile(r"(watch|pro)[\s_-]*\d", re.IGNORECASE)
ADV_SERVICE_EFE7 = "0000efe7-0000-1000-8000-00805f9b34fb"


@dataclass
class Match:
    is_candidate: bool
    model_guess: str  # "watch_pro_1?" | "other_generation" | "cmf_other" | "unknown"
    score: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def manufacturer_data_embeds_address(address: str | None, manufacturer_data: dict[int, bytes] | None) -> bool:
    if not address or not manufacturer_data:
        return False
    try:
        addr = bytes.fromhex(address.replace(":", "").replace("-", ""))
    except ValueError:  # non-MAC address (e.g. macOS UUIDs)
        return False
    if len(addr) != 6:
        return False
    return any(
        cid.to_bytes(2, "little") + bytes(payload[:4]) == addr
        for cid, payload in manufacturer_data.items()
    )


def classify(
    name: str | None,
    name_hint: str | None = None,
    *,
    address: str | None = None,
    service_uuids: list[str] | tuple[str, ...] = (),
    manufacturer_data: dict[int, bytes] | None = None,
    address_hint: str | None = None,
) -> Match:
    if address_hint and address and address.lower() == address_hint.lower():
        return Match(True, "watch_pro_1?", 10, [f"matches --address {address_hint}"])
    if name and name_hint and name_hint.lower() in name.lower():
        return Match(True, "watch_pro_1?", 10, [f"matches --name '{name_hint}'"])
    if name and _OTHER_GENERATION.search(name):
        return Match(False, "other_generation", 0, ["name indicates a different generation; excluded"])

    if ADV_SERVICE_EFE7 in [u.lower() for u in service_uuids] and manufacturer_data_embeds_address(
        address, manufacturer_data
    ):
        return Match(
            True, "watch_pro_1?", 8, ["advertises service 0xEFE7 and manufacturer data embeds its address"]
        )

    if not name:
        return Match(False, "unknown", 0, ["no advertised name"])

    lowered = name.lower().strip()
    if lowered == "watch pro":
        return Match(True, "watch_pro_1?", 5, ["name is exactly 'Watch Pro' (GAP name seen on this watch)"])

    reasons: list[str] = []
    score = 0
    for word, pts in (("cmf", 2), ("watch", 1), ("pro", 1)):
        if word in lowered:
            score += pts
            reasons.append(f"name contains '{word}'")
    if score >= 4:
        return Match(True, "watch_pro_1?", score, reasons)
    if score >= 2:
        return Match(False, "cmf_other", score, reasons)
    return Match(False, "unknown", score, reasons)
