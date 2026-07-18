"""Build the six Formula Buggy coastal circuit world assets with bpy.

Run from the repository root:
    uv run python tools/blender/tracks/generate_tracks.py --track all
"""

from __future__ import annotations

import argparse
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
        "turns": 16,
        "clockwise": True,
        "palette": "sunset",
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
        "turns": 19,
        "clockwise": True,
        "palette": "highland",
        "mirror_y": True,
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


def make_curbs(samples, half_widths, materials, parent):
    verts, faces, indices = [], [], []
    count = len(samples)
    for side in (-1, 1):
        for i, point in enumerate(samples):
            prev, nxt = samples[(i-1) % count], samples[(i+1) % count]
            dx, dy = nxt[0] - prev[0], nxt[1] - prev[1]
            inv = 1.0 / max(0.001, math.hypot(dx, dy))
            nx, ny = -dy * inv, dx * inv
            inner = side * half_widths[i]
            outer = side * (half_widths[i] + 0.85)
            base = len(verts)
            verts.extend([(point[0] + nx*inner, point[1] + ny*inner, point[2]+0.09),
                          (point[0] + nx*outer, point[1] + ny*outer, point[2]+0.09)])
            j = (i + 1) % count
            next_base = (base + 2) if i + 1 < count else (0 if side == -1 else count * 2)
            faces.append((base, next_base, next_base+1, base+1))
            indices.append((i // 2) % 2)
    return mesh_object("track_curbs", verts, faces, materials, indices, parent)


def make_embankment(samples, half_widths, material, parent):
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
            inner = side*(half_widths[i]+4.0)
            outer = side*(half_widths[i]+30.0)
            verts.extend([(point[0]+nx*inner, point[1]+ny*inner, point[2]-0.35),
                          (point[0]+nx*outer, point[1]+ny*outer, 0.16)])
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
    mirror = -1.0 if spec.get("mirror_y") else 1.0
    controls = [(x * scale, y * scale * mirror) for x, y in controls]
    dense = dense_closed(controls)
    authored_length = length_closed(dense)
    target_length = spec["target_length"] or authored_length
    normalization = target_length / authored_length
    dense = [(x * normalization, y * normalization) for x, y in dense]
    center2 = resample_closed(dense, SAMPLES)
    elevations = cpp_pairs(source, spec["elevation"]) if spec.get("elevation") else []
    widths = cpp_pairs(source, spec["width_profile"]) if spec.get("width_profile") else []
    center = []
    half_widths = []
    for i, (x, y) in enumerate(center2):
        distance = target_length * i / SAMPLES
        z = sample_stations(elevations, distance, target_length, 0.0)
        width = sample_stations(widths, distance, target_length, spec.get("width", 13.0))
        center.append((x, y, z + 1.2))
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
    root["units"] = "meters"
    root["target_lap_length_m"] = target_length
    circuit = empty("circuit_root", root)
    terrain = empty("terrain_root", root)
    scenery = empty("scenery_root", root)

    # Octagonal island leaves ocean visible on every side without a costly terrain grid.
    ix0, ix1, iy0, iy1 = min_x-margin, max_x+margin, min_y-margin, max_y+margin
    chamfer = min(span_x, span_y) * 0.09
    island = [(ix0+chamfer,iy0,0), (ix1-chamfer,iy0,0), (ix1,iy0+chamfer,0),
              (ix1,iy1-chamfer,0), (ix1-chamfer,iy1,0), (ix0+chamfer,iy1,0),
              (ix0,iy1-chamfer,0), (ix0,iy0+chamfer,0)]
    mesh_object("sand_island", island, [tuple(range(8))], [materials["sand"]], parent=terrain)
    # Slightly smaller green interior keeps a beach band around the island.
    green = [(cx+(x-cx)*0.90, cy+(y-cy)*0.90, 0.12) for x,y,_ in island]
    mesh_object("island_vegetation", green, [tuple(range(8))], [materials["grass"]], parent=terrain)
    ocean_scale = 1.28
    ocean = [(cx+(x-cx)*ocean_scale, cy+(y-cy)*ocean_scale, -2.5) for x,y,_ in island]
    mesh_object("ocean", ocean, [tuple(range(8))], [materials["water"]], parent=terrain)

    make_embankment(center, half_widths, materials["grass"], terrain)
    make_strip("track_runoff", center, [w+4.0 for w in half_widths], 0.00, materials["shoulder"], circuit)
    make_strip("track_surface", center, half_widths, 0.06, materials["asphalt"], circuit)
    make_curbs(center, half_widths, [materials["red"], materials["white"]], circuit)

    # Place scenery well outside the road ribbon at evenly distributed course stations.
    palms, houses, rocks = [], [], []
    for index in range(30):
        i = int((index + 0.37) * SAMPLES / 30) % SAMPLES
        p, prev, nxt = center[i], center[(i-1)%SAMPLES], center[(i+1)%SAMPLES]
        dx, dy = nxt[0]-prev[0], nxt[1]-prev[1]
        inv = 1.0/max(0.001, math.hypot(dx,dy))
        nx, ny = -dy*inv, dx*inv
        side = -1 if index % 2 else 1
        setback = half_widths[i] + 14 + rng.uniform(0, 10)
        palms.append((p[0]+nx*side*setback, p[1]+ny*side*setback, max(0.2,p[2]-1.2), rng.uniform(0.8,1.4)))
        if index % 5 == 1:
            houses.append((p[0]+nx*side*(setback+5), p[1]+ny*side*(setback+5), max(0.2,p[2]-1.2), rng.uniform(1.0,1.55)))
        if index % 4 == 2:
            rocks.append((p[0]-nx*side*(setback+4), p[1]-ny*side*(setback+4), max(0.1,p[2]-1.2), rng.uniform(0.9,1.7)))
    combined_palms(palms, [materials["trunk"], materials["leaf"]], scenery)
    combined_houses(houses, [materials["wall_a"], materials["wall_b"], materials["roof"]], scenery)
    combined_rocks(rocks, [materials["rock"]], scenery)

    # Start/finish stripe and a 20 m-wide gantry aligned to the opening centerline tangent.
    p, nxt = center[0], center[1]
    heading = math.atan2(nxt[1]-p[1], nxt[0]-p[0])
    gantry = empty("start_gantry", circuit, p)
    gantry.rotation_euler.z = heading
    gv, gf, gi = [], [], []
    for center_box, size, material_index in [
        ((0,-10,5.5),(0.55,0.55,11),0), ((0,10,5.5),(0.55,0.55,11),0),
        ((0,0,10.5),(0.75,21,0.75),0), ((0,0,9.2),(0.35,16,1.8),1)]:
        old = len(gf)
        add_box_geometry(gv,gf,center_box,size)
        gi.extend([material_index]*(len(gf)-old))
    mesh_object("start_gantry_mesh", gv, gf, [materials["gantry"],materials["banner"]],gi,gantry)
    # Thin white line across the asphalt.
    line_verts = [(-0.8,-max(half_widths[0],7),0.16),(0.8,-max(half_widths[0],7),0.16),
                  (0.8,max(half_widths[0],7),0.16),(-0.8,max(half_widths[0],7),0.16)]
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
    metadata = {
        "schema_version": 1,
        "asset": slug,
        "type": "track_world",
        "display_name": spec["display_name"],
        "venue": spec["venue"],
        "country": spec["country"],
        "units": "meters",
        "axes_blender": {"right": "+X", "front": "-Y", "up": "+Z"},
        "target_lap_length_m": info["target_length_m"],
        "measured_planar_centerline_m": info["measured_planar_centerline_m"],
        "measured_surface_centerline_m": info["measured_surface_centerline_m"],
        "turn_count": spec["turns"],
        "clockwise": spec["clockwise"],
        "road_width_m": {"min": info["road_width_min_m"], "max": info["road_width_max_m"],
                         "profile": spec.get("width_profile")},
        "source_centerline": {"file": info["source"], "symbol": spec["centerline"],
                              "control_points": info["control_point_count"],
                              "normalization_scale": info["normalization_scale"]},
        "runtime_geometry": {"centerline_samples": info["sample_count"],
                             "mesh_objects": len(meshes),
                             "vertices": sum(len(obj.data.vertices) for obj in meshes),
                             "triangles": sum(len(poly.vertices)-2 for obj in meshes for poly in obj.data.polygons),
                             "materials": len({mat.name for obj in meshes for mat in obj.data.materials})},
        "measured_bounds_blender": object_bounds(asset_objects),
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
