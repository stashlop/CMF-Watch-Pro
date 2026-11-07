import unittest

from ble.identify import classify
from ble.inspect_gatt import _value, may_read, sig_short_uuid


class ClassifyTests(unittest.TestCase):
    def test_pro_1_candidate(self):
        m = classify("CMF Watch Pro")
        self.assertTrue(m.is_candidate)
        self.assertEqual(m.model_guess, "watch_pro_1?")

    def test_other_generations_excluded(self):
        for name in ("CMF Watch Pro 2", "CMF WATCH PRO2", "CMF Watch 3 Pro", "CMF Watch Pro-2 1A2B"):
            m = classify(name)
            self.assertFalse(m.is_candidate, name)
            self.assertEqual(m.model_guess, "other_generation", name)

    def test_unrelated_and_missing(self):
        self.assertFalse(classify("Galaxy Buds").is_candidate)
        self.assertFalse(classify(None).is_candidate)
        self.assertEqual(classify("CMF Buds").model_guess, "cmf_other")

    def test_gap_name_watch_pro(self):
        self.assertTrue(classify("Watch Pro").is_candidate)

    def test_advertisement_fingerprint(self):
        # Shape observed on this project's watch: no name, service 0xEFE7,
        # company ID + payload[:4] == address bytes (synthetic address here).
        kw = dict(
            address="AA:BB:01:02:03:04",
            service_uuids=["0000efe7-0000-1000-8000-00805f9b34fb"],
            manufacturer_data={0xBBAA: bytes.fromhex("01020304ffee")},
        )
        self.assertTrue(classify(None, **kw).is_candidate)
        self.assertFalse(classify(None, **{**kw, "service_uuids": []}).is_candidate)
        self.assertFalse(classify(None, **{**kw, "address": "AA:BB:01:02:03:05"}).is_candidate)

    def test_address_hint(self):
        self.assertTrue(classify(None, address="aa:bb:cc:dd:ee:ff", address_hint="AA:BB:CC:DD:EE:FF").is_candidate)

    def test_name_hint_overrides(self):
        self.assertTrue(classify("Watch-7F3A", name_hint="7f3a").is_candidate)


class ValueDecodeTests(unittest.TestCase):
    def test_battery_byte_not_shown_as_text(self):
        v = _value("00002a19-0000-1000-8000-00805f9b34fb", bytes([0x64]))
        self.assertEqual(v["decoded"], {"battery_percent": 100})
        self.assertNotIn("utf8", v)

    def test_string_characteristic(self):
        self.assertEqual(_value("00002a00-0000-1000-8000-00805f9b34fb", b"Watch Pro")["utf8"], "Watch Pro")


class ReadPolicyTests(unittest.TestCase):
    BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb"
    CCCD = "00002902-0000-1000-8000-00805f9b34fb"
    UNASSIGNED_16 = "0000fff1-0000-1000-8000-00805f9b34fb"
    VENDOR_128 = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

    def test_sig_short_uuid(self):
        self.assertEqual(sig_short_uuid(self.BATTERY_LEVEL), 0x2A19)
        self.assertIsNone(sig_short_uuid(self.VENDOR_128))

    def test_standard_policy_reads_only_assigned_ranges(self):
        self.assertTrue(may_read(self.BATTERY_LEVEL, "characteristic", "standard"))
        self.assertTrue(may_read(self.CCCD, "descriptor", "standard"))
        self.assertFalse(may_read(self.UNASSIGNED_16, "characteristic", "standard"))
        self.assertFalse(may_read(self.VENDOR_128, "characteristic", "standard"))

    def test_none_and_all(self):
        self.assertFalse(may_read(self.BATTERY_LEVEL, "characteristic", "none"))
        self.assertTrue(may_read(self.VENDOR_128, "characteristic", "all"))


if __name__ == "__main__":
    unittest.main()
