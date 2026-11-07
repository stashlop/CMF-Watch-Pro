# Omnitrix firmware for an ESP32 watch

This is the interactive Omnitrix running on real watch hardware: the
**Waveshare ESP32-S3-Touch-AMOLED-2.06**. The board has a 410 × 502 AMOLED (the same size the designs use), a
touch screen, two side buttons, an RTC and a battery charger.

The CMF Watch Pro 1 can't run third-party software (see `docs/interactive-features.md`), so this is a separate
device. Nothing in `esp32/` talks to the CMF watch.

## What it does

| Screen | How you get there |
|---|---|
| **Omnitrix home**: live clock, seconds, date, battery energy meter | Boot; **BOOT** button from an alien face |
| **Alien dial**: 10 aliens on the orbit, turning animation | **PWR** button, or tap the dial |
| Turn the dial | Swipe left/right, or tap an alien on the orbit |
| **Selection burst**, then the **info card** | Tap the core |
| **Transformation** (wake, symbol, dial spin, ring lights, alien appears, name, flash), then fade to the face | **Hold** 0.6 s on the dial or the info card (a green ring fills while you hold) |
| **Alien watch face**: themed live clock, date, battery | End of the transformation |
| Back | **BOOT** (face → home, info → dial, dial → face/home) |

The screen turns off after 15 s on a face (30 s in the dial/info). Any button or touch wakes it.

## How it is built

The Python renderer (`omnitrix/`) stays the single source of the look. `python -m esp32.assets` renders:

- **Faces**: home + 10 alien faces without their text, as JPEG.
- **Battery meter patches**: chained patches, so 0–16 lit segments (red at 20 % or less) come out exactly as
  the Studio draws them, glow included.
- **Glyph sprites**: one set per theme for the clock, seconds, date and label. The firmware adds them onto the
  face, so the live time keeps the Omnitrix glow.
- **Frame sequences**: the dial, the selection bursts, the info cards and the transformation (10 fps; the first
  2 s are shared by all aliens).

`esp32.assets.compose()` is a PC model of the firmware compositor. `tests/test_esp32.py` checks it against
`omnitrix.screens`.

The pack is about 12.4 MB in a 13.5 MB LittleFS partition (16 MB flash layout, as in Waveshare's demos). The
firmware keeps a 4 MB PSRAM cache with a background prefetch task, so animations don't wait on flash.

## Build and flash

Needs PlatformIO (`pip install platformio`). The first build downloads Arduino-ESP32 3.2.0 (pioarduino).

```powershell
.venv\Scripts\python.exe -m esp32.assets --preview   # 1. render the asset pack (+ PC previews in data/exports/esp32)
cd esp32\firmware
pio run                                              # 2. compile
pio run -t upload                                    # 3. flash the firmware (USB-C)
pio run -t uploadfs                                  # 4. flash the asset pack (takes a few minutes)
cd ..\..
pip install pyserial
.venv\Scripts\python.exe -m esp32.settime            # 5. set the watch clock from the PC
```

Run steps 3 and 4 after every asset rebuild: each pack has a build ID, and the firmware refuses a pack that
doesn't match it (it shows "ASSET MISMATCH").

If upload can't connect, hold **BOOT**, tap **PWR** (or replug USB), release **BOOT**, then retry.

## Serial

`pio device monitor` (115200 baud). Commands: `status`, `time YYYY-MM-DD HH:MM:SS`.

## Known limits

- **Not yet compiled or run on hardware.** The asset pack is checked on the PC (`tests/test_esp32.py`). The
  pins and driver setup come from Waveshare's examples for this board, but touch coordinates, panel offset and
  frame rates still need checking on a real unit.
- Ambient animations (the ring sweep, the energy flow) are frozen on the faces to save flash and battery. Every
  transition is animated.
- 24-hour clock only. No sound, IMU or Wi-Fi yet (the board has an ES8311 codec, a QMI8658 IMU and Wi-Fi/BLE).
