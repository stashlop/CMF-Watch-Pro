# Project Omnitrix on the CMF Watch Pro 1: feasibility report

Date: 2026-11-07. Target: the owner's CMF Watch Pro 1 (model D395). Nothing was written to the watch while
producing this report. Each claim names its evidence: "observed" = seen on this watch with this repo's
read-only tools; "documented" = published by a named third party; "unknown" = no reliable evidence found.

## 1. Summary

| Goal | On the Pro 1? | Route |
|---|---|---|
| Omnitrix home + 10 alien faces (still art, watch draws the clock) | **Yes, today** | Official app → Customize Watch Face (images already on the phone) |
| Omnitrix-styled live clock in a native face, maybe animated | **Maybe; needs research** | Native face format, partly documented (§5) |
| Alien name / buzz / button cues from a companion app | **Maybe; needs your approval to send** | Companion app over the official protocol (§6) |
| Touch alien dial, tap-to-transform, custom menus, boot animation, sound | **No** | Needs replacement firmware; none exists for the Pro 1 (§5) |

The interactive Omnitrix (dial, transformation, menus) needs code running on the watch. The Pro 1 has no way to
load that short of replacing its firmware, and no replacement firmware, build tools or recovery path exists for
it. The closest achievable result is: the face set (done), plus optional live/animated native faces and a
companion-app layer, both of which still need work and your approval before anything is sent to the watch.

## 2. Hardware (Phase 1)

| Item | Finding | Evidence |
|---|---|---|
| Model | D395, "Watch Pro", by Nothing Technology Ltd | FCC ID 2AZEQ-D395 grant; GAP name "Watch Pro" observed |
| Display | 1.96" AMOLED, 410×502 | Retail listing tied to the FCC label; matches the spec sheet |
| Radio | Bluetooth 2402–2480 MHz, dual-mode (BLE + classic audio) | FCC grant; observed advertising + "Watch Pro Hands-Free" |
| Model string | "lark" (internal codename) | observed, characteristic 0x2A24 |
| SoC / RAM / storage | **unknown for the Pro 1** | no teardown or datasheet found |
| Touch controller | **unknown** | not exposed over BLE |
| Bootloader / recovery | **unknown**; firmware container is "AOTA" | documented by Gadgetbridge for the CMF line |

The Pro 1's processor is not published. The Watch **Pro 2** (model D398, a different device) is reported as an
Actions ATS3089C from firmware strings, but that must not be assumed for the Pro 1. The FCC filing lists an
internal-photos exhibit that could identify the chip; it is behind a bot check and the FCC mirror wouldn't open
in this session, so it's left as a next step rather than a confirmed fact.

## 3. Bluetooth (Phase 2)

Observed GATT on this watch (read-only, MTU 247) is recorded in `protocol-notes.md`. Seven vendor services,
each a write + notify pair; none is readable. Cross-referencing the service UUIDs with Gadgetbridge's
open-source CMF driver (AGPLv3) identifies what four of them are:

| Service UUID | Role (per Gadgetbridge) |
|---|---|
| `0000fff0-…` (FFF2 write / FFF1 notify) | Command channel (settings, notifications, music, find-watch) |
| `02f00000-…ffe0` (ffe1/ffe2) | Bulk data channel (watch-face / AGPS upload) |
| `02f00000-…fe00` (ff01/ff02) | Firmware channel |
| `77d4e67c-…` (ff01/ff02) | Factory "AT" shell (e.g. `AT GETSECRET`) |

So the watch **does** have a documented channel for uploading faces and firmware over Bluetooth, and a command
channel that can push notifications, music info and a find-watch buzz. The catch is authentication (§6).

## 4. Official app protocol (Phase 2)

From Gadgetbridge's driver, read today:
- Framed packets: `0xF5`, length, command IDs, chunk count/index. Most payloads are **AES-128-CBC encrypted**
  with a per-session key; a fixed 16-byte IV is in the source.
- **Pairing needs a server key ("K1").** The watch and the official app negotiate it through the vendor's
  servers; it is not derivable locally. Gadgetbridge can only connect if you extract K1 from the official app
  (needs a rooted phone) or capture it from logs during pairing.
- Command IDs are enumerated in the driver: notifications, alarms, weather, music info, find-watch, watch-face
  switch, factory reset, firmware/face transfer, and more.

## 5. Firmware (Phase 3)

- **Format:** firmware images start with `AOTA`; the container uses CRC32 and a version field (documented by
  Gadgetbridge; confirmed for the CMF line, inferred for the Pro 1).
- **Custom firmware:** **none exists for the Pro 1.** No SDK, no build target, no published dump, no recovery
  tool. A Watch **Pro 2** dump and an ESP32-based community toolkit exist, but both target different hardware and
  must not be flashed here.
- **Backup / restore:** the watch exposes no documented way to read its firmware out over BLE, so there is no
  verified backup, and therefore no safe way to restore after a bad flash. Under the project's rules this means
  **do not flash firmware.**
- **Native face format (the realistic "custom software" path):** Gadgetbridge's `CmfFwHelper` documents the
  photo/native face container — a header, a tag "tree", a resources section, a duplicated footer, and two CRC32s,
  with a generation byte that differs between the original Watch Pro (`02`) and the Pro 2/3 (`00`). This is the
  most promising route to an Omnitrix-styled face with a live, possibly animated clock, but the tag tree's
  meaning is only partly known. Filling it in means analysing faces the official app already made (read-only,
  on a rooted phone) — not writing to the watch.

## 6. What a companion app could do (Phase 5, needs approval before sending)

Because the command channel is documented, a PC or phone app could, once authenticated with your K1, use the
watch's existing features to add Omnitrix flavour without new firmware:
- Show an alien's name as a notification or music title.
- Use the watch's media-button events (play/next/previous) as "turn the dial / select".
- Trigger the find-watch vibration as transformation feedback.
- Switch the active watch face by command (face-switch command ID exists; effect on the Pro 1 unverified).

This is **not** the on-watch dial or animation — it's the phone driving screens the watch already has. Every
item sends data to the watch, so each needs your explicit go-ahead, and it reuses Gadgetbridge's protocol, which
still has to be checked against the Pro 1.

## 7. What is not possible on the Pro 1

Touch-based alien selection, an on-watch rotating dial, tap-to-transform, custom menus, a custom boot
animation, and custom sound effects all require code running on the watch, i.e. replacement firmware. With no
firmware tools and no recovery path, that can't be done safely. The full interactive Omnitrix already runs in
the desktop simulator (`omnitrix/`), and as firmware for a programmable 410×502 watch (`esp32/`).

## 8. Recommended next steps

1. **Install the faces** you already have and confirm the display fit (calibration.png first). No risk.
2. **Identify the SoC** from the FCC internal-photos exhibit (2AZEQ-D395) when it's reachable. Read-only.
3. **Study the native face format**: capture a few faces the official app installs (rooted phone, read-only) and
   extend the `CmfFwHelper` structure until an Omnitrix face with a live clock can be built. No writes to the
   watch.
4. **Decide on a companion app** (§6). If you want it, I'll prototype it read-first and ask before any command
   that writes to the watch.
5. **Firmware replacement stays off the table** unless a verified Pro 1 backup-and-recovery path appears.

## Sources

- Observed captures: `data/gatt/…`, `data/scans/…` (local, gitignored), summarised in `protocol-notes.md`.
- Gadgetbridge CMF driver (AGPLv3): service UUIDs, command list, auth flow, `CmfFwHelper` face/firmware format.
- Gadgetbridge "Nothing CMF server pairing" page: K1 key extraction.
- FCC ID 2AZEQ-D395 grant and exhibit list (fccid.io / FCC OET).
- Watch Pro 2 firmware dump and ESP32 CMF toolkit: different hardware, used only to understand the CMF platform.
