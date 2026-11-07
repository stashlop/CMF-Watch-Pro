# Installing the Omnitrix faces on the CMF Watch Pro 1 (D395)

## The installation method, and why

| Route | Status for the Watch Pro 1 | Used? |
|---|---|---|
| **Official CMF Watch app → "My" tab → "Customize Watch Face"** (custom background + style) | Documented by CMF for the Watch Pro. The owner confirmed it exists in their app | **Yes, the only route** |
| Official face marketplace | Only CMF's own faces | n/a |
| Gadgetbridge face upload over BLE | Listed as "implemented and somewhat working", not shown as tested on the D395. Pairing needs an auth key pulled from the official app with root | **No:** not a Pro 1-verified protocol |
| Writing BLE characteristics directly | Protocol unknown; risk to the watch | **Never** |
| Firmware modification | No tools, no recovery path documented | **Never** without explicit approval |

Sources: support.cmf.tech "How do I customize the watch face?" (Watch Pro category, read 2026-11-07);
Gadgetbridge wiki, Nothing devices (D395 tested on firmware 11.0.0.50).
The CMF page documents no resolution, file-size limit or animation support. It only says the display is "AMOLED".

## Steps

```powershell
python -m deploy check                       # 1. identify watch (read-only) + validate all faces
python -m deploy push --faces calibration.png omnitrix_home.png   # 2. copy to phone (optional, needs USB debugging)
python -m deploy guide --face calibration.png                     # 3. follow the app steps
python -m deploy verify --face calibration.png                    # 4. record what you saw
```

In the app (from CMF's documentation, with our layout advice):
1. Pair and connect the watch to the CMF Watch app; charge it above 20 %.
2. **My** tab → **Customize Watch Face**.
3. Choose a background: the PNG from `Pictures/Omnitrix`. If a crop box appears, keep the whole image.
4. Choose a style with the clock at the **top** or **bottom**. The faces keep y < 119 and y > 383 clear for it.
5. Download it to the watch and keep the phone close until it finishes.
6. Check the watch, then run `python -m deploy verify --face <file>`.

**Install `calibration.png` first.** It shows whether the app crops or scales the image (nested 0/4/8/16/32 px
borders, rulers, a circle that must look round). If anything is cut off or stretched, report it, and the faces will be
re-exported to the real size before you install the Omnitrix set.

## What "verified" means here

The watch does not expose its current face over readable BLE, so no script can see what is on the screen.
`deploy verify` checks that the watch is still connected and responding (read-only), then records **your**
confirmation in `data/deploy/install_log.json`. A face counts as installed only when you've confirmed it.
`python -m deploy status` lists what has been confirmed.

## If something goes wrong

- Pick any other face in the app (marketplace or a previous custom face). A custom background changes only the face.
  It doesn't touch firmware or settings.
- Nothing in this project sends data to the watch, so there's nothing to roll back on the project side.
