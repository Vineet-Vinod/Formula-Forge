"""Render the five Formula liveries and Standard Driver as loading artwork."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from asset_helpers import cube, material, reset_scene, torus
import bpy
from mathutils import Vector


CAR_LAYOUT = (
    ("formula_fiery", (-5.25, 4.10, 0.00), 18.0),
    ("formula_marc", (-2.65, 2.25, 0.00), 9.0),
    ("formula_macl", (0.00, 0.45, 0.00), 0.0),
    ("formula_rb", (2.65, 2.25, 0.00), -9.0),
    ("formula_dash", (5.25, 4.10, 0.00), -18.0),
)


def point_at(obj, target) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def import_glb(path: Path, label: str, location, yaw_degrees: float,
               scale: float = 1.0):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    imported_set = set(imported)
    placement = bpy.data.objects.new(label, None)
    bpy.context.scene.collection.objects.link(placement)
    for obj in imported:
        if obj.parent not in imported_set:
            world = obj.matrix_world.copy()
            obj.parent = placement
            obj.matrix_world = world
    placement.location = location
    placement.rotation_euler.z = math.radians(yaw_degrees)
    placement.scale = (scale, scale, scale)
    return placement


def add_area_light(name: str, location, target, color, energy: float,
                   size: float):
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.name = name
    light.data.color = color
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = size
    point_at(light, target)
    return light


def build_scene(project_root: Path, output_dir: Path) -> None:
    reset_scene()

    dark = material("loading_dark", (0.003, 0.004, 0.007, 1),
                    metallic=0.20, roughness=0.26)
    wall_mat = material("loading_wall", (0.006, 0.004, 0.007, 1),
                        roughness=0.72)
    red_emission = material("loading_red_light", (0.42, 0.002, 0.006, 1),
                            emission=(1.0, 0.002, 0.006), emission_strength=18.0,
                            roughness=0.18)

    cube("LOADING_floor", (0, 1.5, -0.08), (18.0, 18.0, 0.12), dark, bevel=0.02)
    cube("LOADING_backdrop", (0, 7.10, 3.15), (17.5, 0.16, 7.0), wall_mat, bevel=0.02)

    # A glowing arena ring and vertical red fixtures frame the semicircle.
    torus("LOADING_red_ring", (0, 2.65, 0.015), 6.65, 0.022,
          red_emission, major_segments=96, minor_segments=8)
    for index, x in enumerate((-6.8, -5.1, -3.4, 3.4, 5.1, 6.8)):
        height = 3.2 + (index % 2) * 0.75
        cube(f"LOADING_red_bar_{index}", (x, 6.92, height * 0.5 + 0.25),
             (0.075, 0.075, height), red_emission, bevel=0.025)

    for slug, location, yaw in CAR_LAYOUT:
        import_glb(project_root / "assets" / "vehicles" / slug / f"{slug}.glb",
                   f"LOADING_{slug}", location, yaw)

    # Cool front fill preserves every livery; saturated red rim lights deliver
    # the requested dark red-lit loading-screen mood.
    add_area_light("LOADING_key", (0.0, -7.0, 8.2), (0.0, 1.6, 0.65),
                   (0.76, 0.84, 1.0), 1850.0, 6.0)
    add_area_light("LOADING_fill_left", (-7.0, -1.5, 4.2), (-2.3, 2.0, 0.5),
                   (0.20, 0.34, 0.64), 1050.0, 4.0)
    add_area_light("LOADING_fill_right", (7.0, -0.5, 3.4), (2.5, 2.2, 0.5),
                   (0.70, 0.12, 0.10), 1150.0, 4.0)
    for index, x in enumerate((-5.0, -2.5, 0.0, 2.5, 5.0)):
        add_area_light(f"LOADING_rim_{index}", (x, 5.5, 4.8),
                       (x * 0.78, 2.0, 0.45), (1.0, 0.004, 0.008),
                       900.0, 2.5)

    bpy.ops.object.camera_add(location=(0.0, -18.6, 7.15))
    camera = bpy.context.object
    camera.name = "LOADING_camera"
    camera.data.lens = 51
    camera.data.sensor_width = 36
    point_at(camera, (0.0, 1.45, 0.72))
    bpy.context.scene.camera = camera

    world = bpy.context.scene.world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.001, 0.001, 0.003, 1)
    background.inputs["Strength"].default_value = 0.055

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "formula_forge_loading.png"
    blend_path = output_dir / "formula_forge_loading.blend"
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.filepath = str(png_path)
    scene.render.image_settings.color_mode = "RGB"
    scene.render.resolution_percentage = 100
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.frame_set(1)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

    manifest = {
        "schema_version": 1,
        "asset": "formula_forge_loading",
        "type": "ui_artwork",
        "resolution": [1280, 720],
        "composition": "five Formula liveries in a red-lit semicircle",
        "lighting": "dark studio with red arena and rim lights",
        "vehicles": [slug for slug, _, _ in CAR_LAYOUT],
        "source": blend_path.name,
        "render": png_path.name,
    }
    (output_dir / "formula_forge_loading.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path,
                        default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    output_dir = (args.output_dir.resolve() if args.output_dir else
                  project_root / "assets" / "ui" / "formula_forge_loading")
    build_scene(project_root, output_dir)


if __name__ == "__main__":
    main()
