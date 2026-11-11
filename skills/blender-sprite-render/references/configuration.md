# Render configuration

See the executable sample at the repository's `examples/render.json`.

| Field | Meaning |
| --- | --- |
| collection | Sprite subject collection in a .blend file |
| canvas_px | Final full width and height |
| anchor_px | Pixel coordinate of anchor_world, top-left origin |
| anchor_world | Stable scene root, default [0,0,0] |
| sample_scale | 1, 3 or 5, sampled at the integer cell center |
| ortho_scale | Shared camera scale in scene units |
| target | Initial camera look-at point |
| distance | Camera distance from target |
| elevation_deg | Elevation of camera above the horizontal |
| depth_range | Increasing camera-view Z bounds for normalized depth |
| fps | Source timeline rate |
| frames | Increasing source frame numbers |
| loop_end_frame | Exclusive end for the last sample, defaults to the previous frame step |
| directions | Named direction-to-azimuth map in degrees |

The demo faces -Y at azimuth zero. X is right and Z is up in Blender. Name directions to match your source convention. They are directory labels, so the tool accepts ASCII letters, digits, underscores and hyphens.

The renderer hides renderable geometry outside the chosen collection, adds a fixed key/fill rig and a transparent world, and controls color management in its background process. Existing source lights still contribute. Prepare a dedicated source scene when exact authored lighting matters.

An object's custom integer `palette_group` property selects a color ramp in a palette JSON map. Unassigned meshes default to group zero. Object-ID rendering disables dithering to keep small integer values stable. Anti-aliased boundaries can still mix group values, so review thin and translucent geometry.

Each direction's output has PNG frame directories, a sheet and `timing.json`. Frame times derive from source-frame gaps and source FPS. All references inside manifests are relative. Source art remains at its full canvas size.

Example invocations from the repository root

~~~sh
blender --background --python-exit-code 1 --python examples/make_demo.py -- .build/bird.blend
blender --background --python-exit-code 1 --python skills/blender-sprite-render/scripts/render_sprites.py -- --input .build/bird.blend --config examples/render.json --output .build/render
python skills/blender-sprite-render/scripts/finish_sprites.py --input .build/render --palettes examples/palettes.json --output .build/sprites
~~~
