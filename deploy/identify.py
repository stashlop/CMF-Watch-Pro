"""Find the watch and confirm it is a CMF Watch Pro 1, using read-only BLE only."""

from __future__ import annotations

from bleak import BleakScanner

from ble.discover import scan
from ble.safety import ReadOnlySession
from deploy import config

_SIG = "0000{:04x}-0000-1000-8000-00805f9b34fb"
READS = {  # SIG characteristics we read, if present (all read-only)
    "gap_name": 0x2A00,
    "model_number": 0x2A24,
    "manufacturer": 0x2A29,
    "firmware_revision": 0x2A26,
    "software_revision": 0x2A28,
    "hardware_revision": 0x2A27,
    "battery_percent": 0x2A19,
}


def _decode(key: str, data: bytes):
    if key == "battery_percent":
        return data[0] if data else None
    return data.decode("utf-8", "replace").strip("\x00 ")


async def identify(address: str | None = None, scan_timeout: float = 10.0) -> dict:
    """Return what the watch reports about itself plus a verdict."""
    result: dict = {"address": address, "found": False, "reads": {}, "checks": {}}

    if address is None:
        found = await scan(scan_timeout, None)
        address = found["best_candidate"]
        result["scan"] = {"devices": len(found["devices"]), "best_candidate": address}
        if address is None:
            result["error"] = "No CMF Watch Pro 1 candidate advertising. Wake the watch, keep it near the PC."
            return result
    result["address"] = address

    device = await BleakScanner.find_device_by_address(address, timeout=scan_timeout)
    if device is None:
        result["error"] = f"{address} is not advertising right now."
        return result
    result["found"] = True

    async with ReadOnlySession(device) as client:
        present = {c.uuid.lower(): c for s in client.services for c in s.characteristics}
        for key, short in READS.items():
            char = present.get(_SIG.format(short))
            if char is None or "read" not in char.properties:
                result["reads"][key] = None  # not exposed by this watch
                continue
            try:
                result["reads"][key] = _decode(key, bytes(await client.read_gatt_char(char)))
            except Exception as exc:  # record, never retry with writes / pairing
                result["reads"][key] = f"read failed: {type(exc).__name__}"

    r = result["reads"]
    result["checks"] = {
        "gap_name": r.get("gap_name") == config.EXPECTED_GAP_NAME,
        "model_number": r.get("model_number") == config.EXPECTED_MODEL_NUMBER,
    }
    result["is_watch_pro_1"] = all(result["checks"].values())
    return result
