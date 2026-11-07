# Omnitrix companion app for the CMF Watch Pro 1 (prototype)

The CMF Watch Pro 1 can't run our UI (no app runtime, no SDK, no custom firmware — see
`../docs/omnitrix-feasibility-report.md`). A **companion app** instead drives the watch's *existing* features
over its documented Bluetooth command channel, to add Omnitrix flavour without new firmware:

- show the selected alien's name on the watch (notification / music line),
- read the watch's media buttons as "turn the dial / select",
- buzz (find-watch) as transformation feedback,
- switch to an already-installed alien face.

This is **not** the on-watch dial or animation. That needs firmware the Pro 1 can't take. The full interactive
Omnitrix lives in the desktop simulator (`../omnitrix/`).

## Status: prototype, dry-run only

Everything works **offline** and is tested (`../tests/test_companion.py`): the packet framing, AES-128-CBC
crypto, chunking, session-key derivation, and the Omnitrix→command mapping. **Live sending is disabled**: the
authenticated handshake isn't implemented, and per your rules nothing is sent to the watch until compatibility
and a recovery path are confirmed.

```powershell
python -m companion status            # is K1 present? what's allowed?
python -m companion dryrun            # build the demo plan, print the packets (sends nothing)
python -m companion select xlr8       # dry-run: announce an alien
python -m companion transform xlr8    # dry-run: transformation feedback
```

## Safety design

- **Separate from the read-only code.** `ble/`, `watchface/`, `omnitrix/`, `deploy/` are read-only and enforced
  by `tests/test_safety.py`. This package is the only one that *can* write, so it's deliberately outside that
  scan and carries its own guards. A test asserts the read-only packages never import it.
- **Documented commands only.** Command IDs and layouts come from the open-source Gadgetbridge CMF driver.
  `commands.ALLOWED` is the whole set this app can emit; `commands.BLOCKED` names destructive ones
  (factory reset, firmware transfer) that are refused at build time.
- **No firmware, no factory shell, no pairing.** The client uses `pair=False` and never touches the firmware
  or factory-shell services.
- **Authenticates with your own key.** The protocol needs a 16-byte pairing key ("K1") that the watch issues to
  *your* CMF account when you pair in the official app. It can't be generated locally and this app never tries
  to; it only reads your K1 from `$CMF_K1` or `data/companion/k1.key` (gitignored). To obtain it, follow
  Gadgetbridge's documented steps for your own device:
  <https://gadgetbridge.org/basics/pairing/nothing-cmf-server/>

## What's left before it can run on the watch

1. **Verify the byte protocol** against a passive capture of the official app (read-only). The current layouts
   mirror Gadgetbridge and are unconfirmed on the Pro 1.
2. **Implement the handshake** (`client._handshake`): AUTH_PHONE_NAME → watch MAC → nonce → confirm.
3. **Confirm a recovery path** (a face/setting can always be restored from the official app) before the first
   live send.
4. Only then, with your K1 and explicit confirmation, try one low-risk command (e.g. a notification) and check
   the watch.
