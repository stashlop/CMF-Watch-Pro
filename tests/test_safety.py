import asyncio
import re
import unittest
from pathlib import Path

from ble.safety import FORBIDDEN_METHODS, ReadOnlyClient, ReadOnlyViolation

ROOT = Path(__file__).resolve().parents[1]
CALL = re.compile(r"\.(%s)\s*\(" % "|".join(FORBIDDEN_METHODS))
SOURCE_DIRS = ("ble", "watchface")


class FakeClient:
    address = "00:11:22:33:44:55"
    is_connected = True
    mtu_size = 23
    services = []

    async def read_gatt_char(self, char):
        return bytearray(b"ok")

    async def write_gatt_char(self, *a, **k):  # must never be reachable
        raise AssertionError("write reached the real client")


class ReadOnlyClientTests(unittest.TestCase):
    def test_reads_pass_through(self):
        c = ReadOnlyClient(FakeClient())
        self.assertEqual(asyncio.run(c.read_gatt_char("x")), bytearray(b"ok"))

    def test_forbidden_methods_raise(self):
        c = ReadOnlyClient(FakeClient())
        for name in FORBIDDEN_METHODS:
            with self.assertRaises(ReadOnlyViolation, msg=name):
                getattr(c, name)

    def test_cannot_reach_wrapped_client(self):
        c = ReadOnlyClient(FakeClient())
        with self.assertRaises(ReadOnlyViolation):
            c.client
        with self.assertRaises(ReadOnlyViolation):
            c.anything = 1


class SourceScanTests(unittest.TestCase):
    """Fails if any project code calls a write/notify/pair BLE method or enables pairing."""

    def test_no_forbidden_calls(self):
        offenders = []
        for d in SOURCE_DIRS:
            for path in (ROOT / d).rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                for m in CALL.finditer(text):
                    offenders.append(f"{path.relative_to(ROOT)}: .{m.group(1)}(")
                if re.search(r"pair\s*=\s*True", text):
                    offenders.append(f"{path.relative_to(ROOT)}: pair=True")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
