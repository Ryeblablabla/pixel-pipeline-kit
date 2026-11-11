# Contributing

Use a small, reproducible input and describe the behavior you want to change. Include your Python/Blender/FFmpeg versions for relevant bugs.

Keep each Skill runnable after copying its directory. Use standard-library arguments and relative manifests. Add a dependency only when it solves a demonstrated problem. Preserve source cels, Alpha, canvas and timing unless the command explicitly changes them.

Run the targeted regression checks with `python -m unittest discover -s tests`. For renderer changes, render one short supplied animation and inspect color, normal, depth and group outputs together. Include native-size and nearest-neighbor previews.

Document changed command arguments and metadata fields in the same change. Keep generation-provider integration optional. Check source paths, media metadata and account details before attaching an example. Preserve third-party notices. Contributions are submitted under the repository's MIT license.
