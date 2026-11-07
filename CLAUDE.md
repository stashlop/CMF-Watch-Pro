# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PC-side tooling (Windows, Python 3.12, `bleak` 3.x, `pillow`) for building a Ben 10 Omnitrix UI for the owner's physical **CMF Watch Pro, 1st generation** (model D395, codename "lark"). **The CMF Watch Pro 1 is the target device.** The Omnitrix UI (`omnitrix/`) is designed in a desktop simulator, and the realistic ways to get it onto the actual watch are: install-ready photo faces via the official app (`deploy/`, `omnitrix/watch_release.py`), and a companion app that drives the watch's documented BLE features (`companion/`, prototype). `esp32/` is an **optional fallback** on different hardware for the fully-interactive experience, not the install target. What can/can't run on the CMF watch, and the install/feasibility analysis, are in `docs/omnitrix-feasibility-report.md`, `docs/hardware-capabilities.md`, `docs/interactive-features.md` and `docs/protocol-notes.md`.

## Hard rules

- **Read-only BLE only.** Never write characteristics or descriptors, subscribe to notifications (`start_notify` writes the CCCD), pair/unpair, enter factory/debug modes, or touch firmware. This holds even if a capture suggests a "harmless" command.
- All connections go through `ble.safety.ReadOnlySession`, which owns the `BleakClient` and yields a `ReadOnlyClient` exposing only `services` and `read_gatt_char`/`read_gatt_descriptor`. Don't construct `BleakClient` anywhere else. `tests/test_safety.py` scans `ble/` and `watchface/` for calls to forbidden methods and `pair=True`, and will fail.
- **Watch Pro 1 ≠ Watch Pro 2 / Watch 3 Pro.** Don't reuse their UUIDs, packet formats, screen sizes or face formats. `ble/identify.py` deliberately excludes names with a generation digit. Only facts observed on this watch go under "Verified" in `docs/protocol-notes.md`, with the capture file they came from.
- Watch faces here are this project's own JSON format, rendered on the PC. Nothing uploads faces to the watch; the native face format is unknown.
- `omnitrix/` must stay separate from watch integration: it never imports `ble`/`bleak` (enforced by `tests/test_omnitrix.py`). Anything that would send data to the watch, a face upload included, needs the owner's explicit approval first.
- Alien emblems are original geometric symbols, not traced Ben 10 character art. Keep it that way.

## Commands

Use the venv interpreter (`.venv\Scripts\python.exe`, or activate it first). Run everything from the repo root as modules so the `ble`/`watchface` packages resolve.

```powershell
pip install -r requirements.txt

python -m unittest discover -s tests -t .                       # all tests
python -m unittest tests.test_identify.ClassifyTests.test_pro_1_candidate   # single test

python -m ble.discover [--timeout 10] [--name "<part of name>"] [--address AA:BB:..]
python -m ble.inspect_gatt [--address AA:BB:..] [--read none|standard|all]

python -m omnitrix.studio                                         # Omnitrix Design Studio (interactive simulator)
python -m omnitrix.export [--only faces|backgrounds|gifs|screens] [--time 10:09]
python -m omnitrix.watch_release [--all | --theme xlr8]          # INSTALL-READY faces -> watch_faces/ (+ previews/)
python -m omnitrix.photoface                                      # phone pack: calibration + photo-face backgrounds (top/center/bottom clock)

python -m deploy check | push | guide | verify --face X | status  # deployment to the real watch (see docs/install-guide.md)

python -m companion status | dryrun | select <alien> | transform <alien>   # CMF companion prototype (dry-run; sends nothing)

python -m esp32.assets [--preview]                                # OPTIONAL fallback hardware (not the CMF watch): render asset pack
cd esp32\firmware; pio run [-t upload | -t uploadfs]              # build / flash firmware / flash asset pack (run assets first)
python -m esp32.settime [COM5]                                    # set the ESP32 watch RTC over USB serial

python -m watchface.preview                                       # live GUI
python -m watchface.preview --face activity_rings --time 10:09:30 --export data/previews/x.png
```

There is no linter or build step configured.

## Architecture

**BLE flow (`ble/`)**: `discover` does a passive scan, scores each device with `identify.classify` (the watch often advertises without a name, so the main rule is the advertisement fingerprint recorded in `docs/protocol-notes.md`; name rules and `--name`/`--address` are fallbacks), and writes `data/scans/scan_<ts>.json` with raw manufacturer/service data and a `best_candidate`. `inspect_gatt` with no `--address` picks `best_candidate` from the newest scan, connects via `ReadOnlySession`, and writes `data/gatt/gatt_<addr>_<ts>.json`. Its `--read` policy controls which values are read: `standard` (default) reads only SIG-assigned characteristics (0x2A00–0x2BFF) and descriptors (0x2900–0x29FF); vendor attributes are listed but not read unless `--read all`. Read failures (e.g. encryption required) are recorded per attribute rather than worked around by pairing.

**Watch faces (`watchface/`)**: `render.render(face_dict, WatchState, DisplayProfile)` is pure and returns a 410×502 RGB image with the rounded-screen corners masked. Text elements are `str.format` templates over `WatchState` fields (`{now:%H:%M}`, `{steps:,}`, `{battery}`...). Element types and fields are documented in the `render.py` docstring; adding a type means extending `_draw_element`. Faces live in `watchface/faces/*.json` and are picked up automatically by the GUI, the `--list` flag and the render test. The Tk GUI reloads a face when its file's mtime changes, so faces can be edited live. `display.py` holds the screen size from the public spec sheet (not read from the device).

**Omnitrix prototype (`omnitrix/`)**: every screen in `screens.py` is a pure function `screen(t, ..., data: WatchData, style: Style) -> 410x502 Image`, where `t` is seconds (it drives all animation). Screens: `home`, `selector` (fractional `sel` while the dial turns; `burst` drives the confirm animation), `select_confirm`, `info`, `alien_face`, and `transform` (an 8-step timeline over `TRANSFORM_DURATION`, whose phases are named in the function). Layout constants (`C`, `R_RING`, `R_CORE`, ...) at the top of `screens.py` are shared with the Studio's hit-testing. `gfx.Frame` draws at 2x supersampling plus a separate glow layer that is blurred and added in `finish()`. Pass `glow=` to make a shape bloom; outlined shapes bloom along the outline only. Expensive layers (`background`, `core_tile`, `holo_tile`) are `lru_cache`d by their arguments, so keep those arguments hashable and coarse. Each `Alien` in `aliens.py` names an emblem drawer (`emblems.DRAWERS`) and an effect (`fx.EFFECTS`). Effects run at intensity ~0.5 as the ambient alien-face theme and at 1.0 as that alien's selection burst; `fx.POST` holds whole-image post-processing (Upgrade's glitch). Adding an alien means adding one `Alien` entry plus an emblem and an effect function. Tests require every alien to have a unique effect. `watch_release.py` produces the actual deliverables in the tracked `watch_faces/` folder: the dial is rendered on black, scaled to `DIAL_SCALE` and centred, with `CLOCK_BANDS` kept dark for the watch's own clock and near-blacks crushed for AMOLED. Its tests enforce centring, dark bands and the true-black share. `photoface.py` makes the still images for the CMF Watch app's custom photo face (confirmed to exist; the owner installs them). They have no clock or date, because the watch draws its own. Its `top` variant moves the dial down via the `c=` centre parameter that the `draw_*` building blocks and `background()` accept. `studio.py` is a Tk state machine (`home -> select -> confirm -> info -> transform -> face`) that simulates the side button, dial turning, tap and long-press. The real watch supports none of those inputs.

**Deployment (`deploy/`)**: the only install route is the official CMF Watch app's "My > Customize Watch Face" (custom background). It's documented by CMF for the Watch Pro, and the owner confirmed it's in their app. `deploy` identifies the watch via `ReadOnlySession` (expects GAP name "Watch Pro" and model "lark"; firmware is not exposed over standard GATT), validates `watch_faces/*.png` (`deploy/validate.py`, layout from `omnitrix.watch_release.CLOCK_BANDS`), can copy faces to the phone over ADB (phone only), and records owner-confirmed results in `data/deploy/install_log.json`. The current face can't be read back over BLE, so never report a face as installed unless `deploy verify` recorded the owner's confirmation. Direct BLE face upload (Gadgetbridge's experimental implementation) is deliberately not used. Feature limits are in `docs/interactive-features.md`.

**Companion app (`companion/`)**: a prototype that adds Omnitrix behaviour to the CMF Watch Pro 1 over its documented BLE command channel, without new firmware (show the alien name via notification/music line, media buttons as dial turns, find-watch buzz as transform feedback, switch an installed face). This is the ONE package that can write to the watch, so it lives outside `tests/test_safety.py`'s read-only scan and carries its own guards: documented commands only (`commands.ALLOWED`; `commands.BLOCKED` refuses factory reset / firmware), `pair=False`, never the firmware or factory-shell services, and **dry-run by default** — `client.run_plan` sends only with `live=True` + a loaded K1 (owner's own pairing key, from `$CMF_K1`/`data/companion/k1.key`, gitignored) + explicit `consent`. Live sending is currently disabled: `client._handshake` is unimplemented pending a verified capture. `protocol.py` (framing/AES/CRC/chunking) and the command layouts mirror Gadgetbridge's AGPLv3 CMF driver and are UNVERIFIED on this watch. `tests/test_companion.py` is fully offline and asserts the read-only packages never import `companion`.

**ESP32 watch (`esp32/`), optional fallback hardware (NOT the CMF watch)**: the interactive Omnitrix as firmware for the Waveshare ESP32-S3-Touch-AMOLED-2.06 (410×502 AMOLED, FT3168 touch, PCF85063 RTC, AXP2101 PMU). It's a separate device, never the CMF watch. `esp32/assets.py` renders with `omnitrix/` and splits screens into textless face JPEGs, chained battery-meter patches (patch k = image(k lit) inside its diff box, so 1..n over the base is exact), per-theme glyph sprites (RGB565, added onto the face), and JPEG frame sequences. It writes `esp32/firmware/data/` (LittleFS) and `src/assets_manifest.h`; both are gitignored and tied by a build ID the firmware checks at boot. Meter/font files are zlib-wrapped (`OZ1`) and inflated with the S3 ROM's miniz. `assets.compose()` mirrors the firmware compositor (`gfx.cpp`, integer 1/16-px text layout), and `tests/test_esp32.py` compares it to `omnitrix.screens`. Firmware: `ui.cpp` mirrors `studio.py`'s state machine (PWR = side button, BOOT = back, swipe/tap turns the dial, 0.6 s hold transforms), and `assets.cpp` keeps a PSRAM cache with a core-0 prefetch task. Flash layout is 16 MB (as in Waveshare's demos) with a 3 MB app, so the pack must stay under `assets.FLASH_BUDGET`. The PMU is only read; don't change its rails.

**Data**: `data/scans`, `data/gatt`, `data/previews`, `data/exports` are gitignored because captures contain the watch's Bluetooth address and the repo is public (github.com/stashlop/CMF-Watch-Pro).

## Windows / BLE gotchas

- `BleakBluetoothNotAvailableError` ("radio is not powered on") means Windows Bluetooth is off; both scripts exit with code 2 and a message.
- The watch is dual-mode: Windows may already have it paired for classic audio ("Watch Pro Hands-Free"), which shows its address in Device Manager. BLE still advertises while paired.
- Connecting right after a scan occasionally fails once; `inspect_gatt` exits 1 with a message, and rerunning works.
- bleak 3.x API: `BleakScanner.discover(return_adv=True)` returns `{address: (BLEDevice, AdvertisementData)}`; `client.services` is a property; characteristic/descriptor objects have `.description` for SIG names.
