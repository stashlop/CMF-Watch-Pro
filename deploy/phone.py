"""Copy faces to the phone over ADB so the CMF Watch app's photo picker can see them.

This touches the PHONE only (a folder under Pictures). It never talks to the watch.
Requires USB debugging enabled on the phone and the PC authorised.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from deploy import config


def find_adb() -> str | None:
    on_path = shutil.which("adb")
    if on_path:
        return on_path
    sdk = Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    return str(sdk) if sdk.exists() else None


def _run(adb: str, *args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run([adb, *args], capture_output=True, text=True, timeout=timeout)


def devices(adb: str) -> list[dict]:
    out = _run(adb, "devices", "-l").stdout.splitlines()[1:]
    result = []
    for line in out:
        parts = line.split()
        if len(parts) >= 2:
            info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
            result.append({"serial": parts[0], "state": parts[1], **info})
    return result


def phone_model(adb: str, serial: str) -> str:
    return _run(adb, "-s", serial, "shell", "getprop", "ro.product.model").stdout.strip()


def push_faces(adb: str, serial: str, files: list[Path]) -> list[dict]:
    _run(adb, "-s", serial, "shell", "mkdir", "-p", config.PHONE_DIR)
    results = []
    for f in files:
        dest = f"{config.PHONE_DIR}/{f.name}"
        r = _run(adb, "-s", serial, "push", str(f), dest, timeout=120)
        # confirm it landed with the right size
        size = _run(adb, "-s", serial, "shell", "stat", "-c", "%s", dest).stdout.strip()
        ok = r.returncode == 0 and size == str(f.stat().st_size)
        # ask the media scanner to index it so it shows in the photo picker (best effort)
        _run(adb, "-s", serial, "shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
             "-d", f"file://{dest}")
        results.append({"file": f.name, "dest": dest, "ok": ok, "detail": (r.stdout or r.stderr).strip()[-200:]})
    return results
