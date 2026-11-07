import unittest
from datetime import datetime

from watchface.display import WATCH_PRO_1
from watchface.preview import list_faces
from watchface.render import WatchState, load_face, render


class RenderTests(unittest.TestCase):
    def test_every_bundled_face_renders_at_screen_size(self):
        faces = list_faces()
        self.assertTrue(faces)
        state = WatchState(now=datetime(2026, 1, 1, 10, 9, 30))
        for name, path in faces.items():
            img = render(load_face(path), state)
            self.assertEqual(img.size, (WATCH_PRO_1.width, WATCH_PRO_1.height), name)
            self.assertEqual(img.mode, "RGB", name)

    def test_corners_are_masked(self):
        img = render({"background": "#ffffff", "elements": []})
        self.assertEqual(img.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(img.getpixel((WATCH_PRO_1.width // 2, WATCH_PRO_1.height // 2)), (255, 255, 255))

    def test_progress_is_clamped(self):
        self.assertEqual(WatchState(steps=50000, steps_goal=10000).progress("steps"), 1.0)
        self.assertEqual(WatchState(battery=-5).progress("battery"), 0.0)

    def test_unknown_element_rejected(self):
        with self.assertRaises(ValueError):
            render({"elements": [{"type": "sprite"}]})


if __name__ == "__main__":
    unittest.main()
