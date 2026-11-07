"""Read-only BLE tooling for the CMF Watch Pro (1st generation).

Every connection must go through ``ble.safety.ReadOnlySession``; nothing in
this package writes characteristics, subscribes to notifications or pairs.
"""
