# SPDX-License-Identifier: MIT
"""Sample aligned Blender passes on one pixel grid and optionally lock palettes."""
import argparse
import json
import math
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


def neighbor(array, y, x, fill=0):
    result = np.full_like(array, fill)
    height, width = array.shape[:2]
    result[max(y, 0):height + min(y, 0), max(x, 0):width + min(x, 0)] = (
        array[max(-y, 0):height - max(y, 0), max(-x, 0):width - max(x, 0)])
    return result


def finish(manifest, source, output, palettes, threshold):
    config = manifest["config"]
    scale = config["sample_scale"]
    center = scale // 2
    width, height = config["canvas_px"]
    directions = {}
    for record in manifest["records"]:
        arrays = {}
        for channel in ("color", "normal", "depth", "groups"):
            relative = Path(record[channel])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Pass references must be relative to the render manifest")
            with Image.open(source / relative) as image:
                arrays[channel] = np.array(image.convert("RGBA"))[center::scale, center::scale]
            if arrays[channel].shape != (height, width, 4):
                raise ValueError("Pass canvas does not match the declared render grid")
        color = arrays["color"]
        solid = color[:, :, 3] >= 128
        depth = arrays["depth"][:, :, 0].astype(np.float32) / 255
        normals = arrays["normal"][:, :, :3].astype(np.float32) / 127.5 - 1
        darken = np.zeros((height, width), dtype=np.float32)
        for y, x in ((-1, 0), (0, -1), (1, 0), (0, 1)):
            adjacent = neighbor(solid, y, x)
            crease = (solid & adjacent & ((neighbor(depth, y, x) - depth) > threshold)
                      & (np.linalg.norm(neighbor(normals, y, x) - normals, axis=2) > 0.3))
            darken = np.maximum(darken, np.where(solid & ~adjacent, 0.25, np.where(crease, 0.18, 0)))
        rgb = color[:, :, :3].astype(np.float32) * (1 - darken[:, :, None])
        groups = arrays["groups"][:, :, 0]
        for group, colors in palettes.items():
            palette = np.array([tuple(bytes.fromhex(code.lstrip("#"))) for code in colors], dtype=np.float32)
            if palette.ndim != 2 or palette.shape[1] != 3 or not len(palette):
                raise ValueError("Each palette needs one or more six-digit RGB colors")
            mask = solid & (groups == int(group))
            samples = rgb[mask]
            # Small sprite palettes are cheaper to compare directly than indexing a tree.
            nearest = ((samples[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
            rgb[mask] = palette[nearest]
        color[:, :, :3] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
        color[:, :, 3] = solid.astype(np.uint8) * 255
        direction = record["direction"]
        if not direction or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in direction):
            raise ValueError("Invalid direction name")
        name = f'frame_{record["index"]:04}.png'
        directory = output / direction
        for channel in arrays:
            folder = directory / ("frames" if channel == "color" else channel + "_frames")
            folder.mkdir(parents=True, exist_ok=True)
            arrays[channel][:, :, 3] = color[:, :, 3]
            Image.fromarray(arrays[channel]).save(folder / name)
        directions.setdefault(direction, []).append((record["source_frame"], color.copy()))
    for direction, records in directions.items():
        frame_numbers = [frame for frame, _ in records]
        if any(a >= b for a, b in zip(frame_numbers, frame_numbers[1:])):
            raise ValueError("Source frames must be strictly increasing within each direction")
        last_step = frame_numbers[-1] - frame_numbers[-2] if len(records) > 1 else 1
        loop_end = config.get("loop_end_frame", frame_numbers[-1] + last_step)
        stops = frame_numbers[1:] + [loop_end]
        durations = [(b - a) * 1000 / config["fps"] for a, b in zip(frame_numbers, stops)]
        if any(not math.isfinite(t) or t <= 0 for t in durations):
            raise ValueError("Frame durations must be positive and finite")
        columns = min(8, len(records))
        sheet = Image.new("RGBA", (columns * width, math.ceil(len(records) / columns) * height))
        for index, (_, array) in enumerate(records):
            sheet.paste(Image.fromarray(array), (index % columns * width, index // columns * height))
        sheet.save(output / direction / "sheet.png")
        data = {"schema_version": 1, "frame_size": [width, height], "anchor": config.get("anchor_px"),
                "durations_ms": durations, "source_frames": frame_numbers,
                "frames": [f"frames/frame_{i:04}.png" for i in range(len(records))],
                "pixel_grid": {"sample_scale": scale, "sample_offset": center},
                "channels": {"normal": "normal_frames", "depth": "depth_frames", "groups": "groups_frames"}}
        (output / direction / "timing.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Directory with render.json")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--palettes", type=Path, help="JSON map of group ID to hex RGB colors")
    parser.add_argument("--depth-threshold", type=float, default=0.012)
    args = parser.parse_args()
    manifest = json.loads((args.input / "render.json").read_text(encoding="utf-8"))
    palettes = json.loads(args.palettes.read_text(encoding="utf-8")) if args.palettes else {}
    destination = args.output.resolve()
    if destination.exists():
        parser.error("Choose a fresh output directory")
    if not math.isfinite(args.depth_threshold) or args.depth_threshold < 0:
        parser.error("depth-threshold must be finite and nonnegative")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".finish-stage-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "result"
        staged.mkdir()
        finish(manifest, args.input, staged, palettes, args.depth_threshold)
        if destination.exists():
            raise ValueError("Output was created concurrently")
        staged.rename(destination)
    print("Finished", destination)


if __name__ == "__main__":
    main()
