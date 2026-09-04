"""Author the surveyed Monza scene with Blender's Python API.

uv run python tools/blender/tracks/build_monza.py --phase foundation
uv run python tools/blender/tracks/build_monza.py --phase environment --section 0
uv run python tools/blender/tracks/build_monza.py --phase render --section 0
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "assets/tracks/monza/reconstruction"
BLEND = OUT / "monza_reconstruction.blend"
SURVEY = json.loads((OUT / "survey.json").read_text())
XY = SURVEY["centerline_xy"]
N = len(XY)
L = 5793.0
STEP = L / N
TAU = math.tau
COLS = {}
MATS = {}
TANGENTS = []
NORMALS = []
CURVATURE = []
for i in range(N):
    v = Vector(XY[(i + 3) % N]) - Vector(XY[(i - 3) % N])
    v.normalize()
    TANGENTS.append(v)
    NORMALS.append(Vector((-v.y, v.x)))
for i in range(N):
    a, b = TANGENTS[(i - 6) % N], TANGENTS[(i + 6) % N]
    CURVATURE.append(math.atan2(a.x * b.y - a.y * b.x, a.dot(b)) / (12 * STEP))
TREE = KDTree(N)
for i, p in enumerate(XY):
    TREE.insert((p[0], p[1], 0), i)
TREE.balance()


def terrain(x, y):
    return 0.0022 * y + 0.10 * math.sin(x / 280) * math.sin(y / 370)


def width(s):
    anchors = [
        (0, 12),
        (400, 12),
        (610, 11),
        (710, 11),
        (1480, 11),
        (1800, 11),
        (1950, 11),
        (2160, 10.5),
        (2600, 10),
        (3100, 10.5),
        (3640, 11),
        (3900, 11),
        (4750, 11),
        (5130, 11),
        (5500, 12),
        (L, 12),
    ]
    for (a, x), (b, y) in itertools.pairwise(anchors):
        if a <= s <= b:
            t = (s - a) / (b - a)
            t = t * t * (3 - 2 * t)
            return x + (y - x) * t
    return 12


def road_z(i, offset=0):
    x, y = XY[i % N]
    crossfall = max(-0.004, min(0.004, CURVATURE[i % N] * 0.4))
    return (
        terrain(x, y)
        + 0.04
        + 0.035 * (1 - min(1, (offset / (width(i % N * STEP) / 2)) ** 2))
        - crossfall * offset
    )


def point(i, offset=0, lift=0):
    i %= N
    p = Vector(XY[i]) + NORMALS[i] * offset
    z = road_z(i, offset)
    edge = width(i * STEP) / 2
    if abs(offset) > edge + 0.35:
        t = min(1, (abs(offset) - edge - 0.35) / 2.0)
        t = t * t * (3 - 2 * t)
        edge_z = road_z(i, math.copysign(edge + 0.35, offset))
        z = edge_z * (1 - t) + (terrain(p.x, p.y) + 0.07) * t
    return (p.x, p.y, z + lift)


def station_point(s, offset=0, lift=0):
    f = (s % L) / STEP
    i = int(f)
    t = f - i
    return (
        Vector(point(i, offset, lift)).lerp(Vector(point(i + 1, offset, lift)), t),
        TANGENTS[i],
        NORMALS[i],
    )


def collection(name):
    if name not in COLS:
        c = bpy.data.collections.get(name)
        if c is None:
            c = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(c)
        COLS[name] = c
    return COLS[name]


def mesh(name, verts, faces, mat, group, indices=None):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    ob = bpy.data.objects.new(name, data)
    collection(group).objects.link(ob)
    for m in mat if isinstance(mat, list) else [mat]:
        data.materials.append(m)
    if indices:
        for p, k in zip(data.polygons, indices):
            p.material_index = k
    return ob


def material(name, color, rough=0.7, metal=0, scale=1, bump=0.03):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    m.use_fake_user = True
    nd = m.node_tree.nodes
    lk = m.node_tree.links
    bs = nd.get("Principled BSDF")
    bs.inputs["Metallic"].default_value = metal
    nd.new("ShaderNodeTexCoord")
    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 4
    # Geometry position is metres regardless of object dimensions or UV seams.
    geo = nd.new("ShaderNodeNewGeometry")
    lk.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = nd.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[0].color = (
        *(max(0, c * (0.89 if name == "Asphalt" else 0.67)) for c in color),
        1,
    )
    ramp.color_ramp.elements[1].color = (
        *(min(1, c * (1.06 if name == "Asphalt" else 1.2)) for c in color),
        1,
    )
    lk.new(noise.outputs["Fac"], ramp.inputs[0])
    lk.new(ramp.outputs[0], bs.inputs["Base Color"])
    remap = nd.new("ShaderNodeMapRange")
    remap.inputs["To Min"].default_value = max(0, rough - 0.10)
    remap.inputs["To Max"].default_value = min(1, rough + 0.12)
    lk.new(noise.outputs["Fac"], remap.inputs["Value"])
    lk.new(remap.outputs[0], bs.inputs["Roughness"])
    fine = nd.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = scale * 24
    fine.inputs["Detail"].default_value = 2
    lk.new(geo.outputs["Position"], fine.inputs["Vector"])
    bn = nd.new("ShaderNodeBump")
    bn.inputs["Strength"].default_value = 0.3
    bn.inputs["Distance"].default_value = bump
    lk.new(fine.outputs["Fac"], bn.inputs["Height"])
    lk.new(bn.outputs[0], bs.inputs["Normal"])
    MATS[name] = m
    return m


def materials():
    specs = [
        ("Asphalt", (0.075, 0.081, 0.084), 0.91, 0, 1.1, 0.006),
        ("Concrete", (0.42, 0.42, 0.39), 0.83, 0, 0.7, 0.016),
        ("White_paint", (0.74, 0.74, 0.68), 0.74, 0, 4, 0.002),
        ("Red_paint", (0.43, 0.021, 0.016), 0.71, 0, 3, 0.003),
        ("Green_paint", (0.025, 0.19, 0.07), 0.77, 0, 4, 0.003),
        ("Grass", (0.125, 0.175, 0.048), 0.94, 0, 0.14, 0.035),
        ("Gravel", (0.40, 0.33, 0.235), 0.96, 0, 4, 0.038),
        ("Armco", (0.43, 0.47, 0.48), 0.43, 0.82, 2, 0.004),
        ("Fence", (0.21, 0.23, 0.22), 0.54, 0.8, 8, 0.002),
        ("Rubber", (0.022, 0.026, 0.028), 0.96, 0, 2, 0.003),
        ("Roof", (0.49, 0.51, 0.48), 0.48, 0.38, 0.8, 0.009),
        ("Terracotta", (0.30, 0.12, 0.061), 0.78, 0, 3, 0.01),
        ("Glass", (0.052, 0.098, 0.12), 0.19, 0.55, 0.3, 0.001),
        ("Blue_seat", (0.018, 0.075, 0.22), 0.63, 0, 3, 0.004),
        ("Yellow", (0.73, 0.49, 0.023), 0.72, 0, 3, 0.004),
        ("Bark", (0.10, 0.073, 0.043), 0.97, 0, 2, 0.026),
        ("Soil", (0.09, 0.065, 0.026), 1, 0, 2, 0.02),
        ("Orange", (0.85, 0.13, 0.013), 0.72, 0, 5, 0.003),
    ]
    for args in specs:
        material(*args)
    for j, c in enumerate(
        [
            (0.062, 0.13, 0.022),
            (0.095, 0.18, 0.025),
            (0.043, 0.099, 0.018),
            (0.14, 0.19, 0.032),
            (0.11, 0.145, 0.021),
        ]
    ):
        m = material(f"Leaf_{j}", c, 0.86, 0, 5, 0.002)
        bs = m.node_tree.nodes.get("Principled BSDF")
        bs.inputs["Subsurface Weight"].default_value = 0.045


def curve(name, points, group, closed=False):
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1
    sp = data.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for v, p in zip(sp.points, points):
        v.co = (*p, 1)
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, data)
    collection(group).objects.link(ob)
    ob.hide_render = True
    ob.show_in_front = True
    ob["units"] = "metres"
    ob["editable"] = True
    return ob


def box(name, center, size, mat, group, angle=0, bevel=0):
    x, y, z = size
    a = math.cos(angle)
    b = math.sin(angle)
    vs = []
    for dz in [-z / 2, z / 2]:
        for dx, dy in [
            (-x / 2, -y / 2),
            (x / 2, -y / 2),
            (x / 2, y / 2),
            (-x / 2, y / 2),
        ]:
            vs.append(
                (
                    center[0] + a * dx - b * dy,
                    center[1] + b * dx + a * dy,
                    center[2] + dz,
                )
            )
    ob = mesh(
        name,
        vs,
        [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ],
        mat,
        group,
    )
    if bevel:
        mod = ob.modifiers.new("soft manufactured edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return ob


def strip(name, inds, left, right, mat, group="Track", lift=0, steps=1, closed=False):
    vs = []
    fs = []
    for i in inds:
        a = left(i) if callable(left) else left
        b = right(i) if callable(right) else right
        for k in range(steps + 1):
            vs.append(point(i, a + (b - a) * k / steps, lift))
    for j in range(len(inds) if closed else len(inds) - 1):
        for k in range(steps):
            a = j * (steps + 1) + k
            b = ((j + 1) % len(inds)) * (steps + 1) + k
            fs.append((a, b, b + 1, a + 1))
    ob = mesh(name, vs, fs, mat, group)
    return ob


def ribbon(name, points, w, mat, group, lift=0.08):
    vs = []
    for j, p in enumerate(points):
        a = points[max(0, j - 1)]
        b = points[min(j + 1, len(points) - 1)]
        t = Vector((b[0] - a[0], b[1] - a[1])).normalized()
        n = Vector((-t.y, t.x))
        for sign in [-1, 1]:
            x, y = p[0] + n.x * w / 2 * sign, p[1] + n.y * w / 2 * sign
            vs.append((x, y, terrain(x, y) + lift))
    return mesh(
        name,
        vs,
        [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1) for i in range(len(points) - 1)],
        mat,
        group,
    )


def camera(name, position, target, lens=28):
    d = bpy.data.cameras.new(name)
    d.lens = lens
    d.clip_end = 7000
    d.clip_start = 0.08
    ob = bpy.data.objects.new(name, d)
    collection("QA_cameras").objects.link(ob)
    ob.location = position
    ob.rotation_euler = (
        (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    )
    return ob


def save():
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1
    for c in [
        "Track",
        "Survey_curves",
        "Safety_barriers",
        "Fencing",
        "Marshal_posts",
        "Signage",
        "Grandstands",
        "Pit_buildings",
        "Bridges",
        "Service_roads",
        "Forest",
        "Distant_environment",
        "QA_cameras",
        "Asset_library",
        "Runoff",
        "Historic_oval",
    ]:
        collection(c)
    materials()
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 12
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 2
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 8
    sc.render.resolution_x = 960
    sc.render.resolution_y = 540
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    sc.world = bpy.data.worlds.new("September northern Italian daylight")
    sc.world.use_nodes = True
    wn = sc.world.node_tree.nodes
    wl = sc.world.node_tree.links
    sky = wn.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(43)
    sky.sun_rotation = math.radians(135)
    sky.altitude = 0.15
    sky.air_density = 1.1
    sky.aerosol_density = 1.8
    sky.sun_intensity = 0.65
    wl.new(sky.outputs[0], wn.get("Background").inputs[0])
    wn.get("Background").inputs[1].default_value = 0.12
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -1.3
    sc["source"] = (
        "OSM contributors / ODbL 1.0, official Monza circuit guide, FIA Monza 2025 map"
    )
    sc["survey_confidence"] = json.dumps(SURVEY["confidence"])
    sc["runtime_integration"] = (
        "Standalone environment study. Game physics and runtime assets unchanged."
    )


def foundation():
    setup()
    inds = list(range(N))
    curve(
        "CENTERLINE | 5793 m | clockwise",
        [point(i) for i in inds],
        "Survey_curves",
        True,
    )
    curve(
        "LEFT_EDGE | variable 10-12 m",
        [point(i, width(i * STEP) / 2) for i in inds],
        "Survey_curves",
        True,
    )
    curve(
        "RIGHT_EDGE | variable 10-12 m",
        [point(i, -width(i * STEP) / 2) for i in inds],
        "Survey_curves",
        True,
    )
    for f in SURVEY["features"]:
        t = f["tags"]
        if f["osm_way"] == 38168747 or t.get("highway") == "service":
            curve(
                "PIT_LANE"
                if f["osm_way"] == 38168747
                else f"SERVICE | OSM {f['osm_way']}",
                [(x, y, terrain(x, y) + 0.04) for x, y in f["points"]],
                "Survey_curves",
            )
    road = strip(
        "ASPHALT | continuous crowned surface",
        inds,
        lambda i: -width(i * STEP) / 2,
        lambda i: width(i * STEP) / 2,
        MATS["Asphalt"],
        steps=8,
        closed=True,
    )
    for p in road.data.polygons:
        p.use_smooth = True
    road["cross_section"] = (
        "35 mm crown, inferred camber <= 0.4 percent; 0.75 m longitudinal sampling"
    )
    for sign, side in [(1, "L"), (-1, "R")]:
        strip(
            f"{side} continuous 150 mm edge line",
            inds,
            lambda i, sign=sign: sign * (width(i * STEP) / 2 - 0.22),
            lambda i, sign=sign: sign * (width(i * STEP) / 2 - 0.07),
            MATS["White_paint"],
            lift=0.007,
            closed=True,
        )
        strip(
            f"{side} drainage concrete",
            inds,
            lambda i, sign=sign: sign * (width(i * STEP) / 2),
            lambda i, sign=sign: sign * (width(i * STEP) / 2 + 0.35),
            MATS["Concrete"],
            lift=-0.017,
            closed=True,
        )
        strip(
            f"{side} grass verge",
            inds,
            lambda i, sign=sign: sign * (width(i * STEP) / 2 + 0.35),
            lambda i, sign=sign: sign * (width(i * STEP) / 2 + 2),
            MATS["Grass"],
            lift=-0.035,
            steps=2,
            closed=True,
        )
    # Broad continuous terrain, all road/structure grounding uses this same height function.
    vs = []
    fs = []
    nx = 112
    ny = 160
    for j in range(ny):
        for i in range(nx):
            x = -650 + i * 22
            y = -1300 + j * 22
            vs.append((x, y, terrain(x, y)))
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            fs.append((a, a + 1, a + nx + 1, a + nx))
    mesh("Park ground", vs, fs, MATS["Grass"], "Distant_environment")
    pit = next(f for f in SURVEY["features"] if f["osm_way"] == 38168747)
    ribbon(
        "Pit lane | mapped entry and exit",
        pit["points"],
        8.0,
        MATS["Asphalt"],
        "Track",
        0.04,
    )
    for side in [-1, 1]:
        # Edges derive from the same pit spline, keeping the entry/exit editable.
        ps = []
        for i, p in enumerate(pit["points"]):
            a = pit["points"][max(0, i - 1)]
            b = pit["points"][min(len(pit["points"]) - 1, i + 1)]
            v = Vector((b[0] - a[0], b[1] - a[1])).normalized()
            ps.append((p[0] - v.y * side * 3.7, p[1] + v.x * side * 3.7))
        ribbon(f"Pit edge {side}", ps, 0.12, MATS["White_paint"], "Track", 0.051)
    driver_stations = [L - 280, 570, 1010, 1775, 2165, 2500, 3190, 3570, 4140, 4790]
    for index, section in enumerate(SURVEY["sections"]):
        s = driver_stations[index]
        p, t, _n = station_point(s, 0, 1.2)
        target = station_point(s + 28)[0]
        camera("DRIVER | " + section["name"], p, target + Vector((0, 0, 1.2)), 28)
        mid = L - 140 if index == 0 else (section["start_m"] + section["end_m"]) / 2
        cp, ct, cn = station_point(mid)
        camera(
            "ELEVATED | " + section["name"],
            cp + Vector((cn.x * 180 - ct.x * 160, cn.y * 180 - ct.y * 160, 180)),
            cp,
            38,
        )
    overview = camera(
        "OVERVIEW | whole circuit", (1900, -1900, 2550), (480, 380, 0), 43
    )
    bpy.context.scene.camera = overview
    # Foundation diagnostics are completed before environment work is allowed.
    length = sum((Vector(point(i + 1)) - Vector(point(i))).length for i in range(N))
    stats = []
    for section in SURVEY["sections"]:
        a = int(section["start_m"] / STEP)
        b = min(N, int(section["end_m"] / STEP))
        ks = CURVATURE[a:b]
        zs = [point(i)[2] for i in range(a, b)]
        stats.append(
            {
                **section,
                "length_m": section["end_m"] - section["start_m"],
                "heading_change_deg": math.degrees(sum(ks) * STEP),
                "minimum_radius_m": 1 / max(abs(k) for k in ks),
                "width_min_m": min(width(i * STEP) for i in range(a, b)),
                "width_max_m": max(width(i * STEP) for i in range(a, b)),
                "elevation_min_m": min(zs),
                "elevation_max_m": max(zs),
                "vertical_and_camber_status": "inferred, not surveyed",
            }
        )
    report = {
        "plan_length_m": SURVEY["plan_length_m"],
        "spatial_centerline_length_m": length,
        "length_error_m": length - L,
        "sections": stats,
        "source_confidence": SURVEY["confidence"],
    }
    assert abs(length - L) < 1, report
    (OUT / "geometry_qa.json").write_text(json.dumps(report, indent=2) + "\n")
    bpy.context.scene["foundation_passed"] = True
    save()


def load():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    COLS.clear()
    MATS.update({m.name: m for m in bpy.data.materials})


def render(section=None, foundation_only=False):
    sc = bpy.context.scene
    folder = OUT / ("qa/foundation" if foundation_only else "qa/sections")
    folder.mkdir(parents=True, exist_ok=True)
    names = (
        ["OVERVIEW | whole circuit"]
        if section is None
        else [
            prefix + " | " + SURVEY["sections"][section]["name"]
            for prefix in ["DRIVER", "ELEVATED"]
        ]
    )
    for name in names:
        sc.camera = bpy.data.objects[name]
        sc.render.filepath = str(folder / (name.replace(" | ", "_") + ".png"))
        bpy.ops.render.render(write_still=True)


def refit_surface_details():
    # Keep paint, kerbs and drains attached when the inferred cross-section is refined.
    for side, sign in [("L", 1), ("R", -1)]:
        specs = [
            (f"{side} continuous 150 mm edge line", -0.22, -0.07, 0.007, 1),
            (f"{side} drainage concrete", 0, 0.35, -0.017, 1),
            (f"{side} grass verge", 0.35, 2, -0.035, 2),
        ]
        for name, a, b, lift, steps in specs:
            ob = bpy.data.objects[name]
            for i in range(N):
                for j in range(steps + 1):
                    ob.data.vertices[i * (steps + 1) + j].co = point(
                        i, sign * (width(i * STEP) / 2 + a + (b - a) * j / steps), lift
                    )
            ob.data.update()
    for ob in collection("Track").objects:
        if ob.type != "MESH":
            continue
        kerb = " kerb " in ob.name
        apron = " green apron " in ob.name
        patch = ob.name.startswith("Edge repair ")
        if not (kerb or apron or patch):
            continue
        for j, v in enumerate(ob.data.vertices):
            p = v.co
            _, i, _d = TREE.find((p.x, p.y, 0))
            off = (Vector((p.x, p.y)) - Vector(XY[i])).dot(NORMALS[i])
            lift = (
                [0.007, 0.042, 0.036, 0.005][j % 4]
                if kerb
                else 0.005
                if apron
                else 0.004
            )
            p.z = point(i, off, lift)[2]
        ob.data.update()


def refit_runoff_surfaces():
    """Partition overlapping mapped/inferred surfaces, including kerb clearance."""
    from monza_environment import KERBS
    from shapely import Polygon, constrained_delaunay_triangles, unary_union

    left, right = [], []
    for i in range(N):
        s = i * STEP
        for side, ring in [(1, left), (-1, right)]:
            margin = 0.45
            if any(a - 2 <= s <= b + 2 and sign == side for a, b, sign in KERBS):
                margin = 2.87
            ring.append(point(i, side * (width(s) / 2 + margin))[:2])
    occupied = Polygon(left, [right]).buffer(0)
    road_area = occupied.area
    report = []
    objects = sorted(
        [ob for ob in collection("Runoff").objects if ob.type == "MESH"],
        key=lambda ob: (
            0
            if "escape road" in ob.name
            else 1
            if ob.name.startswith("Mapped gravel")
            else 2,
            ob.name,
        ),
    )
    for ob in objects:
        pieces = []
        for face in ob.data.polygons:
            poly = Polygon([ob.data.vertices[i].co[:2] for i in face.vertices]).buffer(
                0
            )
            if not poly.is_empty:
                pieces.append(poly)
        footprint = unary_union(pieces)
        allowed = footprint.difference(occupied).buffer(0)
        triangles = constrained_delaunay_triangles(allowed)
        verts, faces = [], []
        for triangle in triangles.geoms:
            pts = list(triangle.exterior.coords)[:3]
            if (pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1]) - (
                pts[1][1] - pts[0][1]
            ) * (pts[2][0] - pts[0][0]) < 0:
                pts.reverse()
            j = len(verts)
            verts.extend((x, y, terrain(x, y) + 0.028) for x, y in pts)
            faces.append((j, j + 1, j + 2))
        mats = list(ob.data.materials)
        data = bpy.data.meshes.new(ob.name + " clipped")
        data.from_pydata(verts, [], faces)
        for mat in mats:
            data.materials.append(mat)
        ob.data = data
        data.update()
        ob["plan_area_m2"] = allowed.area
        ob["surface_partition"] = (
            "Road and kerbs excluded; mapped areas precede inferred infill; disjoint polygons"
        )
        occupied = occupied.union(allowed)
        report.append(
            {
                "name": ob.name,
                "original_area_m2": footprint.area,
                "retained_area_m2": allowed.area,
                "triangles": len(faces),
            }
        )
    (OUT / "qa/runoff_partition.json").write_text(
        json.dumps({"protected_road_area_m2": road_area, "surfaces": report}, indent=2)
        + "\n"
    )


def finalize():
    import sys

    import monza_environment as env

    sc = bpy.context.scene
    assert json.loads(sc.get("completed_sections", "[]")) == list(range(10))
    env.B = sys.modules[__name__]
    for ob in list(collection("Safety_barriers").objects) + list(
        collection("Fencing").objects
    ):
        if " Armco " in ob.name or " catch fence " in ob.name:
            bpy.data.objects.remove(ob, do_unlink=True)
    for section in SURVEY["sections"]:
        env.safety(dict(section))
    env.historic_oval(sys.modules[__name__])
    env.finishing_details(sys.modules[__name__])
    historical = MATS.get("Historic_concrete") or material(
        "Historic_concrete", (0.20, 0.195, 0.17), 0.98, 0, 0.28, 0.024
    )
    for ob in collection("Historic_oval").objects:
        if ob.type == "MESH":
            ob.data.materials.clear()
            ob.data.materials.append(historical)
    # The old oval shares portions of the modern straight. Never lay legacy concrete over it.
    import bmesh

    for ob in collection("Historic_oval").objects:
        if ob.type != "MESH" or not ob.name.startswith("Historic oval "):
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        remove = []
        for face in bm.faces:
            for v in face.verts:
                p = v.co
                _, i, d = TREE.find((p.x, p.y, 0))
                if d < width(i * STEP) / 2 + 1.1 and not 3240 < i * STEP < 3360:
                    remove.append(face)
                    break
        if remove:
            bmesh.ops.delete(bm, geom=remove, context="FACES")
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
    # Remove weeds from mapped, maintained gravel traps while retaining verge tufts.
    gravel = [
        f["points"]
        for f in SURVEY["features"]
        if f["closed"] and f["tags"].get("natural") == "sand"
    ]
    for ob in collection("Forest").objects:
        if "verge tufts" not in ob.name:
            continue
        scales = ob.data.attributes["instance_scale"]
        for i, v in enumerate(ob.data.vertices):
            if any(env.inside(v.co.x, v.co.y, poly) for poly in gravel):
                scales.data[i].vector = (0, 0, 0)
    for ob in collection("Asset_library").objects:
        ob.hide_set(True)
    for ob in collection("Pit_buildings").objects:
        if ob.type == "MESH" and "surveyed footprint" in ob.name and not ob.modifiers:
            bevel = ob.modifiers.new("Weathered corner arris", "BEVEL")
            bevel.width = 0.035
            bevel.segments = 2
    # Re-evaluate the foundation after cross-section refinements discovered during QA.
    road = bpy.data.objects["ASPHALT | continuous crowned surface"]
    for i in range(N):
        for j in range(9):
            road.data.vertices[i * 9 + j].co = point(
                i, -width(i * STEP) / 2 + j * width(i * STEP) / 8
            )
    road.data.update()
    for name, off in [
        ("CENTERLINE | 5793 m | clockwise", 0),
        ("LEFT_EDGE | variable 10-12 m", 1),
        ("RIGHT_EDGE | variable 10-12 m", -1),
    ]:
        for i, v in enumerate(bpy.data.objects[name].data.splines[0].points):
            v.co = (*point(i, off * width(i * STEP) / 2), 1)
    refit_surface_details()
    # Ground visible runoffs and service surfaces; no extension of road camber into gravel.
    for ob in collection("Runoff").objects:
        if ob.type != "MESH":
            continue
        for v in ob.data.vertices:
            p = v.co
            _, i, d = TREE.find((p.x, p.y, 0))
            if d > width(i * STEP) / 2 + 2.4:
                p.z = terrain(p.x, p.y) + 0.028
        ob.data.update()
    refit_runoff_surfaces()
    driver_stations = [L - 280, 570, 1010, 1775, 2165, 2500, 3190, 3570, 4140, 4790]
    for index, s in enumerate(driver_stations):
        ob = bpy.data.objects["DRIVER | " + SURVEY["sections"][index]["name"]]
        ob.location = station_point(s, 0, 1.2)[0]
        target = station_point(s + 28, 0, 1.2)[0]
        ob.rotation_euler = (target - ob.location).to_track_quat("-Z", "Y").to_euler()
    alboreto = bpy.data.objects["ELEVATED | Alboreto"]
    alboreto.location = (430, -1120, 450)
    alboreto.rotation_euler = (
        (Vector((65, -580, 0)) - alboreto.location).to_track_quat("-Z", "Y").to_euler()
    )
    alboreto.data.lens = 44
    # Every frame follows a point on the lap. No straight interpolation through corners.
    old = bpy.data.objects.get("LAP | 1.2 m | animated survey inspection")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    cam = camera(
        "LAP | 1.2 m | animated survey inspection",
        station_point(0, 0, 1.2)[0],
        station_point(20, 0, 1.2)[0],
        24,
    )
    sc.render.fps = 24
    sc.frame_start = 1
    sc.frame_end = 1932
    for frame in range(1, 1933):
        s = (frame - 1) * L / 1931
        p, t, _n = station_point(s, 0, 1.2)
        target = p + Vector((t.x, t.y, 0)) * 18
        target.z = station_point(s + 18, 0, 1.2)[0].z
        cam.location = p
        cam.rotation_euler = (target - p).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert(data_path="location", frame=frame)
        cam.keyframe_insert(data_path="rotation_euler", frame=frame)
    sc.timeline_markers.clear()
    for sec in SURVEY["sections"]:
        sc.timeline_markers.new(
            sec["name"].replace("_", " "), frame=1 + round(sec["start_m"] / L * 1931)
        )
    sc.frame_set(1)
    overview = bpy.data.objects["OVERVIEW | whole circuit"]
    overview.location = (1800, -1850, 2450)
    overview.rotation_euler = (
        (Vector((530, 270, 0)) - overview.location).to_track_quat("-Z", "Y").to_euler()
    )
    overview.data.lens = 46
    # Large ground underlay keeps the horizon continuous beyond the surveyed park patch.
    BOUNDS = 15000
    if not bpy.data.objects.get("Distant ground horizon"):
        mesh(
            "Distant ground horizon",
            [
                (-BOUNDS, -BOUNDS, -5),
                (BOUNDS, -BOUNDS, -5),
                (BOUNDS, BOUNDS, -5),
                (-BOUNDS, BOUNDS, -5),
            ],
            [(0, 1, 2, 3)],
            MATS["Grass"],
            "Distant_environment",
        )
    readme = bpy.data.texts.get(
        "READ ME | survey and limitations"
    ) or bpy.data.texts.new("READ ME | survey and limitations")
    readme.clear()
    readme.write((OUT / "references/SOURCES.md").read_text())
    sc["spatial_centerline_length_m"] = sum(
        (Vector(point(i + 1)) - Vector(point(i))).length for i in range(N)
    )
    sc["driver_camera_height_m"] = 1.2
    sc["final_qa"] = "See qa/final_validation.json and QA.md alongside this scene."
    sc.camera = overview
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.clip_end = 7000
                area.spaces.active.region_3d.view_distance = 2300
                area.spaces.active.region_3d.view_location = (500, 300, 0)
    save()
    sc.cycles.samples = 32
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 1000
    sc.render.filepath = str(OUT / "monza_overview.png")
    bpy.ops.render.render(write_still=True)


def lap(first=1, last=1932):
    sc = bpy.context.scene
    sc.camera = bpy.data.objects["LAP | 1.2 m | animated survey inspection"]
    sc.render.resolution_x = 320
    sc.render.resolution_y = 180
    sc.cycles.samples = 2
    sc.render.use_persistent_data = True
    sc.cycles.max_bounces = 2
    sc.cycles.diffuse_bounces = 1
    sc.cycles.glossy_bounces = 1
    sc.render.threads = 4
    folder = OUT / "qa/lap"
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(first, last + 1):
        sc.frame_set(i)
        sc.render.filepath = str(folder / f"{i - 1:04d}.png")
        bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=[
            "foundation",
            "environment",
            "render",
            "finalize",
            "lap",
            "review",
            "refit",
        ],
        default="foundation",
    )
    parser.add_argument("--section", type=int)
    parser.add_argument("--foundation-only", action="store_true")
    parser.add_argument("--frame-start", type=int, default=1)
    parser.add_argument("--frame-end", type=int, default=1932)
    args = parser.parse_args()
    if args.phase == "foundation":
        foundation()
        render(foundation_only=True)
    else:
        load()
        if args.phase == "render":
            render(args.section, args.foundation_only)
        elif args.phase == "environment":
            import sys

            from monza_environment import build

            build(sys.modules[__name__], args.section)
        elif args.phase == "finalize":
            finalize()
        elif args.phase == "lap":
            lap(args.frame_start, args.frame_end)
        elif args.phase == "refit":
            refit_surface_details()
            refit_runoff_surfaces()
            save()
        elif args.phase == "review":
            sc = bpy.context.scene
            sc.render.use_persistent_data = True
            for i in range(10):
                render(i)
            sc.camera = bpy.data.objects["DRIVER | Start_finish"]
            sc.render.resolution_x = 1920
            sc.render.resolution_y = 1080
            sc.cycles.samples = 64
            sc.render.filepath = str(OUT / "monza_driver.png")
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
