"""Passive BLE scan: list nearby devices and flag likely CMF Watch Pro 1 units.

Scanning only listens to advertisements; it never connects.

    python -m ble.discover [--timeout 10] [--name "Watch Pro"] [--address AA:BB:..] [--out file.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from bleak import BleakScanner
from bleak.exc import BleakBluetoothNotAvailableError

from ble.identify import classify

SCAN_DIR = Path(__file__).resolve().parents[1] / "data" / "scans"


def _device_record(device, adv, name_hint: str | None, address_hint: str | None) -> dict:
    name = adv.local_name or device.name
    match = classify(
        name,
        name_hint,
        address=device.address,
        service_uuids=adv.service_uuids,
        manufacturer_data=adv.manufacturer_data,
        address_hint=address_hint,
    )
    return {
        "address": device.address,
        "name": name,
        "rssi": adv.rssi,
        "tx_power": adv.tx_power,
        "service_uuids": sorted(adv.service_uuids),
        "manufacturer_data": {str(cid): data.hex() for cid, data in adv.manufacturer_data.items()},
        "service_data": {uuid: data.hex() for uuid, data in adv.service_data.items()},
        "match": match.to_dict(),
    }


async def scan(timeout: float, name_hint: str | None, address_hint: str | None = None) -> dict:
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    devices = [_device_record(dev, adv, name_hint, address_hint) for dev, adv in found.values()]
    devices.sort(key=lambda d: (not d["match"]["is_candidate"], -d["match"]["score"], -(d["rssi"] or -999)))
    candidates = [d for d in devices if d["match"]["is_candidate"]]
    return {
        "schema": "cmf-scan/1",
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": {"os": platform.platform(), "bleak": version("bleak")},
        "scan_timeout_s": timeout,
        "name_hint": name_hint,
        "address_hint": address_hint,
        "best_candidate": candidates[0]["address"] if candidates else None,
        "devices": devices,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--timeout", type=float, default=10.0, help="scan duration in seconds")
    parser.add_argument("--name", dest="name_hint", help="substring of the watch's advertised name (overrides heuristics)")
    parser.add_argument("--address", dest="address_hint", help="flag this exact device address as the watch")
    parser.add_argument("--out", type=Path, help="output JSON path (default: data/scans/scan_<timestamp>.json)")
    args = parser.parse_args(argv)

    print(f"Scanning for {args.timeout:.0f}s ...")
    try:
        result = asyncio.run(scan(args.timeout, args.name_hint, args.address_hint))
    except BleakBluetoothNotAvailableError as exc:
        print(f"Bluetooth unavailable: {exc.args[0]}")
        return 2

    out = args.out or SCAN_DIR / f"scan_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    for d in result["devices"]:
        flag = "*" if d["match"]["is_candidate"] else " "
        print(f"{flag} {d['address']}  {str(d['rssi']):>4} dBm  {d['name'] or '<no name>'}  [{d['match']['model_guess']}]")

    print(f"\n{len(result['devices'])} devices saved to {out}")
    if result["best_candidate"]:
        print(f"Likely CMF Watch Pro 1: {result['best_candidate']}  ->  python -m ble.inspect_gatt")
    else:
        print(
            "No CMF Watch Pro 1 candidate found. The watch usually stops advertising while it is\n"
            "connected to the phone app: turn off Bluetooth on the phone, wake the watch, and rescan.\n"
            "If its name is unusual, pass --name with part of it."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
