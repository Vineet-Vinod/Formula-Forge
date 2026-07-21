"""Render the dark, red-lit Formula Forge menu garage with Blender's Python API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bpy
from mathutils import Vector


def material(name: str, color: tuple[float, float, float, float], *, metallic: float = 0.0,
             roughness: float = 0.45, emission: tuple[float, float, float, float] | None = None,
             emission_strength: float = 0.0) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.diffuse_color = color
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = color
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if emission is not None:
        shader.inputs["Emission Color"].default_value = emission
        shader.inputs["Emission Strength"].default_value = emission_strength
    return result


def cube(name: str, location: tuple[float, float, float], dimensions: tuple[float, float, float],
         surface: bpy.types.Material, bevel: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(surface)
    if bevel > 0.0:
        modifier = obj.modifiers.new("Edge softening", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    return obj


def cylinder(name: str, location: tuple[float, float, float], radius: float, depth: float,
             surface: bpy.types.Material, vertices: int = 64, bevel: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(surface)
    if bevel > 0.0:
        modifier = obj.modifiers.new("Edge softening", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    return obj


def area_light(name: str, location: tuple[float, float, float], target: tuple[float, float, float],
               color: tuple[float, float, float], energy: float, size: float) -> None:
    data = bpy.data.lights.new(name, "AREA")
    data.color = color
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build_scene(output_dir: Path) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            datablocks.remove(block)

    graphite = material("FORGE_graphite", (0.010, 0.013, 0.019, 1.0), metallic=0.72, roughness=0.24)
    wall = material("FORGE_wall", (0.018, 0.022, 0.030, 1.0), metallic=0.34, roughness=0.38)
    panel = material("FORGE_panel", (0.028, 0.033, 0.044, 1.0), metallic=0.55, roughness=0.31)
    red_light = material("FORGE_red_light", (0.32, 0.002, 0.006, 1.0), roughness=0.18,
                         emission=(1.0, 0.004, 0.010, 1.0), emission_strength=18.0)
    white_light = material("FORGE_white_light", (0.35, 0.36, 0.39, 1.0), roughness=0.15,
                           emission=(0.72, 0.76, 0.84, 1.0), emission_strength=5.0)
    pedestal_top = material("FORGE_pedestal_top", (0.030, 0.036, 0.048, 1.0), metallic=0.68, roughness=0.23)
    pedestal_edge = material("FORGE_pedestal_edge", (0.19, 0.004, 0.008, 1.0), metallic=0.32, roughness=0.20,
                             emission=(1.0, 0.006, 0.012, 1.0), emission_strength=3.2)

    cube("FORGE_floor", (0.0, 0.0, -0.15), (22.0, 20.0, 0.30), graphite)
    cube("FORGE_back_wall", (0.0, 5.6, 3.8), (22.0, 0.35, 8.0), wall)
    cube("FORGE_left_wall", (-10.8, 0.8, 3.8), (0.35, 10.0, 8.0), wall)
    cube("FORGE_right_wall", (10.8, 0.8, 3.8), (0.35, 10.0, 8.0), wall)
    cube("FORGE_ceiling", (0.0, 1.2, 7.75), (22.0, 10.0, 0.28), wall)

    # Layered wall panels and columns give the empty bay readable depth while
    # preserving a clean central silhouette for the live rotating car.
    for x in (-8.7, -5.8, -2.9, 0.0, 2.9, 5.8, 8.7):
        cube(f"FORGE_wall_panel_{x:+.1f}", (x, 5.35, 3.55), (2.54, 0.12, 6.4), panel, 0.04)
    for x in (-9.1, -6.1, -3.05, 3.05, 6.1, 9.1):
        cube(f"FORGE_red_bar_{x:+.2f}", (x, 5.12, 4.05), (0.075, 0.055, 5.1), red_light, 0.025)
    cube("FORGE_red_header", (0.0, 5.10, 6.72), (18.3, 0.055, 0.075), red_light, 0.025)

    for x in (-6.8, -2.25, 2.25, 6.8):
        cube(f"FORGE_ceiling_light_{x:+.2f}", (x, 0.7, 7.48), (2.4, 0.24, 0.055), white_light, 0.03)

    # A low display plinth gives the composited live car a clear contact plane.
    # The larger dark base and inset top leave a slim illuminated edge instead
    # of a bright disc competing with the livery.
    cylinder("FORGE_pedestal_edge", (0.0, 0.35, 0.055), 4.42, 0.17, pedestal_edge, bevel=0.05)
    cylinder("FORGE_pedestal_top", (0.0, 0.35, 0.145), 4.27, 0.20, pedestal_top, bevel=0.07)

    # A red floor frame echoes the loading-screen arena without copying it.
    cube("FORGE_floor_strip_back", (0.0, 2.7, -0.002), (13.5, 0.055, 0.035), red_light, 0.02)
    cube("FORGE_floor_strip_front", (0.0, -3.7, -0.002), (13.5, 0.055, 0.035), red_light, 0.02)
    cube("FORGE_floor_strip_left", (-6.72, -0.5, -0.002), (0.055, 6.45, 0.035), red_light, 0.02)
    cube("FORGE_floor_strip_right", (6.72, -0.5, -0.002), (0.055, 6.45, 0.035), red_light, 0.02)

    area_light("FORGE_red_rim_left", (-6.8, -0.5, 3.1), (0.0, 0.6, 1.0), (1.0, 0.005, 0.012), 1250.0, 4.0)
    area_light("FORGE_red_rim_right", (6.8, -0.5, 3.1), (0.0, 0.6, 1.0), (1.0, 0.005, 0.012), 1250.0, 4.0)
    area_light("FORGE_softbox", (0.0, -2.4, 6.9), (0.0, 0.4, 0.7), (0.38, 0.44, 0.56), 900.0, 5.0)
    area_light("FORGE_overhead_spot", (0.0, 0.2, 7.15), (0.0, 0.35, 0.2), (1.0, 0.94, 0.88), 2100.0, 4.2)
    area_light("FORGE_back_glow", (0.0, 4.5, 2.6), (0.0, 0.0, 0.8), (1.0, 0.008, 0.014), 220.0, 3.0)

    camera_data = bpy.data.cameras.new("FORGE_camera")
    camera = bpy.data.objects.new("FORGE_camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0.0, -13.8, 4.0)
    camera.rotation_euler = (Vector((0.0, 0.4, 1.35)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 48.0
    camera_data.sensor_width = 36.0

    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("FORGE_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.0015, 0.003, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.025
    scene.world = world

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "formula_garage_background.png"
    blend_path = output_dir / "formula_garage.blend"
    scene.render.filepath = str(png_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.render.render(write_still=True)

    manifest = {
        "schema_version": 1,
        "asset": "formula_garage",
        "type": "ui_background",
        "resolution": [1280, 720],
        "composition": "empty Formula garage bay for a live rotating car overlay",
        "lighting": "dark graphite studio with red practicals and a neutral overhead display light",
        "source": blend_path.name,
        "render": png_path.name,
    }
    (output_dir / "formula_garage.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve() if args.output_dir else (
        args.project_root.resolve() / "assets" / "ui" / "formula_garage")
    build_scene(output_dir)


if __name__ == "__main__":
    main()
