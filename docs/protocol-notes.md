# CMF Watch Pro (1st gen) — observation log

Only record things observed on **this** watch (Watch Pro 1), with the capture file
they came from (`data/gatt/...json`, `data/scans/...json` — local only, gitignored).
Anything taken from Watch Pro 2 / Watch 3 Pro write-ups goes under "Unverified"
until confirmed here. Don't paste the watch's Bluetooth address into this file
(the repo is public).

## Verified

Source: `scan_20261107_114314.json`, `scan_20261107_114619.json`,
`gatt_<addr>_20261107_114436.json`, `gatt_<addr>_20261107_114628.json`
(Windows 11, bleak 3.0.2, read policy `standard`).

### Advertising
- Dual-mode: the same address is used for classic Bluetooth (Windows pairs it as
  "Watch Pro" + "Watch Pro Hands-Free" for calls) and for BLE.
- Advertisement had **no local name** in the first scan; once Windows knew the device it
  reported the name "Watch Pro". Don't rely on the name being present.
- Advertises 16-bit service UUID `0xEFE7`.
- Manufacturer data: the 2-byte company ID (little-endian) + the first 4 payload bytes equal
  the 6-byte device address; the remaining payload bytes are unexplained. The "company ID" is
  therefore not a real Bluetooth SIG company. `ble/identify.py` uses this + `0xEFE7` as its fingerprint.
- Still advertising and connectable over BLE while paired to Windows for classic audio.

### GATT (MTU 247)
| Service | Characteristics (properties) | Value read |
|---|---|---|
| 0x1801 GATT | 2A05 (indicate), 2B29 Client Supported Features (read,write), 2B2A Database Hash (read) | 2B29 = `01`, 2B2A = 16-byte hash |
| 0x1800 GAP | 2A00 Device Name, 2A01 Appearance, 2A04 PPCP | "Watch Pro", 0 (unknown), interval 0x18–0x28, latency 0, timeout 0x1F4 |
| 0x180F Battery | 2A19 (notify,read) | 100 % at capture time |
| 0x180A Device Info | 2A24 Model Number, 2A29 Manufacturer Name, 2A50 PnP ID | "lark", "Manufacturer" (placeholder), source 1 / vendor 0x0000 / product 0x0000 / version 0x0001 |
| 0xFFD0 | FFD1 (write,wwr), FFD2 (notify), FFD3 (notify,write,wwr) | not readable; FFD2's CCCD read → *Insufficient Encryption* |
| 0xFFF0 | FFF2 (write,wwr), FFF1 (notify) | not readable |
| e49a3001-f69a-11e8-8eb2-f2801f1b9fd1 | …3002 (write,wwr), …3003 (notify) | not readable |
| f48a23c0-f69a-11e8-8eb2-f2801f1b9fd1 | f48a24c1… (write,wwr), f48a25c2… (notify) | not readable |
| 77d4e67c-2fe2-2334-0d35-9ccd078f529c | 77d4ff01… (write,wwr), 77d4ff02… (notify) | not readable |
| 02f00000-0000-0000-0000-00000000fe00 | …ff01 (write,wwr), …ff02 (notify) | not readable |
| 02f00000-0000-0000-0000-00000000ffe0 | …ffe1 (write,wwr), …ffe2 (notify) | not readable |

Every vendor service is a write + notify pair (command/response channels). Nothing
vendor-specific is readable, so their purpose cannot be learned from reads alone.
All other CCCDs read `0000`.

### Connection behaviour (Windows)
- The first `inspect_gatt` attempt right after a scan once failed; an immediate retry succeeded.

## Unverified / to check

- Which vendor service carries the companion-app protocol, OTA, or face upload — unknown.
  Finding out would require observing the phone app's traffic (e.g. an Android HCI snoop log),
  not writing to the watch.
- Classic-BT HFP entry reports VID `0x10D6` / PID `0xB009` (from Windows device manager);
  the chipset vendor has not been confirmed.
- Model string "lark" may be an internal codename; not checked against other units.
- Screen 410×502 is from the public spec sheet, not from the device.
