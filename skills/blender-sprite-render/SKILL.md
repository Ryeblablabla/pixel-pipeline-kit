---
name: blender-sprite-render
description: Render supplied Blender or glTF animation into fixed-grid transparent directional sprites with aligned camera normals, normalized depth and palette-group masks.
---

# Blender sprite render

Use an existing editable model or animation. Establish the intended directions, action range, full frame size, root anchor and pixels-per-scene-unit before rendering. Keep one shared camera scale across the animation.

1. Read [render configuration](references/configuration.md). Use a supplied .blend scene or GLB/glTF. For a .blend file, put subjects in the configured collection. For glTF the script creates a Sprite collection.
2. Run Blender in the background with `scripts/render_sprites.py`. It renders RGBA color, camera-space normals, normalized depth and palette-group data from the same orthographic camera.
3. Run Python with `scripts/finish_sprites.py`. An odd integer sample scale selects the same center in every grid cell. Optional palettes apply by group. Depth/normal differences contribute a restrained outline.
4. Inspect all directions, loop seams, full-frame containment, anchor placement and thin details at native size and integer zoom. Adjust the model/camera/lighting or palettes from that evidence.
5. Deliver the relative-path render manifest, final frames, atlas and exact frame durations. Retain the editable source separately as appropriate.

Blender dependencies run in Blender's own Python. Finishing requires Pillow and NumPy. Use `--python-exit-code 1` in unattended Blender calls so script failures are observable.

The demo authoring script creates an original geometric clockwork bird with keyed transforms. Existing rigs and animation from user-supplied files are evaluated by Blender. Automatic rigging, AI model generation and game-specific registration remain separate tasks.

Data passes disable render dithering and use Raw color management. The current depth output is normalized RGB8. Pick a tight depth range around the subject and verify thresholds at the intended scale. This output is a sprite outline guide. Camera-space normals use the selected camera and remain separate from any engine-specific semantic normal convention.

Default pixel Alpha becomes binary after sampling. Preserve the raw RGBA renders when smooth transparency matters. Check partially transparent surfaces separately because depth/group data can mix at such surfaces.
