# Third-party notices

## Agent Sprite Forge

Upstream project https://github.com/0x0funky/agent-sprite-forge

Copyright (c) 2026 0x0funky. MIT license. Full text is included at `licenses/agent-sprite-forge-MIT.txt`.

`skills/sprite-sequence/scripts/gif_preview.py` adapts the shared-palette transparent GIF implementation from a locally maintained May 2026 snapshot. `pixel_sequence_tools.py` carries the associated fixed-canvas workflow and locally developed additions. Conservatively retain this notice with both files and derivatives. The exact upstream commit of that downloaded snapshot was unavailable.

Local changes include original-cel recipes, point-edit replay, fixed-grid guides and slicing, source basenames in ledgers, real timestamp extraction and staged output directories. The current upstream has evolved independently. This project has its own reduced scope and dependency set.

## External dependencies

- Pillow and NumPy are installed from their upstream distributions.
- Blender runs the renderer and demo authoring scripts using its own Python.
- FFmpeg and FFprobe are optional executables for supplied-video extraction.

These dependencies are installed separately. Their own distributions provide their notices and licenses.

## Original demo

`examples/make_demo.py` creates the clockwork bird geometry, materials and transform animation. The preview and resulting demo frames were rendered from that source. They are covered by this repository's MIT license.

The published repository was assembled from selected, reviewed source files in a new Git history. It contains public author attribution and relative-path examples.
