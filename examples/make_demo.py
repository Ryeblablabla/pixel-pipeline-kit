# SPDX-License-Identifier: MIT
"""Create an original animated clockwork bird in Blender for the MIT demo."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
collection = bpy.data.collections.new("Sprite")
scene.collection.children.link(collection)


def material(name, color):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    node = result.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*color, 1)
    node.inputs["Roughness"].default_value = 0.8
    return result


teal = material("Teal enamel", (0.02, 0.42, 0.38))
gold = material("Warm brass", (0.85, 0.38, 0.045))
cream = material("Cream face", (0.92, 0.83, 0.61))
dark = material("Dark eyes", (0.012, 0.025, 0.04))


def move_to_collection(obj):
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)


def joint(name, position, parent=None):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.location = position
    obj.parent = parent
    return obj


def ellipsoid(name, position, scale, mat, parent=None, group=0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj.parent = parent
    obj["palette_group"] = group
    move_to_collection(obj)
    return obj


body = joint("Body", (0, 0, 0.8))
ellipsoid("Body shell", (0, 0, 0.17), (0.44, 0.34, 0.52), teal, body)
ellipsoid("Chest", (0, -0.26, 0.16), (0.29, 0.14, 0.36), gold, body, 1)
ellipsoid("Head", (0, -0.02, 0.82), (0.36, 0.32, 0.34), teal, body)
ellipsoid("Face", (0, -0.263, 0.83), (0.30, 0.09, 0.24), cream, body, 2)
for side in (-1, 1):
    ellipsoid("Eye", (side * 0.13, -0.345, 0.89), (0.055, 0.035, 0.068), dark, body, 2)
    ellipsoid("Eye shine", (side * 0.13 - 0.012, -0.377, 0.913), (0.016, 0.009, 0.018), cream, body, 2)
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.105, radius2=0, depth=0.24)
beak = bpy.context.object
beak.name = "Beak"
beak.parent = body
beak.location = (0, -0.37, 0.75)
beak.rotation_euler.x = math.pi / 2
beak.data.materials.append(gold)
beak["palette_group"] = 1
move_to_collection(beak)
wings = []
legs = []
for side in (-1, 1):
    wing = joint("Wing pivot", (side * 0.34, 0.05, 0.42), body)
    ellipsoid("Wing", (side * 0.16, 0, -0.18), (0.26, 0.12, 0.34), gold, wing, 1)
    wings.append(wing)
    leg = joint("Leg pivot", (side * 0.19, 0, 0.55))
    ellipsoid("Leg", (0, 0, -0.19), (0.085, 0.09, 0.23), gold, leg, 1)
    ellipsoid("Foot", (0, -0.09, -0.43), (0.14, 0.23, 0.07), dark, leg, 1)
    legs.append(leg)
ellipsoid("Tail", (0, 0.34, -0.02), (0.25, 0.35, 0.17), teal, body)
ellipsoid("Crest", (0, 0.02, 1.15), (0.095, 0.12, 0.18), gold, body, 1)
for frame in range(1, 25):
    phase = (frame - 1) / 24 * math.tau
    body.location.z = 0.8 + 0.035 * math.cos(phase * 2)
    body.rotation_euler.y = 0.05 * math.sin(phase)
    body.keyframe_insert(data_path="location", frame=frame)
    body.keyframe_insert(data_path="rotation_euler", frame=frame)
    for index, leg in enumerate(legs):
        leg.rotation_euler.x = 0.45 * math.sin(phase + index * math.pi)
        leg.keyframe_insert(data_path="rotation_euler", frame=frame)
    for index, wing in enumerate(wings):
        wing.rotation_euler.y = (1 if index else -1) * (0.12 + 0.14 * math.sin(phase))
        wing.keyframe_insert(data_path="rotation_euler", frame=frame)
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 24
bpy.context.preferences.filepaths.save_version = 0
path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
