# Interactive Omnitrix on the CMF Watch Pro 1: what the hardware allows

Evidence used: read-only GATT dump of this watch (`protocol-notes.md`), CMF support documentation for the
Watch Pro, and the Gadgetbridge wiki for the D395. Nothing from Watch Pro 2 / Pro 3 is assumed.

## Findings

- CMF documents only two face options for the Watch Pro: the **marketplace** and **Customize Watch Face**
  (a background image plus a CMF-supplied style). There is no app store, no SDK, and no way to install
  third-party apps.
- A community "Watchface SDK" for the CMF Watch Pro was announced on the Nothing Community forum, but nothing
  has been released (unverified since).
- Gadgetbridge has reverse-engineered much of the D395 protocol (notifications, activity, settings), and its
  face upload is experimental. Native faces are files in a proprietary format, cached by the official app under
  `/data/data/com.nothing.cmf.watch/.../cache/dial/` (root required to read). Their structure is undocumented.
- The 7 vendor BLE services on this watch are all write + notify command channels. Nothing about faces or apps
  can be learned or done through reads.

## Feature table

| Omnitrix feature | On the watch today | What it would take |
|---|---|---|
| Omnitrix home face (static artwork, watch-drawn clock) | **Supported** via Customize Watch Face | Done: `watch_faces/omnitrix_home.png` |
| 10 alien-themed faces | **Supported** (one at a time, switched in the app) | Done: `watch_faces/<alien>.png` |
| Live time/date/battery in Omnitrix style (our digits, our layout) | Not with a photo face | A **native face file**: reverse-engineer the cached `dial` format (read-only analysis, needs root to obtain files). Installing it would be a write; needs explicit approval and a verified Pro 1 upload path |
| Animated energy ring / animated face | **Unknown** | Only if the native face format supports animation. Not determinable without that format |
| Alien selection by touch / rotating dial | **Not supported** | Custom touch handling = custom application = **firmware modification** |
| Transformation animation on demand | **Not supported** | Firmware modification |
| Alien-specific screens / info pages | **Not supported** (beyond picking a face) | Firmware modification |
| Custom menus / custom home interface | **Not supported** | Firmware modification |
| Side button opens the alien dial | **Not supported** | Firmware modification |
| Sound effects | **Not supported** | Firmware modification |

**Firmware modification** is out of scope under this project's safety rules: no tools exist, no recovery path is
documented, and it risks bricking the watch.

## Options for the interactive part (on the CMF Watch Pro 1)

1. **Photo faces (done):** the Omnitrix home + 10 alien faces via the official app. Still art; the watch draws the clock.
2. **Native CMF face (research):** a live, possibly animated Omnitrix clock in the watch's own face format. Needs
   read-only analysis of the format; still not interactive. The best the Pro 1 can do beyond photos.
3. **Companion app (`companion/`, prototype):** a phone/PC app that borrows the watch's existing features over its
   documented BLE command channel — show the alien's name, use the media buttons as a dial, buzz on "transform",
   switch an installed face. Not the on-watch dial/animation, but it runs on the real Pro 1. Dry-run only until the
   protocol is verified and a recovery path is confirmed (see `companion/README.md`).

### Fallback on different hardware (not the CMF watch)

- **Programmable 410 × 502 watch:** the Waveshare ESP32-S3-Touch-AMOLED-2.06 has the same resolution plus touch,
  buttons and audio. **Implemented in `esp32/`**: the full interactive Omnitrix as firmware (see `esp32/README.md`).
  It hasn't been compiled or run on a board, and it is NOT the CMF-watch install target.
