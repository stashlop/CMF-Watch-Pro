"""Omnitrix deployment to the CMF Watch Pro 1 (D395).

    python -m deploy check  [--address AA:BB:..] [--firmware 11.0.0.xx]   identify watch + validate faces
    python -m deploy push   [--faces omnitrix_home.png ...]               copy faces to the phone (ADB)
    python -m deploy guide  [--face heatblast.png]                         official install steps
    python -m deploy verify --face omnitrix_home.png [--confirm yes|no]   record an on-watch check
    python -m deploy status                                                what has been verified so far

Installation itself happens in the official CMF Watch app (the only documented,
Pro 1-verified route). Nothing here writes to the watch.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

from bleak.exc import BleakBluetoothNotAvailableError, BleakError

from deploy import config, phone
from deploy.validate import validate_all

LOG = config.DEPLOY_DATA / "install_log.json"


def _load_log() -> list[dict]:
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []


def _append_log(entry: dict) -> None:
    config.DEPLOY_DATA.mkdir(parents=True, exist_ok=True)
    log = _load_log()
    log.append(entry)
    LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _identify(address, timeout=10.0) -> dict:
    from deploy.identify import identify

    try:
        return asyncio.run(identify(address, timeout))
    except BleakBluetoothNotAvailableError as exc:
        return {"found": False, "error": f"Bluetooth unavailable: {exc.args[0]}"}
    except (BleakError, TimeoutError, OSError) as exc:
        return {"found": False, "error": f"BLE connection failed ({type(exc).__name__}: {exc}); wake the watch and retry"}


def _print_identity(ident: dict) -> None:
    if not ident.get("found"):
        print(f"  watch: NOT FOUND - {ident.get('error')}")
        return
    r = ident["reads"]
    print(f"  address           {ident['address']}")
    for k in ("gap_name", "model_number", "manufacturer", "firmware_revision", "software_revision", "battery_percent"):
        v = r.get(k)
        print(f"  {k:<17} {v if v is not None else '(not exposed over standard GATT)'}")
    print(f"  CMF Watch Pro 1?  {'YES' if ident['is_watch_pro_1'] else 'NO'}  {ident['checks']}")


def cmd_check(args) -> int:
    print("[1/4] Identifying the watch (read-only BLE)")
    ident = _identify(args.address)
    _print_identity(ident)

    print("\n[2/4] Firmware")
    fw = (ident.get("reads") or {}).get("firmware_revision") or args.firmware
    if fw:
        note = "matches" if fw == config.GADGETBRIDGE_TESTED_FIRMWARE else "differs from"
        print(f"  firmware {fw} ({note} Gadgetbridge-tested {config.GADGETBRIDGE_TESTED_FIRMWARE}; informational)")
    else:
        print("  not readable over standard GATT on this watch. Look it up in the CMF Watch app's device info,")
        print("  then pass --firmware <version> to record it. Photo faces are an app feature; no firmware gate is documented.")

    print("\n[3/4] Validating faces in watch_faces/")
    results = validate_all()
    for r in results:
        flag = "OK " if r["ok"] else "BAD"
        extra = f"{r.get('bytes', 0) // 1024:>4} KB  black {r.get('true_black_pct', '-')}%"
        print(f"  {flag} {r['file']:<20} {extra}  {'; '.join(r['problems'])}")
    faces_ok = all(r["ok"] for r in results)

    print("\n[4/4] Installation method")
    print(f"  {config.OFFICIAL_METHOD}")
    print("  Direct BLE upload: NOT USED. No Pro 1-verified face-upload protocol (Gadgetbridge marks it")
    print("  'somewhat working', untested on the D395, and pairing needs a root-extracted key).")
    if not config.DISPLAY_SIZE_VERIFIED:
        print(f"  Display {config.DISPLAY_SIZE[0]}x{config.DISPLAY_SIZE[1]} is from the spec sheet; install calibration.png to confirm.")

    adb = phone.find_adb()
    devs = phone.devices(adb) if adb else []
    print(f"\n  ADB: {'found' if adb else 'not installed'}; phones connected: {len([d for d in devs if d['state'] == 'device'])}")

    report = {"time": datetime.now().isoformat(timespec="seconds"), "identity": ident, "firmware": fw,
              "faces": results, "faces_ok": faces_ok, "method": config.OFFICIAL_METHOD}
    config.DEPLOY_DATA.mkdir(parents=True, exist_ok=True)
    (config.DEPLOY_DATA / "last_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ready = faces_ok and ident.get("is_watch_pro_1")
    print(f"\nREADY FOR INSTALL: {'YES' if ready else 'NO'}   (report: data/deploy/last_check.json)")
    return 0 if ready else 1


def cmd_push(args) -> int:
    adb = phone.find_adb()
    if not adb:
        print("ADB not found. Copy the PNGs from watch_faces/ to the phone any other way (cable, cloud, email).")
        return 2
    ready = [d for d in phone.devices(adb) if d["state"] == "device"]
    if not ready:
        print("No phone connected over ADB. On the phone: Settings > About phone > tap Build number 7x,")
        print("then Developer options > USB debugging ON; connect USB and accept the 'Allow USB debugging' prompt.")
        return 2
    serial = args.serial or ready[0]["serial"]
    print(f"Phone: {phone.phone_model(adb, serial)} ({serial})")
    names = args.faces or config.FACE_FILES
    bad = [r for r in validate_all() if r["file"] in names and not r["ok"]]
    if bad:
        print("Refusing to push faces that fail validation:", ", ".join(r["file"] for r in bad))
        return 1
    for r in phone.push_faces(adb, serial, [config.FACES_DIR / n for n in names]):
        print(f"  {'OK ' if r['ok'] else 'ERR'} {r['dest']}  {'' if r['ok'] else r['detail']}")
    print(f"\nFaces are in the phone's gallery under Pictures/Omnitrix. Next: python -m deploy guide")
    return 0


GUIDE = """\
OFFICIAL INSTALL - CMF Watch app (CMF Watch Pro, documented by CMF support)

 0. First time only: install calibration.png (python -m deploy push --faces calibration.png) and check the edges
    (see docs/install-guide.md). It confirms the real screen size before the Omnitrix faces.
 1. Watch paired and connected to the CMF Watch app on the phone; watch charged > 20 %.
 2. Have {face} on the phone (python -m deploy push, or copy it manually).
 3. CMF Watch app > "My" tab > "Customize Watch Face".
 4. Choose a background: pick {face} from Pictures/Omnitrix.
    If the app shows a crop box, keep the WHOLE image (do not zoom).
 5. Choose a style with the clock at the TOP or BOTTOM (not centre); the dial is kept clear for that.
 6. Download/sync it to the watch and wait for it to finish. Keep the phone near the watch.
 7. Look at the watch, then record the result:
       python -m deploy verify --face {face}
"""


def cmd_guide(args) -> int:
    print(GUIDE.format(face=args.face))
    return 0


def cmd_verify(args) -> int:
    if args.face not in config.FACE_FILES and args.face != "calibration.png":
        print(f"unknown face {args.face}")
        return 2
    print("Checking the watch is still connected and responding (read-only)...")
    ident = _identify(args.address)
    _print_identity(ident)
    print("\nThe installed face cannot be read back over BLE on this watch: only you can see it.")
    answer = args.confirm
    if answer is None:
        if not sys.stdin.isatty():
            print("No --confirm given and no terminal to ask; nothing recorded.")
            return 2
        answer = input(f"Is {args.face} showing correctly on the watch (no cut edges, clock not over the dial)? [yes/no] ")
    confirmed = answer.strip().lower() in ("y", "yes")
    notes = args.notes or (input("Notes (clock position, anything cut off) [enter to skip]: ") if sys.stdin.isatty() and args.confirm is None else "")
    _append_log({
        "time": datetime.now().isoformat(timespec="seconds"),
        "face": args.face,
        "watch_found": bool(ident.get("found")),
        "watch_is_pro_1": ident.get("is_watch_pro_1"),
        "battery_percent": (ident.get("reads") or {}).get("battery_percent"),
        "method": "CMF Watch app > My > Customize Watch Face",
        "owner_confirmed_on_watch": confirmed,
        "notes": notes,
    })
    print(f"\nRecorded: {args.face} -> {'VERIFIED on the watch (owner-confirmed)' if confirmed else 'NOT verified'}  ({LOG})")
    return 0 if confirmed else 1


def cmd_status(args) -> int:
    log = _load_log()
    latest = {}
    for e in log:
        latest[e["face"]] = e
    for name in ["calibration.png", *config.FACE_FILES]:
        e = latest.get(name)
        state = "not installed/recorded" if not e else ("VERIFIED " + e["time"] if e["owner_confirmed_on_watch"] else "FAILED " + e["time"])
        print(f"  {name:<20} {state}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m deploy", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--address")
    c.add_argument("--firmware", help="firmware version shown in the CMF Watch app")
    p = sub.add_parser("push")
    p.add_argument("--faces", nargs="*")
    p.add_argument("--serial")
    g = sub.add_parser("guide")
    g.add_argument("--face", default="omnitrix_home.png")
    v = sub.add_parser("verify")
    v.add_argument("--face", required=True)
    v.add_argument("--address")
    v.add_argument("--confirm", choices=("yes", "no"))
    v.add_argument("--notes")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    return {"check": cmd_check, "push": cmd_push, "guide": cmd_guide, "verify": cmd_verify, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
