"""Deployment of the Omnitrix watch faces to a real CMF Watch Pro 1 (D395).

The only installation route this project uses is the official CMF Watch app's
"Customize Watch Face" (custom background). This package:
  * identifies the watch over BLE with read-only operations,
  * validates the exported faces,
  * optionally copies them to the phone over ADB (the phone, never the watch),
  * walks through the official install steps and records user-confirmed results.

It never writes to the watch. Direct BLE face upload is not used: no protocol for
it is verified on the Pro 1 (see docs/install-guide.md).
"""
