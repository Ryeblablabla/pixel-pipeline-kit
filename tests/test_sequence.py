# SPDX-License-Identifier: MIT
"""Behavioral regressions for source preservation, timing and staged exports."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "skills/sprite-sequence/scripts/pixel_sequence_tools.py"


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.frames = self.root / "input"
        self.frames.mkdir()
        self.images = []
        for index in range(3):
            pixels = np.zeros((12, 12, 4), dtype=np.uint8)
            pixels[3:8, 4 + index, :] = (31, 91 + index, 172, 180)
            image = Image.fromarray(pixels)
            image.save(self.frames / f"frame_{index}.png")
            self.images.append(image)
        self.times = self.root / "timing.json"
        self.times.write_text(json.dumps({"durations_ms": [70, 90, 130]}))

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, *arguments, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_export_preserves_rgba_and_nonuniform_timing(self):
        output = self.root / "export"
        self.command("export", "--frames", self.frames, "--timings", self.times,
                     "--anchor", 6, 10, "--output", output)
        metadata = json.loads((output / "timing.json").read_text())
        self.assertEqual(metadata["durations_ms"], [70, 90, 130])
        self.assertEqual(metadata["anchor"], [6, 10])
        for index, image in enumerate(self.images):
            self.assertEqual(image.tobytes(), Image.open(output / f"frames/frame_{index:04}.png").tobytes())

    def test_cyclic_repair_moves_timing_with_cels(self):
        recipe = self.root / "recipe.json"
        recipe.write_text(json.dumps({"loop": True, "cycle_offset": 1,
                                      "transform": {"translate": [1, 0]}}))
        output = self.root / "repair"
        self.command("repair-cels", "--frames", self.frames, "--timings", self.times,
                     "--recipe", recipe, "--output", output)
        self.assertEqual(json.loads((output / "timing.json").read_text())["durations_ms"], [90, 130, 70])
        repaired = Image.open(output / "frames/frame_0000.png")
        self.assertEqual(repaired.getpixel((6, 3)), self.images[1].getpixel((5, 3)))
        self.assertNotIn(str(self.root), (output / "repair_ledger.json").read_text())

    def test_failed_export_leaves_no_partial_result(self):
        times = self.root / "short.json"
        times.write_text("[1, 1, 1]")
        output = self.root / "failed"
        self.command("export", "--frames", self.frames, "--timings", times,
                     "--output", output, success=False)
        self.assertFalse(output.exists())
        self.assertEqual(len(list(self.frames.glob("*.png"))), 3)

    def test_output_is_never_overwritten(self):
        output = self.root / "existing"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("preserve")
        self.command("export", "--frames", self.frames, "--output", output, success=False)
        self.assertEqual(marker.read_text(), "preserve")

    def test_fixed_grid_slice_preserves_partial_alpha(self):
        sheet = Image.new("RGBA", (24, 24))
        for index, image in enumerate(self.images):
            sheet.paste(image, (index % 2 * 12, index // 2 * 12))
        source = self.root / "sheet.png"
        sheet.save(source)
        output = self.root / "sliced"
        self.command("slice-sheet", "--input", source, "--rows", 2, "--cols", 2,
                     "--count", 3, "--output", output)
        for index, image in enumerate(self.images):
            self.assertEqual(Image.open(output / f"frames/frame_{index:04}.png").tobytes(), image.tobytes())


if __name__ == "__main__":
    unittest.main()
