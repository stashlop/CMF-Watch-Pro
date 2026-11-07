import tempfile
import unittest
from pathlib import Path

from PIL import Image

from deploy import config
from deploy.__main__ import GUIDE
from deploy.validate import check_face, validate_all


class DeployValidationTests(unittest.TestCase):
    def test_face_list_matches_release_exporter(self):
        from omnitrix.aliens import ALIENS
        from omnitrix.watch_release import file_name

        self.assertEqual(set(config.FACE_FILES), {file_name(None), *(file_name(a) for a in ALIENS)})
        self.assertEqual(config.FACE_FILES[0], "omnitrix_home.png")

    def test_committed_faces_pass(self):
        for r in validate_all():
            self.assertTrue(r["ok"], f"{r['file']}: {r['problems']}")

    def test_bad_faces_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.png"
            Image.new("RGBA", (400, 400), (255, 255, 255, 255)).save(p)
            problems = " ".join(check_face(p)["problems"])
            self.assertIn("size", problems)
            self.assertIn("mode", problems)
            self.assertFalse(check_face(Path(d) / "missing.png")["ok"])

    def test_guide_uses_documented_menu(self):
        text = GUIDE.format(face="heatblast.png")
        self.assertIn('"My" tab > "Customize Watch Face"', text)
        self.assertIn("heatblast.png", text)


if __name__ == "__main__":
    unittest.main()
