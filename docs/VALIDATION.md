# Validation record

The initial release was exercised on macOS arm64, Python 3.9 and Blender 5.2.2 LTS.

The bundled clockwork-bird source produced four directions and eight animation samples per direction. Each sample rendered RGBA color, camera normals, normalized depth and palette groups. Center sampling produced a fixed 128×128 canvas and configured root. The color exporter preserves input RGBA and per-frame milliseconds. Regression checks cover loop timing, fixed-cell slicing, explicit cel transforms and failure cleanup.

Rendering disables color-management dithering because low-valued palette group IDs otherwise fluctuate. Geometry passes use Raw, and color uses Standard. The selected source animation and the camera's shared scale are evaluated unchanged across frames.

Windows, Linux, other Blender releases, transparent PBR assets and animation-heavy imported rigs need their own validation. No automatic identity, anatomy or gait-quality score is produced.
