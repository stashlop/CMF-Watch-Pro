# CMF-Watch-Pro

Python BLE companion app for the CMF Watch Pro using `bleak` and `pillow`.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```powershell
python -m ble.discover          # passive scan, saves data/scans/*.json
python -m ble.inspect_gatt      # read-only GATT dump of the found watch, saves data/gatt/*.json
python -m omnitrix.studio       # Omnitrix Design Studio (desktop simulator)
python -m omnitrix.export       # export Omnitrix PNGs/GIFs to data/exports/omnitrix
python -m watchface.preview     # watch-face preview window
python -m unittest discover -s tests -t .
```

All BLE access is read-only: no characteristic writes, notifications, pairing or firmware changes.

The Omnitrix UI is a fan project inspired by Ben 10 (names and trademarks belong to their owners). It runs as a desktop simulator; see `docs/hardware-capabilities.md` for what the watch itself supports.
