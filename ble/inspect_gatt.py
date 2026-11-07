"""Connect to the watch and dump its GATT table using read-only operations.

    python -m ble.inspect_gatt                       # use best candidate from latest scan
    python -m ble.inspect_gatt --address AA:BB:...   # explicit device
    python -m ble.inspect_gatt --read none|standard|all

Read policy (which attribute VALUES are read; the table is always enumerated):
  none      enumerate services/characteristics/descriptors only
  standard  (default) read only Bluetooth SIG-assigned characteristics
            (0x2A00-0x2BFF, e.g. Device Information, Battery) and descriptors
            (0x2900-0x29FF). Vendor-specific attributes are listed, not read.
  all       read every attribute that advertises the 'read' property,
            including vendor-specific ones.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from bleak import BleakScanner
from bleak.exc import BleakBluetoothNotAvailableError, BleakError

from ble.discover import SCAN_DIR
from ble.safety import ReadOnlyClient, ReadOnlySession

GATT_DIR = Path(__file__).resolve().parents[1] / "data" / "gatt"
_SIG_BASE_SUFFIX = "-0000-1000-8000-00805f9b34fb"


def sig_short_uuid(uuid: str) -> int | None:
    """Return the 16-bit value of a SIG-base UUID, else None (vendor 128-bit)."""
    u = uuid.lower()
    if u.startswith("0000") and u.endswith(_SIG_BASE_SUFFIX):
        return int(u[4:8], 16)
    return None


def may_read(uuid: str, kind: str, policy: str) -> bool:
    if policy == "none":
        return False
    if policy == "all":
        return True
    short = sig_short_uuid(uuid)
    if short is None:
        return False
    if kind == "characteristic":
        return 0x2A00 <= short <= 0x2BFF
    return 0x2900 <= short <= 0x29FF  # descriptor


def _decode_known(uuid: str, data: bytes):
    """Decode a few SIG characteristics whose bytes are numbers, not text."""
    short = sig_short_uuid(uuid)
    if short == 0x2A19 and len(data) == 1:  # Battery Level, uint8 percent
        return {"battery_percent": data[0]}
    if short == 0x2A01 and len(data) == 2:  # Appearance
        return {"appearance": int.from_bytes(data, "little")}
    if short == 0x2A50 and len(data) == 7:  # PnP ID
        return {
            "vendor_id_source": data[0],
            "vendor_id": f"0x{int.from_bytes(data[1:3], 'little'):04x}",
            "product_id": f"0x{int.from_bytes(data[3:5], 'little'):04x}",
            "product_version": f"0x{int.from_bytes(data[5:7], 'little'):04x}",
        }
    return None


def _value(uuid: str, data: bytes) -> dict:
    out = {"status": "ok", "length": len(data), "hex": data.hex()}
    decoded = _decode_known(uuid, data)
    if decoded is not None:
        out["decoded"] = decoded
        return out
    try:
        text = data.decode("utf-8")
        # Single bytes are almost always numbers (0x64 would show as "d").
        if len(text) >= 2 and text.isprintable():
            out["utf8"] = text
    except UnicodeDecodeError:
        pass
    return out


async def _read(uuid: str, coro) -> dict:
    try:
        return _value(uuid, bytes(await coro))
    except Exception as exc:  # access denied / needs encryption / timeout: record, don't retry
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


async def dump(client: ReadOnlyClient, policy: str) -> list[dict]:
    services = []
    for service in client.services:
        chars = []
        for char in service.characteristics:
            entry = {
                "uuid": char.uuid,
                "description": char.description,
                "handle": char.handle,
                "properties": sorted(char.properties),
            }
            if "read" not in char.properties:
                entry["read"] = {"status": "not_readable"}
            elif may_read(char.uuid, "characteristic", policy):
                entry["read"] = await _read(char.uuid, client.read_gatt_char(char))
            else:
                entry["read"] = {"status": "skipped_by_policy"}

            entry["descriptors"] = []
            for desc in char.descriptors:
                d = {"uuid": desc.uuid, "description": desc.description, "handle": desc.handle}
                d["read"] = (
                    await _read(desc.uuid, client.read_gatt_descriptor(desc))
                    if may_read(desc.uuid, "descriptor", policy)
                    else {"status": "skipped_by_policy"}
                )
                entry["descriptors"].append(d)
            chars.append(entry)
        services.append(
            {
                "uuid": service.uuid,
                "description": service.description,
                "handle": service.handle,
                "vendor_specific": sig_short_uuid(service.uuid) is None,
                "characteristics": chars,
            }
        )
    return services


def latest_scan_candidate() -> tuple[str | None, str | None]:
    scans = sorted(SCAN_DIR.glob("scan_*.json"))
    if not scans:
        return None, None
    data = json.loads(scans[-1].read_text(encoding="utf-8"))
    addr = data.get("best_candidate")
    name = next((d["name"] for d in data["devices"] if d["address"] == addr), None)
    return addr, name


async def inspect(address: str, policy: str, scan_timeout: float, connect_timeout: float) -> dict:
    device = await BleakScanner.find_device_by_address(address, timeout=scan_timeout)
    if device is None:
        raise SystemExit(
            f"{address} is not advertising. Wake the watch and make sure it is not connected to the phone."
        )
    async with ReadOnlySession(device, timeout=connect_timeout) as client:
        services = await dump(client, policy)
        mtu = client.mtu_size
    return {
        "schema": "cmf-gatt/1",
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "device": {"address": address, "name": device.name},
        "read_policy": policy,
        "mtu": mtu,
        "services": services,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--address", help="device address (default: best candidate from latest scan)")
    parser.add_argument("--read", dest="policy", choices=("none", "standard", "all"), default="standard")
    parser.add_argument("--scan-timeout", type=float, default=10.0)
    parser.add_argument("--connect-timeout", type=float, default=20.0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    address, name = args.address, None
    if not address:
        address, name = latest_scan_candidate()
        if not address:
            parser.error("no --address given and no candidate in data/scans; run `python -m ble.discover` first")
        print(f"Using latest scan candidate {address} ({name})")

    try:
        result = asyncio.run(inspect(address, args.policy, args.scan_timeout, args.connect_timeout))
    except BleakBluetoothNotAvailableError as exc:
        print(f"Bluetooth unavailable: {exc.args[0]}")
        return 2
    except (BleakError, TimeoutError, OSError) as exc:
        # Windows connections to this watch occasionally fail on the first try.
        print(f"Connection failed ({type(exc).__name__}: {exc}). Wake the watch and run again.")
        return 1

    safe_addr = address.replace(":", "")
    out = args.out or GATT_DIR / f"gatt_{safe_addr}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    for s in result["services"]:
        tag = "vendor" if s["vendor_specific"] else "SIG"
        print(f"[{tag}] {s['uuid']}  {s['description']}")
        for c in s["characteristics"]:
            r = c["read"]
            val = r.get("decoded") or r.get("utf8") or r.get("hex") or r["status"]
            print(f"    {c['uuid']}  {','.join(c['properties']):<32} {val}")
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
