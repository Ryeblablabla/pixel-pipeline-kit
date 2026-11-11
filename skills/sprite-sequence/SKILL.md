---
name: sprite-sequence
description: Produce reference-locked 2D sprite sequences with four-frame reconstruction guides, original-cel repairs, explicit pixel edits, real video timestamps and fixed-canvas exports.
---

# Sprite sequence

Choose the route from the supplied art and requested change.

- New sprite animation. Lock an accepted identity reference, direction, canvas, anchor and pixel scale. Generate one action and direction at a time using the available image/video provider. For motion reconstruction, use video as pose reference, then rebuild a small complete loop in 2×2 four-frame batches alongside the accepted art and the approved first batch. Request native RGBA from an image tool supporting transparency. Keep source masters and assess the actual animation.
- Existing approved animation. Preserve complete original cels. Use an explicit whole-cel translation, uniform scale, original held cel or a justified looping phase adjustment. Read [recipes](references/recipes.md) for the supported repair format.
- Literal pixel idle requested by the user. Replay declared eye, hair or fabric point changes from the accepted base. Read [recipes](references/recipes.md). New body motion needs its own art or animation source.
- Supplied video. Inspect it and select an actual loop. Use the included timestamp extractor with FFmpeg. An opaque video remains opaque after extraction. Choose a suitable segmentation workflow explicitly if needed.

## Essential constraints

Retain the full fixed canvas, shared direction scale, root point, source colors and authored timing. Use nearest-neighbor operations for accepted pixel art. Avoid independent per-frame bounding-box fitting. Explicit mirroring must preserve the anchor and invert the normal map X channel when that companion is supplied. Inspect original-size playback, an integer enlargement, a loop seam and direction switches. Numeric completeness checks cannot approve identity or anatomy.

## Commands

Use Python with Pillow and NumPy. Scripts are self-contained within this skill.

- `python scripts/pixel_sequence_tools.py batch-guides --frames INPUT --output GUIDES` creates 2×2 reference boards. Padding slots are marked as references and excluded from the intended frame count.
- `python scripts/pixel_sequence_tools.py export --frames INPUT --timings timing.json --anchor 64 112 --output OUTPUT` preserves RGBA PNGs and per-frame milliseconds, with an atlas and a shared-palette GIF preview.
- `python scripts/pixel_sequence_tools.py repair-cels --help` applies explicit complete-cel recipes and optional aligned normal/material companions.
- `python scripts/pixel_sequence_tools.py replay-edits --help` replays approved point operations.
- `python scripts/extract_video_frames.py --video INPUT.mp4 --indices 0 3 6 9 --out OUTPUT` decodes selected display frames and records actual PTS. Use `--times` to select nearest actual presentation times.

Choose a new output directory. Each sequence command stages its complete result before moving it into place. PNG RGBA is authoritative. GIF has binary transparency, 255 visible palette entries and centisecond timing.

Generation credentials and provider clients stay in the user's selected environment. Follow its normal costs and authorization rules. A text prompt or skeleton image is a soft reference unless the selected model supplies an actual conditioning mechanism.
