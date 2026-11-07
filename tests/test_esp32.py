"""ESP32 Omnitrix asset pack: formats round-trip and the PC compositor model matches the Studio renderer."""

import struct
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from esp32 import assets as A
from omnitrix import screens as S
from omnitrix.aliens import ALIENS


class FormatTests(unittest.TestCase):
    def test_deflate_round_trip(self):
        data = bytes(range(256)) * 50
        z = A.deflate(data)
        self.assertEqual(z[:4], A.ZMAGIC)
        self.assertEqual(A.inflate(z), data)
        self.assertEqual(A.inflate(b"raw"), b"raw")

    def test_rgb565_round_trip_is_close(self):
        colours = [(255, 0, 0), (57, 255, 20), (8, 8, 8)]
        img = Image.new("RGB", (3, 1))
        img.putdata(colours)
        px = struct.unpack("<3H", A.rgb565(img))
        self.assertEqual(px[0], 0xF800)
        self.assertEqual(px[1], 0x3FE2)  # Omnitrix green used by the firmware's hold ring
        for (r, g, b), v in zip(colours, px):
            rr, gg, bb = A.from565(v)
            self.assertLessEqual(max(abs(r - rr), abs(g - gg), abs(b - bb)), 7)

    def test_battery_mapping_matches_draw_meter(self):
        for b in range(0, 101):
            lit, red = A.battery_lit(b)
            self.assertEqual(lit, round(b / 100 * A.SEGS))
            self.assertEqual(red, b <= 20)

    def test_meter_shape_matches_screens(self):
        """_meter() must draw exactly what screens.draw_meter draws."""
        from omnitrix.gfx import Frame

        style = S.Style()
        for b in (0, 15, 50, 100):
            lit, red = A.battery_lit(b)
            f1, f2 = Frame(), Frame()
            S.draw_meter(f1, style, style.omni_green, b, 1.0)
            A._meter(f2, style.omni_green, A.LOW_RED if red else style.omni_green, lit, 1.0, style.background)
            self.assertIsNone(ImageChops.difference(f1.finish(), f2.finish()).getbbox(), b)

    def test_font_pack_layout(self):
        th = A.themes()[0]
        fnt = A.parse_font(A.deflate(A.font_pack(th, A.SPOTS["sec"], S.Style())))
        self.assertEqual(set(fnt["glyphs"]), set(A.DIGITS))
        adv, xo, yo, img = fnt["glyphs"]["0"]
        self.assertGreater(adv, 0)
        self.assertLess(yo, 0)  # glyph sits above the baseline
        self.assertIsNotNone(img)


class PackTests(unittest.TestCase):
    """Builds a reduced pack once (faces only) and checks it against the Studio renderer."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        style = S.Style()
        for idx in (0, 3):
            th = A.themes(style)[idx]
            mtr, unlit = A.meter_pack(th, style)
            for sub, name, data in (("m", f"{idx}.mtr", A.deflate(mtr)), ("f", f"{idx}.jpg", A.jpeg(unlit, 90, True))):
                (cls.dir / sub).mkdir(exist_ok=True)
                (cls.dir / sub / name).write_bytes(data)
            (cls.dir / "t").mkdir(exist_ok=True)
            for key, spot in A.SPOTS.items():
                (cls.dir / "t" / f"{idx}_{key}.fnt").write_bytes(A.deflate(A.font_pack(th, spot, style)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_composed_faces_match_studio(self):
        now = datetime(2026, 11, 7, 10, 9, 30)
        for b in (100, 76, 15, 0):
            for idx, ref in ((0, S.home(A.T, S.WatchData(now, b))),
                             (3, S.alien_face(A.T, ALIENS[2], S.WatchData(now, b)))):
                got = A.compose(idx, now, b, self.dir)
                mean = ImageStat.Stat(ImageChops.difference(ref, got)).mean
                self.assertLess(max(mean), 4.0, (idx, b, mean))

    def test_meter_chain_is_exact(self):
        th = A.themes()[0]
        m = A.parse_meter((self.dir / "m" / "0.mtr").read_bytes())
        self.assertEqual(len(m["normal"]), A.SEGS)
        self.assertEqual(len(m["red"]), A.RED_MAX_LIT + 1)
        for b in (60, 10):
            lit, red = A.battery_lit(b)
            img = A.base(th, 0, False)
            A.apply_meter(img, m, b)
            ref = A.base(th, lit, red)
            diff = ImageChops.difference(img, ref)
            self.assertLessEqual(max(e[1] for e in diff.getextrema()), 8, b)  # RGB565 rounding only


class SeparationTests(unittest.TestCase):
    def test_esp32_tools_never_touch_ble(self):
        root = Path(A.__file__).resolve().parent
        for p in root.rglob("*.py"):
            src = p.read_text(encoding="utf-8")
            self.assertNotIn("bleak", src, p)
            self.assertNotIn("from ble", src, p)


if __name__ == "__main__":
    unittest.main()
