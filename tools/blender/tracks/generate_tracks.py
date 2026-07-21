"""Build the five Formula Forge circuit world assets with bpy.

Run from the repository root:
    uv run python tools/blender/tracks/generate_tracks.py --track all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from pathlib import Path

import bpy
from mathutils import Vector


REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPO / "assets_src" / "tracks"
SAMPLES = 1024
RUNOFF_TRANSITION_METERS = 4.0
TERRAIN_REACH_METERS = 36.0

TRACKS = {
    "spa": {
        "display_name": "Spa-Francorchamps",
        "venue": "Circuit de Spa-Francorchamps inspired Ardennes circuit",
        "country": "Belgium",
        "source_file": "src/track_layout.hpp",
        "centerline": "kSpaControlPoints",
        "source_scale": 1.0,
        "target_length": 7004.0,
        "elevation": "kSpaElevationProfile",
        "bank_profile": "kSpaBankProfile",
        "runtime_runoff_profile": "kSpaRunoffProfile",
        "width": 13.0,
        "width_formula": "spaRoadWidthMetersForPhase",
        "turns": 19,
        "clockwise": True,
        "palette": "highland",
        "runtime_mirror_y": False,
        "cpp_layout_id": "TrackLayoutId::SpaCoast",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "suzuka": {
        "display_name": "Suzuka",
        "venue": "Suzuka International Racing Course inspired circuit",
        "country": "Japan",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kSuzukaCenterline",
        "target_length": 5807.0,
        "elevation": "kSuzukaElevation",
        "bank_profile": "kSuzukaBank",
        "runtime_runoff_profile": "kSuzukaRunoff",
        "width_profile": "kSuzukaWidth",
        "turns": 18,
        "clockwise": True,
        "palette": "japan",
        "runtime_mirror_y": True,
        "cpp_layout_id": "TrackLayoutId::Suzuka",
        "start_phase": 0.0,
        "bridge_crossing": {
            "lower_distance_m": 2315.7,
            "lower_section": "Degner to Hairpin",
            "upper_distance_m": 4660.5,
            "upper_section": "Spoon to 130R",
            "minimum_clearance_m": 10.0,
        },
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "silverstone": {
        "display_name": "Silverstone",
        "venue": "Silverstone Circuit inspired historic airfield",
        "country": "United Kingdom",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kSilverstoneCenterline",
        "target_length": 5891.0,
        "elevation": "kSilverstoneElevation",
        "bank_profile": "kSilverstoneBank",
        "runtime_runoff_profile": "kSilverstoneRunoff",
        "width_profile": "kSilverstoneWidth",
        "turns": 18,
        "clockwise": True,
        "palette": "airfield",
        "runtime_mirror_y": True,
        "cpp_layout_id": "TrackLayoutId::Silverstone",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "monza": {
        "display_name": "Monza",
        "venue": "Autodromo Nazionale Monza inspired royal parkland",
        "country": "Italy",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kMonzaCenterline",
        "target_length": 5793.0,
        "elevation": "kMonzaElevation",
        "bank_profile": "kMonzaBank",
        "runtime_runoff_profile": "kMonzaRunoff",
        "width_profile": "kMonzaWidth",
        "turns": 11,
        "clockwise": True,
        "palette": "parkland",
        "runtime_mirror_y": True,
        "cpp_layout_id": "TrackLayoutId::Monza",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "interlagos": {
        "display_name": "Interlagos",
        "venue": "Autodromo Jose Carlos Pace inspired Sao Paulo hillside",
        "country": "Brazil",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kInterlagosCenterline",
        "target_length": 4309.0,
        "elevation": "kInterlagosElevation",
        "width_profile": "kInterlagosWidth",
        "bank_profile": "kInterlagosBank",
        "runtime_runoff_profile": "kInterlagosRunoff",
        "turns": 15,
        "clockwise": False,
        "palette": "hillside",
        "runtime_mirror_y": True,
        "cpp_layout_id": "TrackLayoutId::Interlagos",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
}

PALETTES = {
    "highland": {"sand": (0.58, 0.39, 0.18, 1), "grass": (0.10, 0.26, 0.12, 1), "roof": (0.22, 0.08, 0.04, 1)},
    "japan": {"sand": (0.72, 0.49, 0.22, 1), "grass": (0.10, 0.34, 0.19, 1), "roof": (0.68, 0.045, 0.035, 1)},
    "airfield": {"sand": (0.59, 0.44, 0.25, 1), "grass": (0.18, 0.31, 0.20, 1), "roof": (0.18, 0.29, 0.36, 1)},
    "parkland": {"sand": (0.68, 0.48, 0.23, 1), "grass": (0.13, 0.34, 0.15, 1), "roof": (0.66, 0.18, 0.055, 1)},
    "hillside": {"sand": (0.64, 0.42, 0.16, 1), "grass": (0.08, 0.31, 0.15, 1), "roof": (0.82, 0.38, 0.045, 1)},
}

ASPHALT_COLOR = (0.35, 0.365, 0.38, 1)
ASPHALT_MIN_LUMINANCE = 0.32
ASPHALT_MAX_LUMINANCE = 0.42


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                   bpy.data.cameras, bpy.data.lights):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    # The pip-distributed Blender 5 bpy module exposes Eevee under this enum.
    scene.render.engine = "BLENDER_EEVEE"
    bpy.context.preferences.filepaths.save_version = 0


def mat(name: str, color, roughness=0.65, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return material


def empty(name: str, parent=None, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.parent = parent
    return obj


def mesh_object(name, vertices, faces, materials, material_indices=None, parent=None):
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.clear()
    for material in materials:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    if material_indices:
        for polygon, index in zip(mesh.polygons, material_indices):
            polygon.material_index = index
    return obj


def planar_fan(name, perimeter, material, parent):
    """Triangulate large flat layers explicitly to avoid driver-dependent n-gon seams."""
    count = len(perimeter)
    center = tuple(sum(vertex[axis] for vertex in perimeter)/count for axis in range(3))
    vertices = [center, *perimeter]
    faces = [(0,index+1,((index+1) % count)+1) for index in range(count)]
    return mesh_object(name, vertices, faces, [material], parent=parent)


def planar_ring(name, outer, inner, material, parent):
    """Build an explicit non-overlapping annulus between matching perimeters."""
    if len(outer) != len(inner):
        raise ValueError(f"{name}: ring perimeters must have matching vertex counts")
    count = len(outer)
    vertices = [*outer, *inner]
    faces = []
    for index in range(count):
        outer_next = (index+1) % count
        inner_index = count+index
        inner_next = count+outer_next
        faces.extend(((index,outer_next,inner_next),(index,inner_next,inner_index)))
    return mesh_object(name, vertices, faces, [material], parent=parent)


def cpp_pairs(path: Path, symbol: str):
    text = path.read_text(encoding="utf-8")
    start = text.index(symbol)
    equal = text.index("=", start)
    end = text.index("};", equal)
    body = text[equal:end]
    pattern = r"\{\s*(-?\d+(?:\.\d+)?)f?\s*,\s*(-?\d+(?:\.\d+)?)f?\s*\}"
    result = [(float(a), float(b)) for a, b in re.findall(pattern, body)]
    if not result:
        raise ValueError(f"No pairs parsed for {symbol} in {path}")
    return result


def cpp_runoff_zones(path: Path, symbol: str):
    text = path.read_text(encoding="utf-8")
    start = text.index(symbol)
    equal = text.index("=", start)
    end = text.index("};", equal)
    body = text[equal:end]
    number = r"(-?\d+(?:\.\d+)?)f?"
    pattern = (r"\{\s*" + number + r"\s*,\s*" + number + r"\s*,\s*(-?\d+)\s*,\s*"
               r"TrackRunoffSurface::(Asphalt|Gravel|Grass)\s*,\s*" + number + r"\s*\}")
    side_names = {-1: "right", 0: "both", 1: "left"}
    result = []
    for start_m, end_m, side, surface, width_m in re.findall(pattern, body):
        result.append({"start_m": float(start_m), "end_m": float(end_m),
                       "side": side_names[int(side)], "surface": surface.lower(),
                       "width_m": float(width_m)})
    if not result:
        raise ValueError(f"No runoff zones parsed for {symbol} in {path}")
    return result


def canonical_runoff_zones(zones):
    return [(float(zone["start_m"]), float(zone["end_m"]), zone["side"], zone["surface"],
             float(zone["width_m"])) for zone in zones]


def catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return (
        0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
               (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2 +
               (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3),
        0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
               (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2 +
               (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3),
    )


def dense_closed(points, steps=32):
    dense = []
    count = len(points)
    for i in range(count):
        for step in range(steps):
            dense.append(catmull(points[(i-1) % count], points[i], points[(i+1) % count],
                                 points[(i+2) % count], step / steps))
    return dense


def length_closed(points):
    return sum(math.dist(points[i], points[(i + 1) % len(points)]) for i in range(len(points)))


def resample_closed(points, count):
    cumulative = [0.0]
    for i in range(len(points)):
        cumulative.append(cumulative[-1] + math.dist(points[i], points[(i + 1) % len(points)]))
    total = cumulative[-1]
    result = []
    seg = 0
    for i in range(count):
        distance = total * i / count
        while cumulative[seg + 1] < distance:
            seg += 1
        span = max(1e-8, cumulative[seg + 1] - cumulative[seg])
        blend = (distance - cumulative[seg]) / span
        a, b = points[seg], points[(seg + 1) % len(points)]
        result.append((a[0] + (b[0] - a[0]) * blend,
                       a[1] + (b[1] - a[1]) * blend))
    return result


def sample_stations(stations, distance, total, fallback):
    if not stations:
        return fallback
    distance %= total
    for i in range(len(stations) - 1):
        a, b = stations[i], stations[i + 1]
        if a[0] <= distance <= b[0]:
            t = (distance - a[0]) / max(0.001, b[0] - a[0])
            return a[1] + (b[1] - a[1]) * t
    return stations[-1][1]


def load_course_design(slug):
    """Load presentation-only runoff and barrier placement for one circuit."""
    path = Path(__file__).with_name("profiles") / f"{slug}.json"
    if not path.exists():
        return {"sources": [], "runoff_zones": [], "barrier_zones": []}
    profile = json.loads(path.read_text(encoding="utf-8"))
    for key in ("sources", "runoff_zones", "barrier_zones"):
        if not isinstance(profile.get(key, []), list):
            raise ValueError(f"{path}: {key} must be an array")
    return profile


def distance_in_zone(distance, start, end, total):
    distance %= total
    start %= total
    if end == total:
        end = total
    else:
        end %= total
    return start <= distance <= end if start <= end else distance >= start or distance <= end


def side_matches(zone_side, side):
    return zone_side == "both" or zone_side == ("left" if side > 0 else "right")


def active_zone(zones, distance, side, total):
    """Return the last matching zone, allowing specific entries to override broad ones."""
    result = None
    for zone in zones:
        if side_matches(zone.get("side", "both"), side) and distance_in_zone(
                distance, float(zone["start_m"]), float(zone["end_m"]), total):
            result = zone
    return result


def bank_height(lateral, angle_degrees):
    return math.tan(math.radians(angle_degrees)) * lateral


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def runtime_track_width(phase):
    """Port trackWidthForPhase from formula_forge.cpp."""
    phase %= 1.0
    zone_width = 216.0 if phase < 0.30 or phase >= 0.90 else (190.0 if phase < 0.60 else 202.0)
    for boundary, width_a, width_b in ((0.30,216.0,190.0),(0.60,190.0,202.0),(0.90,202.0,216.0)):
        if boundary-0.034 <= phase <= boundary+0.034:
            blend = smoothstep((phase-boundary+0.034)/0.068)
            zone_width = width_a+(width_b-width_a)*blend
    return zone_width


def spa_road_width(phase):
    """Port spaRoadWidthMetersForPhase from formula_forge.cpp."""
    normalized = max(0.0,min(1.0,(runtime_track_width(phase)-190.0)/26.0))
    return 14.0+2.0*normalized


def pair_digest(pairs):
    canonical = json.dumps(pairs, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def loop_pose(samples, phase):
    count = len(samples)
    u = (phase % 1.0) * count
    index = int(math.floor(u)) % count
    blend = u-math.floor(u)
    a, b = samples[index], samples[(index+1) % count]
    position = tuple(a[axis]+(b[axis]-a[axis])*blend for axis in range(3))
    prev = samples[(index-1) % count]
    nxt = samples[(index+1) % count]
    dx,dy = nxt[0]-prev[0],nxt[1]-prev[1]
    inv = 1.0/max(0.001,math.hypot(dx,dy))
    return position, (dx*inv,dy*inv,0.0)


def make_strip(name, samples, half_widths, z_offset, material, parent, bank_angles=None):
    verts = []
    count = len(samples)
    for i, point in enumerate(samples):
        prev = samples[(i - 1) % count]
        nxt = samples[(i + 1) % count]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        inv = 1.0 / max(0.001, math.hypot(dx, dy))
        nx, ny = -dy * inv, dx * inv
        width = half_widths[i]
        bank = bank_angles[i] if bank_angles else 0.0
        verts.extend([(point[0] + nx * width, point[1] + ny * width,
                       point[2] + z_offset + bank_height(width, bank)),
                      (point[0] - nx * width, point[1] - ny * width,
                       point[2] + z_offset + bank_height(-width, bank))])
    faces = [(i*2, ((i+1) % count)*2, ((i+1) % count)*2+1, i*2+1) for i in range(count)]
    return mesh_object(name, verts, faces, [material], parent=parent)


def track_frame(samples, index):
    """Return the center point, unit tangent, and left normal at a sample."""
    count = len(samples)
    point = samples[index % count]
    prev = samples[(index - 1) % count]
    nxt = samples[(index + 1) % count]
    dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
    inv = 1.0 / max(0.001, math.hypot(dx, dy))
    tangent = (dx * inv, dy * inv)
    return point, tangent, (-tangent[1], tangent[0])


def shoulder_ground_z(point_z, half_width, lateral_distance, detail_scale,
                      bank_angle=0.0, runoff_width=4.0):
    """Road-matched terrain height shared by runoff, scenery, barriers and physics."""
    signed_lateral = lateral_distance
    lateral_distance = abs(lateral_distance)
    side = -1.0 if signed_lateral < 0.0 else 1.0
    inner_distance = half_width + runoff_width * detail_scale
    outer_distance = half_width + TERRAIN_REACH_METERS * detail_scale
    if lateral_distance <= inner_distance:
        return point_z + bank_height(signed_lateral, bank_angle)
    inner_z = point_z + bank_height(side * inner_distance, bank_angle)
    blend = smoothstep((lateral_distance - inner_distance) /
                       max(0.001, outer_distance - inner_distance))
    return inner_z + (point_z - inner_z) * blend


def make_track_limits(samples, half_widths, material, parent, detail_scale, surface_offset,
                      bank_angles):
    """Author continuous white edge lines inside both circuit boundaries."""
    vertices, faces = [], []
    line_width = 0.18 * detail_scale
    count = len(samples)
    for side in (-1, 1):
        side_start = len(vertices)
        for index, point in enumerate(samples):
            _, _, normal = track_frame(samples, index)
            outer = side * (half_widths[index] - 0.08 * detail_scale)
            inner = side * (half_widths[index] - line_width)
            bank = bank_angles[index]
            vertices.extend(((point[0] + normal[0] * outer,
                              point[1] + normal[1] * outer,
                              point[2] + surface_offset + 0.025 * detail_scale +
                              bank_height(outer, bank)),
                             (point[0] + normal[0] * inner,
                              point[1] + normal[1] * inner,
                              point[2] + surface_offset + 0.025 * detail_scale +
                              bank_height(inner, bank))))
        for index in range(count):
            base = side_start + index * 2
            next_base = side_start + ((index + 1) % count) * 2
            faces.append((base, next_base, next_base + 1, base + 1))
    return mesh_object("track_limit_lines", vertices, faces, [material], parent=parent)


def make_safety_barriers(samples, half_widths, bank_angles, barrier_offsets,
                         barrier_types, materials, parent, detail_scale):
    """Build grounded continuous concrete/Tecpro barriers and catch fencing."""
    wall_vertices, wall_faces, wall_indices = [], [], []
    fence_vertices, fence_faces = [], []
    wall_height = 1.15 * detail_scale
    wall_thickness = 0.34 * detail_scale
    fence_height = 2.70 * detail_scale
    count = len(samples)
    grounding = []
    for side in (-1, 1):
        wall_side_start = len(wall_vertices)
        for index, point in enumerate(samples):
            _, _, normal = track_frame(samples, index)
            wall_offset = barrier_offsets[side][index] * detail_scale
            lateral = half_widths[index] + wall_offset
            signed_lateral = side * lateral
            base_z = shoulder_ground_z(point[2], half_widths[index], signed_lateral,
                                        detail_scale, bank_angles[index])
            grounding.append((side, index, round(base_z, 6)))
            outer = side * (lateral + wall_thickness * 0.5)
            inner = side * (lateral - wall_thickness * 0.5)
            wall_vertices.extend(((point[0] + normal[0] * inner,
                                   point[1] + normal[1] * inner, base_z),
                                  (point[0] + normal[0] * outer,
                                   point[1] + normal[1] * outer, base_z),
                                  (point[0] + normal[0] * inner,
                                   point[1] + normal[1] * inner, base_z + wall_height),
                                  (point[0] + normal[0] * outer,
                                   point[1] + normal[1] * outer, base_z + wall_height)))
        for index in range(count):
            base = wall_side_start + index * 4
            nxt = wall_side_start + ((index + 1) % count) * 4
            wall_faces.extend(((base, nxt, nxt + 2, base + 2),
                               (base + 1, base + 3, nxt + 3, nxt + 1),
                               (base + 2, nxt + 2, nxt + 3, base + 3)))
            if barrier_types[side][index] == "tecpro":
                material_index = 2 + ((index // 10) + (1 if side > 0 else 0)) % 2
            else:
                material_index = ((index // 12) + (1 if side > 0 else 0)) % 2
            wall_indices.extend((material_index,) * 3)
        # Three uninterrupted rails read as fencing without relying on alpha blending.
        for rail in range(3):
            rail_start = len(fence_vertices)
            rail_z = wall_height + fence_height * (0.22 + rail * 0.34)
            rail_thickness = 0.10 * detail_scale
            for index, point in enumerate(samples):
                _, _, normal = track_frame(samples, index)
                wall_offset = barrier_offsets[side][index] * detail_scale
                lateral = half_widths[index] + wall_offset + wall_thickness * 0.5
                base_z = shoulder_ground_z(point[2], half_widths[index],
                                            side * (half_widths[index] + wall_offset), detail_scale,
                                            bank_angles[index])
                fence_lateral = side * lateral
                fence_vertices.extend(((point[0] + normal[0] * fence_lateral,
                                        point[1] + normal[1] * fence_lateral,
                                        base_z + rail_z - rail_thickness * 0.5),
                                       (point[0] + normal[0] * fence_lateral,
                                        point[1] + normal[1] * fence_lateral,
                                        base_z + rail_z + rail_thickness * 0.5)))
            for index in range(count):
                base = rail_start + index * 2
                nxt = rail_start + ((index + 1) % count) * 2
                fence_faces.append((base, nxt, nxt + 1, base + 1))
        for index in range(0, count, 16):
            point, tangent, normal = track_frame(samples, index)
            wall_offset = barrier_offsets[side][index] * detail_scale
            lateral = half_widths[index] + wall_offset + wall_thickness * 0.5
            base_z = shoulder_ground_z(point[2], half_widths[index],
                                        side * (half_widths[index] + wall_offset), detail_scale,
                                        bank_angles[index])
            center = (point[0] + normal[0] * side * lateral,
                      point[1] + normal[1] * side * lateral,
                      base_z + wall_height + fence_height * 0.5)
            add_oriented_box_geometry(fence_vertices, fence_faces, center,
                                      (0.14 * detail_scale, 0.14 * detail_scale, fence_height),
                                      tangent, normal)
    wall = mesh_object("continuous_safety_barriers", wall_vertices, wall_faces,
                       materials[:4], wall_indices, parent)
    fence = mesh_object("continuous_catch_fence", fence_vertices, fence_faces,
                        [materials[4]], parent=parent)
    wall["sample_count_per_side"] = count
    wall["grounding_contract"] = "shoulder_grade"
    fence["sample_count_per_side"] = count
    fence["rail_count_per_side"] = 3
    fence["post_interval_samples"] = 16
    return wall, fence, grounding


def make_curbs(samples, half_widths, bank_angles, materials, parent, curb_width=0.85):
    verts, faces, indices = [], [], []
    count = len(samples)
    for side in (-1, 1):
        for i, point in enumerate(samples):
            prev, nxt = samples[(i-1) % count], samples[(i+1) % count]
            dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
            inv = 1.0 / max(0.001, math.hypot(dx, dy))
            nx, ny = -dy * inv, dx * inv
            inner = side * half_widths[i]
            outer = side * (half_widths[i] + curb_width)
            bank = bank_angles[i]
            base = len(verts)
            verts.extend([(point[0] + nx*inner, point[1] + ny*inner,
                           point[2]+0.09+bank_height(inner, bank)),
                          (point[0] + nx*outer, point[1] + ny*outer,
                           point[2]+0.09+bank_height(outer, bank))])
            j = (i + 1) % count
            next_base = (base + 2) if i + 1 < count else (0 if side == -1 else count * 2)
            faces.append((base, next_base, next_base+1, base+1))
            indices.append((i // 2) % 2)
    return mesh_object("track_curbs", verts, faces, materials, indices, parent)


def make_surface_runoff_zones(samples, half_widths, bank_angles, zones, materials,
                              parent, target_length, surface_offset):
    """Place gravel/grass/asphalt runoff ribbons only where the circuit profile calls for them."""
    objects = []
    count = len(samples)
    for surface in ("gravel", "grass", "asphalt"):
        vertices, faces = [], []
        for side in (-1, 1):
            for index, point in enumerate(samples):
                nxt_index = (index + 1) % count
                distance = target_length * index / count
                next_distance = target_length * nxt_index / count
                zone = active_zone(zones, distance, side, target_length)
                next_zone = active_zone(zones, next_distance, side, target_length)
                if (zone is None or next_zone is None or zone.get("surface") != surface or
                        next_zone.get("surface") != surface):
                    continue
                inner = half_widths[index] + 0.95
                outer = inner + float(zone.get("width_m", 6.0))
                next_inner = half_widths[nxt_index] + 0.95
                next_outer = next_inner + float(next_zone.get("width_m", 6.0))
                _, _, normal = track_frame(samples, index)
                _, _, next_normal = track_frame(samples, nxt_index)
                signed = (side * inner, side * outer)
                next_signed = (side * next_inner, side * next_outer)
                base = len(vertices)
                vertices.extend((
                    (point[0] + normal[0] * signed[0], point[1] + normal[1] * signed[0],
                     surface_offset + 0.018 + shoulder_ground_z(
                         point[2], half_widths[index], signed[0], 1.0, bank_angles[index])),
                    (point[0] + normal[0] * signed[1], point[1] + normal[1] * signed[1],
                     surface_offset + 0.018 + shoulder_ground_z(
                         point[2], half_widths[index], signed[1], 1.0, bank_angles[index])),
                    (samples[nxt_index][0] + next_normal[0] * next_signed[1],
                     samples[nxt_index][1] + next_normal[1] * next_signed[1],
                     surface_offset + 0.018 + shoulder_ground_z(
                         samples[nxt_index][2], half_widths[nxt_index], next_signed[1], 1.0,
                         bank_angles[nxt_index])),
                    (samples[nxt_index][0] + next_normal[0] * next_signed[0],
                     samples[nxt_index][1] + next_normal[1] * next_signed[0],
                     surface_offset + 0.018 + shoulder_ground_z(
                         samples[nxt_index][2], half_widths[nxt_index], next_signed[0], 1.0,
                         bank_angles[nxt_index])),
                ))
                faces.append((base, base + 1, base + 2, base + 3))
        if faces:
            obj = mesh_object(f"{surface}_runoff_zones", vertices, faces,
                              [materials[surface]], parent=parent)
            obj["profiled_surface"] = surface
            objects.append(obj)
    return objects


def make_starting_grid_slots(samples, half_widths, bank_angles, start_phase, target_length,
                             material, parent, surface_offset, slot_count=6):
    """Author six staggered F1-style grid boxes immediately before the line."""
    vertices, faces = [], []
    count = len(samples)
    # Mirrors initializeRace(): 83.6 simulation-unit car length, 17 units/m,
    # a 1 m first-row clearance and 3 m between consecutive rows.
    car_length = 83.6 / 17.0
    first_center_inset = car_length * 0.5 + 1.0
    slot_length, slot_width, line_width, spacing = car_length + 0.68, 2.25, 0.16, car_length + 3.0

    def add_marking(center, tangent, normal, half_forward, half_lateral, z):
        base = len(vertices)
        vertices.extend((
            (center[0] - tangent[0]*half_forward - normal[0]*half_lateral,
             center[1] - tangent[1]*half_forward - normal[1]*half_lateral, z),
            (center[0] + tangent[0]*half_forward - normal[0]*half_lateral,
             center[1] + tangent[1]*half_forward - normal[1]*half_lateral, z),
            (center[0] + tangent[0]*half_forward + normal[0]*half_lateral,
             center[1] + tangent[1]*half_forward + normal[1]*half_lateral, z),
            (center[0] - tangent[0]*half_forward + normal[0]*half_lateral,
             center[1] - tangent[1]*half_forward + normal[1]*half_lateral, z),
        ))
        faces.append((base, base + 1, base + 2, base + 3))

    start_index = int(start_phase * count) % count
    for slot in range(slot_count):
        distance_behind = first_center_inset + slot * spacing
        index = int(round(start_index - distance_behind * count / target_length)) % count
        point, tangent, normal = track_frame(samples, index)
        side = -1 if slot % 2 == 0 else 1
        lane = side * min(half_widths[index] * 0.28, 2.0)
        center = (point[0] + normal[0] * lane, point[1] + normal[1] * lane)
        z = point[2] + surface_offset + 0.038 + bank_height(lane, bank_angles[index])
        # Two long and two short strokes form an open, highly legible grid box.
        for lateral in (-slot_width * 0.5, slot_width * 0.5):
            stripe_center = (center[0] + normal[0] * lateral,
                             center[1] + normal[1] * lateral)
            add_marking(stripe_center, tangent, normal, slot_length * 0.5,
                        line_width * 0.5, z + bank_height(lateral, bank_angles[index]))
        for forward in (-slot_length * 0.5, slot_length * 0.5):
            stripe_center = (center[0] + tangent[0] * forward,
                             center[1] + tangent[1] * forward)
            add_marking(stripe_center, tangent, normal, line_width * 0.5,
                        slot_width * 0.5, z)
    obj = mesh_object("starting_grid_slots", vertices, faces, [material], parent=parent)
    obj["slot_count"] = slot_count
    obj["staggered"] = True
    obj["before_start_finish"] = True
    return obj


def make_embankment(samples, half_widths, bank_angles, material, parent, detail_scale=1.0,
                    skip_indices=None):
    """Create sloped terrain shoulders from the road grade to the island datum."""
    verts, faces = [], []
    skip_indices = set(skip_indices or ())
    count = len(samples)
    for side in (-1, 1):
        side_start = len(verts)
        for i, point in enumerate(samples):
            prev, nxt = samples[(i-1) % count], samples[(i+1) % count]
            dx, dy = nxt[0]-prev[0], nxt[1]-prev[1]
            inv = 1.0/max(0.001, math.hypot(dx,dy))
            nx, ny = -dy*inv, dx*inv
            inner = side*(half_widths[i]+4.0*detail_scale)
            outer = side*(half_widths[i]+TERRAIN_REACH_METERS*detail_scale)
            inner_z = shoulder_ground_z(point[2], half_widths[i], inner, detail_scale,
                                         bank_angles[i])
            outer_z = shoulder_ground_z(point[2], half_widths[i], outer, detail_scale,
                                         bank_angles[i])
            verts.extend([(point[0]+nx*inner, point[1]+ny*inner, inner_z),
                          (point[0]+nx*outer, point[1]+ny*outer, outer_z)])
        for i in range(count):
            if i in skip_indices or (i+1) % count in skip_indices:
                continue
            base = side_start+i*2
            next_base = side_start+((i+1) % count)*2
            faces.append((base,next_base,next_base+1,base+1))
    return mesh_object("track_embankment", verts, faces, [material], parent=parent)


def find_crossover(samples):
    """Find the closest pair of course stations separated by at least 1/8 lap."""
    count = len(samples)
    best = (float("inf"), None, None)
    for first in range(count):
        for second in range(first + 1, count):
            separation = min(second-first, count-(second-first))
            if separation < count//8:
                continue
            distance = math.hypot(samples[first][0]-samples[second][0],
                                  samples[first][1]-samples[second][1])
            if distance < best[0]:
                best = (distance, first, second)
    if best[1] is None:
        raise ValueError("closed course has no non-adjacent crossover candidate")
    lower, upper = sorted((best[1], best[2]), key=lambda index: samples[index][2])
    return {"planar_distance": best[0], "lower_station": lower, "upper_station": upper}


def make_bridge_structure(samples, half_widths, bank_angles, crossing, material, parent,
                          surface_offset, detail_scale):
    """Build Suzuka's elevated crossover as an open bridge deck and side fascia."""
    upper = crossing["upper_station"]
    count = len(samples)
    half_span = 14
    stations = [(upper + offset) % count for offset in range(-half_span, half_span+1)]
    vertices, faces = [], []
    slab_depth = 0.62 * detail_scale
    for index in stations:
        point, _, normal = track_frame(samples, index)
        width = half_widths[index] + 1.35 * detail_scale
        for side in (-1, 1):
            crossfall = bank_height(side * width, bank_angles[index])
            vertices.extend(((point[0] + normal[0]*side*width,
                              point[1] + normal[1]*side*width,
                              point[2] + surface_offset + crossfall - slab_depth),
                             (point[0] + normal[0]*side*width,
                              point[1] + normal[1]*side*width,
                              point[2] + surface_offset + crossfall)))
    # Each station contributes lower/upper fascia vertices for right then left.
    for local in range(len(stations)-1):
        base, nxt = local*4, (local+1)*4
        faces.extend(((base, nxt, nxt+1, base+1),
                      (base+2, base+3, nxt+3, nxt+2),
                      (base, base+2, nxt+2, nxt),
                      (base+1, nxt+1, nxt+3, base+3)))
    obj = mesh_object("suzuka_bridge_structure", vertices, faces, [material], parent=parent)
    lower = crossing["lower_station"]
    clearance = ((samples[upper][2] + surface_offset - slab_depth) -
                 (samples[lower][2] + surface_offset))
    obj["upper_station"] = upper
    obj["lower_station"] = lower
    obj["clearance_asset_units"] = clearance
    obj["open_underpass"] = True
    return obj, clearance, stations


def add_box_geometry(verts, faces, center, size):
    x, y, z = center
    sx, sy, sz = (v * 0.5 for v in size)
    base = len(verts)
    verts.extend([(x+dx*sx, y+dy*sy, z+dz*sz)
                  for dz in (-1, 1) for dy in (-1, 1) for dx in (-1, 1)])
    faces.extend([(base+0,base+1,base+3,base+2), (base+4,base+6,base+7,base+5),
                  (base+0,base+4,base+5,base+1), (base+2,base+3,base+7,base+6),
                  (base+0,base+2,base+6,base+4), (base+1,base+5,base+7,base+3)])


def add_oriented_box_geometry(verts, faces, center, size, tangent, normal):
    """Append a box whose local X/Y axes follow a course tangent/normal."""
    x, y, z = center
    sx, sy, sz = (value * 0.5 for value in size)
    base = len(verts)
    for dz in (-1, 1):
        for dy in (-1, 1):
            for dx in (-1, 1):
                verts.append((x + tangent[0] * dx * sx + normal[0] * dy * sy,
                              y + tangent[1] * dx * sx + normal[1] * dy * sy,
                              z + dz * sz))
    faces.extend(((base+0,base+1,base+3,base+2), (base+4,base+6,base+7,base+5),
                  (base+0,base+4,base+5,base+1), (base+2,base+3,base+7,base+6),
                  (base+0,base+2,base+6,base+4), (base+1,base+5,base+7,base+3)))


def combined_palms(locations, mats, parent):
    verts, faces, face_mats = [], [], []
    sides = 8
    for x, y, z, scale in locations:
        base = len(verts)
        for level, radius in ((0, 0.38*scale), (1, 0.25*scale)):
            height = z + level * 7.0 * scale
            for i in range(sides):
                angle = math.tau * i / sides
                verts.append((x + math.cos(angle)*radius, y + math.sin(angle)*radius, height))
        for i in range(sides):
            faces.append((base+i, base+(i+1)%sides, base+sides+(i+1)%sides, base+sides+i))
            face_mats.append(0)
        crown_z = z + 7.0 * scale
        for leaf in range(7):
            angle = math.tau * leaf / 7
            direction = (math.cos(angle), math.sin(angle))
            center = (x + direction[0]*2.2*scale, y + direction[1]*2.2*scale, crown_z+0.3*scale)
            start = len(verts)
            perp = (-direction[1]*0.7*scale, direction[0]*0.7*scale)
            verts.extend([(x, y, crown_z+0.5*scale),
                          (center[0]+perp[0], center[1]+perp[1], center[2]),
                          (x+direction[0]*4.8*scale, y+direction[1]*4.8*scale, crown_z-0.8*scale),
                          (center[0]-perp[0], center[1]-perp[1], center[2])])
            faces.append((start, start+1, start+2, start+3))
            face_mats.append(1)
    return mesh_object("palm_groves", verts, faces, mats, face_mats, parent)


def combined_houses(locations, mats, parent):
    verts, faces, indices = [], [], []
    for i, (x, y, z, scale) in enumerate(locations):
        old = len(faces)
        add_box_geometry(verts, faces, (x, y, z + 2.4*scale), (7*scale, 6*scale, 4.8*scale))
        indices.extend([i % 2] * (len(faces)-old))
        # Broad roof gives huts a readable arcade silhouette from above.
        old = len(faces)
        add_box_geometry(verts, faces, (x, y, z + 5.2*scale), (8.2*scale, 7.2*scale, 1.0*scale))
        indices.extend([2] * (len(faces)-old))
    return mesh_object("coastal_houses", verts, faces, mats, indices, parent)


def combined_rocks(locations, materials, parent):
    verts, faces = [], []
    for x, y, z, scale in locations:
        base = len(verts)
        verts.extend([(x-2.5*scale,y-1.9*scale,z), (x+2.0*scale,y-2.2*scale,z),
                      (x+2.8*scale,y+1.1*scale,z), (x-1.8*scale,y+2.4*scale,z),
                      (x-1.1*scale,y-0.8*scale,z+3.1*scale), (x+1.4*scale,y+0.4*scale,z+2.5*scale)])
        faces.extend([(base,base+1,base+4), (base+1,base+5,base+4),
                      (base+1,base+2,base+5), (base+2,base+3,base+5),
                      (base+3,base+4,base+5), (base+3,base,base+4),
                      (base,base+3,base+2,base+1)])
    return mesh_object("coastal_rocks", verts, faces, materials, parent=parent)


def combined_formula_infrastructure(placements, materials, parent, detail_scale):
    """Create grounded grandstands, spectators, pit buildings and marshal posts."""
    stand_verts, stand_faces, stand_indices = [], [], []
    crowd_verts, crowd_faces, crowd_indices = [], [], []
    marshal_verts, marshal_faces, marshal_indices = [], [], []
    pit_verts, pit_faces, pit_indices = [], [], []
    for placement in placements:
        x, y, z = placement["position"]
        tangent, normal = placement["tangent"], placement["normal"]
        kind = placement["kind"]
        if kind == "grandstand":
            length = 30.0 * detail_scale
            depth = 8.0 * detail_scale
            for tier in range(4):
                old = len(stand_faces)
                tier_depth = depth / 4.0
                center = (x + normal[0] * (tier - 1.5) * tier_depth,
                          y + normal[1] * (tier - 1.5) * tier_depth,
                          z + (tier + 0.5) * 0.85 * detail_scale)
                add_oriented_box_geometry(stand_verts, stand_faces, center,
                                          (length, tier_depth, 0.85 * detail_scale),
                                          tangent, normal)
                stand_indices.extend([0] * (len(stand_faces) - old))
                for seat in range(12):
                    crowd_x = x + tangent[0] * ((seat - 5.5) * length / 13.0)
                    crowd_y = y + tangent[1] * ((seat - 5.5) * length / 13.0)
                    crowd_x += normal[0] * (tier - 1.5) * tier_depth
                    crowd_y += normal[1] * (tier - 1.5) * tier_depth
                    old = len(crowd_faces)
                    add_oriented_box_geometry(crowd_verts, crowd_faces,
                                              (crowd_x, crowd_y,
                                               z + (tier + 1.0) * 0.85 * detail_scale +
                                               0.55 * detail_scale),
                                              (0.52 * detail_scale, 0.52 * detail_scale,
                                               1.10 * detail_scale), tangent, normal)
                    crowd_indices.extend([(seat + tier) % 4] * (len(crowd_faces) - old))
            old = len(stand_faces)
            add_oriented_box_geometry(stand_verts, stand_faces,
                                      (x, y, z + 5.0 * detail_scale),
                                      (length + 2.0 * detail_scale, depth + detail_scale,
                                       0.35 * detail_scale), tangent, normal)
            stand_indices.extend([1] * (len(stand_faces) - old))
        elif kind == "marshal":
            old = len(marshal_faces)
            add_oriented_box_geometry(marshal_verts, marshal_faces,
                                      (x, y, z + 1.25 * detail_scale),
                                      (3.2 * detail_scale, 2.4 * detail_scale,
                                       2.5 * detail_scale), tangent, normal)
            marshal_indices.extend([0] * (len(marshal_faces) - old))
            old = len(marshal_faces)
            add_oriented_box_geometry(marshal_verts, marshal_faces,
                                      (x, y, z + 2.70 * detail_scale),
                                      (3.8 * detail_scale, 2.8 * detail_scale,
                                       0.40 * detail_scale), tangent, normal)
            marshal_indices.extend([1] * (len(marshal_faces) - old))
        elif kind == "pit":
            old = len(pit_faces)
            add_oriented_box_geometry(pit_verts, pit_faces,
                                      (x, y, z + 3.0 * detail_scale),
                                      (42.0 * detail_scale, 9.0 * detail_scale,
                                       6.0 * detail_scale), tangent, normal)
            pit_indices.extend([0] * (len(pit_faces) - old))
            old = len(pit_faces)
            add_oriented_box_geometry(pit_verts, pit_faces,
                                      (x, y, z + 6.35 * detail_scale),
                                      (44.0 * detail_scale, 10.0 * detail_scale,
                                       0.70 * detail_scale), tangent, normal)
            pit_indices.extend([1] * (len(pit_faces) - old))
    objects = {
        "grandstands": mesh_object("formula_grandstands", stand_verts, stand_faces,
                                    materials["stands"], stand_indices, parent),
        "spectators": mesh_object("grandstand_spectators", crowd_verts, crowd_faces,
                                   materials["crowd"], crowd_indices, parent),
        "marshal_posts": mesh_object("marshal_posts", marshal_verts, marshal_faces,
                                      materials["marshal"], marshal_indices, parent),
        "pit_buildings": mesh_object("pit_buildings", pit_verts, pit_faces,
                                      materials["pit"], pit_indices, parent),
    }
    for obj in objects.values():
        obj["grounding_contract"] = "shoulder_grade"
    return objects


def combined_park_trees(locations, materials, parent):
    verts, faces, indices = [], [], []
    sides = 7
    for x, y, z, scale in locations:
        base = len(verts)
        trunk_height = 4.0 * scale
        for level, radius in ((0, 0.35 * scale), (1, 0.24 * scale)):
            for index in range(sides):
                angle = math.tau * index / sides
                verts.append((x + math.cos(angle) * radius,
                              y + math.sin(angle) * radius,
                              z + level * trunk_height))
        for index in range(sides):
            faces.append((base + index, base + (index + 1) % sides,
                          base + sides + (index + 1) % sides, base + sides + index))
            indices.append(0)
        crown = len(verts)
        verts.extend(((x, y, z + trunk_height + 4.0 * scale),
                      (x - 2.8 * scale, y - 2.4 * scale, z + trunk_height),
                      (x + 2.8 * scale, y - 2.4 * scale, z + trunk_height),
                      (x + 2.8 * scale, y + 2.4 * scale, z + trunk_height),
                      (x - 2.8 * scale, y + 2.4 * scale, z + trunk_height)))
        faces.extend(((crown, crown+1, crown+2), (crown, crown+2, crown+3),
                      (crown, crown+3, crown+4), (crown, crown+4, crown+1),
                      (crown+1, crown+4, crown+3, crown+2)))
        indices.extend([1] * 5)
    obj = mesh_object("park_trees", verts, faces, materials, indices, parent)
    obj["grounding_contract"] = "shoulder_grade"
    return obj


def make_world(slug, spec):
    reset_scene()
    seed_index = {"spa": 1, "suzuka": 2, "silverstone": 3, "monza": 4, "interlagos": 5}[slug]
    rng = random.Random(7901 + seed_index * 101)
    palette = PALETTES[spec["palette"]]
    course_design = load_course_design(slug)
    source = REPO / spec["source_file"]
    runtime_runoff = cpp_runoff_zones(source, spec["runtime_runoff_profile"])
    if canonical_runoff_zones(runtime_runoff) != canonical_runoff_zones(course_design["runoff_zones"]):
        raise ValueError(f"{slug}: Blender and runtime runoff profiles differ")
    controls = cpp_pairs(source, spec["centerline"])
    scale = spec.get("source_scale", 1.0)
    runtime_mirror = -1.0 if spec.get("runtime_mirror_y") else 1.0
    runtime_controls = [(x * scale, y * scale * runtime_mirror) for x, y in controls]
    dense = dense_closed(runtime_controls)
    authored_length = length_closed(dense)
    target_length = spec["target_length"] or authored_length
    normalization = target_length / authored_length
    dense = [(x * normalization, y * normalization) for x, y in dense]
    runtime_center2 = resample_closed(dense, SAMPLES)
    elevations = cpp_pairs(source, spec["elevation"]) if spec.get("elevation") else []
    widths = cpp_pairs(source, spec["width_profile"]) if spec.get("width_profile") else []
    banks = cpp_pairs(source, spec["bank_profile"]) if spec.get("bank_profile") else []
    center = []
    half_widths = []
    bank_angles = []
    detail_scale = 1.0
    surface_offset = 0.06
    for i, (runtime_x, runtime_y) in enumerate(runtime_center2):
        distance = target_length * i / SAMPLES
        z = sample_stations(elevations, distance, target_length, 0.0)
        width = (spa_road_width(i/SAMPLES) if slug == "spa" else
                 sample_stations(widths, distance, target_length, spec.get("width", 13.0)))
        bank_angle = sample_stations(banks, distance, target_length, 0.0)
        # glTF Y-up conversion maps Blender (x, y, z) to (x, z, -y).
        # Negating runtime Y here therefore makes raylib GLB Z equal C++ track Y.
        # runtime_mirror_y corrects the handedness reversal introduced when the
        # Cartesian source plan is driven in raylib's Y-up XZ ground plane.
        center.append((runtime_x, -runtime_y, z))
        half_widths.append(width * 0.5)
        bank_angles.append(bank_angle)

    barrier_offsets = {-1: [], 1: []}
    barrier_types = {-1: [], 1: []}
    for side in (-1, 1):
        for index in range(SAMPLES):
            distance = target_length * index / SAMPLES
            zone = active_zone(course_design["barrier_zones"], distance, side, target_length)
            barrier_offsets[side].append(float(zone.get("offset_m", 6.0)) if zone else 6.0)
            barrier_types[side].append(zone.get("type", "concrete") if zone else "concrete")

    min_x, max_x = min(p[0] for p in center), max(p[0] for p in center)
    min_y, max_y = min(p[1] for p in center), max(p[1] for p in center)
    min_z, max_z = min(p[2] for p in center), max(p[2] for p in center)
    span_x, span_y = max_x-min_x, max_y-min_y
    cx, cy = (min_x+max_x)*0.5, (min_y+max_y)*0.5
    margin = max(180.0, min(span_x, span_y) * 0.12)
    crossing = find_crossover(center) if slug == "suzuka" else None

    materials = {
        "asphalt": mat("asphalt", ASPHALT_COLOR, 0.87),
        "shoulder": mat("runoff", (0.30, 0.33, 0.31, 1), 0.92),
        "gravel": mat("runoff_gravel", (0.52, 0.40, 0.24, 1), 0.98),
        "runoff_grass": mat("runoff_grass", palette["grass"], 0.98),
        "runoff_asphalt": mat("runoff_asphalt", (0.24, 0.255, 0.265, 1), 0.94),
        "red": mat("curb_red", (0.72, 0.035, 0.025, 1), 0.60),
        "white": mat("curb_white", (0.90, 0.88, 0.78, 1), 0.65),
        "sand": mat("terrain_verge", tuple(min(1.0, channel * 1.18) for channel in palette["grass"][:3]) + (1,), 0.98),
        "grass": mat("infield_grass", palette["grass"], 0.98),
        "water": mat("terrain_outskirts", tuple(channel * 0.62 for channel in palette["grass"][:3]) + (1,), 0.99),
        "trunk": mat("palm_trunk", (0.30, 0.13, 0.045, 1), 0.90),
        "leaf": mat("palm_fronds", (0.025, 0.29, 0.10, 1), 0.88),
        "rock": mat("coastal_stone", (0.25, 0.27, 0.25, 1), 0.96),
        "gantry": mat("gantry_metal", (0.06, 0.10, 0.12, 1), 0.35, 0.72),
        "banner": mat("start_banner", (0.94, 0.35, 0.025, 1), 0.45),
        "barrier_white": mat("barrier_white", (0.78, 0.80, 0.78, 1), 0.72),
        "barrier_red": mat("barrier_red", (0.62, 0.035, 0.025, 1), 0.68),
        "tecpro_blue": mat("tecpro_blue", (0.025, 0.16, 0.52, 1), 0.70),
        "tecpro_red": mat("tecpro_red", (0.78, 0.035, 0.025, 1), 0.70),
        "fence": mat("catch_fence", (0.17, 0.21, 0.23, 1), 0.38, 0.55),
        "stand": mat("grandstand_concrete", (0.30, 0.32, 0.32, 1), 0.86),
        "canopy": mat("grandstand_canopy", (0.82, 0.84, 0.80, 1), 0.62),
        "crowd_red": mat("spectator_red", (0.72, 0.04, 0.03, 1), 0.76),
        "crowd_blue": mat("spectator_blue", (0.04, 0.24, 0.62, 1), 0.76),
        "crowd_yellow": mat("spectator_yellow", (0.90, 0.58, 0.025, 1), 0.76),
        "crowd_white": mat("spectator_white", (0.86, 0.86, 0.81, 1), 0.76),
        "marshal_orange": mat("marshal_orange", (0.95, 0.23, 0.015, 1), 0.70),
        "marshal_roof": mat("marshal_roof", (0.12, 0.14, 0.15, 1), 0.55),
        "pit_wall": mat("pit_building_wall", (0.68, 0.70, 0.68, 1), 0.78),
        "pit_roof": mat("pit_building_roof", (0.12, 0.15, 0.16, 1), 0.48, 0.35),
        "tree_leaf": mat("tree_canopy", (0.035, 0.23, 0.075, 1), 0.90),
        "bridge": mat("bridge_concrete", (0.42, 0.44, 0.43, 1), 0.82),
    }

    root = empty("map_root")
    root["asset_id"] = f"formula_forge.track.{slug}"
    root["units"] = spec["coordinate_unit"]
    root["target_lap_length_m"] = target_length
    circuit = empty("circuit_root", root)
    terrain = empty("terrain_root", root)
    scenery = empty("scenery_root", root)

    # Nested non-overlapping inland terrain rings avoid kilometer-scale z-fighting.
    ix0, ix1, iy0, iy1 = min_x-margin, max_x+margin, min_y-margin, max_y+margin
    chamfer = min(span_x, span_y) * 0.09
    sand_z = -0.80*detail_scale
    island = [(ix0+chamfer,iy0,sand_z), (ix1-chamfer,iy0,sand_z),
              (ix1,iy0+chamfer,sand_z), (ix1,iy1-chamfer,sand_z),
              (ix1-chamfer,iy1,sand_z), (ix0+chamfer,iy1,sand_z),
              (ix0,iy1-chamfer,sand_z), (ix0,iy0+chamfer,sand_z)]
    # Slightly smaller infield defines a contrasting close-cut verge ring.
    green = [(cx+(x-cx)*0.90, cy+(y-cy)*0.90, -0.40*detail_scale) for x,y,_ in island]
    sand_inner = [(x,y,sand_z) for x,y,_ in green]
    planar_ring("terrain_verge", island, sand_inner, materials["sand"], terrain)
    planar_fan("terrain_infield", green, materials["grass"], terrain)
    outskirts_scale = 1.28
    outskirts = [(cx+(x-cx)*outskirts_scale, cy+(y-cy)*outskirts_scale, -5.0*detail_scale) for x,y,_ in island]
    outskirts_inner = [(x,y,-5.0*detail_scale) for x,y,_ in island]
    planar_ring("terrain_outskirts", outskirts, outskirts_inner, materials["water"], terrain)

    bridge_skip = set()
    if crossing:
        upper = crossing["upper_station"]
        bridge_skip = {(upper+offset) % SAMPLES for offset in range(-15,16)}
    make_embankment(center, half_widths, bank_angles, materials["grass"], terrain, detail_scale,
                    bridge_skip)
    make_strip("track_runoff", center, [w+4.0*detail_scale for w in half_widths], 0.00,
               materials["shoulder"], circuit, bank_angles)
    make_strip("track_surface", center, half_widths, surface_offset, materials["asphalt"],
               circuit, bank_angles)
    runoff_objects = make_surface_runoff_zones(
        center, half_widths, bank_angles, course_design["runoff_zones"],
        {"gravel": materials["gravel"], "grass": materials["runoff_grass"],
         "asphalt": materials["runoff_asphalt"]},
        circuit, target_length, surface_offset)
    make_curbs(center, half_widths, bank_angles, [materials["red"], materials["white"]], circuit,
               0.85*detail_scale)
    make_track_limits(center, half_widths, materials["white"], circuit, detail_scale,
                      surface_offset, bank_angles)
    _, _, barrier_grounding = make_safety_barriers(
        center, half_widths, bank_angles, barrier_offsets, barrier_types,
        [materials["barrier_white"], materials["barrier_red"],
         materials["tecpro_blue"], materials["tecpro_red"], materials["fence"]],
        circuit, detail_scale)
    bridge_clearance = None
    bridge_stations = []
    if crossing:
        _, bridge_clearance, bridge_stations = make_bridge_structure(
            center, half_widths, bank_angles, crossing, materials["bridge"], circuit,
            surface_offset, detail_scale)

    # Every prop base samples the same sloped shoulder function as track_embankment.
    palms, trees, rocks, infrastructure, grounded_instances = [], [], [], [], []
    for index in range(36):
        i = int((index + 0.37) * SAMPLES / 36) % SAMPLES
        p, tangent, normal = track_frame(center, i)
        side = -1 if index % 2 else 1
        lateral = half_widths[i] + (13.0 + rng.uniform(0, 11))*detail_scale
        base_z = shoulder_ground_z(p[2], half_widths[i], side * lateral, detail_scale,
                                    bank_angles[i])
        position = (p[0] + normal[0]*side*lateral,
                    p[1] + normal[1]*side*lateral, base_z)
        grounded_instances.append({"kind": "vegetation", "station": i, "side": side,
                                   "lateral": round(lateral, 6), "base_z": round(base_z, 6)})
        if index % 3 == 0:
            palms.append((*position, rng.uniform(0.8,1.25)*detail_scale))
        else:
            trees.append((*position, rng.uniform(0.85,1.35)*detail_scale))
        if index % 7 == 3:
            rocks.append((*position, rng.uniform(0.7,1.25)*detail_scale))

    infrastructure_schedule = {
        "grandstand": (0.08, 0.24, 0.43, 0.62, 0.82),
        "marshal": (0.03, 0.14, 0.31, 0.49, 0.70, 0.91),
        "pit": (0.965,),
    }
    for kind, phases in infrastructure_schedule.items():
        for ordinal, phase in enumerate(phases):
            i = int(phase * SAMPLES) % SAMPLES
            p, tangent, normal = track_frame(center, i)
            side = -1 if (ordinal + (0 if kind == "pit" else 1)) % 2 else 1
            extra = {"grandstand": 16.0, "marshal": 10.0, "pit": 13.0}[kind]
            lateral = half_widths[i] + extra * detail_scale
            base_z = shoulder_ground_z(p[2], half_widths[i], side * lateral, detail_scale,
                                        bank_angles[i])
            position = (p[0] + normal[0]*side*lateral,
                        p[1] + normal[1]*side*lateral, base_z)
            infrastructure.append({"kind": kind, "position": position,
                                   "tangent": tangent, "normal": normal})
            grounded_instances.append({"kind": kind, "station": i, "side": side,
                                       "lateral": round(lateral, 6),
                                       "base_z": round(base_z, 6)})
    combined_palms(palms, [materials["trunk"], materials["leaf"]], scenery)
    combined_park_trees(trees, [materials["trunk"], materials["tree_leaf"]], scenery)
    combined_rocks(rocks, [materials["rock"]], scenery)
    combined_formula_infrastructure(
        infrastructure,
        {"stands": [materials["stand"], materials["canopy"]],
         "crowd": [materials["crowd_red"], materials["crowd_blue"],
                   materials["crowd_yellow"], materials["crowd_white"]],
         "marshal": [materials["marshal_orange"], materials["marshal_roof"]],
         "pit": [materials["pit_wall"], materials["pit_roof"]]},
        scenery, detail_scale)

    # Start/finish stripe and a 20 m-wide gantry aligned to the opening centerline tangent.
    start_phase = spec["start_phase"]
    p, start_forward = loop_pose(center, start_phase)
    heading = math.atan2(start_forward[1], start_forward[0])
    gantry = empty("start_gantry", circuit, p)
    gantry.rotation_euler.z = heading
    gv, gf, gi = [], [], []
    gantry_half_span = max(10.0*detail_scale, half_widths[int(start_phase*SAMPLES)%SAMPLES]+3.0*detail_scale)
    gantry_height = 10.5*detail_scale
    for center_box, size, material_index in [
        ((0,-gantry_half_span,gantry_height*0.52),(0.55*detail_scale,0.55*detail_scale,gantry_height*1.04),0),
        ((0,gantry_half_span,gantry_height*0.52),(0.55*detail_scale,0.55*detail_scale,gantry_height*1.04),0),
        ((0,0,gantry_height),(0.75*detail_scale,gantry_half_span*2+detail_scale,0.75*detail_scale),0),
        ((0,0,gantry_height-1.3*detail_scale),(0.35*detail_scale,gantry_half_span*1.6,1.8*detail_scale),1)]:
        old = len(gf)
        add_box_geometry(gv,gf,center_box,size)
        gi.extend([material_index]*(len(gf)-old))
    mesh_object("start_gantry_mesh", gv, gf, [materials["gantry"],materials["banner"]],gi,gantry)
    # Thin white line across the asphalt.
    start_half_width = half_widths[int(start_phase*SAMPLES)%SAMPLES]
    line_verts = [(-0.8*detail_scale,-start_half_width,surface_offset+0.10*detail_scale),
                  (0.8*detail_scale,-start_half_width,surface_offset+0.10*detail_scale),
                  (0.8*detail_scale,start_half_width,surface_offset+0.10*detail_scale),
                  (-0.8*detail_scale,start_half_width,surface_offset+0.10*detail_scale)]
    line = mesh_object("start_finish_line", line_verts, [(0,1,2,3)], [materials["white"]], parent=gantry)
    make_starting_grid_slots(center, half_widths, bank_angles, start_phase, target_length,
                             materials["white"], circuit, surface_offset)

    planar = length_closed([(p[0],p[1]) for p in center])
    surface = length_closed(center)
    return {
        "target_length_m": round(target_length, 4),
        "measured_planar_centerline_m": round(planar, 4),
        "measured_surface_centerline_m": round(surface, 4),
        "control_point_count": len(controls),
        "sample_count": SAMPLES,
        "normalization_scale": round(normalization, 8),
        "road_width_min_m": round(min(w*2 for w in half_widths), 3),
        "road_width_max_m": round(max(w*2 for w in half_widths), 3),
        "bounds": [min_x-margin, max_x+margin, min_y-margin, max_y+margin, min_z, max_z],
        "center": [cx, cy, (min_z+max_z)*0.5],
        "source": spec["source_file"],
        "control_sha256": pair_digest(controls),
        "elevation_sha256": pair_digest(elevations) if elevations else None,
        "width_sha256": pair_digest(widths) if widths else None,
        "bank_sha256": pair_digest(banks) if banks else None,
        "bank_angle_min_degrees": round(min(bank_angles), 3),
        "bank_angle_max_degrees": round(max(bank_angles), 3),
        "course_design": course_design,
        "profiled_runoff_objects": [obj.name for obj in runoff_objects],
        "tecpro_samples": sum(kind == "tecpro" for side in (-1, 1)
                              for kind in barrier_types[side]),
        "start_phase": start_phase,
        "start_position_blender": [round(v, 6) for v in p],
        "start_forward_blender": [round(v, 8) for v in start_forward],
        "surface_offset": surface_offset,
        "opaque_layer_elevations": {"outskirts": -5.0*detail_scale,
                                    "verge": sand_z,
                                    "infield": -0.40*detail_scale},
        "grounded_instances": grounded_instances,
        "barrier_grounding": barrier_grounding,
        "bridge": ({"lower_station": crossing["lower_station"],
                    "upper_station": crossing["upper_station"],
                    **spec["bridge_crossing"],
                    "planar_separation_asset_units": round(crossing["planar_distance"], 6),
                    "clearance_asset_units": round(bridge_clearance, 6),
                    "embankment_open_stations": bridge_stations}
                   if crossing else None),
    }


def render_preview(path: Path, info):
    min_x,max_x,min_y,max_y,min_z,max_z = info["bounds"]
    cx,cy,cz = info["center"]
    span = max(max_x-min_x,max_y-min_y)
    bpy.ops.object.light_add(type="SUN", location=(cx-span*0.2,cy-span*0.3,max_z+span))
    sun = bpy.context.object
    sun.name = "PREVIEW_sun"
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(-35))
    bpy.ops.object.camera_add(location=(cx-span*0.72, cy-span*0.86, max_z+span*1.10))
    camera = bpy.context.object
    camera.name = "PREVIEW_camera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = span * 1.34
    camera.data.clip_start = 1.0
    camera.data.clip_end = span * 5.0
    camera.rotation_euler = (Vector((cx,cy,cz))-camera.location).to_track_quat("-Z","Y").to_euler()
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 768
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(path)
    scene.world.color = (0.018,0.045,0.075)
    scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.ops.render.render(write_still=True)


def object_bounds(objects):
    points = []
    for obj in objects:
        if obj.type == "MESH":
            points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    mins = [min(p[i] for p in points) for i in range(3)]
    maxs = [max(p[i] for p in points) for i in range(3)]
    return {"min": [round(v,3) for v in mins], "max": [round(v,3) for v in maxs],
            "dimensions": [round(maxs[i]-mins[i],3) for i in range(3)]}


def transform_bounds_blender_to_gltf(bounds):
    minimum, maximum = bounds["min"], bounds["max"]
    gltf_min = [minimum[0], minimum[2], -maximum[1]]
    gltf_max = [maximum[0], maximum[2], -minimum[1]]
    return {"min": gltf_min, "max": gltf_max,
            "dimensions": [round(gltf_max[i]-gltf_min[i],3) for i in range(3)]}


def export_track(slug, spec, output_root):
    info = make_world(slug, spec)
    output = output_root / slug
    output.mkdir(parents=True, exist_ok=True)
    asset_objects = [obj for obj in bpy.context.scene.objects if not obj.name.startswith("PREVIEW_")]
    glb = output / f"{slug}.glb"
    blend = output / f"{slug}.blend"
    preview = output / f"{slug}_preview.png"
    bpy.ops.object.select_all(action="DESELECT")
    for obj in asset_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = asset_objects[0]
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True, export_cameras=False,
                              export_lights=False, export_extras=True, export_animations=False)
    render_preview(preview, info)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    meshes = [obj for obj in asset_objects if obj.type == "MESH"]
    bounds_blender = object_bounds(asset_objects)
    bounds_gltf = transform_bounds_blender_to_gltf(bounds_blender)
    cpp_scale = spec["cpp_simulation_units_per_asset_unit"] * 0.085
    bounds_cpp_world = {
        "min": [round(v*cpp_scale,3) for v in bounds_gltf["min"]],
        "max": [round(v*cpp_scale,3) for v in bounds_gltf["max"]],
        "dimensions": [round(v*cpp_scale,3) for v in bounds_gltf["dimensions"]],
    }
    start_b = info["start_position_blender"]
    forward_b = info["start_forward_blender"]
    start_gltf = [start_b[0], start_b[2], -start_b[1]]
    forward_gltf = [forward_b[0], forward_b[2], -forward_b[1]]
    material_roles = {
        "road": "asphalt", "runoff": "runoff", "curb_primary": "curb_red",
        "curb_secondary": "curb_white", "verge": "terrain_verge",
        "infield": "infield_grass", "outskirts": "terrain_outskirts",
        "palm_trunk": "palm_trunk", "palm_fronds": "palm_fronds",
        "tree_canopy": "tree_canopy", "rocks": "coastal_stone",
        "gantry": "gantry_metal", "start_banner": "start_banner",
        "barrier_primary": "barrier_white", "barrier_secondary": "barrier_red",
        "barrier_tecpro_primary": "tecpro_blue", "barrier_tecpro_secondary": "tecpro_red",
        "catch_fence": "catch_fence", "grandstand": "grandstand_concrete",
        "grandstand_canopy": "grandstand_canopy", "spectator_red": "spectator_red",
        "spectator_blue": "spectator_blue", "spectator_yellow": "spectator_yellow",
        "spectator_white": "spectator_white", "marshal_post": "marshal_orange",
        "marshal_roof": "marshal_roof", "pit_wall": "pit_building_wall",
        "pit_roof": "pit_building_roof",
    }
    required_nodes = ["map_root", "circuit_root", "terrain_root", "scenery_root",
                      "track_surface", "track_runoff", "track_limit_lines", "track_curbs",
                      "track_embankment", "continuous_safety_barriers", "continuous_catch_fence",
                      "terrain_verge", "terrain_infield", "terrain_outskirts",
                      "palm_groves", "park_trees", "coastal_rocks",
                      "formula_grandstands", "grandstand_spectators", "marshal_posts", "pit_buildings",
                      "start_gantry", "start_finish_line", "starting_grid_slots"]
    for object_name in info["profiled_runoff_objects"]:
        required_nodes.append(object_name)
        surface = object_name.removesuffix("_runoff_zones")
        material_roles[f"runoff_{surface}"] = f"runoff_{surface}"
    if info["bridge"]:
        material_roles["bridge"] = "bridge_concrete"
        required_nodes.append("suzuka_bridge_structure")
    metadata = {
        "schema_version": 1,
        "asset": slug,
        "type": "track_world",
        "display_name": spec["display_name"],
        "venue": spec["venue"],
        "country": spec["country"],
        "units": spec["coordinate_unit"],
        "coordinate_unit": spec["coordinate_unit"],
        "axes_blender": {"right": "+X", "front": "-Y", "up": "+Z"},
        "target_lap_length": {"value": info["target_length_m"], "unit": spec["coordinate_unit"]},
        "target_lap_length_m": info["target_length_m"] if spec["coordinate_unit"] == "meter" else None,
        "measured_planar_centerline_asset_units": info["measured_planar_centerline_m"],
        "measured_surface_centerline_asset_units": info["measured_surface_centerline_m"],
        "turn_count": spec["turns"],
        "clockwise": spec["clockwise"],
        "road_width_asset_units": {"min": info["road_width_min_m"], "max": info["road_width_max_m"],
                                   "unit": spec["coordinate_unit"],
                                   "profile": spec.get("width_profile"),
                                   "formula": spec.get("width_formula")},
        "road_width_cpp_world_units": {"min": round(info["road_width_min_m"]*cpp_scale,3),
                                       "max": round(info["road_width_max_m"]*cpp_scale,3)},
        "source_centerline": {"file": info["source"], "symbol": spec["centerline"],
                              "control_points": info["control_point_count"],
                              "normalization_scale": info["normalization_scale"],
                              "control_sha256": info["control_sha256"],
                              "elevation_symbol": spec.get("elevation"),
                              "elevation_sha256": info["elevation_sha256"],
                              "width_symbol": spec.get("width_profile"),
                              "width_sha256": info["width_sha256"],
                              "bank_symbol": spec.get("bank_profile"),
                              "bank_sha256": info["bank_sha256"],
                              "catmull_rom_steps_per_control_segment": 32,
                              "closed_loop_arc_length_resampling": True},
        "bank_profile": {"min_angle_degrees": info["bank_angle_min_degrees"],
                          "max_angle_degrees": info["bank_angle_max_degrees"],
                          "sign_convention": "positive raises driver-left edge",
                          "follows_runtime_contact_plane": True},
        "course_design_profile": info["course_design"],
        "runtime_geometry": {"centerline_samples": info["sample_count"],
                             "mesh_objects": len(meshes),
                             "vertices": sum(len(obj.data.vertices) for obj in meshes),
                             "triangles": sum(len(poly.vertices)-2 for obj in meshes for poly in obj.data.polygons),
                             "materials": len({mat.name for obj in meshes for mat in obj.data.materials})},
        "measured_bounds_blender": bounds_blender,
        "measured_bounds_gltf_y_up": bounds_gltf,
        "expected_bounds_cpp_world": bounds_cpp_world,
        "runtime_alignment": {
            "cpp_layout_id": spec["cpp_layout_id"],
            "asset_origin": "C++ catalog plan origin and zero-elevation datum; not the start line",
            "blender_to_gltf_matrix_row_major": [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]],
            "gltf_and_raylib_axes": {"right": "+X", "up": "+Y", "course_plan_y": "+Z"},
            "source_plan_y_reflected": bool(spec.get("runtime_mirror_y")),
            "cpp_simulation_units_per_asset_unit": spec["cpp_simulation_units_per_asset_unit"],
            "cpp_render_scale": 0.085,
            "recommended_glb_uniform_scale": round(cpp_scale, 6),
            "recommended_world_position": [0.0,0.0,0.0],
            "recommended_yaw_degrees": 0.0,
            "mapping": "cppWorld = gltfPosition * recommended_glb_uniform_scale",
            "road_surface_offset_above_centerline_asset_units": info["surface_offset"],
            "opaque_layer_elevations_asset_units": info["opaque_layer_elevations"],
            "visual_replacement_scope": ["road", "runoff", "track_limits", "curbs", "barriers",
                                         "fencing", "terrain", "grandstands", "spectators",
                                         "marshal_posts", "pit_buildings", "props", "start_gantry",
                                         "starting_grid_slots"],
            "authoritative_runtime_system": "Track3D remains authoritative for physics, progress, elevation and width",
            "start": {"phase": info["start_phase"],
                      "position_blender": start_b, "forward_blender": forward_b,
                      "position_gltf_raylib": [round(v,6) for v in start_gltf],
                      "forward_gltf_raylib": [round(v,8) for v in forward_gltf]},
        },
        "material_roles": material_roles,
        "presentation_contract": {
            "asphalt_base_color_rgba": list(ASPHALT_COLOR),
            "asphalt_relative_luminance": round(0.2126*ASPHALT_COLOR[0] +
                                                  0.7152*ASPHALT_COLOR[1] +
                                                  0.0722*ASPHALT_COLOR[2], 6),
            "asphalt_luminance_range": [ASPHALT_MIN_LUMINANCE, ASPHALT_MAX_LUMINANCE],
            "barriers_continuous": True,
            "barrier_samples_per_side": SAMPLES,
            "tecpro_barrier_samples": info["tecpro_samples"],
            "profiled_runoff_objects": info["profiled_runoff_objects"],
            "starting_grid_slots": 6,
            "opaque_materials_only": True,
        },
        "grounding_contract": {
            "terrain_function": "shoulder_ground_z",
            "runoff_transition_asset_units": RUNOFF_TRANSITION_METERS,
            "terrain_reach_asset_units": TERRAIN_REACH_METERS,
            "outer_edge_follows_local_centerline": True,
            "tolerance_asset_units": 0.002,
            "instances": info["grounded_instances"],
            "barrier_samples": len(info["barrier_grounding"]),
            "barrier_max_authored_error": 0.0,
        },
        "bridge_contract": info["bridge"],
        "required_materials": sorted(material_roles.values()),
        "required_nodes": required_nodes,
        "source": blend.name,
        "export": glb.name,
        "preview": preview.name,
    }
    (output / f"{slug}.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    print(f"generated {slug}: target={info['target_length_m']:.1f}m "
          f"planar={info['measured_planar_centerline_m']:.1f}m meshes={len(meshes)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track", choices=["all", *TRACKS], default="all")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    targets = TRACKS if args.track == "all" else [args.track]
    for slug in targets:
        export_track(slug, TRACKS[slug], args.output_root.resolve())


if __name__ == "__main__":
    main()
