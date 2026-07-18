"""Build the six Formula Buggy coastal circuit world assets with bpy.

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

TRACKS = {
    "sunset_cove": {
        "display_name": "Sunset Cove",
        "venue": "Sunset Cove Grand Prix",
        "country": "Fictional coast",
        "source_file": "src/track_layout.hpp",
        "centerline": "kBreakwaterControlPoints",
        "source_scale": 1.5,
        "target_length": None,
        "elevation": None,
        "width": 14.0,
        "width_formula": "trackWidthForPhase * (kRoadSurfaceRatio * 2)",
        "turns": 16,
        "clockwise": True,
        "palette": "sunset",
        "cpp_layout_id": "TrackLayoutId::SunsetCove",
        "start_phase": 0.795,
        "cpp_simulation_units_per_asset_unit": 1.0,
        "coordinate_unit": "sunset_course_unit",
    },
    "spa": {
        "display_name": "Spa Coast",
        "venue": "Spa-Francorchamps inspired coastal circuit",
        "country": "Belgium",
        "source_file": "src/track_layout.hpp",
        "centerline": "kSpaControlPoints",
        "source_scale": 1.0,
        "target_length": 7004.0,
        "elevation": "kSpaElevationProfile",
        "width": 13.0,
        "width_formula": "spaRoadWidthMetersForPhase",
        "turns": 19,
        "clockwise": True,
        "palette": "highland",
        "runtime_mirror_y": True,
        "cpp_layout_id": "TrackLayoutId::SpaCoast",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "suzuka": {
        "display_name": "Suzuka",
        "venue": "Suzuka International Racing Course inspired coastal circuit",
        "country": "Japan",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kSuzukaCenterline",
        "target_length": 5807.0,
        "elevation": "kSuzukaElevation",
        "width_profile": "kSuzukaWidth",
        "turns": 18,
        "clockwise": True,
        "palette": "japan",
        "cpp_layout_id": "TrackLayoutId::Suzuka",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "silverstone": {
        "display_name": "Silverstone",
        "venue": "Silverstone Circuit inspired coastal airfield",
        "country": "United Kingdom",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kSilverstoneCenterline",
        "target_length": 5891.0,
        "elevation": "kSilverstoneElevation",
        "width_profile": "kSilverstoneWidth",
        "turns": 18,
        "clockwise": True,
        "palette": "airfield",
        "cpp_layout_id": "TrackLayoutId::Silverstone",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "monza": {
        "display_name": "Monza",
        "venue": "Autodromo Nazionale Monza inspired coastal parkland",
        "country": "Italy",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kMonzaCenterline",
        "target_length": 5793.0,
        "elevation": "kMonzaElevation",
        "width_profile": "kMonzaWidth",
        "turns": 11,
        "clockwise": True,
        "palette": "parkland",
        "cpp_layout_id": "TrackLayoutId::Monza",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
    "interlagos": {
        "display_name": "Interlagos",
        "venue": "Autodromo Jose Carlos Pace inspired coastal hillside",
        "country": "Brazil",
        "source_file": "src/track_catalog.cpp",
        "centerline": "kInterlagosCenterline",
        "target_length": 4309.0,
        "elevation": "kInterlagosElevation",
        "width_profile": "kInterlagosWidth",
        "turns": 15,
        "clockwise": False,
        "palette": "hillside",
        "cpp_layout_id": "TrackLayoutId::Interlagos",
        "start_phase": 0.0,
        "cpp_simulation_units_per_asset_unit": 17.0,
        "coordinate_unit": "meter",
    },
}

PALETTES = {
    "sunset": {"sand": (0.66, 0.36, 0.12, 1), "grass": (0.12, 0.30, 0.16, 1), "roof": (0.72, 0.12, 0.045, 1)},
    "highland": {"sand": (0.58, 0.39, 0.18, 1), "grass": (0.10, 0.26, 0.12, 1), "roof": (0.22, 0.08, 0.04, 1)},
    "japan": {"sand": (0.72, 0.49, 0.22, 1), "grass": (0.10, 0.34, 0.19, 1), "roof": (0.68, 0.045, 0.035, 1)},
    "airfield": {"sand": (0.59, 0.44, 0.25, 1), "grass": (0.18, 0.31, 0.20, 1), "roof": (0.18, 0.29, 0.36, 1)},
    "parkland": {"sand": (0.68, 0.48, 0.23, 1), "grass": (0.13, 0.34, 0.15, 1), "roof": (0.66, 0.18, 0.055, 1)},
    "hillside": {"sand": (0.64, 0.42, 0.16, 1), "grass": (0.08, 0.31, 0.15, 1), "roof": (0.82, 0.38, 0.045, 1)},
}


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


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def sunset_elevation(phase):
    """Match elevationForPhase + procedural detail in harbor_karts_3d.cpp."""
    phase %= 1.0
    stations = ((0.00,4.0),(0.20,4.0),(0.29,7.0),(0.40,20.0),(0.56,36.0),
                (0.67,34.0),(0.78,18.0),(0.89,5.0),(1.00,4.0))
    elevation = stations[-1][1]
    for a, b in zip(stations, stations[1:]):
        if a[0] <= phase <= b[0]:
            blend = smoothstep((phase-a[0])/max(0.001,b[0]-a[0]))
            elevation = a[1] + (b[1]-a[1])*blend
            break
    elevation += 0.55 * math.sin(phase * math.tau * 3.0)
    for center in (0.145, 0.735):
        distance = phase-center
        while distance > 0.5:
            distance -= 1.0
        while distance < -0.5:
            distance += 1.0
        if -0.008 <= distance < -0.001:
            elevation += 12.0*smoothstep((distance+0.008)/0.007)
        elif -0.001 <= distance <= 0.012:
            elevation += 12.0*(1.0-smoothstep((distance+0.001)/0.013))
    return elevation


def runtime_track_width(phase):
    """Port trackWidthForPhase from harbor_karts_3d.cpp."""
    phase %= 1.0
    zone_width = 216.0 if phase < 0.30 or phase >= 0.90 else (190.0 if phase < 0.60 else 202.0)
    for boundary, width_a, width_b in ((0.30,216.0,190.0),(0.60,190.0,202.0),(0.90,202.0,216.0)):
        if boundary-0.034 <= phase <= boundary+0.034:
            blend = smoothstep((phase-boundary+0.034)/0.068)
            zone_width = width_a+(width_b-width_a)*blend
    return zone_width


def sunset_road_width(phase):
    """Match the visible runtime road width: trackWidthForPhase * 0.8."""
    return runtime_track_width(phase)*0.8


def spa_road_width(phase):
    """Port spaRoadWidthMetersForPhase from harbor_karts_3d.cpp."""
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


def make_strip(name, samples, half_widths, z_offset, material, parent):
    verts = []
    count = len(samples)
    for i, point in enumerate(samples):
        prev = samples[(i - 1) % count]
        nxt = samples[(i + 1) % count]
        dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
        inv = 1.0 / max(0.001, math.hypot(dx, dy))
        nx, ny = -dy * inv, dx * inv
        width = half_widths[i]
        verts.extend([(point[0] + nx * width, point[1] + ny * width, point[2] + z_offset),
                      (point[0] - nx * width, point[1] - ny * width, point[2] + z_offset)])
    faces = [(i*2, ((i+1) % count)*2, ((i+1) % count)*2+1, i*2+1) for i in range(count)]
    return mesh_object(name, verts, faces, [material], parent=parent)


def make_curbs(samples, half_widths, materials, parent, curb_width=0.85):
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
            base = len(verts)
            verts.extend([(point[0] + nx*inner, point[1] + ny*inner, point[2]+0.09),
                          (point[0] + nx*outer, point[1] + ny*outer, point[2]+0.09)])
            j = (i + 1) % count
            next_base = (base + 2) if i + 1 < count else (0 if side == -1 else count * 2)
            faces.append((base, next_base, next_base+1, base+1))
            indices.append((i // 2) % 2)
    return mesh_object("track_curbs", verts, faces, materials, indices, parent)


def make_embankment(samples, half_widths, material, parent, detail_scale=1.0):
    """Create sloped terrain shoulders from the road grade to the island datum."""
    verts, faces = [], []
    count = len(samples)
    for side in (-1, 1):
        side_start = len(verts)
        for i, point in enumerate(samples):
            prev, nxt = samples[(i-1) % count], samples[(i+1) % count]
            dx, dy = nxt[0]-prev[0], nxt[1]-prev[1]
            inv = 1.0/max(0.001, math.hypot(dx,dy))
            nx, ny = -dy*inv, dx*inv
            inner = side*(half_widths[i]+4.0*detail_scale)
            outer = side*(half_widths[i]+30.0*detail_scale)
            inner_z = max(-0.15*detail_scale, point[2]-0.35*detail_scale)
            verts.extend([(point[0]+nx*inner, point[1]+ny*inner, inner_z),
                          (point[0]+nx*outer, point[1]+ny*outer, -0.20*detail_scale)])
        for i in range(count):
            base = side_start+i*2
            next_base = side_start+((i+1) % count)*2
            faces.append((base,next_base,next_base+1,base+1))
    return mesh_object("track_embankment", verts, faces, [material], parent=parent)


def add_box_geometry(verts, faces, center, size):
    x, y, z = center
    sx, sy, sz = (v * 0.5 for v in size)
    base = len(verts)
    verts.extend([(x+dx*sx, y+dy*sy, z+dz*sz)
                  for dz in (-1, 1) for dy in (-1, 1) for dx in (-1, 1)])
    faces.extend([(base+0,base+1,base+3,base+2), (base+4,base+6,base+7,base+5),
                  (base+0,base+4,base+5,base+1), (base+2,base+3,base+7,base+6),
                  (base+0,base+2,base+6,base+4), (base+1,base+5,base+7,base+3)])


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


def make_world(slug, spec):
    reset_scene()
    rng = random.Random(7901 + list(TRACKS).index(slug) * 101)
    palette = PALETTES[spec["palette"]]
    source = REPO / spec["source_file"]
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
    center = []
    half_widths = []
    detail_scale = 12.0 if slug == "sunset_cove" else 1.0
    surface_offset = 0.20 if slug == "sunset_cove" else 0.06
    for i, (runtime_x, runtime_y) in enumerate(runtime_center2):
        distance = target_length * i / SAMPLES
        z = (sunset_elevation(i/SAMPLES) if slug == "sunset_cove" else
             sample_stations(elevations, distance, target_length, 0.0))
        width = (sunset_road_width(i/SAMPLES) if slug == "sunset_cove" else
                 spa_road_width(i/SAMPLES) if slug == "spa" else
                 sample_stations(widths, distance, target_length, spec.get("width", 13.0)))
        # glTF Y-up conversion maps Blender (x, y, z) to (x, z, -y).
        # Negating runtime Y here therefore makes raylib GLB Z equal C++ track Y.
        center.append((runtime_x, -runtime_y, z))
        half_widths.append(width * 0.5)

    min_x, max_x = min(p[0] for p in center), max(p[0] for p in center)
    min_y, max_y = min(p[1] for p in center), max(p[1] for p in center)
    min_z, max_z = min(p[2] for p in center), max(p[2] for p in center)
    span_x, span_y = max_x-min_x, max_y-min_y
    cx, cy = (min_x+max_x)*0.5, (min_y+max_y)*0.5
    margin = max(180.0, min(span_x, span_y) * 0.12)

    materials = {
        "asphalt": mat("asphalt", (0.055, 0.062, 0.067, 1), 0.87),
        "shoulder": mat("runoff", (0.18, 0.22, 0.20, 1), 0.92),
        "red": mat("curb_red", (0.72, 0.035, 0.025, 1), 0.60),
        "white": mat("curb_white", (0.90, 0.88, 0.78, 1), 0.65),
        "sand": mat("beach_sand", palette["sand"], 0.96),
        "grass": mat("island_vegetation", palette["grass"], 0.96),
        "water": mat("ocean_water", (0.018, 0.22, 0.34, 1), 0.20, 0.12),
        "trunk": mat("palm_trunk", (0.30, 0.13, 0.045, 1), 0.90),
        "leaf": mat("palm_fronds", (0.025, 0.29, 0.10, 1), 0.88),
        "wall_a": mat("house_coral", (0.83, 0.35, 0.19, 1), 0.82),
        "wall_b": mat("house_sun", (0.89, 0.68, 0.28, 1), 0.82),
        "roof": mat("house_roof", palette["roof"], 0.72),
        "rock": mat("coastal_stone", (0.25, 0.27, 0.25, 1), 0.96),
        "gantry": mat("gantry_metal", (0.06, 0.10, 0.12, 1), 0.35, 0.72),
        "banner": mat("start_banner", (0.94, 0.35, 0.025, 1), 0.45),
    }

    root = empty("map_root")
    root["asset_id"] = f"formula_buggy.track.{slug}"
    root["units"] = spec["coordinate_unit"]
    root["target_lap_length_m"] = target_length
    circuit = empty("circuit_root", root)
    terrain = empty("terrain_root", root)
    scenery = empty("scenery_root", root)

    # Octagonal island leaves ocean visible on every side without a costly terrain grid.
    ix0, ix1, iy0, iy1 = min_x-margin, max_x+margin, min_y-margin, max_y+margin
    chamfer = min(span_x, span_y) * 0.09
    sand_z = -0.80*detail_scale
    island = [(ix0+chamfer,iy0,sand_z), (ix1-chamfer,iy0,sand_z),
              (ix1,iy0+chamfer,sand_z), (ix1,iy1-chamfer,sand_z),
              (ix1-chamfer,iy1,sand_z), (ix0+chamfer,iy1,sand_z),
              (ix0,iy1-chamfer,sand_z), (ix0,iy0+chamfer,sand_z)]
    # Slightly smaller green interior defines the inner edge of the beach ring.
    green = [(cx+(x-cx)*0.90, cy+(y-cy)*0.90, -0.40*detail_scale) for x,y,_ in island]
    sand_inner = [(x,y,sand_z) for x,y,_ in green]
    planar_ring("sand_island", island, sand_inner, materials["sand"], terrain)
    planar_fan("island_vegetation", green, materials["grass"], terrain)
    ocean_scale = 1.28
    ocean = [(cx+(x-cx)*ocean_scale, cy+(y-cy)*ocean_scale, -5.0*detail_scale) for x,y,_ in island]
    ocean_inner = [(x,y,-5.0*detail_scale) for x,y,_ in island]
    planar_ring("ocean", ocean, ocean_inner, materials["water"], terrain)

    make_embankment(center, half_widths, materials["grass"], terrain, detail_scale)
    make_strip("track_runoff", center, [w+4.0*detail_scale for w in half_widths], 0.00, materials["shoulder"], circuit)
    make_strip("track_surface", center, half_widths, surface_offset, materials["asphalt"], circuit)
    make_curbs(center, half_widths, [materials["red"], materials["white"]], circuit,
               0.85*detail_scale)

    # Place scenery well outside the road ribbon at evenly distributed course stations.
    palms, houses, rocks = [], [], []
    for index in range(30):
        i = int((index + 0.37) * SAMPLES / 30) % SAMPLES
        p, prev, nxt = center[i], center[(i-1)%SAMPLES], center[(i+1)%SAMPLES]
        dx, dy = nxt[0]-prev[0], nxt[1]-prev[1]
        inv = 1.0/max(0.001, math.hypot(dx,dy))
        nx, ny = -dy*inv, dx*inv
        side = -1 if index % 2 else 1
        setback = half_widths[i] + (14 + rng.uniform(0, 10))*detail_scale
        palms.append((p[0]+nx*side*setback, p[1]+ny*side*setback, max(0.2,p[2]),
                      rng.uniform(0.8,1.4)*detail_scale))
        if index % 5 == 1:
            houses.append((p[0]+nx*side*(setback+5*detail_scale),
                           p[1]+ny*side*(setback+5*detail_scale), max(0.2,p[2]),
                           rng.uniform(1.0,1.55)*detail_scale))
        if index % 4 == 2:
            rocks.append((p[0]-nx*side*(setback+4*detail_scale),
                          p[1]-ny*side*(setback+4*detail_scale), max(0.1,p[2]),
                          rng.uniform(0.9,1.7)*detail_scale))
    combined_palms(palms, [materials["trunk"], materials["leaf"]], scenery)
    combined_houses(houses, [materials["wall_a"], materials["wall_b"], materials["roof"]], scenery)
    combined_rocks(rocks, [materials["rock"]], scenery)

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
        "start_phase": start_phase,
        "start_position_blender": [round(v, 6) for v in p],
        "start_forward_blender": [round(v, 8) for v in start_forward],
        "surface_offset": surface_offset,
        "opaque_layer_elevations": {"ocean": -5.0*detail_scale,
                                    "sand": sand_z,
                                    "vegetation": -0.40*detail_scale,
                                    "embankment_outer": -0.20*detail_scale},
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
        "curb_secondary": "curb_white", "sand": "beach_sand",
        "vegetation": "island_vegetation", "ocean": "ocean_water",
        "palm_trunk": "palm_trunk", "palm_fronds": "palm_fronds",
        "house_primary": "house_coral", "house_secondary": "house_sun",
        "house_roof": "house_roof", "rocks": "coastal_stone",
        "gantry": "gantry_metal", "start_banner": "start_banner",
    }
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
                              "catmull_rom_steps_per_control_segment": 32,
                              "closed_loop_arc_length_resampling": True},
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
            "cpp_simulation_units_per_asset_unit": spec["cpp_simulation_units_per_asset_unit"],
            "cpp_render_scale": 0.085,
            "recommended_glb_uniform_scale": round(cpp_scale, 6),
            "recommended_world_position": [0.0,0.0,0.0],
            "recommended_yaw_degrees": 0.0,
            "mapping": "cppWorld = gltfPosition * recommended_glb_uniform_scale",
            "road_surface_offset_above_centerline_asset_units": info["surface_offset"],
            "opaque_layer_elevations_asset_units": info["opaque_layer_elevations"],
            "visual_replacement_scope": ["road", "runoff", "curbs", "terrain", "ocean", "props", "start_gantry"],
            "authoritative_runtime_system": "Track3D remains authoritative for physics, progress, elevation and width",
            "start": {"phase": info["start_phase"],
                      "position_blender": start_b, "forward_blender": forward_b,
                      "position_gltf_raylib": [round(v,6) for v in start_gltf],
                      "forward_gltf_raylib": [round(v,8) for v in forward_gltf]},
        },
        "material_roles": material_roles,
        "required_materials": sorted(material_roles.values()),
        "required_nodes": ["map_root", "circuit_root", "terrain_root", "scenery_root",
                           "track_surface", "track_runoff", "track_curbs", "track_embankment", "sand_island",
                           "ocean", "palm_groves", "coastal_houses", "coastal_rocks",
                           "start_gantry", "start_finish_line"],
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
