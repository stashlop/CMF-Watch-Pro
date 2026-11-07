"""Set the Omnitrix watch's clock (PCF85063 RTC) from this PC over USB serial.

    python -m esp32.settime [COM5]

Without a port it picks the first Espressif USB device (VID 0x303A). Needs pyserial (`pip install pyserial`).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

ESPRESSIF_VID = 0x303A


def find_port() -> str | None:
    from serial.tools import list_ports

    for p in list_ports.comports():
        if p.vid == ESPRESSIF_VID:
            return p.device
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port", nargs="?")
    args = ap.parse_args(argv)
    try:
        import serial
    except ImportError:
        print("pyserial is not installed: pip install pyserial")
        return 2
    port = args.port or find_port()
    if not port:
        print("No Espressif USB device found. Plug the watch in or pass the COM port.")
        return 2
    with serial.Serial(port, 115200, timeout=1) as s:
        time.sleep(0.3)
        s.reset_input_buffer()
        # send at the start of a second so the RTC lands within a few ms
        while datetime.now().microsecond > 20_000:
            time.sleep(0.002)
        now = datetime.now()
        s.write(f"time {now:%Y-%m-%d %H:%M:%S}\n".encode())
        deadline = time.time() + 3
        while time.time() < deadline:
            line = s.readline().decode(errors="replace").strip()
            if line == "ok time":
                print(f"{port}: clock set to {now:%Y-%m-%d %H:%M:%S}")
                s.write(b"status\n")
                time.sleep(0.3)
                print(s.read_all().decode(errors="replace").strip())
                return 0
    print("No confirmation from the watch (is the Omnitrix firmware running?)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
