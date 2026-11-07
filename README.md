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
python -m watchface.preview     # watch-face preview window
python -m unittest discover -s tests -t .
```

All BLE access is read-only: no characteristic writes, notifications, pairing or firmware changes.
