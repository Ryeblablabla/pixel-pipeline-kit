# SPDX-License-Identifier: MIT
"""Render a fixed orthographic sprite camera and aligned auxiliary passes in Blender.

Run with Blender --background --python render_sprites.py -- --help.
"""
import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


def emission_material(name, source):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    source(material.node_tree, emission.inputs["Color"])
    return material


def normal_source(tree, destination):
    geometry = tree.nodes.new("ShaderNodeNewGeometry")
    transform = tree.nodes.new("ShaderNodeVectorTransform")
    transform.vector_type = "NORMAL"
    transform.convert_from = "WORLD"
    transform.convert_to = "CAMERA"
    encode = tree.nodes.new("ShaderNodeVectorMath")
    encode.operation = "MULTIPLY_ADD"
    encode.inputs[1].default_value = (0.5, 0.5, 0.5)
    encode.inputs[2].default_value = (0.5, 0.5, 0.5)
    tree.links.new(geometry.outputs["Normal"], transform.inputs[0])
    tree.links.new(transform.outputs[0], encode.inputs[0])
    tree.links.new(encode.outputs[0], destination)


def depth_source(tree, destination, bounds):
    camera = tree.nodes.new("ShaderNodeCameraData")
    mapping = tree.nodes.new("ShaderNodeMapRange")
    mapping.inputs["From Min"].default_value = bounds[0]
    mapping.inputs["From Max"].default_value = bounds[1]
    mapping.clamp = True
    tree.links.new(camera.outputs["View Z Depth"], mapping.inputs["Value"])
    tree.links.new(mapping.outputs[0], destination)


def group_source(tree, destination):
    obj = tree.nodes.new("ShaderNodeObjectInfo")
    tree.links.new(obj.outputs["Color"], destination)


def open_input(path):
    if path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    elif path.suffix.lower() in (".glb", ".gltf"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
        collection = bpy.data.collections.new("Sprite")
        bpy.context.scene.collection.children.link(collection)
        for obj in list(bpy.context.scene.objects):
            for owner in list(obj.users_collection):
                owner.objects.unlink(obj)
            collection.objects.link(obj)
    else:
        raise ValueError("Input must be .blend, .glb or .gltf")


def render(args, config, out):
    open_input(args.input.resolve())
    scene = bpy.context.scene
    target = bpy.data.collections.get(config.get("collection", "Sprite"))
    if target is None:
        raise ValueError("Configured sprite collection is missing")
    subjects = set(target.all_objects)
    meshes = [obj for obj in subjects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("Sprite collection has no meshes")
    for obj in scene.objects:
        if obj.type in ("MESH", "CURVE", "SURFACE", "META", "FONT", "VOLUME") and obj not in subjects:
            obj.hide_render = True
    for obj in meshes:
        group = int(obj.get("palette_group", 0))
        if not 0 <= group <= 255:
            raise ValueError("palette_group must be an integer from 0 to 255")
        obj.color = (group / 255.0, 0, 0, 1)

    engines = scene.render.bl_rna.properties["engine"].enum_items.keys()
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.render.dither_intensity = 0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.render.resolution_x = config["canvas_px"][0] * config["sample_scale"]
    scene.render.resolution_y = config["canvas_px"][1] * config["sample_scale"]
    scene.render.fps = config["fps"]
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.use_file_extension = True
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Sprite world")
    scene.world.use_nodes = True
    world_nodes = scene.world.node_tree.nodes
    world_nodes.clear()
    background = world_nodes.new("ShaderNodeBackground")
    world_output = world_nodes.new("ShaderNodeOutputWorld")
    background.inputs[0].default_value = (0.22, 0.25, 0.3, 1)
    background.inputs[1].default_value = 0.5
    scene.world.node_tree.links.new(background.outputs[0], world_output.inputs[0])

    camera_data = bpy.data.cameras.new("SpriteCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = config["ortho_scale"]
    camera = bpy.data.objects.new("SpriteCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, position, energy, size in (
        ("Key", (4, -6, 7), 900, 4),
        ("Fill", (-4, -2, 4), 450, 5),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        lamp = bpy.data.objects.new(name, data)
        scene.collection.objects.link(lamp)
        lamp.location = position
        lamp.rotation_euler = (Vector(config["target"]) - lamp.location).to_track_quat("-Z", "Y").to_euler()

    guides = {
        "normal": emission_material("Camera normals", normal_source),
        "depth": emission_material("Normalized depth", lambda tree, dst: depth_source(tree, dst, config["depth_range"])),
        "groups": emission_material("Palette groups", group_source),
    }
    layer = bpy.context.view_layer
    records = []
    for direction, azimuth in config["directions"].items():
        pitch = math.radians(config["elevation_deg"])
        angle = math.radians(azimuth)
        target_point = Vector(config["target"])
        camera.location = target_point + config["distance"] * Vector(
            (math.cos(pitch) * math.sin(angle), -math.cos(pitch) * math.cos(angle), math.sin(pitch)))
        camera.rotation_euler = (target_point - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.shift_x = 0
        camera.data.shift_y = 0
        bpy.context.view_layer.update()
        anchor_world = Vector(config.get("anchor_world", (0, 0, 0)))
        projected = world_to_camera_view(scene, camera, anchor_world)
        anchor_px = config["anchor_px"]
        # Blender orthographic shift is measured against the larger canvas dimension.
        width, height = config["canvas_px"]
        camera.data.shift_x = (projected.x - anchor_px[0] / width) * width / max(width, height)
        camera.data.shift_y = (projected.y - (1 - anchor_px[1] / height)) * height / max(width, height)
        for index, frame in enumerate(config["frames"]):
            scene.frame_set(frame)
            record = {"direction": direction, "index": index, "source_frame": frame}
            for channel in ("color", "normal", "depth", "groups"):
                layer.material_override = guides.get(channel)
                scene.view_settings.view_transform = "Standard" if channel == "color" else "Raw"
                file = Path(channel) / direction / f"frame_{index:04}.png"
                (out / file).parent.mkdir(parents=True, exist_ok=True)
                scene.render.filepath = str(out / file)
                bpy.ops.render.render(write_still=True)
                record[channel] = file.as_posix()
            records.append(record)
    manifest = {
        "schema_version": 1,
        "source": args.input.name,
        "config": config,
        "normal_encoding": "camera-space xyz mapped from [-1,1] to [0,1], RGB8 Raw",
        "depth_encoding": "camera view z mapped to depth_range, RGB8 Raw, clamped",
        "group_encoding": "palette_group integer in red byte, Raw",
        "records": records,
    }
    (out / "render.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    config = json.loads(args.config.read_text(encoding="utf-8"))
    width, height = config["canvas_px"]
    if min(width, height) < 1 or config["sample_scale"] not in (1, 3, 5):
        raise ValueError("Positive canvas dimensions and odd sample_scale 1, 3 or 5 required")
    if not config["frames"] or not config["directions"]:
        raise ValueError("At least one frame and direction required")
    for name in config["directions"]:
        if not name or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for char in name):
            raise ValueError("Direction names must be simple directory names")
    if config["depth_range"][0] >= config["depth_range"][1]:
        raise ValueError("depth_range must be increasing")
    destination = args.output.resolve()
    if destination.exists():
        raise ValueError("Choose a fresh output directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".render-stage-", dir=destination.parent) as stage:
        out = Path(stage) / "result"
        out.mkdir()
        render(args, config, out)
        if destination.exists():
            raise ValueError("Output was created concurrently")
        out.rename(destination)
    print("Rendered", destination)


if __name__ == "__main__":
    main()
