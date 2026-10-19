from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from ico_core import ICON_SIZES, convert_batch, convert_image, icon_canvas, load_image, validate_sizes


class IconTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.png = self.root / "wide.png"
        Image.new("RGBA", (80, 40), (20, 80, 160, 128)).save(self.png)

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_requested_sizes_reopen(self):
        output = self.root / "output.ico"
        convert_image(self.png, output)
        with Image.open(output) as icon:
            self.assertEqual(icon.format, "ICO")
            self.assertEqual(icon.ico.sizes(), {(size, size) for size in ICON_SIZES})
            for size in ICON_SIZES:
                self.assertEqual(icon.ico.getimage((size, size)).size, (size, size))

    def test_transparency_and_aspect_ratio_are_preserved(self):
        output = self.root / "alpha.ico"
        convert_image(self.png, output, (64,))
        with Image.open(output) as icon:
            image = icon.convert("RGBA")
            self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(image.getpixel((32, 32))[3], 128)
            self.assertEqual(image.getbbox(), (0, 16, 64, 48))

    def test_jpeg_converts_with_opaque_subject(self):
        source = self.root / "photo.jpg"
        Image.new("RGB", (24, 48), "red").save(source)
        output = self.root / "photo.ico"
        convert_image(source, output, (32, 64))
        with Image.open(output) as icon:
            self.assertEqual(icon.convert("RGBA").getpixel((32, 32))[3], 255)

    def test_exif_orientation_is_applied(self):
        source = self.root / "rotated.jpg"
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (32, 64), "blue").save(source, exif=exif)
        self.assertEqual(load_image(source).size, (64, 32))

    def test_palette_png_transparency_is_preserved(self):
        source = self.root / "palette.png"
        image = Image.new("P", (16, 16), 0)
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * 762)
        image.putpixel((8, 8), 1)
        image.save(source, transparency=0)
        decoded = load_image(source)
        self.assertEqual(decoded.getpixel((0, 0))[3], 0)
        self.assertEqual(decoded.getpixel((8, 8))[3], 255)

    def test_bad_input_cannot_overwrite_destination(self):
        source, output = self.root / "broken.png", self.root / "keep.ico"
        source.write_bytes(b"not an image")
        output.write_bytes(b"original")
        with self.assertRaises(OSError): convert_image(source, output, overwrite=True)
        self.assertEqual(output.read_bytes(), b"original")

    def test_existing_file_is_preserved_by_default(self):
        output = self.root / "existing.ico"
        output.write_bytes(b"original")
        with self.assertRaises(FileExistsError): convert_image(self.png, output)
        self.assertEqual(output.read_bytes(), b"original")

    def test_explicit_overwrite(self):
        output = self.root / "replace.ico"
        output.write_bytes(b"old")
        convert_image(self.png, output, (32,), overwrite=True)
        with Image.open(output) as icon: self.assertEqual(icon.format, "ICO")

    def test_failed_replace_preserves_existing_and_cleans_new_placeholder(self):
        existing, fresh = self.root / "existing.ico", self.root / "fresh.ico"
        existing.write_bytes(b"original")
        with patch("ico_core.os.replace", side_effect=PermissionError("read only")):
            with self.assertRaises(PermissionError): convert_image(self.png, existing, overwrite=True)
            with self.assertRaises(PermissionError): convert_image(self.png, fresh)
        self.assertEqual(existing.read_bytes(), b"original")
        self.assertFalse(fresh.exists())
        self.assertEqual(list(self.root.glob(".ico-export-*")), [])

    def test_batch_duplicate_names_do_not_overwrite(self):
        folder = self.root / "other"
        folder.mkdir()
        other = folder / "wide.png"
        Image.new("RGB", (32, 32), "green").save(other)
        existing = self.root / "wide.ico"
        existing.write_bytes(b"original")
        results = list(convert_batch([self.png, other], self.root, (32,)))
        self.assertTrue(all(item["ok"] for item in results))
        self.assertEqual([Path(item["output"]).name for item in results], ["wide (2).ico", "wide (3).ico"])
        self.assertEqual(existing.read_bytes(), b"original")

    def test_batch_continues_after_bad_image(self):
        broken = self.root / "broken.png"
        broken.write_bytes(b"bad")
        results = list(convert_batch([broken, self.png], self.root, (16,)))
        self.assertEqual([item["ok"] for item in results], [False, True])

    def test_cancel_stops_before_next_file(self):
        cancel = threading.Event()
        batch = convert_batch([self.png, self.png], self.root, (16,), cancel)
        self.assertTrue(next(batch)["ok"])
        cancel.set()
        self.assertEqual(list(batch), [])

    def test_size_validation_and_wrong_extension(self):
        for sizes in ((), (0,), (512,), (True,), (16.0,)):
            with self.subTest(sizes=sizes), self.assertRaises(ValueError): validate_sizes(sizes)
        with self.assertRaises(ValueError): convert_image(self.png, self.root / "wrong.png")

    def test_large_input_is_rejected_before_conversion(self):
        with patch("ico_core.MAX_PIXELS", 100):
            with self.assertRaisesRegex(ValueError, "40-megapixel"):
                icon_canvas(self.png)


if __name__ == "__main__":
    unittest.main()
