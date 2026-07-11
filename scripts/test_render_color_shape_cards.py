import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

SCRIPT = Path(__file__).resolve().parent / "render_color_shape_cards.py"


def load_module():
    spec = importlib.util.spec_from_file_location("render_color_shape_cards", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ColorCardTest(unittest.TestCase):
    def test_color_card_is_full_bleed_with_no_background(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(module, "VOCAB", Path(tmp)):
                module.render_color("red", "#E53935")
            with Image.open(Path(tmp) / "red.jpg") as image:
                rgb = image.convert("RGB")
                samples = [rgb.getpixel(point) for point in ((0, 0), (512, 512), (1023, 1023))]
            for pixel in samples:
                self.assertLess(max(pixel) - min(pixel), 200)
                self.assertGreater(pixel[0], 210)
                self.assertLess(pixel[1], 80)
                self.assertLess(pixel[2], 80)
    def test_shape_card_has_transparent_background(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(module, "ADJS", Path(tmp)):
                module.render_shape("round")
            with Image.open(Path(tmp) / "round.png") as image:
                rgba = image.convert("RGBA")
                self.assertEqual(rgba.getpixel((0, 0))[3], 0)
                self.assertEqual(rgba.getpixel((512, 512))[3], 255)


if __name__ == "__main__":
    unittest.main()
