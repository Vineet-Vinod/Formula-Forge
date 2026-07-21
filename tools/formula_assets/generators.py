from __future__ import annotations

import math
from collections.abc import Callable

import bpy


def _material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, roughness: float = 0.5):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return material


def _cube(collection, name: str, location, scale, material, bevel: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("edge_softening", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    obj.data.materials.append(material)
    _move_to_collection(obj, collection)
    return obj


def _move_to_collection(obj, collection) -> None:
    for current in tuple(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def _parent_keep_transform(child, parent) -> None:
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def build_smoke_kart(runtime_collection) -> None:
    """Build a small dimensioned kart used to prove the authoring pipeline."""
    red = _material("paint_coral", (0.72, 0.035, 0.025, 1.0), metallic=0.12, roughness=0.28)
    cream = _material("paint_cream", (0.92, 0.73, 0.40, 1.0), metallic=0.02, roughness=0.4)
    rubber = _material("rubber", (0.018, 0.022, 0.025, 1.0), roughness=0.78)
    metal = _material("brushed_metal", (0.28, 0.34, 0.38, 1.0), metallic=0.82, roughness=0.24)

    root = bpy.data.objects.new("FB_Root", None)
    runtime_collection.objects.link(root)
    root["formula_forge.units"] = "meters"
    root["formula_forge.forward"] = "+Y"
    root["formula_forge.up"] = "+Z"

    chassis = _cube(runtime_collection, "chassis", (0.0, 0.0, 0.48), (0.63, 1.02, 0.22), red, 0.16)
    nose = _cube(runtime_collection, "nose", (0.0, 0.83, 0.57), (0.42, 0.47, 0.18), cream, 0.12)
    seat = _cube(runtime_collection, "seat", (0.0, -0.30, 0.84), (0.39, 0.42, 0.34), rubber, 0.12)
    bumper_front = _cube(runtime_collection, "bumper_front", (0.0, 1.27, 0.34), (0.62, 0.06, 0.07), metal, 0.04)
    bumper_rear = _cube(runtime_collection, "bumper_rear", (0.0, -1.27, 0.34), (0.62, 0.06, 0.07), metal, 0.04)

    steering = bpy.data.objects.new("steering_pivot", None)
    steering.empty_display_type = "ARROWS"
    steering.empty_display_size = 0.18
    steering.location = (0.0, 0.35, 0.76)
    runtime_collection.objects.link(steering)

    for name, x, y in (
        ("wheel_fl", -0.70, 0.72),
        ("wheel_fr", 0.70, 0.72),
        ("wheel_rl", -0.70, -0.72),
        ("wheel_rr", 0.70, -0.72),
    ):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.30, depth=0.20, location=(x, y, 0.32), rotation=(0.0, math.pi / 2.0, 0.0))
        wheel = bpy.context.object
        wheel.name = name
        wheel.data.materials.append(rubber)
        bevel = wheel.modifiers.new("tire_rounding", "BEVEL")
        bevel.width = 0.045
        bevel.segments = 3
        _move_to_collection(wheel, runtime_collection)
        _parent_keep_transform(wheel, steering if name.startswith("wheel_f") else root)

    for obj in (chassis, nose, seat, bumper_front, bumper_rear, steering):
        _parent_keep_transform(obj, root)


GENERATORS: dict[str, Callable] = {
    "smoke_kart": build_smoke_kart,
}
