# SPDX-License-Identifier: MIT
"""Shared-palette GIF preview, adapted from Agent Sprite Forge (MIT)."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image

def save_transparent_gif(frames: list[Image.Image], out_path: Path, duration: int | list[int]) -> None:
    if not frames:
        raise ValueError("No frames to encode.")

    # GIF has binary alpha. Reserve palette index 0 using source alpha only;
    # never make a subject color transparent because it resembles a key color.
    width, height = frames[0].size
    stacked = Image.new("RGB", (width, height * len(frames)))
    for index, frame in enumerate(frames):
        stacked.paste(frame.convert("RGB"), (0, index * height))
    paletted = stacked.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = [0, 0, 0] + list(paletted.getpalette() or [])[:255 * 3]
    palette.extend([0] * (768 - len(palette)))
    out_frames = []
    for index, frame in enumerate(frames):
        indices = np.array(paletted.crop((0, index * height, width, (index + 1) * height)), dtype=np.uint16) + 1
        indices[np.asarray(frame.getchannel("A")) < 128] = 0
        encoded = Image.fromarray(indices.astype(np.uint8), mode="P")
        encoded.putpalette(palette)
        out_frames.append(encoded)
    out_frames[0].save(
        out_path,
        format="GIF",
        save_all=True,
        append_images=out_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        transparency=0,
        background=0,
    )
