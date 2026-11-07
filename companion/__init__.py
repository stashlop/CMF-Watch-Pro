"""Companion-app prototype for the CMF Watch Pro 1 (model D395).

This package is DIFFERENT from the rest of the project: it can WRITE to the watch. Everything in
``ble/``, ``watchface/``, ``omnitrix/`` and ``deploy/`` is strictly read-only and is enforced by
``tests/test_safety.py``. This package is deliberately outside that scan, so it carries its own guard rails:

  * It speaks only the **documented** CMF protocol (reverse-engineered by the open-source Gadgetbridge
    project, AGPLv3), never undocumented commands.
  * It authenticates with the owner's OWN pairing key ("K1"), obtained from their own CMF account/app,
    exactly as Gadgetbridge does. It never cracks, guesses or bypasses authentication.
  * It defaults to DRY-RUN: it builds and prints packets but sends nothing. Sending to the watch needs
    a loaded K1 plus an explicit, per-run confirmation.
  * It never sends firmware, never uses the factory shell, never factory-resets. Those commands are
    excluded at the builder level (see ``commands.ALLOWED``).

Byte-level details mirror Gadgetbridge and have NOT been confirmed against this watch's own traffic, so
nothing here should be treated as verified until a capture confirms it.
"""
