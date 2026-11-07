import re
import unittest
from datetime import datetime
from pathlib import Path

from PIL import ImageStat

from omnitrix import screens as S
from omnitrix.aliens import ALIENS
from omnitrix.emblems import DRAWERS
from omnitrix.fx import EFFECTS
from omnitrix.gfx import H, W

ROOT = Path(__file__).resolve().parents[1]
DATA = S.WatchData(now=datetime(2026, 11, 7, 10, 9, 30), battery=76)


class OmnitrixRenderTests(unittest.TestCase):
    def assertScreen(self, img, label):
        self.assertEqual(img.size, (W, H), label)
        self.assertEqual(img.mode, "RGB", label)
        self.assertEqual(img.getpixel((0, 0)), (0, 0, 0), f"{label}: corners must be masked")

    def test_profiles_are_complete(self):
        self.assertEqual(len(ALIENS), 10)
        self.assertEqual(len({a.key for a in ALIENS}), 10)
        for a in ALIENS:
            self.assertIn(a.emblem, DRAWERS, a.key)
            self.assertIn(a.fx, EFFECTS, a.key)
        self.assertEqual(len({a.fx for a in ALIENS}), 10, "each alien needs its own selection effect")

    def test_static_screens(self):
        self.assertScreen(S.home(1.0, DATA), "home")
        self.assertScreen(S.home_background(1.0), "home_background")
        for sel in (0.0, 2.5, 9.0):
            self.assertScreen(S.selector(1.0, sel, DATA), f"selector {sel}")

    def test_every_alien_every_screen(self):
        for a in ALIENS:
            self.assertScreen(S.info(1.0, a, DATA), f"info {a.key}")
            self.assertScreen(S.alien_face(1.0, a, DATA), f"face {a.key}")
            self.assertScreen(S.alien_face(1.0, a, DATA, show_clock=False), f"background {a.key}")
            for p in (0.0, 0.5, 1.0):
                self.assertScreen(S.select_confirm(1.0, p, ALIENS.index(a), DATA), f"confirm {a.key} {p}")

    def test_transformation_timeline(self):
        a = ALIENS[2]
        t, step = 0.0, 0.15
        while t <= S.TRANSFORM_DURATION:
            self.assertScreen(S.transform(t, a, DATA), f"transform t={t:.2f}")
            t += step
        start, end = S.transform(0.0, a, DATA), S.transform(S.TRANSFORM_DURATION, a, DATA)
        mean = lambda im: ImageStat.Stat(im.convert("L")).mean[0]
        self.assertLess(mean(start), mean(end), "sequence should start dark")

    def test_customisation_applies(self):
        img = S.home(1.0, DATA, S.Style(background="#202060", hex_grid=0.0))
        self.assertGreater(img.getpixel((60, 470))[2], 60, "background colour should show in empty areas")
        self.assertScreen(S.home(1.0, DATA, S.Style(font="OCRAEXT.TTF", ring_width=12, glow=0)), "custom style")

    def test_low_battery_turns_meter_red(self):
        img = S.home(1.0, S.WatchData(now=DATA.now, battery=10))
        x, y = S.polar(S.C, S.R_METER, 135)
        r, g, b = img.getpixel((int(x), int(y)))
        self.assertGreater(r, g)


class SeparationTests(unittest.TestCase):
    def test_prototype_never_touches_ble(self):
        for path in (ROOT / "omnitrix").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^\s*(from|import)\s+(ble|bleak)\b", text, re.M), path.name)


if __name__ == "__main__":
    unittest.main()


class PhotoFaceTests(unittest.TestCase):
    def test_every_theme_and_placement(self):
        from omnitrix.photoface import PLACEMENTS, calibration, photo_face

        self.assertEqual(calibration().size, (W, H))
        self.assertEqual(calibration().getpixel((0, 0)), (255, 42, 42), "0 px border must reach the very edge")
        for alien in (None, *ALIENS):
            for pos in PLACEMENTS:
                img = photo_face(alien, pos)
                self.assertEqual(img.size, (W, H), f"{alien} {pos}")

    def test_top_placement_leaves_top_band_dark(self):
        from omnitrix.photoface import photo_face

        top, bottom = photo_face(None, "top"), photo_face(None, "bottom")
        band = lambda im: ImageStat.Stat(im.crop((120, 20, 290, 70)).convert("L")).mean[0]
        self.assertLess(band(top), band(bottom))


class WatchReleaseTests(unittest.TestCase):
    def test_release_layout_rules(self):
        from omnitrix.watch_release import CENTER, CLOCK_BANDS, DIAL_SCALE, render

        for alien in (None, *ALIENS):
            img = render(alien)
            label = alien.key if alien else "home"
            self.assertEqual((img.size, img.mode), ((W, H), "RGB"), label)
            lum = img.convert("L")
            hist = lum.histogram()
            floor = 0.6 if alien is None else 0.5
            self.assertGreater(hist[0] / sum(hist), floor, f"{label}: AMOLED face should be mostly true black")
            ring_r = round(S.R_RING * DIAL_SCALE)
            for dx, dy in ((ring_r, 0), (-ring_r, 0), (0, ring_r), (0, -ring_r)):
                self.assertGreater(lum.getpixel((CENTER[0] + dx, CENTER[1] + dy)), 100, f"{label}: ring off-centre")
            if alien is None:  # aliens have ambient effects outside the dial
                bright = lum.point(lambda v: 255 if v > 40 else 0).getbbox()
                self.assertAlmostEqual((bright[0] + bright[2]) / 2, CENTER[0], delta=2, msg=label)
                self.assertAlmostEqual((bright[1] + bright[3]) / 2, CENTER[1], delta=2, msg=label)
            for name, (y0, y1) in CLOCK_BANDS.items():
                self.assertLess(ImageStat.Stat(lum.crop((60, y0, 350, y1))).mean[0], 6, f"{label}: {name} clock band must stay dark")

    def test_install_file_names(self):
        from omnitrix.watch_release import file_name

        expected = {"omnitrix_home.png", "heatblast.png", "four_arms.png", "xlr8.png", "diamondhead.png", "wildmutt.png",
                    "upgrade.png", "ghostfreak.png", "cannonbolt.png", "stinkfly.png", "ripjaws.png"}
        produced = {file_name(None), *(file_name(a) for a in ALIENS)}
        self.assertTrue(expected <= produced)
