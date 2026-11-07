"""Offline tests for the CMF companion prototype: framing, crypto, auth, and the Omnitrix bridge.

No Bluetooth and no watch. These check that the protocol layer round-trips and that the write path is
gated. Byte-level fidelity to the real watch is NOT asserted (unverified), only internal consistency.
"""

import struct
import unittest
import zlib

from companion import auth, bridge, client, commands, protocol
from omnitrix.aliens import BY_KEY


class ProtocolTests(unittest.TestCase):
    KEY = bytes(range(16))

    def test_crc32_le_matches_zlib(self):
        self.assertEqual(protocol.crc32_le(b"hello"), struct.pack("<I", zlib.crc32(b"hello")))

    def test_aes_round_trip(self):
        for pt in (b"", b"a", b"x" * 15, b"y" * 16, b"z" * 100):
            self.assertEqual(protocol.aes_decrypt(protocol.aes_encrypt(pt, self.KEY), self.KEY), pt)

    def test_aes_requires_16_byte_key(self):
        with self.assertRaises(ValueError):
            protocol.aes_encrypt(b"x", b"short")

    def test_plaintext_frame_round_trip(self):
        pkts = protocol.encode(0x0065, 0x0001, b"payload-data", key=None)
        self.assertEqual(len(pkts), 1)
        c1, c2, count, idx, payload = protocol.decode_chunk(pkts[0], key=None)
        self.assertEqual((c1, c2, count, idx, payload), (0x0065, 0x0001, 1, 1, b"payload-data"))

    def test_encrypted_frame_round_trip(self):
        pkts = protocol.encode(0xFFFF, 0x905C, b"now playing: XLR8", key=self.KEY)
        c1, c2, count, idx, payload = protocol.decode_chunk(pkts[0], key=self.KEY)
        self.assertEqual((c1, c2, payload), (0xFFFF, 0x905C, b"now playing: XLR8"))

    def test_multi_chunk_reassembles(self):
        payload = bytes(range(256)) * 4  # > one MTU chunk
        pkts = protocol.encode(0x0065, 0x0001, payload, key=self.KEY, mtu=64)
        self.assertGreater(len(pkts), 1)
        got = b""
        for i, pkt in enumerate(pkts):
            _, _, count, idx, part = protocol.decode_chunk(pkt, key=self.KEY)
            self.assertEqual((idx, count), (i + 1, len(pkts)))
            got += part
        self.assertEqual(got, payload)

    def test_crc_mismatch_detected(self):
        pkt = bytearray(protocol.encode(0x0065, 0x0001, b"data", key=None)[0])
        pkt[-1] ^= 0xFF  # corrupt the CRC trailer
        with self.assertRaises(ValueError):
            protocol.decode_chunk(bytes(pkt), key=None)


class AuthTests(unittest.TestCase):
    def test_session_key_is_deterministic_16_bytes(self):
        k1 = bytes(range(16))
        nonce = b"\xaa" * 16
        sk = auth.session_key(nonce, k1)
        self.assertEqual(len(sk), 16)
        self.assertEqual(sk, auth.session_key(nonce, k1))
        self.assertNotEqual(sk, auth.session_key(b"\xbb" * 16, k1))

    def test_parse_k1_accepts_bare_and_prefixed(self):
        hexstr = "c31c05f244c74a52903f0275a237237d"
        self.assertEqual(auth.parse_k1(hexstr), bytes.fromhex(hexstr))
        self.assertEqual(auth.parse_k1("0x" + hexstr.upper()), bytes.fromhex(hexstr))

    def test_parse_k1_rejects_bad(self):
        for bad in ("xyz", "12", "g" * 32):
            with self.assertRaises(ValueError):
                auth.parse_k1(bad)


class BridgeTests(unittest.TestCase):
    def test_select_builds_allowed_steps(self):
        steps = bridge.select_alien(BY_KEY["heatblast"])
        self.assertTrue(steps)
        for s in steps:
            self.assertIn(s.cmd.name, commands.ALLOWED)

    def test_transform_includes_buzz(self):
        steps = bridge.transform(BY_KEY["xlr8"], face_index=3)
        names = [s.cmd.name for s in steps]
        self.assertIn("FIND_WATCH", names)
        self.assertIn("WATCHFACE", names)

    def test_button_mapping(self):
        self.assertEqual(bridge.button_to_action(0x0102), "dial +1 (next)")
        self.assertIsNone(bridge.button_to_action(0x9999))


class SafetyTests(unittest.TestCase):
    def test_build_packets_refuses_blocked_command(self):
        bad = bridge.Step("factory reset", commands.Cmd("FACTORY_RESET", 0x009A, 0x0001), b"\xa5")
        with self.assertRaises(client.RefusedToSend):
            client.build_packets([bad], session_key=None)

    def test_dry_run_sends_nothing_and_describes(self):
        lines = client.dry_run(bridge.demo_plan())
        self.assertTrue(any("dry-run" in ln for ln in lines))

    def test_blocked_set_excludes_destructive(self):
        self.assertIn("FACTORY_RESET", commands.BLOCKED)
        self.assertNotIn("FACTORY_RESET", commands.ALLOWED)

    def test_companion_isolated_from_readonly_packages(self):
        """The read-only packages must never import the writing companion package."""
        from pathlib import Path
        root = Path(client.__file__).resolve().parents[1]
        for pkg in ("ble", "watchface", "omnitrix", "deploy"):
            for p in (root / pkg).rglob("*.py"):
                self.assertNotIn("import companion", p.read_text(encoding="utf-8"), p)


if __name__ == "__main__":
    unittest.main()
