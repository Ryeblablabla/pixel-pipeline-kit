# Explicit sequence recipes

These recipes act on complete source cels. Frame indices are zero-based and PNG filenames use natural numeric order. Input metadata may be a list of milliseconds or an object with `durations_ms` or `durations_seconds`.

## Whole-cel repair

~~~json
{
  "anchor": [64, 112],
  "loop": true,
  "cycle_offset": 0,
  "transform": {"scale": 1.0, "translate": [0, 0]},
  "frames": {
    "2": {"translate": [1, 0], "reason": "approved full-cel alignment"}
  }
}
~~~

A local translation is transformed by the global scale, then the global translation is added. Nearest-neighbor scale is applied once to each original cel. Coordinates are canvas pixels, so scaling around a fixed anchor requires a matching translation. Cropping visible pixels fails.

Optional `mirror_axis_x` mirrors the pixel centers around the supplied root axis. With a declared anchor it must equal the anchor's X value. A `cycle_offset` requires `loop: true` and shifts timing slots with the loop. A per-slot `source_index` holds another original image while preserving that output slot's duration. Matching companion maps are transformed together and their input/output Alpha is checked.

## Literal pixel edits

~~~json
{
  "anchor": [64, 112],
  "allowed_regions": [[56, 35, 15, 7]],
  "states": {
    "blink": [
      {"op": "copy", "from": [58, 40], "to": [59, 39]},
      {"op": "erase", "to": [60, 38]}
    ]
  },
  "timeline": [
    {"duration_ms": 500},
    {"states": ["blink"], "duration_ms": 100},
    {"duration_ms": 500}
  ]
}
~~~

Every frame starts from the approved base. Supported operations are `copy`, `erase` and `paint` with four-byte `rgba`. Painted visible colors must occur in the original palette unless `allow_new_colors` is true. Changes outside `allowed_regions` fail. An optional `base_sha256` locks the exact source PNG. The output ledger records changed pixels and the base hash using source basenames.
