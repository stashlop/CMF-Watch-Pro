# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PC-side tooling (Windows, Python 3.12, `bleak` 3.x, `pillow`) for building a custom UI for the **CMF Watch Pro, 1st generation**. Current scope: discover the watch over BLE, inspect its GATT table read-only, and design/preview watch faces locally.

## Hard rules

- **Read-only BLE only.** Never write characteristics or descriptors, subscribe to notifications (`start_notify` writes the CCCD), pair/unpair, enter factory/debug modes, or touch firmware. This holds even if a capture suggests a "harmless" command.
- All connections go through `ble.safety.ReadOnlySession`, which owns the `BleakClient` and yields a `ReadOnlyClient` exposing only `services` and `read_gatt_char`/`read_gatt_descriptor`. Don't construct `BleakClient` anywhere else. `tests/test_safety.py` scans `ble/` and `watchface/` for calls to forbidden methods and `pair=True`, and will fail.
- **Watch Pro 1 ≠ Watch Pro 2 / Watch 3 Pro.** Don't reuse their UUIDs, packet formats, screen sizes or face formats. `ble/identify.py` deliberately excludes names with a generation digit. Only facts observed on this watch go under "Verified" in `docs/protocol-notes.md`, with the capture file they came from.
- Watch faces here are this project's own JSON format, rendered on the PC. Nothing uploads faces to the watch; the native face format is unknown.

## Commands

Use the venv interpreter (`.venv\Scripts\python.exe`, or activate it first). Run everything from the repo root as modules so the `ble`/`watchface` packages resolve.

```powershell
pip install -r requirements.txt

python -m unittest discover -s tests -t .                       # all tests
python -m unittest tests.test_identify.ClassifyTests.test_pro_1_candidate   # single test

python -m ble.discover [--timeout 10] [--name "<part of name>"] [--address AA:BB:..]
python -m ble.inspect_gatt [--address AA:BB:..] [--read none|standard|all]

python -m watchface.preview                                       # live GUI
python -m watchface.preview --face activity_rings --time 10:09:30 --export data/previews/x.png
```

There is no linter or build step configured.

## Architecture

**BLE flow (`ble/`)**: `discover` does a passive scan, scores each device with `identify.classify` (the watch often advertises without a name, so the main rule is the advertisement fingerprint recorded in `docs/protocol-notes.md`; name rules and `--name`/`--address` are fallbacks), and writes `data/scans/scan_<ts>.json` with raw manufacturer/service data and a `best_candidate`. `inspect_gatt` with no `--address` picks `best_candidate` from the newest scan, connects via `ReadOnlySession`, and writes `data/gatt/gatt_<addr>_<ts>.json`. Its `--read` policy controls which values are read: `standard` (default) reads only SIG-assigned characteristics (0x2A00–0x2BFF) and descriptors (0x2900–0x29FF); vendor attributes are listed but not read unless `--read all`. Read failures (e.g. encryption required) are recorded per attribute rather than worked around by pairing.

**Watch faces (`watchface/`)**: `render.render(face_dict, WatchState, DisplayProfile)` is pure and returns a 410×502 RGB image with the rounded-screen corners masked. Text elements are `str.format` templates over `WatchState` fields (`{now:%H:%M}`, `{steps:,}`, `{battery}`...). Element types and fields are documented in the `render.py` docstring; adding a type means extending `_draw_element`. Faces live in `watchface/faces/*.json` and are picked up automatically by the GUI, the `--list` flag and the render test. The Tk GUI reloads a face when its file's mtime changes, so faces can be edited live. `display.py` holds the screen size from the public spec sheet (not read from the device).

**Data**: `data/scans`, `data/gatt`, `data/previews` are gitignored because captures contain the watch's Bluetooth address and the repo is public (github.com/stashlop/CMF-Watch-Pro).

## Windows / BLE gotchas

- `BleakBluetoothNotAvailableError` ("radio is not powered on") means Windows Bluetooth is off; both scripts exit with code 2 and a message.
- The watch is dual-mode: Windows may already have it paired for classic audio ("Watch Pro Hands-Free"), which shows its address in Device Manager. BLE still advertises while paired.
- Connecting right after a scan occasionally fails once; `inspect_gatt` exits 1 with a message, and rerunning works.
- bleak 3.x API: `BleakScanner.discover(return_adv=True)` returns `{address: (BLEDevice, AdvertisementData)}`; `client.services` is a property; characteristic/descriptor objects have `.description` for SIG names.
