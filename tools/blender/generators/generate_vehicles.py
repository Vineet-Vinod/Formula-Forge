"""Generate one Formula model in five original livery variants."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import bpy
import bmesh

from asset_helpers import (ASSET_PROP, add_wheel, asset_objects, bar,
                           build_rigid_rig, create_rig_action, cube, cylinder,
                           empty, export_asset, material, reset_scene, sphere,
                           torus)


# Dimensions are Blender X width, Y length and Z height in metres. All five
# entries share exactly one mesh recipe and mechanical contract; only material
# roles and original geometric paint graphics vary.
VEHICLES = {
    "formula_marc": {
        "display_name": "Marc", "model_name": "Formula",
        "livery_name": "Marc", "pattern": "marc",
        "family": "Formula livery",
        "dimensions_target_m": [2.03, 4.92, 1.13],
        "paint": (0.008, 0.012, 0.018, 1),
        "secondary": (0.54, 0.60, 0.62, 1),
        "accent": (0.00, 0.76, 0.66, 1),
        "detail": (0.90, 0.94, 0.92, 1),
        "aero": "agile",
        "roles": {"nose": "secondary", "monocoque": "secondary",
                  "sidepod": "paint", "engine": "paint",
                  "airbox": "paint", "spear": "accent",
                  "stripe": "accent", "fin": "secondary",
                  "rail": "paint", "headrest": "accent",
                  "front_upper": "secondary", "endplate": "paint",
                  "rear_flap": "accent"},
    },
    "formula_fiery": {
        "display_name": "Fiery", "model_name": "Formula",
        "livery_name": "Fiery", "pattern": "fiery",
        "family": "Formula livery", "dimensions_target_m": [2.03, 4.92, 1.13],
        "paint": (0.74, 0.010, 0.018, 1),
        "secondary": (0.94, 0.90, 0.82, 1),
        "accent": (1.00, 0.60, 0.015, 1),
        "detail": (0.11, 0.012, 0.018, 1), "aero": "agile",
        "roles": {"nose": "paint", "monocoque": "paint",
                  "sidepod": "paint", "engine": "secondary",
                  "airbox": "secondary", "spear": "secondary",
                  "stripe": "accent", "fin": "secondary",
                  "rail": "paint", "headrest": "secondary",
                  "front_upper": "secondary", "endplate": "paint",
                  "rear_flap": "secondary"},
    },
    "formula_macl": {
        "display_name": "MacL", "model_name": "Formula",
        "livery_name": "MacL", "pattern": "macl",
        "family": "Formula livery", "dimensions_target_m": [2.03, 4.92, 1.13],
        "paint": (1.00, 0.25, 0.010, 1),
        "secondary": (0.008, 0.012, 0.020, 1),
        "accent": (0.025, 0.30, 0.95, 1),
        "detail": (0.92, 0.94, 0.96, 1), "aero": "agile",
        "roles": {"nose": "paint", "monocoque": "paint",
                  "sidepod": "secondary", "engine": "secondary",
                  "airbox": "paint", "spear": "accent",
                  "stripe": "accent", "fin": "paint",
                  "rail": "secondary", "headrest": "paint",
                  "front_upper": "paint", "endplate": "paint",
                  "rear_flap": "paint"},
    },
    "formula_rb": {
        "display_name": "RB", "model_name": "Formula",
        "livery_name": "RB", "pattern": "rb",
        "family": "Formula livery", "dimensions_target_m": [2.03, 4.92, 1.13],
        "paint": (0.010, 0.035, 0.16, 1),
        "secondary": (0.015, 0.16, 0.58, 1),
        "accent": (0.90, 0.008, 0.018, 1),
        "detail": (1.00, 0.60, 0.010, 1), "aero": "agile",
        "roles": {"nose": "paint", "monocoque": "paint",
                  "sidepod": "paint", "engine": "paint",
                  "airbox": "detail", "spear": "accent",
                  "stripe": "accent", "fin": "accent",
                  "rail": "paint", "headrest": "detail",
                  "front_upper": "secondary", "endplate": "paint",
                  "rear_flap": "accent"},
    },
    "formula_dash": {
        "display_name": "Dash", "model_name": "Formula",
        "livery_name": "Dash", "pattern": "dash",
        "family": "Formula livery", "dimensions_target_m": [2.03, 4.92, 1.13],
        "paint": (0.92, 0.93, 0.91, 1),
        "secondary": (0.015, 0.10, 0.54, 1),
        "accent": (0.92, 0.008, 0.020, 1),
        "detail": (0.008, 0.025, 0.11, 1), "aero": "agile",
        "roles": {"nose": "paint", "monocoque": "paint",
                  "sidepod": "secondary", "engine": "paint",
                  "airbox": "secondary", "spear": "accent",
                  "stripe": "accent", "fin": "accent",
                  "rail": "paint", "headrest": "secondary",
                  "front_upper": "paint", "endplate": "secondary",
                  "rear_flap": "paint"},
    },
}

REQUIRED = ["car_root", "body", "wheel_FL", "wheel_FR", "wheel_RL",
            "wheel_RR", "steering", "brake_lights", "driver_mount",
            "vehicle_rig", "seat_anchor"]


def ensure_outward_normals() -> None:
    """Make every closed runtime mesh opaque under back-face culling."""
    invalid = []
    for obj in asset_objects():
        if obj.type != "MESH":
            continue
        mesh = obj.data
        editable = bmesh.new()
        editable.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(editable, faces=editable.faces)
        if any(not edge.is_manifold for edge in editable.edges):
            invalid.append(f"{obj.name}: non-manifold")
        elif editable.calc_volume(signed=True) <= 0.0:
            invalid.append(f"{obj.name}: inward normals")
        editable.to_mesh(mesh)
        mesh.update()
        editable.free()
    if invalid:
        raise RuntimeError("Vehicle mesh orientation failed: " + ", ".join(invalid))


def common_materials(spec):
    slug = spec["livery_name"].lower()
    return {
        "paint": material(f"{slug}_paint", spec["paint"], metallic=0.25,
                          roughness=0.25),
        "secondary": material(f"{slug}_secondary", spec["secondary"],
                              metallic=0.20, roughness=0.27),
        "accent": material(f"{slug}_accent", spec["accent"], metallic=0.12,
                           roughness=0.30),
        "detail": material(f"{slug}_detail", spec["detail"], metallic=0.18,
                           roughness=0.26),
        "carbon": material(f"{slug}_carbon", (0.012, 0.016, 0.019, 1),
                           metallic=0.38, roughness=0.28),
        "rubber": material(f"{slug}_rubber", (0.006, 0.007, 0.008, 1),
                           roughness=0.82),
        "metal": material(f"{slug}_metal", (0.29, 0.33, 0.36, 1),
                          metallic=0.86, roughness=0.19),
        "cockpit": material(f"{slug}_cockpit", (0.014, 0.020, 0.025, 1),
                            roughness=0.58),
        "brake": material(f"{slug}_rain_light", (0.52, 0.002, 0.003, 1),
                          roughness=0.18, emission=(1, 0.002, 0.001),
                          emission_strength=7.0),
    }


def tapered_box(name, y_front, y_rear, width_front, width_rear, z_bottom,
                z_top, mat, owner, bevel=0.025):
    """Create a low-poly tapered volume with clean quad topology."""
    vertices = [
        (-width_front / 2, y_front, z_bottom),
        (width_front / 2, y_front, z_bottom),
        (width_front / 2, y_front, z_top),
        (-width_front / 2, y_front, z_top),
        (-width_rear / 2, y_rear, z_bottom),
        (width_rear / 2, y_rear, z_bottom),
        (width_rear / 2, y_rear, z_top),
        (-width_rear / 2, y_rear, z_top),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
             (3, 2, 6, 7), (0, 3, 7, 4), (1, 5, 6, 2)]
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = owner
    obj[ASSET_PROP] = True
    if bevel:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new("aero_edge", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(False)
    return obj


def vertical_fin(name, points, thickness, mat, owner):
    """Extrude a triangular profile across X for fins and wing endplates."""
    vertices = []
    for x in (-thickness / 2, thickness / 2):
        vertices.extend((x, y, z) for y, z in points)
    faces = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1),
             (1, 4, 5, 2), (2, 5, 3, 0)]
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = owner
    obj[ASSET_PROP] = True
    return obj


def aero_loft(name, sections, mat, owner, *, sides=12, bevel=0.0):
    """Loft smooth closed sections along Y for sculpted formula bodywork.

    Each section is ``(y, x_center, half_width, z_center, half_height)``.
    Keeping this primitive deterministic makes the authored Blender source
    reproducible while avoiding the toy-like stack of boxes used by the first
    vehicle pass.
    """
    vertices = []
    for y, x_center, half_width, z_center, half_height in sections:
        for index in range(sides):
            angle = math.tau * index / sides
            vertices.append((x_center + math.cos(angle) * half_width,
                             y,
                             z_center + math.sin(angle) * half_height))
    faces = []
    for ring in range(len(sections) - 1):
        start = ring * sides
        following = (ring + 1) * sides
        for index in range(sides):
            nxt = (index + 1) % sides
            faces.append((start + index, start + nxt,
                          following + nxt, following + index))
    faces.append(tuple(reversed(range(sides))))
    last = (len(sections) - 1) * sides
    faces.append(tuple(last + index for index in range(sides)))
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = owner
    obj[ASSET_PROP] = True
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    if bevel:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new("surface_finish", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.select_set(False)
    return obj


def swept_wing(name, stations, z, thickness, mat, owner, *, camber=0.0):
    """Create a swept wing plane from (x, leading_y, trailing_y) stations."""
    vertices = []
    for x, leading, trailing in stations:
        chord = trailing - leading
        vertices.extend(((x, leading, z),
                         (x, leading + chord * 0.54, z + camber),
                         (x, trailing, z),
                         (x, leading, z + thickness),
                         (x, leading + chord * 0.54,
                          z + thickness + camber),
                         (x, trailing, z + thickness)))
    faces = []
    count = len(stations)
    for station in range(count - 1):
        a, b = station * 6, (station + 1) * 6
        for offset in (0, 1):
            faces.append((a + offset, b + offset, b + offset + 1,
                          a + offset + 1))
            faces.append((a + offset + 3, a + offset + 4,
                          b + offset + 4, b + offset + 3))
        faces.extend(((a, a + 3, b + 3, b),
                      (a + 2, b + 2, b + 5, a + 5)))
    faces.extend(((0, 1, 2, 5, 4, 3),
                  tuple((count - 1) * 6 + i for i in (0, 3, 4, 5, 2, 1))))
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = owner
    obj[ASSET_PROP] = True
    bevel = obj.modifiers.new("wing_edge", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.select_set(False)
    return obj


def detail_torus(name, location, major_radius, minor_radius, mat, owner,
                 rotation=(0.0, 0.0, 0.0)):
    """A budget-friendly ring for wheel graphics viewed at game distance."""
    bpy.ops.mesh.primitive_torus_add(major_radius=major_radius,
                                     minor_radius=minor_radius,
                                     major_segments=18, minor_segments=6,
                                     location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_mesh"
    obj.data.materials.append(mat)
    obj.parent = owner
    obj[ASSET_PROP] = True
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def add_modern_agile_body(body, mats, spec):
    """Original compact formula body influenced by current rule-era proportions."""
    roles = spec["roles"]

    def livery_material(part, fallback="paint"):
        return mats[roles.get(part, fallback)]

    # A broad floor lip and central keel keep the body visually planted while
    # the raised outer edge exposes the ground-effect tunnel exits.
    tapered_box("floor", -1.66, 1.83, 0.52, 1.27, 0.105, 0.17,
                mats["carbon"], body, 0.016)
    tapered_box("floor_edge_left", -0.72, 1.62, 0.10, 0.14,
                0.13, 0.23, livery_material("stripe", "accent"),
                body, 0.012).location.x = -0.67
    tapered_box("floor_edge_right", -0.72, 1.62, 0.10, 0.14,
                0.13, 0.23, livery_material("stripe", "accent"),
                body, 0.012).location.x = 0.67
    cube("center_plank", (0, 0.03, 0.084), (0.17, 3.45, 0.028),
         mats["detail"], body, 0.006)

    # The nose droops toward the front wing and grows organically into the
    # monocoque rather than reading as a rectangular beam.
    aero_loft("needle_nose", (
        (-2.23, 0, 0.085, 0.245, 0.075),
        (-1.94, 0, 0.115, 0.285, 0.095),
        (-1.45, 0, 0.155, 0.355, 0.12),
        (-0.94, 0, 0.215, 0.445, 0.155),
        (-0.50, 0, 0.29, 0.505, 0.185),
    ), livery_material("nose"), body, sides=14, bevel=0.008)
    aero_loft("monocoque", (
        (-0.62, 0, 0.30, 0.47, 0.19),
        (-0.18, 0, 0.35, 0.50, 0.22),
        (0.44, 0, 0.37, 0.48, 0.22),
        (0.94, 0, 0.34, 0.45, 0.20),
        (1.46, 0, 0.22, 0.40, 0.15),
        (1.82, 0, 0.12, 0.36, 0.09),
    ), livery_material("monocoque"), body, sides=14, bevel=0.006)

    # A warm-white spear is the signature graphic; it is geometry, not a
    # borrowed sponsor mark, and remains legible at gameplay camera distance.
    aero_loft("nose_spear", (
        (-2.19, 0, 0.029, 0.320, 0.010),
        (-1.38, 0, 0.042, 0.466, 0.012),
        (-0.70, 0, 0.052, 0.625, 0.014),
    ), livery_material("spear", "detail"), body, sides=8)

    # Independent sidepod volumes pinch sharply beneath the inlets and taper
    # into a narrow coke-bottle tail, creating the modern high-waisted shape.
    for side in (-1, 1):
        aero_loft(f"sidepod_{side:+}", (
            (-0.53, side * 0.49, 0.235, 0.43, 0.16),
            (-0.25, side * 0.53, 0.27, 0.42, 0.18),
            (0.22, side * 0.55, 0.27, 0.40, 0.17),
            (0.74, side * 0.51, 0.24, 0.37, 0.15),
            (1.22, side * 0.40, 0.17, 0.34, 0.12),
            (1.55, side * 0.28, 0.10, 0.33, 0.08),
        ), livery_material("sidepod"), body, sides=12, bevel=0.006)
        aero_loft(f"sidepod_inlet_{side:+}", (
            (-0.58, side * 0.50, 0.22, 0.44, 0.135),
            (-0.525, side * 0.50, 0.22, 0.44, 0.135),
        ), mats["cockpit"], body, sides=12)
        # Swept aqua shoulder blade gives the car its own graphic identity.
        bar(f"sidepod_stripe_{side:+}",
            (side * 0.63, -0.26, 0.575),
            (side * 0.42, 1.15, 0.455), 0.026,
            livery_material("stripe", "accent"), body)
        vertical_fin(f"floor_fence_{side:+}",
                     ((-0.66, 0.18), (-0.24, 0.38), (-0.17, 0.18)),
                     0.025, mats["carbon"], body).location.x = side * 0.68

    # Engine cover and roll structure stay compact and leave a distinct open
    # cockpit rather than filling the cabin with bodywork.
    aero_loft("engine_cover", (
        (0.34, 0, 0.27, 0.63, 0.22),
        (0.72, 0, 0.29, 0.64, 0.24),
        (1.24, 0, 0.23, 0.56, 0.21),
        (1.72, 0, 0.12, 0.43, 0.10),
    ), livery_material("engine"), body, sides=14, bevel=0.006)
    aero_loft("airbox", (
        (0.38, 0, 0.14, 0.80, 0.13),
        (0.57, 0, 0.16, 0.84, 0.17),
        (0.83, 0, 0.11, 0.76, 0.12),
    ), livery_material("airbox", "accent"), body, sides=12)
    vertical_fin("engine_shark_fin",
                 ((0.68, 0.73), (1.64, 0.44), (1.19, 0.84)),
                 0.035, livery_material("fin", "detail"), body)

    cube("cockpit_cavity", (0, 0.03, 0.685), (0.43, 0.92, 0.19),
         mats["cockpit"], body, 0.09)
    for side in (-1, 1):
        aero_loft(f"cockpit_rail_{side:+}", (
            (-0.45, side * 0.285, 0.07, 0.675, 0.11),
            (0.05, side * 0.31, 0.075, 0.725, 0.12),
            (0.49, side * 0.27, 0.065, 0.69, 0.10),
        ), livery_material("rail"), body, sides=10)
        sphere(f"headrest_{side:+}", (side * 0.205, 0.35, 0.735),
               (0.09, 0.20, 0.09),
               livery_material("headrest", "detail"), body, 18, 10)

    # Halo follows the safety cell but uses a satin dark finish to avoid
    # visually merging with the primary livery.
    bar("halo_pillar", (0, -0.37, 0.68), (0, -0.32, 0.99),
        0.032, mats["metal"], body)
    for side in (-1, 1):
        bar(f"halo_forward_{side:+}", (0, -0.32, 0.99),
            (side * 0.27, 0.18, 0.91), 0.034, mats["metal"], body)
        bar(f"halo_rear_{side:+}", (side * 0.27, 0.18, 0.91),
            (side * 0.23, 0.51, 0.79), 0.034, mats["metal"], body)
        bar(f"mirror_stalk_{side:+}", (side * 0.30, -0.16, 0.75),
            (side * 0.53, -0.31, 0.78), 0.012, mats["carbon"], body)
        aero_loft(f"mirror_{side:+}", (
            (-0.35, side * 0.55, 0.065, 0.78, 0.042),
            (-0.24, side * 0.55, 0.065, 0.78, 0.042),
        ), livery_material("stripe", "accent"), body, sides=10)

    tapered_box("rear_diffuser", 1.43, 2.18, 0.70, 1.25,
                0.10, 0.27, mats["carbon"], body, 0.010)
    for x in (-0.48, -0.24, 0.0, 0.24, 0.48):
        cube(f"diffuser_strake_{x:+}", (x, 1.89, 0.24),
             (0.022, 0.58, 0.27), mats["carbon"], body, 0.004)

    add_livery_graphics(body, mats, spec)


def add_livery_graphics(body, mats, spec):
    """Add original, logo-free paint sweeps unique to each Formula livery."""
    pattern = spec["pattern"]
    for side in (-1, 1):
        if pattern == "marc":
            # Silver body fade, black flank and a fine aqua horizon line.
            bar(f"marc_silver_sweep_{side:+}",
                (side * 0.67, -0.18, 0.535),
                (side * 0.43, 0.98, 0.445), 0.050,
                mats["secondary"], body)
            bar(f"marc_aqua_pin_{side:+}",
                (side * 0.66, -0.28, 0.585),
                (side * 0.40, 1.24, 0.485), 0.014,
                mats["accent"], body)
        elif pattern == "fiery":
            # Dark rising sill beneath the red body and pale engine cover.
            bar(f"fiery_dark_sweep_{side:+}",
                (side * 0.68, -0.30, 0.46),
                (side * 0.39, 1.18, 0.39), 0.048,
                mats["detail"], body)
            bar(f"fiery_gold_pin_{side:+}",
                (side * 0.64, -0.22, 0.555),
                (side * 0.45, 0.88, 0.47), 0.014,
                mats["accent"], body)
        elif pattern == "macl":
            # Papaya blade cuts upward through the dark sidepod field.
            bar(f"macl_papaya_blade_{side:+}",
                (side * 0.66, -0.24, 0.55),
                (side * 0.42, 0.86, 0.43), 0.054,
                mats["paint"], body)
            bar(f"macl_blue_tick_{side:+}",
                (side * 0.61, -0.34, 0.59),
                (side * 0.51, 0.18, 0.53), 0.015,
                mats["accent"], body)
        elif pattern == "rb":
            # Red speedline with a smaller warm highlight, no bull graphic.
            bar(f"rb_red_sweep_{side:+}",
                (side * 0.67, -0.24, 0.55),
                (side * 0.40, 1.16, 0.43), 0.047,
                mats["accent"], body)
            bar(f"rb_gold_pin_{side:+}",
                (side * 0.63, -0.20, 0.59),
                (side * 0.49, 0.54, 0.52), 0.013,
                mats["detail"], body)
        else:
            # White rising wave over the cobalt flank, edged in red.
            bar(f"dash_white_wave_{side:+}",
                (side * 0.67, -0.24, 0.50),
                (side * 0.41, 1.02, 0.44), 0.056,
                mats["paint"], body)
            bar(f"dash_red_edge_{side:+}",
                (side * 0.65, -0.22, 0.565),
                (side * 0.45, 0.82, 0.49), 0.014,
                mats["accent"], body)


def add_modern_agile_wings(body, mats, spec):
    """Compact multi-element wings with an original swept planform."""
    roles = spec["roles"]
    stations = ((-1.0, -2.50, -2.15), (-0.70, -2.47, -2.10),
                (-0.30, -2.40, -2.07), (0.0, -2.37, -2.05),
                (0.30, -2.40, -2.07), (0.70, -2.47, -2.10),
                (1.0, -2.50, -2.15))
    swept_wing("front_wing_main", stations, 0.125, 0.042,
               mats["carbon"], body, camber=0.018)
    upper = tuple((x * 0.92, leading + 0.19, trailing + 0.06)
                  for x, leading, trailing in stations)
    swept_wing("front_wing_color_plane", upper, 0.205, 0.032,
               mats["accent"], body, camber=0.024)
    upper_two = tuple((x * 0.78, leading + 0.17, trailing + 0.05)
                      for x, leading, trailing in upper)
    swept_wing("front_wing_upper_flap", upper_two, 0.272, 0.028,
               mats[roles.get("front_upper", "detail")], body,
               camber=0.022)
    for side in (-1, 1):
        tapered_box(f"front_endplate_{side:+}", -2.53, -2.07,
                    0.045, 0.055, 0.11, 0.40,
                    mats[roles.get("endplate", "paint")],
                    body, 0.010).location.x = side * 0.985
        bar(f"front_wing_stay_{side:+}",
            (side * 0.11, -2.08, 0.32),
            (side * 0.26, -2.29, 0.18), 0.015, mats["carbon"], body)

    # Narrower rear wing reflects the compact visual language of the new car.
    rear_stations = ((-0.73, 2.02, 2.32), (-0.36, 1.99, 2.30),
                     (0.0, 1.98, 2.29), (0.36, 1.99, 2.30),
                     (0.73, 2.02, 2.32))
    swept_wing("rear_wing_lower", rear_stations, 0.82, 0.055,
               mats["accent"], body, camber=0.025)
    swept_wing("rear_wing_main", rear_stations, 0.94, 0.075,
               mats["carbon"], body, camber=0.042)
    swept_wing("rear_wing_flap",
               tuple((x * 0.94, leading - 0.04, trailing - 0.06)
                     for x, leading, trailing in rear_stations),
               1.035, 0.038, mats[roles.get("rear_flap", "detail")],
               body, camber=0.030)
    for side in (-1, 1):
        tapered_box(f"rear_endplate_{side:+}", 1.98, 2.34,
                    0.045, 0.055, 0.72, 1.08,
                    mats[roles.get("endplate", "paint")],
                    body, 0.010).location.x = side * 0.72
        bar(f"rear_wing_mount_{side:+}",
            (side * 0.17, 1.67, 0.37),
            (side * 0.17, 2.06, 0.84), 0.021, mats["carbon"], body)


def add_suspension(body, positions, mats, style):
    """Expose double wishbones and push rods at all four corners."""
    for corner, (x, y, z) in positions.items():
        side = math.copysign(1.0, x)
        axle = "front" if "F" in corner else "rear"
        chassis_y = y + (0.22 if axle == "front" else -0.20)
        wheel_width = 0.30 if axle == "front" else 0.38
        upright_x = x - side * (wheel_width * 0.5 + 0.015)
        if style == "agile" and axle == "front":
            # These points sit just inside the curved nose surface. The old
            # generic X=0.28 pickups floated outside this car's slender nose.
            pickups = ((chassis_y - 0.24, 0.085, 0.075),
                       (chassis_y + 0.24, 0.120, 0.130))
            lower_chassis_z, upper_chassis_z = 0.29, 0.40
            pushrod_chassis = (side * 0.06, chassis_y + 0.04, 0.45)
        elif style == "agile":
            # Rear arms attach to the sidepod/gearbox shoulder, then converge
            # onto the narrow tail for an unmistakably connected structure.
            pickups = ((chassis_y - 0.24, 0.290, 0.200),
                       (chassis_y + 0.24, 0.100, 0.100))
            lower_chassis_z, upper_chassis_z = 0.24, 0.48
            pushrod_chassis = (side * 0.18, chassis_y - 0.08, 0.59)
        else:
            pickups = ((chassis_y - 0.24, 0.280, 0.280),
                       (chassis_y + 0.24, 0.280, 0.280))
            lower_chassis_z, upper_chassis_z = 0.24, 0.48
            pushrod_chassis = (side * 0.22, chassis_y, 0.60)
        for layer, hub_z, chassis_z in (("lower", z - 0.12, 0.24),
                                       ("upper", z + 0.13, 0.48)):
            if style == "agile":
                chassis_z = (lower_chassis_z if layer == "lower"
                             else upper_chassis_z)
            x_index = 1 if layer == "lower" else 2
            for pickup_index, pickup in enumerate(pickups):
                pickup_y, pickup_x = pickup[0], pickup[x_index]
                chassis_point = (side * pickup_x, pickup_y, chassis_z)
                bar(f"{corner}_{layer}_{pickup_index}",
                    chassis_point, (upright_x, y, hub_z), 0.018,
                    mats["carbon"], body)
                if style == "agile":
                    cylinder(f"{corner}_{layer}_pickup_{pickup_index}",
                             chassis_point, 0.030, 0.050,
                             mats["metal"], body,
                             rotation=(0, math.pi / 2, 0),
                             vertices=8, bevel=0.0)
        if style == "agile":
            bar(f"{corner}_upright", (upright_x, y, z - 0.15),
                (upright_x, y, z + 0.16), 0.024, mats["metal"], body)
        bar(f"{corner}_pushrod", pushrod_chassis,
            (upright_x, y, z + 0.10), 0.014, mats["metal"], body)


def add_wings(body, style, mats):
    front_span = {"high_downforce": 2.00, "low_drag": 1.96,
                  "agile": 2.01, "retro": 2.02}[style]
    rear_span = {"high_downforce": 1.50, "low_drag": 1.38,
                 "agile": 1.46, "retro": 1.52}[style]
    rear_height = {"high_downforce": 0.93, "low_drag": 0.88,
                   "agile": 0.97, "retro": 0.92}[style]

    # Front wing planes sit above a 90 mm ground clearance and remain clearly
    # separate from the exposed front tires.
    cube("front_wing_main", (0, -2.38, 0.145),
         (front_span, 0.35, 0.065), mats["carbon"], body, 0.015)
    cube("front_wing_color_plane", (0, -2.22, 0.225),
         (front_span - 0.18, 0.17, 0.052), mats["accent"], body, 0.012)
    if style in ("high_downforce", "agile"):
        cube("front_wing_upper_flap", (0, -2.14, 0.292),
             (front_span - 0.36, 0.12, 0.045), mats["paint"], body, 0.01)
    for side in (-1, 1):
        cube(f"front_endplate_{side:+}",
             (side * (front_span / 2 - 0.022), -2.31, 0.235),
             (0.044, 0.46, 0.33), mats["detail"], body, 0.012)
        bar(f"front_wing_stay_{side:+}",
            (side * 0.11, -2.10, 0.34),
            (side * 0.32, -2.28, 0.19), 0.018, mats["carbon"], body)

    cube("rear_wing_lower", (0, 2.10, rear_height - 0.13),
         (rear_span - 0.08, 0.25, 0.075), mats["accent"], body, 0.016)
    cube("rear_wing_main", (0, 2.18, rear_height),
         (rear_span, 0.31, 0.105), mats["carbon"], body, 0.018)
    if style != "low_drag":
        cube("rear_wing_flap", (0, 2.06, rear_height + 0.085),
             (rear_span - 0.10, 0.14, 0.050), mats["paint"], body, 0.012)
    for side in (-1, 1):
        cube(f"rear_endplate_{side:+}",
             (side * (rear_span / 2 - 0.022), 2.13, rear_height - 0.11),
             (0.044, 0.46, 0.52), mats["detail"], body, 0.012)
        bar(f"rear_wing_mount_{side:+}",
            (side * 0.22, 1.70, 0.38),
            (side * 0.22, 2.08, rear_height - 0.12),
            0.025, mats["carbon"], body)


def add_formula_body(body, style, mats):
    # Flat floor and plank establish a readable ground reference without
    # visually enclosing the wheels.
    tapered_box("floor", -1.88, 1.87, 0.54, 0.82, 0.105, 0.19,
                mats["carbon"], body, 0.018)
    cube("center_plank", (0, 0.02, 0.088), (0.18, 3.55, 0.036),
         mats["detail"], body, 0.008)
    tapered_box("needle_nose", -2.29, -0.42, 0.15, 0.50, 0.21, 0.53,
                mats["paint"], body, 0.035)
    tapered_box("monocoque", -0.58, 1.28, 0.53, 0.72, 0.20, 0.66,
                mats["paint"], body, 0.055)

    # The black cavity and raised rails leave the driver visibly exposed.
    cube("cockpit_cavity", (0, 0.12, 0.69), (0.43, 1.10, 0.18),
         mats["cockpit"], body, 0.10)
    for side in (-1, 1):
        tapered_box(f"cockpit_rail_{side:+}", -0.50, 0.73,
                    0.10, 0.16, 0.58, 0.79, mats["paint"], body, 0.025).location.x = side * 0.29

    sidepod_width = {"high_downforce": 1.37, "low_drag": 1.26,
                     "agile": 1.32, "retro": 1.42}[style]
    for side in (-1, 1):
        pod = tapered_box(f"sidepod_{side:+}", -0.48, 1.22,
                          0.37, 0.53, 0.22, 0.57, mats["paint"], body, 0.045)
        pod.location.x = side * (sidepod_width / 2 - 0.23)
        cube(f"sidepod_inlet_{side:+}",
             (side * (sidepod_width / 2 - 0.22), -0.49, 0.45),
             (0.34, 0.055, 0.23), mats["carbon"], body, 0.018)
        cube(f"sidepod_stripe_{side:+}",
             (side * (sidepod_width / 2 + 0.003), 0.22, 0.56),
             (0.055, 1.25, 0.065), mats["accent"], body, 0.012)

    tapered_box("engine_cover", 0.46, 1.72, 0.54, 0.26, 0.42, 0.82,
                mats["paint"], body, 0.04)
    cube("airbox", (0, 0.52, 0.86), (0.30, 0.30, 0.27),
         mats["carbon"], body, 0.07)
    vertical_fin("engine_shark_fin", ((0.62, 0.76), (1.66, 0.52),
                                      (1.22, 0.84)), 0.055,
                 mats["accent"], body)

    # Halo: central pillar, two forward arms and the rear cockpit hoop.
    bar("halo_pillar", (0, -0.38, 0.68), (0, -0.34, 1.00),
        0.035, mats["metal"], body)
    for side in (-1, 1):
        bar(f"halo_forward_{side:+}", (0, -0.34, 1.00),
            (side * 0.28, 0.25, 0.91), 0.035, mats["metal"], body)
        bar(f"halo_rear_{side:+}", (side * 0.28, 0.25, 0.91),
            (side * 0.25, 0.58, 0.80), 0.035, mats["metal"], body)
        bar(f"mirror_stalk_{side:+}", (side * 0.29, -0.12, 0.74),
            (side * 0.53, -0.25, 0.80), 0.014, mats["carbon"], body)
        sphere(f"mirror_{side:+}", (side * 0.55, -0.26, 0.81),
               (0.12, 0.055, 0.065), mats["accent"], body, 16, 10)

    # Ventral diffuser strakes communicate formula-car ground effect from the
    # rear three-quarter game camera.
    tapered_box("rear_diffuser", 1.48, 2.22, 0.70, 1.30, 0.10, 0.25,
                mats["carbon"], body, 0.012)
    for x in (-0.48, -0.24, 0.0, 0.24, 0.48):
        cube(f"diffuser_strake_{x:+}", (x, 1.90, 0.24),
             (0.025, 0.61, 0.26), mats["carbon"], body, 0.005)

    if style == "high_downforce":
        for side in (-1, 1):
            cube(f"sidepod_vane_{side:+}", (side * 0.71, -0.34, 0.32),
                 (0.035, 0.42, 0.34), mats["accent"], body, 0.008)
            cube(f"floor_fence_{side:+}", (side * 0.62, 0.72, 0.22),
                 (0.030, 0.78, 0.18), mats["detail"], body, 0.006)
    elif style == "low_drag":
        vertical_fin("long_shark_fin", ((0.35, 0.78), (1.68, 0.54),
                                        (1.20, 0.97)), 0.04,
                     mats["detail"], body)
        cube("nose_center_stripe", (0, -1.40, 0.52),
             (0.09, 1.45, 0.035), mats["accent"], body, 0.008)
    elif style == "agile":
        for side in (-1, 1):
            cube(f"nose_canard_{side:+}", (side * 0.34, -1.69, 0.39),
                 (0.43, 0.16, 0.035), mats["detail"], body, 0.008)
            cube(f"halo_flash_{side:+}", (side * 0.29, 0.22, 0.88),
                 (0.035, 0.44, 0.065), mats["accent"], body, 0.008)
    else:
        cube("retro_nose_band", (0, -1.55, 0.49),
             (0.32, 0.19, 0.08), mats["detail"], body, 0.012)
        for side in (-1, 1):
            torus(f"sidepod_pinstripe_{side:+}",
                  (side * 0.69, 0.18, 0.43), 0.13, 0.018,
                  mats["detail"], body, rotation=(math.pi / 2, 0, 0))


def build_vehicle(slug: str):
    reset_scene()
    spec = VEHICLES[slug]
    mats = common_materials(spec)
    root = empty("car_root")
    root["asset_id"] = f"formula_forge.vehicle.{slug}"
    root["units"] = "meters"
    root["vehicle_class"] = "formula"
    body = empty("body", owner=root)
    steering = empty("steering", (0, -0.28, 0.77), root)
    brakes = empty("brake_lights", owner=root)
    # This becomes approximately (0, 0.74, -0.12) in raylib's Y-up space.
    driver_mount = empty("driver_mount", (0, 0.12, 0.74), root)

    style = spec["aero"]
    if style == "agile":
        add_modern_agile_body(body, mats, spec)
        add_modern_agile_wings(body, mats, spec)
    else:
        add_formula_body(body, style, mats)
        add_wings(body, style, mats)

    front_y = -1.60 if style != "low_drag" else -1.63
    rear_y = 1.57 if style != "retro" else 1.59
    front_x = 0.805 if style != "agile" else 0.815
    rear_x = 0.775 if style != "retro" else 0.785
    front_radius, rear_radius = 0.355, 0.365
    positions = {
        "wheel_FL": (-front_x, front_y, front_radius),
        "wheel_FR": (front_x, front_y, front_radius),
        "wheel_RL": (-rear_x, rear_y, rear_radius),
        "wheel_RR": (rear_x, rear_y, rear_radius),
    }
    wheels = {}
    for name, pos in positions.items():
        rear = name in ("wheel_RL", "wheel_RR")
        width = 0.38 if rear else 0.30
        radius = rear_radius if rear else front_radius
        pivot, _ = add_wheel(name, pos, radius, width, root,
                             mats["rubber"], mats["metal"])
        wheels[name] = pivot
        side = math.copysign(1.0, pos[0])
        if style == "agile":
            outer_face = side * width * 0.545
            cylinder(f"{name}_aero_cover", (outer_face, 0, 0),
                     radius * 0.50, 0.025, mats["carbon"], pivot,
                     rotation=(0, math.pi / 2, 0), vertices=32,
                     bevel=0.006)
            detail_torus(f"{name}_aqua_ring",
                         (outer_face + side * 0.014, 0, 0),
                         radius * 0.46, radius * 0.020,
                         mats["accent"], pivot,
                         rotation=(0, math.pi / 2, 0))
            detail_torus(f"{name}_sidewall_mark",
                         (outer_face + side * 0.018, 0, 0),
                         radius * 0.83, radius * 0.012,
                         mats["detail"], pivot,
                         rotation=(0, math.pi / 2, 0))
        cylinder(f"{name}_center_lock", (side * width * 0.55, 0, 0),
                 radius * 0.12, width * 0.08, mats["accent"], pivot,
                 rotation=(0, math.pi / 2, 0), vertices=16, bevel=0.008)
    add_suspension(body, positions, mats, style)

    torus("steering_wheel", (0, 0, 0), 0.145, 0.022,
          mats["carbon"], steering, rotation=(math.radians(68), 0, 0))
    cube("steering_display", (0, -0.015, -0.005), (0.16, 0.045, 0.10),
         mats["detail"], steering, 0.018)
    cube("rear_rain_light", (0, 2.225, 0.42), (0.16, 0.045, 0.09),
         mats["brake"], brakes, 0.012)

    # Blender's preview displays both face directions, while the runtime
    # intentionally culls back-faces. Normalize every generated shell before
    # skinning/export so opposite-side suspension cannot show through bodywork.
    ensure_outward_normals()

    bone_specs = {
        "rig_root": {"head": (0, 0, 0), "tail": (0, 0, 0.25)},
        "body_anim": {"head": (0, 0, 0.45), "tail": (0, 0, 0.78),
                      "parent": "rig_root"},
        "wheel_FL_anim": {"head": positions["wheel_FL"], "parent": "rig_root"},
        "wheel_FR_anim": {"head": positions["wheel_FR"], "parent": "rig_root"},
        "wheel_RL_anim": {"head": positions["wheel_RL"], "parent": "rig_root"},
        "wheel_RR_anim": {"head": positions["wheel_RR"], "parent": "rig_root"},
        "steering_anim": {"head": tuple(steering.location), "parent": "body_anim"},
        "brake_lights_anim": {"head": (0, 2.225, 0.42), "parent": "body_anim"},
        "seat_anchor": {"head": (0, 0.12, 0.74),
                        "tail": (0, -0.08, 0.74), "parent": "body_anim"},
    }

    def group_for_object(obj):
        # Suspension parts deliberately share the corner prefix in names such
        # as wheel_FL_lower_0. Only meshes parented beneath the actual wheel
        # pivot may inherit wheel spin or steering animation.
        current = obj
        while current:
            for wheel_name, wheel_pivot in wheels.items():
                if current == wheel_pivot:
                    return f"{wheel_name}_anim"
            if current.name == "steering":
                return "steering_anim"
            if current.name == "brake_lights":
                return "brake_lights_anim"
            current = current.parent
        return "body_anim"

    rig = build_rigid_rig("vehicle_rig", bone_specs, asset_objects(), root,
                          group_for_object)
    suspension_tokens = ("lower", "upper", "upright", "pushrod")
    suspension_meshes = [
        obj for obj in asset_objects()
        if obj.type == "MESH" and any(
            obj.name.startswith(f"{corner}_{token}")
            for corner in positions for token in suspension_tokens)
    ]
    rotating_wheel_meshes = [
        obj for obj in asset_objects()
        if obj.type == "MESH" and any(
            group.name == f"{corner}_anim" for corner in positions
            for group in obj.vertex_groups)
    ]
    wrongly_animated_suspension = [
        obj.name for obj in suspension_meshes
        if {group.name for group in obj.vertex_groups} != {"body_anim"}
    ]
    if wrongly_animated_suspension or not rotating_wheel_meshes:
        raise RuntimeError(
            "Vehicle animation isolation failed: "
            f"suspension={wrongly_animated_suspension}, "
            f"rotating_wheel_meshes={len(rotating_wheel_meshes)}"
        )
    wheel_channels = [
        {"bone": f"{name}_anim", "index": 0,
         "keys": [(1, 0), (24, -math.tau * 3.5)]}
        for name in ("wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR")
    ]
    create_rig_action(rig, "accelerate", (1, 24), wheel_channels + [
        {"bone": "body_anim", "path": "location", "index": 2,
         "keys": [(1, 0), (8, -0.010), (16, 0.006), (24, 0)]},
    ])
    create_rig_action(rig, "brake", (60, 72), [
        {"bone": "body_anim", "index": 0,
         "keys": [(60, 0), (66, math.radians(-2.2)), (72, 0)]},
        {"bone": "brake_lights_anim", "path": "scale", "index": 0,
         "keys": [(60, 1), (63, 1.28), (69, 1.28), (72, 1)]},
    ])
    for clip, sign in (("turn_left", 1), ("turn_right", -1)):
        create_rig_action(rig, clip, (30, 50), [
            {"bone": "wheel_FL_anim", "index": 2,
             "keys": [(30, 0), (40, sign * math.radians(18)), (50, 0)]},
            {"bone": "wheel_FR_anim", "index": 2,
             "keys": [(30, 0), (40, sign * math.radians(18)), (50, 0)]},
            {"bone": "steering_anim", "index": 1,
             "keys": [(30, 0), (40, sign * math.radians(48)), (50, 0)]},
            {"bone": "body_anim", "index": 1,
             "keys": [(30, 0), (40, sign * math.radians(1.2)), (50, 0)]},
        ])
    create_rig_action(rig, "idle", (80, 108), [
        {"bone": "body_anim", "path": "location", "index": 2,
         "keys": [(80, 0), (94, 0.005), (108, 0)]},
    ])

    animation_contract = {
        "wheel_only_rotation": True,
        "fixed_suspension_meshes": len(suspension_meshes),
        "rotating_wheel_meshes": len(rotating_wheel_meshes),
    }
    return spec, positions, animation_contract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", choices=["all", *VEHICLES], default="all")
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[3] / "assets" / "vehicles")
    args = parser.parse_args()
    targets = VEHICLES if args.asset == "all" else [args.asset]
    for slug in targets:
        spec, positions, animation_contract = build_vehicle(slug)
        wheelbase = abs(positions["wheel_RL"][1] - positions["wheel_FL"][1])
        metadata = {
            "type": "vehicle",
            "display_name": spec["display_name"],
            "model_name": spec["model_name"],
            "livery_name": spec["livery_name"],
            "livery_policy": "original geometry; no logos or sponsorship marks",
            "family": spec["family"],
            "vehicle_class": "formula",
            "target_dimensions_m": {"width_x": spec["dimensions_target_m"][0],
                                    "length_y": spec["dimensions_target_m"][1],
                                    "height_z": spec["dimensions_target_m"][2]},
            "hard_points_m": {
                "wheelbase": round(wheelbase, 3),
                "front_track_centers": round(abs(positions["wheel_FL"][0]) * 2, 3),
                "rear_track_centers": round(abs(positions["wheel_RL"][0]) * 2, 3),
                "ground_clearance": 0.07,
                "tire_contact_z": 0.0,
                "seat_anchor_blender": [0.0, 0.12, 0.74],
            },
            "animation_clips": {"accelerate": [1, 24], "turn_left": [30, 50],
                                "turn_right": [30, 50], "brake": [60, 72],
                                "idle": [80, 108]},
            "animation_contract": animation_contract,
            "mounts": {"driver_object": "driver_mount", "driver_bone": "seat_anchor",
                       "gltf_local_y_up_z_forward_m": [0.0, 0.74, -0.12]},
        }
        export_asset(args.output_root / slug, slug, metadata, REQUIRED,
                     (6.7, -7.9, 3.7), (0, 0, 0.58))


if __name__ == "__main__":
    main()
