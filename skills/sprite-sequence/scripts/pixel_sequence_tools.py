# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""Fixed-canvas guides, original-cel repairs, literal point replay and exports.

Requires Pillow and NumPy. Uses existing complete frames and explicit recipes.
Generation tools are selected separately by the user or agent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import os
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from gif_preview import save_transparent_gif


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def frame_files(folder):
    def key(path):
        return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", path.name)]
    return sorted(folder.glob("*.png"), key=key)


def load_frames(folder):
    paths = frame_files(folder)
    if not paths:
        raise ValueError("No PNG frames in " + str(folder))
    frames = [Image.open(p).convert("RGBA") for p in paths]
    if any(f.size != frames[0].size for f in frames):
        raise ValueError("Frames must retain one common canvas; no automatic fitting")
    return paths, frames


def durations(value, count, fps):
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be positive and finite")
    if value is None:
        return [1000.0 / fps] * count
    data = json.loads(value.read_text())
    if isinstance(data, dict):
        if "durations_seconds" in data:
            data = [x * 1000 for x in data["durations_seconds"]]
        else:
            data = data["durations_ms"]
    if len(data) != count or any(not math.isfinite(float(x)) or x <= 0 for x in data):
        raise ValueError("Provide one positive duration per source frame")
    return list(map(float, data))


def export(frames, times, out, anchor=None):
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "frames"
    dest.mkdir(exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(dest / f"frame_{index:04}.png")
    columns = min(8, len(frames))
    width, height = frames[0].size
    sheet = Image.new("RGBA", (columns * width, math.ceil(len(frames) / columns) * height))
    for index, frame in enumerate(frames):
        sheet.paste(frame, (index % columns * width, index // columns * height))
    sheet.save(out / "sheet.png")
    elapsed = 0.0
    tick = 0
    gif_times = []
    for milliseconds in times:
        elapsed += milliseconds
        end = round(elapsed / 10)
        if end <= tick:
            raise ValueError("GIF cannot represent this sub-10ms interval; retain PNG timing or combine poses explicitly")
        gif_times.append((end - tick) * 10)
        tick = end
    save_transparent_gif(frames, out / "preview.gif", gif_times)
    metadata = {"frame_size": [width, height], "frame_count": len(frames),
                "columns": columns, "anchor": anchor, "durations_ms": times,
                "gif_durations_ms": gif_times, "gif_alpha": "binary preview; PNG RGBA preserved",
                "gif_palette": "shared 255-color quantized preview; PNG colors unchanged",
                "geometry": "fixed full canvas; no fitting, trimming, resampling or interpolation"}
    write_json(out / "timing.json", metadata)
    return metadata


def batch_guides(args):
    paths, frames = load_frames(args.frames)
    if args.output.resolve() == args.frames.resolve():
        raise ValueError("Keep derived guides outside the source-frame directory")
    args.output.mkdir(parents=True, exist_ok=True)
    width, height = frames[0].size
    batches = []
    for start in range(0, len(frames), 4):
        real = list(range(start, min(start + 4, len(frames))))
        indices = real + [i % len(frames) for i in range(4 - len(real))]
        board = Image.new("RGBA", (width * 2, height * 2))
        slots = []
        for slot, index in enumerate(indices):
            board.paste(frames[index], (slot % 2 * width, slot // 2 * height))
            slots.append({"slot": slot, "source_index": index,
                          "source": paths[index].name, "export": slot < len(real)})
        board = board.resize((width * 2 * args.scale, height * 2 * args.scale), Image.Resampling.NEAREST)
        path = args.output / f"batch_{start // 4:03}.png"
        board.save(path)
        batches.append({"guide": path.name, "slots": slots})
    write_json(args.output / "batches.json", {"frame_size": [width, height], "scale": args.scale,
               "source_frames": len(frames), "layout": [2, 2], "batches": batches,
               "padding": "reference-only slots; never import as extra animation frames"})
    print(json.dumps({"source_frames": len(frames), "batches": len(batches), "output": str(args.output)}))


def replay_edits(args):
    recipe = json.loads(args.recipe.read_text())
    source_hash = hashlib.sha256(args.base.read_bytes()).hexdigest()
    if recipe.get("base_sha256", source_hash) != source_hash:
        raise ValueError("Approved base hash differs")
    base = Image.open(args.base).convert("RGBA")
    original = np.asarray(base)
    width, height = base.size
    allowed = np.zeros((height, width), dtype=bool)
    for x, y, w, h in recipe["allowed_regions"]:
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > width or y + h > height:
            raise ValueError("Allowed region outside approved canvas")
        allowed[y:y + h, x:x + w] = True
    palette = {tuple(c[:3]) for c in original.reshape(-1, 4) if c[3]}
    frames, times, ledger = [], [], []
    for index, entry in enumerate(recipe["timeline"]):
        frame = base.copy()  # Always replay from the approved base, never previous frame.
        for state in entry.get("states", []):
            for op in recipe["states"][state]:
                x, y = op["to"]
                if not (0 <= x < width and 0 <= y < height and allowed[y, x]):
                    raise ValueError("Point outside declared editable region")
                if op["op"] == "copy":
                    sx, sy = op["from"]
                    if not (0 <= sx < width and 0 <= sy < height):
                        raise ValueError("Sample point outside source")
                    color = base.getpixel((sx, sy))
                elif op["op"] == "erase":
                    color = (0, 0, 0, 0)
                elif op["op"] == "paint":
                    color = tuple(op["rgba"])
                    if len(color) != 4 or any(not isinstance(v, int) or v < 0 or v > 255 for v in color):
                        raise ValueError("paint requires four byte RGBA values")
                else:
                    raise ValueError("Unknown literal pixel operation")
                if color[3] and tuple(color[:3]) not in palette and not recipe.get("allow_new_colors", False):
                    raise ValueError("New color not present in approved base palette")
                frame.putpixel((x, y), color)
        changed = np.any(np.asarray(frame) != original, axis=2)
        if np.any(changed & ~allowed):
            raise ValueError("Protected original pixels changed")
        for y, x in zip(*np.nonzero(changed)):
            ledger.append({"frame": index, "xy": [int(x), int(y)],
                           "old_rgba": original[y, x].tolist(), "new_rgba": list(frame.getpixel((x, y)))})
        frames.append(frame)
        times.append(float(entry["duration_ms"]))
    if not frames or any(not math.isfinite(t) or t <= 0 for t in times):
        raise ValueError("Nonempty timeline with positive durations required")
    if recipe.get("first_frame_is_base", True) and frames[0].tobytes() != base.tobytes():
        raise ValueError("Opening frame must be the approved base")
    if any((args.output / "frames" / f"frame_{i:04}.png").resolve() == args.base.resolve() for i in range(len(frames))):
        raise ValueError("Output would overwrite the approved base")
    metadata = export(frames, times, args.output, recipe.get("anchor"))
    write_json(args.output / "pixel_ledger.json", {"base": args.base.name,
               "base_sha256": source_hash, "editable_regions": recipe["allowed_regions"],
               "protected_pixels_unchanged": True, "edits": ledger})
    print(json.dumps({"frames": metadata["frame_count"], "changed_pixel_instances": len(ledger), "output": str(args.output)}))


def slice_sheet(args):
    with Image.open(args.input) as image:
        sheet = image.convert("RGBA")
    if min(args.rows, args.cols, args.sample_scale) <= 0:
        raise ValueError("Rows, columns and sample scale must be positive integers")
    if sheet.width % args.cols or sheet.height % args.rows:
        raise ValueError("Sheet dimensions must divide exactly into fixed cells")
    width, height = sheet.width // args.cols, sheet.height // args.rows
    if width % args.sample_scale or height % args.sample_scale:
        raise ValueError("Cell dimensions must divide exactly by sample scale")
    count = args.count if args.count is not None else args.rows * args.cols
    if not 1 <= count <= args.rows * args.cols:
        raise ValueError("count must select a nonempty row-major prefix of the grid")
    frames = []
    for index in range(count):
        left, top = index % args.cols * width, index // args.cols * height
        cell = np.asarray(sheet.crop((left, top, left + width, top + height)))
        center = args.sample_scale // 2
        frames.append(Image.fromarray(cell[center::args.sample_scale, center::args.sample_scale].copy()))
    export(frames, durations(args.timings, count, args.fps), args.output, args.anchor)


def _cel_transform(spec):
    scale = float(spec.get("scale", 1.0))
    xy = spec.get("translate", [0, 0])
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Whole-cel scale must be positive and finite")
    if len(xy) != 2 or any(type(v) is not int for v in xy):
        raise ValueError("Whole-cel translation requires two integer pixels")
    return scale, xy


def _repair_cel(source, scale, xy, axis=None, normal=False):
    width, height = source.size
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    layer = source if size == source.size else source.resize(size, Image.Resampling.NEAREST)
    if np.count_nonzero(np.asarray(source)[..., 3]) and not np.count_nonzero(np.asarray(layer)[..., 3]):
        raise ValueError("Resampling would erase the original subject")
    output = Image.new("RGBA", source.size)
    output.paste(layer, tuple(xy))
    if np.count_nonzero(np.asarray(output)[..., 3]) != np.count_nonzero(np.asarray(layer)[..., 3]):
        raise ValueError("Transform would crop visible original pixels; revise the explicit calibration")
    if axis is not None:
        indices = int(round(axis * 2)) - np.arange(width)
        valid = (indices >= 0) & (indices < width)
        before = np.asarray(output)
        mirrored = np.zeros_like(before)
        mirrored[:, valid] = before[:, indices[valid]]
        if np.count_nonzero(mirrored[..., 3]) != np.count_nonzero(before[..., 3]):
            raise ValueError("Root-axis mirror would crop visible original pixels")
        if normal:
            visible = mirrored[..., 3] > 0
            mirrored[visible, 0] = 255 - mirrored[visible, 0]
        output = Image.fromarray(mirrored)
    return output


def repair_cels(args):
    recipe = json.loads(args.recipe.read_text())
    known = {"anchor", "loop", "transform", "frames", "cycle_offset", "mirror_axis_x", "note"}
    if set(recipe) - known:
        raise ValueError("Unsupported repair fields: " + str(sorted(set(recipe) - known)))
    paths, originals = load_frames(args.frames)
    count = len(originals)
    times = durations(args.timings, count, 24.0)
    offset = recipe.get("cycle_offset", 0)
    if type(offset) is not int or offset and not recipe.get("loop", False):
        raise ValueError("A cyclic offset requires an integer and an explicitly looping animation")
    transform = recipe.get("transform", {})
    if set(transform) - {"scale", "translate"}:
        raise ValueError("Only whole-cel scale and translation are supported")
    global_scale, global_xy = _cel_transform(transform)
    axis = recipe.get("mirror_axis_x")
    if axis is not None and (type(axis) not in (int, float) or not math.isfinite(axis) or not float(axis * 2).is_integer()):
        raise ValueError("Mirror axis must preserve an integer pixel grid")
    anchor = recipe.get("anchor")
    if axis is not None and anchor is not None and float(anchor[0]) != float(axis):
        raise ValueError("Root-axis mirroring must retain the declared anchor, not the image midline")
    edits = recipe.get("frames", {})
    if any(not str(k).isdigit() or str(int(k)) != k or int(k) >= count for k in edits):
        raise ValueError("Frame repair keys must be output-slot indices in this sequence")
    families = {"color": originals}
    companion_sources = {}
    source_roots = [args.frames.resolve()]
    for family, directory in [("normal", args.normal_frames), ("material", args.material_frames)]:
        if directory is None:
            continue
        _, data = load_frames(directory)
        if len(data) != count or data[0].size != originals[0].size:
            raise ValueError(f"{family}: companion count/canvas differs from original cels")
        if any(not np.array_equal(np.asarray(a)[..., 3], np.asarray(b)[..., 3]) for a, b in zip(originals, data)):
            raise ValueError(f"{family}: companion Alpha differs; do not silently remake it")
        families[family] = data
        companion_sources[family] = directory.name
        source_roots.append(directory.resolve())
    destinations = [args.output.resolve()] + [(args.output / ("frames" if k == "color" else k + "_frames")).resolve() for k in families]
    if any(p in source_roots for p in destinations):
        raise ValueError("Keep all repaired outputs outside original frame/map directories")
    if args.output.exists() and any(p.name != ".DS_Store" for p in args.output.iterdir()):
        raise ValueError("Use a fresh output directory so stale frames cannot enter this sequence")
    results = {key: [] for key in families}
    ledger, output_times = [], []
    source_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    for index in range(count):
        slot_source = (index + offset) % count
        spec = edits.get(str(index), {})
        if set(spec) - {"source_index", "scale", "translate", "reason"}:
            raise ValueError("Only complete original-cel references and similarity transforms are supported")
        source_index = spec.get("source_index", slot_source)
        if type(source_index) is not int or not 0 <= source_index < count:
            raise ValueError("Original source_index outside this sequence")
        local_scale, local_xy = _cel_transform(spec)
        scale = global_scale * local_scale
        xy = [round(global_scale * v + t) for v, t in zip(local_xy, global_xy)]
        for family, frames in families.items():
            results[family].append(_repair_cel(frames[source_index], scale, xy, axis, family == "normal"))
        for family in results:
            if not np.array_equal(np.asarray(results["color"][-1])[..., 3], np.asarray(results[family][-1])[..., 3]):
                raise ValueError("Paired transformed Alpha differs")
        output_times.append(times[slot_source])
        ledger.append({"output_index": index, "time_slot_source_index": slot_source,
                       "image_source_index": source_index, "pose_source": paths[source_index].name,
                       "original_file_sha256": source_hashes[source_index],
                       "output_rgba_sha256": hashlib.sha256(results["color"][-1].tobytes()).hexdigest(),
                       "duration_ms": output_times[-1], "scale": scale, "translate": xy,
                       "mirror_axis_x": axis, "source_cel_held": source_index != slot_source,
                       "reason": spec.get("reason", "")})
    metadata = export(results["color"], output_times, args.output, recipe.get("anchor"))
    metadata.update({"geometry": "fixed original canvas; explicit complete-cel similarity transform, one original resample",
                     "loop": bool(recipe.get("loop", False)), "cycle_offset": offset,
                     "companion_sheets": {key: key + "_sheet.png" for key in families if key != "color"}})
    width, height = originals[0].size
    for family, frames in results.items():
        if family == "color":
            continue
        folder = args.output / (family + "_frames")
        folder.mkdir(exist_ok=True)
        columns = metadata["columns"]
        sheet = Image.new("RGBA", (columns * width, math.ceil(count / columns) * height))
        for i, frame in enumerate(frames):
            frame.save(folder / f"frame_{i:04}.png")
            sheet.paste(frame, (i % columns * width, i // columns * height))
        sheet.save(args.output / (family + "_sheet.png"))
    write_json(args.output / "timing.json", metadata)
    write_json(args.output / "repair_ledger.json", {"source": args.frames.name,
               "source_file_hashes": source_hashes, "original_canvas": [width, height],
               "companion_sources": companion_sources,
               "new_art_generated": False, "entries": ledger,
               "runtime_pose_note": "image_source_index/pose_source identify original art. Bind held cels to their verified pose; phase-aligned directions need the aligned model phase. Do not infer 3D time solely from an original or output index."})
    print(json.dumps({"frames": count, "duration_ms": sum(output_times), "companions": list(families)[1:],
                      "cycle_offset": offset, "new_art_generated": False, "output": str(args.output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    batch = commands.add_parser("batch-guides")
    batch.add_argument("--frames", type=Path, required=True)
    batch.add_argument("--output", type=Path, required=True)
    batch.add_argument("--scale", type=int, default=6)
    idle = commands.add_parser("replay-edits")
    idle.add_argument("--base", type=Path, required=True)
    idle.add_argument("--recipe", type=Path, required=True)
    idle.add_argument("--output", type=Path, required=True)
    repair = commands.add_parser("repair-cels", help="Replay explicit repairs to complete original cels")
    repair.add_argument("--frames", type=Path, required=True)
    repair.add_argument("--timings", type=Path, required=True)
    repair.add_argument("--recipe", type=Path, required=True)
    repair.add_argument("--normal-frames", type=Path)
    repair.add_argument("--material-frames", type=Path)
    repair.add_argument("--output", type=Path, required=True)
    fixed = commands.add_parser("export")
    fixed.add_argument("--frames", type=Path, required=True)
    fixed.add_argument("--timings", type=Path)
    fixed.add_argument("--fps", type=float, default=24.0)
    fixed.add_argument("--anchor", type=float, nargs=2)
    fixed.add_argument("--output", type=Path, required=True)
    slicing = commands.add_parser("slice-sheet", help="Split a fixed grid without per-frame fitting")
    slicing.add_argument("--input", type=Path, required=True)
    slicing.add_argument("--rows", type=int, required=True)
    slicing.add_argument("--cols", type=int, required=True)
    slicing.add_argument("--count", type=int)
    slicing.add_argument("--sample-scale", type=int, default=1)
    slicing.add_argument("--fps", type=float, default=24)
    slicing.add_argument("--timings", type=Path)
    slicing.add_argument("--anchor", type=float, nargs=2)
    slicing.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output.expanduser().resolve()
    if destination.exists():
        parser.error("Output already exists. Choose a fresh output directory.")
    for field in ("frames", "normal_frames", "material_frames"):
        source = getattr(args, field, None)
        if source is not None and source.resolve() in destination.parents:
            parser.error("Output must be outside source frame directories.")
    if args.command == "batch-guides" and args.scale < 1:
        parser.error("scale must be a positive integer")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sprite-stage-", dir=destination.parent) as stage:
        args.output = Path(stage) / "result"
        if args.command == "batch-guides":
            batch_guides(args)
        elif args.command == "replay-edits":
            replay_edits(args)
        elif args.command == "repair-cels":
            repair_cels(args)
        elif args.command == "slice-sheet":
            slice_sheet(args)
        else:
            _, frames = load_frames(args.frames)
            export(frames, durations(args.timings, len(frames), args.fps), args.output, args.anchor)
        if destination.exists():
            raise ValueError("Output was created by another process. Choose a fresh directory.")
        os.rename(args.output, destination)
    print(json.dumps({"output": str(destination)}))


if __name__ == "__main__":
    main()
