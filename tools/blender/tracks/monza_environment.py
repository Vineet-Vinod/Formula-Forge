"""Section-by-section environment authoring for build_monza.py.

Footprints and planting masks come from the checked-in survey. Construction
details and heights are artist estimates, kept separate from mapped geometry.
"""

import itertools
import json
import math
import random

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from mathutils.kdtree import KDTree

B = None
TAU = math.tau


class Batch:
    def __init__(self):
        self.v = []
        self.f = []
        self.m = []

    def face(self, points, mat=0):
        i = len(self.v)
        self.v.extend(points)
        self.f.append(tuple(range(i, i + len(points))))
        self.m.append(mat)

    def cube(self, c, size, angle=0, mat=0):
        x, y, z = size
        ca, sa = math.cos(angle), math.sin(angle)
        v = []
        for dz in [-z / 2, z / 2]:
            for dx, dy in [
                (-x / 2, -y / 2),
                (x / 2, -y / 2),
                (x / 2, y / 2),
                (-x / 2, y / 2),
            ]:
                v.append(
                    (c[0] + ca * dx - sa * dy, c[1] + sa * dx + ca * dy, c[2] + dz)
                )
        j = len(self.v)
        self.v.extend(v)
        for f in [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]:
            self.f.append(tuple(j + i for i in f))
            self.m.append(mat)

    def rod(self, a, b, r, mat=0, sides=7, tip=None):
        a, b = Vector(a), Vector(b)
        t = (b - a).normalized()
        n = t.cross(Vector((0.123, 0.932, 0.343))).normalized()
        v = t.cross(n)
        j = len(self.v)
        for p, rad in [(a, r), (b, r if tip is None else tip)]:
            for k in range(sides):
                self.v.append(
                    tuple(
                        p
                        + rad
                        * (
                            n * math.cos(k * TAU / sides)
                            + v * math.sin(k * TAU / sides)
                        )
                    )
                )
        for k in range(sides):
            self.f.append(
                (j + k, j + (k + 1) % sides, j + (k + 1) % sides + sides, j + k + sides)
            )
            self.m.append(mat)
        self.f.append(tuple(j + k for k in reversed(range(sides))))
        self.m.append(mat)
        self.f.append(tuple(j + k + sides for k in range(sides)))
        self.m.append(mat)

    def ellipsoid(self, c, r, mat=0, lon=10, lat=6, phase=0):
        j = len(self.v)
        for b in range(lat + 1):
            p = math.pi * b / lat
            for a in range(lon):
                t = a * TAU / lon
                irregular = 1 + 0.12 * math.sin(t * 3 + phase) * math.sin(p * 4 + phase)
                self.v.append(
                    (
                        c[0] + r[0] * math.sin(p) * math.cos(t) * irregular,
                        c[1] + r[1] * math.sin(p) * math.sin(t) * irregular,
                        c[2] + r[2] * math.cos(p) * irregular,
                    )
                )
        for b in range(lat):
            for a in range(lon):
                self.f.append(
                    (
                        j + b * lon + a,
                        j + b * lon + (a + 1) % lon,
                        j + (b + 1) * lon + (a + 1) % lon,
                        j + (b + 1) * lon + a,
                    )
                )
                self.m.append(mat)

    def object(self, name, mats, group, smooth=False):
        ob = B.mesh(name, self.v, self.f, mats, group, self.m)
        if smooth:
            for p in ob.data.polygons:
                p.use_smooth = True
        return ob


def inside(x, y, polygon):
    yes = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (
            b[1] - a[1]
        ) + a[0]:
            yes = not yes
    return yes


def centroid(ps):
    return (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))


def polygon(name, ps, material, group, lift=0.05):
    points = [Vector((x, y, B.terrain(x, y) + lift)) for x, y in ps]
    if (points[0] - points[-1]).length < 0.01:
        points.pop()
    tris = tessellate_polygon([points])
    verts = []
    faces = []
    for tri in tris:
        i = len(verts)
        verts.extend(points[v] if isinstance(v, int) else v for v in tri)
        faces.append((i, i + 1, i + 2))
    return B.mesh(name, verts, faces, material, group)


# Kerb segments follow the actual corner order. Positive offsets are driver-left.
KERBS = [
    (609, 642, -1),
    (644, 686, 1),
    (700, 790, -1),
    (1817, 1858, 1),
    (1864, 1904, -1),
    (1910, 1970, 1),
    (2200, 2315, -1),
    (2280, 2385, 1),
    (2545, 2606, -1),
    (2590, 2680, 1),
    (3630, 3675, 1),
    (3700, 3783, -1),
    (3800, 3872, 1),
    (3865, 3940, -1),
    (4820, 4945, -1),
    (4990, 5230, -1),
]
RUNOFF = [
    (540, 722, 1, 24, "Asphalt"),
    (1800, 1940, -1, 32, "Gravel"),
    (2180, 2390, 1, 29, "Gravel"),
    (2500, 2680, 1, 28, "Gravel"),
    (3610, 3880, -1, 28, "Gravel"),
    (3620, 3860, 1, 22, "Gravel"),
    (4770, 5180, 1, 35, "Gravel"),
    (5180, 5420, 1, 26, "Asphalt"),
]


def barrier_offset(s, side):
    offset = 10.5
    if 40 < s < 490:
        offset = 12 if side == 1 else 17
    if s > 5460 or s < 40:
        offset = 10 if side == 1 else 8.5
    for a, b, sign, w, mat in RUNOFF:
        if sign == side:
            center = (a + b) / 2
            extent = (b - a) / 2
            u = max(0, min(1, (extent + 65 - abs(s - center)) / 65))
            u = u * u * (3 - 2 * u)
            offset = max(offset, 10.5 + (w + 5 - 10.5) * u)
    i = int(s / B.STEP) % B.N
    k = B.CURVATURE[i]
    if k * side > 0.002:
        offset = min(offset, max(9, 1 / abs(k) * 0.70))
    return B.width(s) / 2 + offset


def instances(name, prototype, placements, group):
    if not placements:
        return
    vs = [p[0] for p in placements]
    ob = B.mesh(name, vs, [], B.MATS["Bark"], group)
    for attr, values in [
        ("instance_scale", [p[1] for p in placements]),
        ("instance_rotation", [(0, 0, p[2]) for p in placements]),
    ]:
        a = ob.data.attributes.new(attr, "FLOAT_VECTOR", "POINT")
        a.data.foreach_set("vector", [v for val in values for v in val])
    nodes = bpy.data.node_groups.new(name + " instances", "GeometryNodeTree")
    nodes.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    nodes.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    n = nodes.nodes
    l = nodes.links
    i = n.new("NodeGroupInput")
    o = n.new("NodeGroupOutput")
    inst = n.new("GeometryNodeInstanceOnPoints")
    info = n.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = prototype
    info.transform_space = "ORIGINAL"
    l.new(i.outputs["Geometry"], inst.inputs["Points"])
    l.new(info.outputs["Geometry"], inst.inputs["Instance"])
    l.new(inst.outputs["Instances"], o.inputs["Geometry"])
    for attr, slot in [("instance_scale", "Scale"), ("instance_rotation", "Rotation")]:
        at = n.new("GeometryNodeInputNamedAttribute")
        at.data_type = "FLOAT_VECTOR"
        at.inputs["Name"].default_value = attr
        l.new(at.outputs["Attribute"], inst.inputs[slot])
    mod = ob.modifiers.new("Linked asset instances", "NODES")
    mod.node_group = nodes
    ob["instance_count"] = len(placements)
    return ob


def library():
    grass_library()
    if bpy.data.objects.get("LIB_Armco_4m"):
        return
    b = Batch()
    # Corrugated W-beam, three courses. Local X follows the circuit tangent.
    for z in [0.36, 0.67, 0.98]:
        profile = [
            (-0.075, z - 0.145),
            (0.055, z - 0.10),
            (0.075, z - 0.035),
            (-0.025, z),
            (0.075, z + 0.035),
            (0.055, z + 0.10),
            (-0.075, z + 0.145),
        ]
        for a, c in itertools.pairwise(profile):
            b.face(
                [(-2, a[0], a[1]), (2, a[0], a[1]), (2, c[0], c[1]), (-2, c[0], c[1])]
            )
    for x in [-1, 1]:
        b.cube((x, 0.10, 0.56), (0.11, 0.15, 1.12))
        b.cube((x, 0.075, 1.0), (0.12, 0.025, 0.08))
    ob = b.object("LIB_Armco_4m", [B.MATS["Armco"]], "Asset_library")
    ob.hide_render = True
    f = Batch()
    f.rod((-2, 0, 0), (-2, 0, 3.25), 0.038)
    f.rod((-2, 0, 3.25), (-2, -0.42, 3.8), 0.031)
    for h in [0.5, 1.5, 2.5, 3.25]:
        f.rod((-2, 0, h), (2, 0, h), 0.008, sides=4)
    # Actual diamond wires, 120 mm mesh. Instanced rather than a solid fence sheet.
    for direction in [-1, 1]:
        for k in range(-31, 35):
            intercept = k * 0.17
            candidates = []
            for x in [-2, 2]:
                z = direction * x + intercept
                if 0.25 <= z <= 3.25:
                    candidates.append((x, 0.018, z))
            for z in [0.25, 3.25]:
                x = (z - intercept) / direction
                if -2 <= x <= 2:
                    candidates.append((x, 0.018, z))
            if len(candidates) >= 2:
                f.rod(candidates[0], candidates[1], 0.0025, sides=3)
    ob = f.object("LIB_Fence_4m", [B.MATS["Fence"]], "Asset_library")
    ob.hide_render = True
    b = Batch()
    b.cube((0, 0, 0.5), (1.95, 0.78, 1.0))
    ob = b.object("LIB_Tecpro", [B.MATS["Red_paint"]], "Asset_library")
    ob.hide_render = True
    b = Batch()
    b.rod((0, 0, 0), (0, 0, 1.0), 0.07, sides=8)
    ob = b.object("LIB_Bollard", [B.MATS["Orange"]], "Asset_library")
    ob.hide_render = True
    # Twelve broadleaf forms: four mature crowns, mixed younger growth, lower-cost distant crowns.
    for kind in range(12):
        rng = random.Random(9300 + kind)
        near = kind < 6
        b = Batch()
        height = 17 + kind % 3 * 3
        spread = 5.2 + (kind % 4) * 0.7
        if kind % 6 == 4:
            height = 25
            spread = 3.1
        b.rod((0, 0, 0), (0.35, -0.18, height * 0.77), 0.34, 0, 10, 0.075)
        clusters = []
        for j in range(22 if near else 15):
            z = height * (0.37 + 0.52 * rng.random())
            ang = j * 2.399963
            radius = (
                spread * (0.4 + 0.6 * rng.random()) * math.sin((z / height) * math.pi)
            )
            end = Vector((math.cos(ang) * radius, math.sin(ang) * radius, z))
            base = Vector((0.25, -0.1, z - height * 0.2))
            b.rod(base, end, 0.12 * (1 - z / height) + 0.025, 0, 6, 0.018)
            for q in range(3):
                tip = end + Vector(
                    (
                        rng.uniform(-1.3, 1.3),
                        rng.uniform(-1.3, 1.3),
                        rng.uniform(0.1, 1.8),
                    )
                )
                if near:
                    b.rod(end, tip, 0.019, 0, 5, 0.005)
                clusters.append(
                    (
                        tip,
                        Vector(
                            (
                                1.15 + rng.random() * 0.65,
                                1.15 + rng.random() * 0.65,
                                1.2 + rng.random() * 0.9,
                            )
                        ),
                    )
                )
        for j, (c, rad) in enumerate(clusters):
            # Individual overlapping leaves form the crown; no opaque spherical canopy.
            for leaf in range(180 if near else 70):
                zz = rng.uniform(-1, 1)
                ang = rng.random() * TAU
                rr = math.sqrt(1 - zz * zz)
                normal = Vector((rr * math.cos(ang), rr * math.sin(ang), zz))
                p = c + Vector(
                    (normal.x * rad.x, normal.y * rad.y, normal.z * rad.z)
                ) * rng.uniform(0.68, 1.15)
                u = normal.cross(Vector((0.13, 0.83, 0.35))).normalized()
                v = normal.cross(u)
                size = rng.uniform(0.11, 0.21) if near else rng.uniform(0.23, 0.38)
                b.face(
                    [
                        p - u * size,
                        p - v * size * 0.55 + normal * 0.025,
                        p + u * size * 0.72 - v * size * 0.22,
                        p + u * size,
                        p + u * size * 0.72 + v * size * 0.22,
                        p + v * size * 0.55,
                    ],
                    1 + (j + leaf) % 5,
                )
        ob = b.object(
            f"LIB_Tree_{kind:02d}",
            [B.MATS["Bark"]] + [B.MATS[f"Leaf_{j}"] for j in range(5)],
            "Asset_library",
            True,
        )
        ob.hide_render = True
        ob["height_m"] = height
        ob["detail"] = "foreground leaf geometry" if near else "distant reduced foliage"


def grass_library():
    if bpy.data.objects.get("LIB_Grass_tuft"):
        return
    b = Batch()
    rng = random.Random(73)
    for j in range(34):
        x, y = rng.uniform(-0.32, 0.32), rng.uniform(-0.32, 0.32)
        h = rng.uniform(0.12, 0.38)
        a = rng.random() * TAU
        dx, dy = math.cos(a) * 0.012, math.sin(a) * 0.012
        b.face(
            [
                (x - dx, y - dy, 0),
                (x + dx, y + dy, 0),
                (x + 0.07, y - 0.04, h * 0.65),
                (x + 0.12, y - 0.08, h),
            ],
            j % 3,
        )
    ob = b.object(
        "LIB_Grass_tuft",
        [B.MATS["Grass"], B.MATS["Leaf_3"], B.MATS["Soil"]],
        "Asset_library",
    )
    ob.hide_render = True


def surface(section):
    start, end = section["start_m"], section["end_m"]
    list(range(math.ceil(start / B.STEP), min(B.N, math.ceil(end / B.STEP)) + 1))
    for a, b, side in KERBS:
        a = max(a, start)
        b = min(b, end)
        if a >= b:
            continue
        vs = []
        fs = []
        mi = []
        for k in range(math.ceil((b - a) / B.STEP)):
            i = int(a / B.STEP) + k
            w = B.width(i * B.STEP) / 2
            j = len(vs)
            for q in [i, i + 1]:
                for offset, z in [
                    (0, 0.007),
                    (0.3, 0.042),
                    (1.1, 0.036),
                    (1.45, 0.005),
                ]:
                    vs.append(
                        B.point(q, side * (B.width(q % B.N * B.STEP) / 2 + offset), z)
                    )
            for c in range(3):
                face = (j + c, j + 4 + c, j + 5 + c, j + 1 + c)
                fs.append(face if side > 0 else tuple(reversed(face)))
                mi.append(int((a + k * B.STEP) / 1.5) % 2)
        B.mesh(
            f"{section['name']} kerb {a:.0f}",
            vs,
            fs,
            [B.MATS["White_paint"], B.MATS["Red_paint"]],
            "Track",
            mi,
        )
        ids = list(range(int(a / B.STEP), int(b / B.STEP) + 1))
        B.strip(
            f"{section['name']} green apron {a:.0f}",
            ids,
            lambda i, side=side: side * (B.width(i % B.N * B.STEP) / 2 + 1.45),
            lambda i, side=side: side * (B.width(i % B.N * B.STEP) / 2 + 2.8),
            B.MATS["Green_paint"],
            lift=0.005,
        )
    # Gravel traps use mapped polygons; these strips fill unmapped transitions only.
    for a, b, side, w, mat in RUNOFF:
        a = max(a, start)
        b = min(b, end)
        if a >= b:
            continue
        ids = list(range(int(a / B.STEP), int(b / B.STEP) + 1))

        def extent(i, a=a, b=b, w=w):
            t = (i * B.STEP - a) / max(1, b - a)
            return 3 + (w - 3) * min(1, t * 8, (1 - t) * 8)

        B.strip(
            f"{section['name']} {mat} runoff",
            ids,
            lambda i, side=side: side * (B.width(i % B.N * B.STEP) / 2 + 2),
            lambda i, side=side, extent=extent: (
                side * (B.width(i % B.N * B.STEP) / 2 + max(3, extent(i)))
            ),
            B.MATS[mat],
            "Runoff",
            lift=-0.035,
            steps=6,
        )
    # Racing rubber is a graded material on the asphalt, no floating overlay ribbon.
    road = bpy.data.objects["ASPHALT | continuous crowned surface"]
    attr = road.data.attributes.get("rubber_deposit") or road.data.attributes.new(
        "rubber_deposit", "FLOAT", "POINT"
    )
    for i in range(math.ceil(start / B.STEP), min(B.N, math.ceil(end / B.STEP))):
        s = i * B.STEP
        k = B.CURVATURE[i]
        offset = -math.tanh(k * 65) * B.width(s) * 0.22
        intensity = 0.18 + min(0.50, abs(k) * 36)
        for a, b, side in KERBS:
            if a - 110 < s < a:
                intensity = max(intensity, 0.44)
        for cross in range(9):
            x = -B.width(s) / 2 + B.width(s) * cross / 8
            attr.data[i * 9 + cross].value = intensity * math.exp(
                -(((x - offset) / 1.9) ** 4)
            )
    asphalt = B.MATS["Asphalt"]
    nodes = asphalt.node_tree.nodes
    links = asphalt.node_tree.links
    if not nodes.get("Rubber deposit"):
        bs = nodes.get("Principled BSDF")
        original = bs.inputs["Base Color"].links[0].from_socket
        at = nodes.new("ShaderNodeAttribute")
        at.attribute_name = "rubber_deposit"
        at.name = "Rubber deposit"
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MIX"
        mix.inputs[2].default_value = (0.013, 0.014, 0.014, 1)
        links.new(at.outputs["Fac"], mix.inputs[0])
        links.new(original, mix.inputs[1])
        links.new(mix.outputs[0], bs.inputs["Base Color"])
    # Drain grates and localized repair patches are placed at braking/maintenance locations.
    b = Batch()
    for s in range(math.ceil(start / 40) * 40, int(end), 40):
        for side in [-1, 1]:
            p, t, _n = B.station_point(s, side * (B.width(s) / 2 + 0.2), -0.014)
            ang = math.atan2(t.y, t.x)
            for k in range(7):
                b.cube(
                    p + Vector((t.x, t.y, 0)) * (k * 0.065 - 0.2),
                    (0.018, 0.28, 0.025),
                    ang,
                )
    b.object(section["name"] + " drain gratings", [B.MATS["Fence"]], "Track")
    # Small edge repairs, kept sparse on the recently resurfaced track.
    for s, side in [(425, 1), (1515, -1), (2780, 1), (4230, -1), (4680, 1), (5620, -1)]:
        if start <= s < end:
            ids = list(range(int(s / B.STEP), int((s + 3.75) / B.STEP) + 1))
            off = side * (B.width(s) / 2 - 0.6)
            B.strip(
                f"Edge repair at {s}m",
                ids,
                off - 0.23,
                off + 0.23,
                B.MATS["Rubber"],
                lift=0.004,
            )
    if start < 625 < end:
        # Mapped motorcycle bypass also explains the Rettifilo escape-road alignment.
        bypass = next(f for f in B.SURVEY["features"] if f["osm_way"] == 38168756)
        B.ribbon(
            "Rettifilo escape road",
            bypass["points"],
            6,
            B.MATS["Asphalt"],
            "Runoff",
            0.11,
        )
        bollards = []
        for s, offset in [(639, 8.6), (647, 10.3), (660, 11.8)]:
            p, _t, _n = B.station_point(s, offset)
            p.z = B.terrain(p.x, p.y) + 0.12
            bollards.append((p, (1, 1, 1), 0))
        instances(
            "Rettifilo escape bollards",
            bpy.data.objects["LIB_Bollard"],
            bollards,
            "Safety_barriers",
        )
        # Low rounded deterrent elements on the first chicane islands; inferred dimensions.
        batch = Batch()
        for s, side in [(627, -1), (666, 1)]:
            p, t, _n = B.station_point(s, side * (B.width(s) / 2 + 1.9), 0.035)
            for j in range(12):
                q = p + Vector((t.x, t.y, 0)) * (j * 0.22 - 1.2)
                batch.ellipsoid(q, (0.19, 0.19, 0.045), 0, lon=10, lat=4)
        ob = batch.object(
            "Rettifilo low raised anti-cut kerbs", [B.MATS["Yellow"]], "Track", True
        )
        ob["confidence"] = (
            "Inferred low-profile deterrent geometry; exact 2026 installation unverified"
        )


def safety(section):
    name = section["name"]
    a, b = section["start_m"], section["end_m"]
    report = []
    for side in [-1, 1]:
        rails = []
        fences = []
        min_offset = 1000
        paths = []
        path = []
        for s in [a] + [float(s) for s in range(math.ceil(a / 2) * 2, int(b), 2)] + [b]:
            off = barrier_offset(s, side)
            i = int(s / B.STEP) % B.N
            p, t, _n = B.station_point(s, side * off)
            p.z = B.terrain(p.x, p.y) + 0.05
            _, near, d = B.TREE.find((p.x, p.y, 0))
            # Leave chicane islands open. Do not fold an offset through a small inside radius.
            omit = (
                (side == -1 and (s < 145 or s > 5400))
                or (B.CURVATURE[i] * side > 1 / (off + 2))
                or d < B.width(near * B.STEP) / 2 + 3.0
            )
            if omit:
                if len(path) > 1:
                    paths.append(path)
                path = []
                continue
            min_offset = min(min_offset, d - B.width(near * B.STEP) / 2)
            path.append(p)
        if len(path) > 1:
            paths.append(path)
        for path in paths:
            # Resample the barrier itself, so each instanced beam meets its neighbour.
            distances = [0]
            for p, q in itertools.pairwise(path):
                distances.append(distances[-1] + (q - p).length)
            count = max(1, math.ceil(distances[-1] / 4))
            pts = []
            j = 0
            for k in range(count + 1):
                s = k * distances[-1] / count
                while j < len(path) - 2 and distances[j + 1] < s:
                    j += 1
                t = (s - distances[j]) / max(1e-9, distances[j + 1] - distances[j])
                pts.append(path[j].lerp(path[j + 1], t))
            for p, q in itertools.pairwise(pts):
                v = q - p
                length = v.length
                mid = (p + q) / 2
                angle = math.atan2(v.y, v.x)
                rails.append((mid, ((length + 0.025) / 4, 1, 1), angle))
                normal = Vector((-math.sin(angle), math.cos(angle), 0))
                fp = mid + normal * side * 0.55
                fences.append(
                    (
                        fp,
                        ((length + 0.025) / 4, 1, 1),
                        angle + (math.pi if side < 0 else 0),
                    )
                )
        instances(
            name + f" Armco {side}",
            bpy.data.objects["LIB_Armco_4m"],
            rails,
            "Safety_barriers",
        )
        instances(
            name + f" catch fence {side}",
            bpy.data.objects["LIB_Fence_4m"],
            fences,
            "Fencing",
        )
        report.append(
            {
                "side": side,
                "minimum_edge_offset_m": min_offset,
                "armco_modules": len(rails),
            }
        )
    section["safety_review"] = report


def text_object(name, body, p, size, angle=0, mat="White_paint", group="Signage"):
    data = bpy.data.curves.new(name, "FONT")
    data.body = body
    data.size = size
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.extrude = 0.004
    ob = bpy.data.objects.new(name, data)
    B.collection(group).objects.link(ob)
    data.materials.append(B.MATS[mat])
    ob.location = p
    ob.rotation_euler = (math.pi / 2, 0, angle)
    return ob


def signage(section):
    a, b = section["start_m"], section["end_m"]
    batch = Batch()
    turns = [
        (620, 1),
        (658, 2),
        (1190, 3),
        (1845, 4),
        (1880, 5),
        (2255, 6),
        (2575, 7),
        (3646, 8),
        (3753, 9),
        (3831, 10),
        (4940, 11),
    ]
    for apex, num in turns:
        if not a <= apex < b:
            continue
        p, t, n = B.station_point(apex, barrier_offset(apex, 1) + 1)
        p.z = B.terrain(p.x, p.y)
        batch.cube((p.x, p.y, p.z + 1.6), (0.08, 0.08, 3.2))
        ang = math.atan2(t.y, t.x) - math.pi / 2
        batch.cube((p.x, p.y, p.z + 2.7), (1.15, 0.13, 0.9), ang)
        text_object(
            f"Turn {num}",
            str(num),
            p + Vector((-t.x * 0.08, -t.y * 0.08, 2.7)),
            0.65,
            ang,
        )
        # Distance boards are generated by monza_map_details from the shared policy.
    batch.object(section["name"] + " corner panels", [B.MATS["Green_paint"]], "Signage")
    # Marshal posts follow FIA map stations, rather than equal spacing around the lap.
    posts = [
        (65, "0.1"),
        (300, "0.3"),
        (515, "0.5"),
        (622, "1"),
        (698, "2"),
        (1140, "3"),
        (1700, "3.4"),
        (1845, "4"),
        (1940, "5"),
        (2180, "5.2"),
        (2290, "6"),
        (2525, "7.1"),
        (2730, "7.2"),
        (3040, "7.5"),
        (3390, "7.7"),
        (3590, "8.1"),
        (3735, "9"),
        (3920, "10"),
        (4300, "10.3"),
        (4760, "11.1"),
        (5020, "11.3"),
        (5320, "11.5"),
        (5610, "12.1"),
    ]
    for s, label in posts:
        if not a <= s < b:
            continue
        side = 1
        p, t, n = B.station_point(s, side * (barrier_offset(s, side) + 3))
        z = B.terrain(p.x, p.y)
        ang = math.atan2(t.y, t.x)
        B.box(
            "Marshal M" + label,
            (p.x, p.y, z + 1.15),
            (2.5, 2, 2.3),
            B.MATS["Concrete"],
            "Marshal_posts",
            ang,
            0.04,
        )
        B.box(
            "M" + label + " glazed front",
            (p.x - n.x * 1.01, p.y - n.y * 1.01, z + 1.7),
            (2.15, 0.06, 0.72),
            B.MATS["Glass"],
            "Marshal_posts",
            ang,
        )
        B.box(
            "M" + label + " canopy",
            (p.x, p.y, z + 2.42),
            (3.1, 2.5, 0.16),
            B.MATS["Roof"],
            "Marshal_posts",
            ang,
            0.025,
        )
        text_object(
            "M" + label, label, (p.x - n.x * 1.1, p.y - n.y * 1.1, z + 0.72), 0.4, ang
        )
        equip = Batch()
        equip.rod((p.x + 1.6, p.y, z), (p.x + 1.6, p.y, z + 0.62), 0.13, sides=10)
        equip.object(
            "M" + label + " extinguisher", [B.MATS["Red_paint"]], "Marshal_posts"
        )


def footprint_axes(f):
    ps = f["points"][:-1] if f["closed"] else f["points"]
    cx, cy = centroid(ps)
    a, b = max(zip(ps, ps[1:] + ps[:1]), key=lambda ab: math.dist(*ab))
    u = Vector((b[0] - a[0], b[1] - a[1])).normalized()
    v = Vector((-u.y, u.x))
    coords = [
        ((p[0] - cx) * u.x + (p[1] - cy) * u.y, (p[0] - cx) * v.x + (p[1] - cy) * v.y)
        for p in ps
    ]
    xmin, xmax = min(p[0] for p in coords), max(p[0] for p in coords)
    ymin, ymax = min(p[1] for p in coords), max(p[1] for p in coords)
    cx += u.x * (xmin + xmax) / 2 + v.x * (ymin + ymax) / 2
    cy += u.y * (xmin + xmax) / 2 + v.y * (ymin + ymax) / 2
    return Vector((cx, cy)), u, v, xmax - xmin, ymax - ymin


def building(f):
    tags = f["tags"]
    name = tags.get("name", f"Building {f['osm_way']}")
    c, u, v, length, depth = footprint_axes(f)
    ang = math.atan2(u.y, u.x)
    z = B.terrain(c.x, c.y)
    special = f["osm_way"] in [34404652, 194458105]
    if tags.get("building") == "grandstand":
        nearest, _idx, _dist = B.TREE.find((c.x, c.y, 0))
        toward = Vector((nearest.x - c.x, nearest.y - c.y))
        if toward.dot(v) < 0:
            v = -v
            u = -u
            ang = math.atan2(u.y, u.x)
        rows = max(5, int(depth / 0.85))
        step = 0.38
        batch = Batch()
        seats = Batch()
        steel = Batch()
        for row in range(rows):
            yy = depth / 2 - row * 0.85
            h = 0.45 + row * step
            p = c + v * yy
            batch.cube((p.x, p.y, z + h / 2), (length, 0.9, h), ang)
            for x in range(int(-length / 2 + 0.5), int(length / 2), 1):
                if (x + int(length / 2)) % 18 in [0, 1]:
                    continue
                q = p + u * x
                mi = 0 if (x // 12 + row // 3) % 5 else 1
                seats.cube((q.x, q.y, z + h + 0.25), (0.44, 0.4, 0.09), ang, mi)
                q = q - v * 0.21
                seats.cube((q.x, q.y, z + h + 0.46), (0.44, 0.075, 0.38), ang, mi)
        batch.object(name + " concrete terraces", [B.MATS["Concrete"]], "Grandstands")
        seats.object(
            name + " individual seats",
            [B.MATS["Blue_seat"], B.MATS["White_paint"]],
            "Grandstands",
        )
        covered = f["osm_way"] in [34404645, 193647795, 193647796, 194457667, 231026020]
        if covered:
            roof_z = z + rows * step + 3.0
            roofmat = "Terracotta" if f["osm_way"] == 34404645 else "Roof"
            B.box(
                name + " canopy",
                (c.x, c.y, roof_z),
                (length + 1.5, depth + 2, 0.26),
                B.MATS[roofmat],
                "Grandstands",
                ang,
                0.06,
            )
            for x in range(int(-length / 2), int(length / 2) + 1, 9):
                q = c + u * x - v * (depth / 2 - 0.5)
                steel.rod((q.x, q.y, z), (q.x, q.y, roof_z), 0.1)
                front = c + u * x + v * depth / 2
                steel.rod(
                    (q.x, q.y, roof_z - 0.6), (front.x, front.y, roof_z - 0.2), 0.085
                )
        steel.object(name + " canopy supports", [B.MATS["Armco"]], "Grandstands")
        return
    if tags.get("building") == "tower" and name == "Podio":
        # Monza's circular podium projects over the pit wall on an elevated bridge.
        batch = Batch()
        batch.rod((c.x, c.y, z + 6.8), (c.x, c.y, z + 7.2), 4.6, 0, 40)
        batch.rod((c.x, c.y, z + 11.7), (c.x, c.y, z + 12), 5.0, 0, 40)
        for j in range(6):
            x, y = c.x + 4.2 * math.cos(j * TAU / 6), c.y + 4.2 * math.sin(j * TAU / 6)
            batch.rod((x, y, z + 7), (x, y, z + 12), 0.10)
        batch.object("Monza circular podium", [B.MATS["Roof"]], "Pit_buildings")
        B.box(
            "Podium access bridge",
            (c.x + 8, c.y, z + 6.8),
            (16, 3, 0.7),
            B.MATS["Concrete"],
            "Bridges",
            ang,
        )
        return
    if special:
        height = 8.5 if f["osm_way"] == 34404652 else 13
    else:
        height = (
            float(tags.get("height", 5))
            if tags.get("height", "").replace(".", "").isdigit()
            else 5
        )
    ps = f["points"]
    ps = ps[:-1] if f["closed"] else ps
    vs = [(x, y, B.terrain(x, y)) for x, y in ps] + [(x, y, z + height) for x, y in ps]
    n = len(ps)
    fs = [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)] + [
        tuple(range(n, 2 * n))
    ]
    ob = B.mesh(
        name + " surveyed footprint", vs, fs, B.MATS["Concrete"], "Pit_buildings"
    )
    ob["osm_way"] = f["osm_way"]
    ob["height_status"] = "estimated"
    B.box(
        name + " parapet roof",
        (c.x, c.y, z + height + 0.13),
        (length + 0.4, depth + 0.4, 0.26),
        B.MATS["Roof"],
        "Pit_buildings",
        ang,
        0.035,
    )
    near, _idx, _dist = B.TREE.find((c.x, c.y, 0))
    front = Vector((near.x - c.x, near.y - c.y))
    if front.dot(v) < 0:
        v = -v
    windows = Batch()
    frames = Batch()
    spacing = 5.5 if special else 3.5
    bays = max(1, int(length / spacing))
    for bay in range(bays):
        along = -length / 2 + (bay + 0.5) * length / bays
        p = c + u * along + v * (depth / 2 + 0.03)
        if special:
            windows.cube((p.x, p.y, z + 1.8), (spacing - 0.4, 0.10, 3.1), ang)
            frames.cube((p.x, p.y, z + 3.45), (spacing - 0.1, 0.28, 0.18), ang)
            # Garage upper rolling-door slats catch light at the appropriate 12 cm pitch.
            for h in [0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3.0]:
                frames.cube((p.x, p.y, z + h), (spacing - 0.5, 0.13, 0.018), ang)
        windows.cube((p.x, p.y, z + height - 2.0), (spacing - 0.7, 0.10, 1.55), ang)
        frames.cube((p.x, p.y, z + height - 2.0), (0.10, 0.19, 1.85), ang)
    windows.object(
        name + " glazing and garage openings", [B.MATS["Glass"]], "Pit_buildings"
    )
    frames.object(name + " facade frames", [B.MATS["Armco"]], "Pit_buildings")
    if special:
        frames = Batch()
        for x in range(int(-length / 2), int(length / 2), 9):
            p = c + u * x
            left = p - v * depth / 2
            right = p + v * depth / 2
            apex = p + Vector((0, 0))
            frames.rod(
                (left.x, left.y, z + height + 0.25),
                (apex.x, apex.y, z + height + 2),
                0.085,
            )
            frames.rod(
                (right.x, right.y, z + height + 0.25),
                (apex.x, apex.y, z + height + 2),
                0.085,
            )
        frames.object(name + " roof trusses", [B.MATS["White_paint"]], "Pit_buildings")


def features(section):
    for f in B.SURVEY["features"]:
        t = f["tags"]
        c = centroid(f["points"])
        _, idx, dist = B.TREE.find((*c, 0))
        s = idx * B.STEP
        if s > 5480 and t.get("building"):
            s = 0
        if not section["start_m"] <= s < section["end_m"]:
            continue
        if t.get("building") and dist < 235:
            building(f)
        if t.get("natural") == "sand" and f["closed"]:
            polygon(
                f"Mapped gravel {f['osm_way']}",
                f["points"],
                B.MATS["Gravel"],
                "Runoff",
                0.055,
            )
        if t.get("amenity") == "parking" and f["closed"] and dist < 180:
            polygon(
                f"Paddock hardstanding {f['osm_way']}",
                f["points"],
                B.MATS["Asphalt"],
                "Service_roads",
                0.045,
            )
        if t.get("highway") in ["service", "path", "footway", "track"] and dist < 250:
            if t.get("tunnel") == "yes" or t.get("layer") == "-1":
                continue
            width = 4.2 if t.get("highway") == "service" else 2.1
            B.ribbon(
                f"Service {f['osm_way']}",
                f["points"],
                width,
                B.MATS["Asphalt"] if width > 3 else B.MATS["Soil"],
                "Service_roads",
                0.075,
            )


def forest(section):
    woods = [
        f
        for f in B.SURVEY["features"]
        if f["tags"].get("landuse") == "forest" or f["tags"].get("natural") == "wood"
    ]
    exclusion = [
        f
        for f in B.SURVEY["features"]
        if f["closed"]
        and (
            "building" in f["tags"]
            or f["tags"].get("natural") == "sand"
            or f["tags"].get("amenity") == "parking"
        )
    ]
    road_points = []
    for f in B.SURVEY["features"]:
        if f["tags"].get("highway") in ["service", "raceway", "path", "footway"]:
            for a, b in zip(f["points"], f["points"][1:]):
                d = math.dist(a, b)
                for i in range(max(1, int(d / 4))):
                    t = i / max(1, int(d / 4))
                    road_points.append(
                        (a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t, 0)
                    )
    roads = KDTree(len(road_points))
    for i, p in enumerate(road_points):
        roads.insert(p, i)
    roads.balance()
    masks = []
    for f in woods:
        ps = f["points"]
        masks.append(
            (
                min(p[0] for p in ps),
                max(p[0] for p in ps),
                min(p[1] for p in ps),
                max(p[1] for p in ps),
                f,
            )
        )
    groups = [[] for _ in range(12)]
    undergrowth = Batch()
    total = 0
    # Low-discrepancy candidates give irregular spacing; ecological masks decide occupancy.
    for i in range(1, 112000):
        x = -300 + 1850 * ((i * 0.7548776662466927) % 1)
        y = -950 + 2620 * ((i * 0.5698402909980532) % 1)
        _, idx, d = B.TREE.find((x, y, 0))
        s = idx * B.STEP
        if not section["start_m"] <= s < section["end_m"] or d > 420:
            continue
        side = 1 if (Vector((x, y)) - Vector(B.XY[idx])).dot(B.NORMALS[idx]) > 0 else -1
        if d < barrier_offset(s, side) + 8:
            continue
        found = False
        for xmin, xmax, ymin, ymax, f in masks:
            if (
                xmin <= x <= xmax
                and ymin <= y <= ymax
                and inside(x, y, f["points"])
                and not any(inside(x, y, h) for h in f.get("holes", []))
            ):
                found = True
                break
        if not found:
            continue
        # Broad canopy gaps, thickets, and age mosaics replace constant-density distribution.
        density = (
            0.56
            + 0.23 * math.sin(x / 68) * math.cos(y / 97)
            + 0.15 * math.sin(x / 24 + y / 37)
        )
        selector = (i * 0.41421356237) % 1
        if selector > density:
            continue
        _, _, rd = roads.find((x, y, 0))
        if rd < 7:
            continue
        if any(inside(x, y, f["points"]) for f in exclusion):
            continue
        kind = (i * 7) % 6 + (0 if d < 100 else 6)
        age = 0.65 + 0.43 * ((i * 0.6180339887) % 1)
        if math.sin(x / 103 + y / 59) > 0.85:
            age *= 0.63
        sx = age * (0.88 + 0.22 * ((i * 0.381966) % 1))
        sy = age * (0.86 + 0.27 * ((i * 0.236068) % 1))
        groups[kind].append(
            ((x, y, B.terrain(x, y)), (sx, sy, age), (i * 2.399963) % TAU)
        )
        total += 1
        if d < 75 and i % 3 == 0:
            undergrowth.ellipsoid(
                (x + 1.2, y - 1.0, B.terrain(x, y) + 0.7),
                (1.6, 1.2, 0.85),
                i % 5,
                lon=8,
                lat=4,
                phase=i,
            )
    for kind, placements in enumerate(groups):
        instances(
            section["name"] + f" woodland {kind:02d}",
            bpy.data.objects[f"LIB_Tree_{kind:02d}"],
            placements,
            "Forest",
        )
    undergrowth.object(
        section["name"] + " woodland understory",
        [B.MATS[f"Leaf_{j}"] for j in range(5)],
        "Forest",
        True,
    )
    section["tree_instances"] = total
    tufts = []
    for i in range(
        math.ceil(section["start_m"] / 1.7), math.ceil(section["end_m"] / 1.7)
    ):
        s = i * 1.7
        for side in [-1, 1]:
            frac = (i * 0.6180339 + side * 0.34) % 1
            if frac < 0.27 or any(
                a - 15 < s < b + 15 and sg == side for a, b, sg in KERBS
            ):
                continue
            off = B.width(s) / 2 + 1 + frac * 4
            if any(a < s < b and sg == side for a, b, sg, _, _ in RUNOFF):
                continue
            p, t, _n = B.station_point(s, side * off)
            p.z = B.terrain(p.x, p.y) + 0.01
            if any(
                inside(p.x, p.y, f["points"])
                for f in B.SURVEY["features"]
                if f["tags"].get("natural") == "sand" and f["closed"]
            ):
                continue
            scale = 0.7 + frac * 0.7
            tufts.append((p, (scale, scale, scale), i * 2.3999 % TAU))
    instances(
        section["name"] + " irregular verge tufts",
        bpy.data.objects["LIB_Grass_tuft"],
        tufts,
        "Forest",
    )


def landmarks(section):
    a, b = section["start_m"], section["end_m"]
    if a == 0:
        batch = Batch()
        for s in range(5510, 5785, 4):
            p, t, n = B.station_point(s, -8.2)
            p.z = B.terrain(p.x, p.y) + 0.7
            batch.cube(p, (4.05, 0.55, 1.4), math.atan2(t.y, t.x))
        for s in range(0, 101, 4):
            p, t, n = B.station_point(s, -8.2)
            p.z = B.terrain(p.x, p.y) + 0.7
            batch.cube(p, (4.05, 0.55, 1.4), math.atan2(t.y, t.x))
        batch.object(
            "Pit wall | separate entry and exit",
            [B.MATS["Concrete"]],
            "Safety_barriers",
        )
        # Control line crosses the complete racing surface.
        B.strip("Start finish line", [0, 1], -6, 6, B.MATS["White_paint"], lift=0.013)
        for slot in range(22):
            s = B.L - 12 - slot * 8.0
            off = (-1 if slot % 2 else 1) * 2.6
            ids = [int(s / B.STEP), int(s / B.STEP) + 1]
            B.strip(
                f"Grid {slot + 1:02d}",
                ids,
                off - 0.9,
                off + 0.9,
                B.MATS["White_paint"],
                lift=0.013,
            )
        p, t, n = B.station_point(12)
        z = B.terrain(p.x, p.y)
        ang = math.atan2(t.y, t.x)
        gantry = Batch()
        for side in [-1, 1]:
            q = p + Vector((n.x, n.y, 0)) * side * 11
            gantry.rod((q.x, q.y, z), (q.x, q.y, z + 7), 0.16)
        left = p + Vector((n.x, n.y, 0)) * 11
        right = p - Vector((n.x, n.y, 0)) * 11
        gantry.rod((left.x, left.y, z + 7), (right.x, right.y, z + 7), 0.17)
        gantry.object("Timing gantry", [B.MATS["Armco"]], "Signage")
        B.box(
            "MONZA start bridge",
            p + Vector((0, 0, 6.5)),
            (1.2, 22, 1.3),
            B.MATS["Green_paint"],
            "Signage",
            ang,
        )
        text_object(
            "Start gantry lettering",
            "AUTODROMO NAZIONALE MONZA",
            p + Vector((-t.x * 0.65, -t.y * 0.65, 6.5)),
            0.66,
            ang - math.pi / 2,
        )
        lights = Batch()
        for k in range(5):
            q = p + Vector((n.x, n.y, 0)) * (k - 0.2) * 0.5
            lights.cube((q.x, q.y, z + 5.35), (0.38, 0.28, 0.8), ang, 0)
            for h in [5.15, 5.50]:
                lights.ellipsoid(
                    (q.x - t.x * 0.17, q.y - t.y * 0.17, z + h),
                    (0.12, 0.12, 0.12),
                    1,
                    lon=10,
                    lat=6,
                )
        lights.object(
            "Five start light pairs", [B.MATS["Rubber"], B.MATS["Red_paint"]], "Signage"
        )
    if a < 3300 < b:
        # The disused north banking crosses Serraglio. Clear deck underside exceeds 5 m.
        p, t, n = B.station_point(3298)
        z = B.terrain(p.x, p.y)
        ang = math.atan2(t.y, t.x)
        B.box(
            "Serraglio historic banking underpass",
            p + Vector((0, 0, 6.3)),
            (15, 44, 1.1),
            B.MATS["Concrete"],
            "Bridges",
            ang,
            0.07,
        )
        for side in [-1, 1]:
            q = p + Vector((n.x, n.y, 0)) * side * 16
            B.box(
                "Banking bridge abutment",
                (q.x, q.y, z + 2.8),
                (15, 2.8, 5.6),
                B.MATS["Concrete"],
                "Bridges",
                ang,
                0.06,
            )
    for s in [730, 3960]:
        if not a <= s < b:
            continue
        p, t, n = B.station_point(s)
        z = B.terrain(p.x, p.y)
        ang = math.atan2(t.y, t.x)
        B.box(
            f"Pedestrian bridge {s}",
            (p.x, p.y, z + 6.6),
            (3.2, 32, 0.7),
            B.MATS["Concrete"],
            "Bridges",
            ang,
            0.06,
        )
        for sign in [-1, 1]:
            q = p + Vector((n.x, n.y, 0)) * sign * 14
            B.box(
                "Bridge support",
                (q.x, q.y, z + 3),
                (2, 1, 6),
                B.MATS["Concrete"],
                "Bridges",
                ang,
            )
        B.box(
            "Bridge MONZA fascia",
            (p.x - t.x * 1.7, p.y - t.y * 1.7, z + 7.3),
            (0.15, 31, 1.3),
            B.MATS["Green_paint"],
            "Signage",
            ang,
        )
        text_object(
            "Bridge venue name",
            "MONZA  |  TEMPIO DELLA VELOCITA",
            (p.x - t.x * 1.8, p.y - t.y * 1.8, z + 7.3),
            0.78,
            ang - math.pi / 2,
        )


def build(module, index):
    global B
    B = module
    library()
    sc = bpy.context.scene
    done = json.loads(sc.get("completed_sections", "[]"))
    if index in done:
        raise RuntimeError("Section already built; rebuild foundation to replace it.")
    if index > 0 and index - 1 not in done:
        raise RuntimeError("Build sections in lap order.")
    section = dict(B.SURVEY["sections"][index])
    print("Building section", index, section["name"], flush=True)
    surface(section)
    safety(section)
    features(section)
    signage(section)
    landmarks(section)
    forest(section)
    done.append(index)
    sc["completed_sections"] = json.dumps(done)
    (B.OUT / "qa").mkdir(exist_ok=True)
    (B.OUT / f"qa/section_{index:02d}.json").write_text(
        json.dumps(section, indent=2) + "\n"
    )
    B.save()
    B.render(index)


def historic_oval(module):
    global B
    B = module
    if bpy.data.objects.get("Historic oval survey curves"):
        return
    from survey_monza import smooth

    for f in B.SURVEY["features"]:
        name = f["tags"].get("name", "")
        if f["tags"].get("highway") != "raceway" or not (
            "Sopraelevata" in name or "anello alta" in name
        ):
            continue
        ps = smooth(f["points"], False, 2.0)
        vs = []
        faces = []
        ribs = Batch()
        "Sopraelevata" in name or f["osm_way"] == 34404729
        for i, p in enumerate(ps):
            prev = ps[max(0, i - 1)]
            nex = ps[min(len(ps) - 1, i + 1)]
            t = Vector((nex[0] - prev[0], nex[1] - prev[1])).normalized()
            n = Vector((-t.y, t.x))
            if "Nord" in name or f["osm_way"] == 34404729:
                strength = max(0, min(1, (p[1] - 300) / 240))
            elif "Sud" in name:
                strength = max(0, min(1, (-p[1] - 560) / 230))
            else:
                strength = 0
            _, idx, d = B.TREE.find((p[0], p[1], 0))
            underpass = math.exp(-(((idx * B.STEP - 3300) / 36) ** 2)) * max(
                0, 1 - d / 70
            )
            mid = B.terrain(*p) + 0.10 + 4.3 * strength + underpass * 2.8
            for j in range(7):
                off = -6 + j * 2
                xy = Vector(p) + n * off
                vs.append(
                    (
                        xy.x,
                        xy.y,
                        mid
                        + off
                        * math.tan(math.radians(27))
                        * strength
                        * (1 - underpass * 0.85),
                    )
                )
            if i and i % 5 == 0 and strength > 0.4:
                outer = Vector(p) + n * 5.7
                low = B.terrain(outer.x, outer.y)
                high = mid + 5.7 * math.tan(math.radians(27)) * strength
                # Historic concrete support ribs, grounded on the same park terrain.
                if d > 22:
                    ribs.cube(
                        (outer.x, outer.y, (low + high) / 2),
                        (0.42, 1.7, high - low),
                        math.atan2(t.y, t.x),
                    )
        for i in range(len(ps) - 1):
            for j in range(6):
                a = i * 7 + j
                faces.append((a, a + 7, a + 8, a + 1))
        ob = B.mesh(
            f"Historic oval {f['osm_way']}",
            vs,
            faces,
            B.MATS["Concrete"],
            "Historic_oval",
        )
        ob["bank_angle_status"] = (
            "inferred 27 degree visible cross-section, not a measured bank profile"
        )
        ribs.object(
            f"Banking ribs {f['osm_way']}", [B.MATS["Concrete"]], "Historic_oval"
        )
        B.curve(
            f"OVAL | {f['osm_way']}",
            [(p[0], p[1], B.terrain(*p)) for p in ps],
            "Survey_curves",
        )
    ob = bpy.data.objects.new("Historic oval survey curves", None)
    B.collection("Historic_oval").objects.link(ob)


def finishing_details(module):
    global B
    B = module
    if bpy.data.objects.get("Impact tyre stacks"):
        southern_details(module)
        return
    tyre = Batch()
    for layer in range(4):
        j = len(tyre.v)
        for a in range(20):
            t = a * TAU / 20
            for b in range(10):
                p = b * TAU / 10
                r = 0.245 + 0.105 * math.cos(p)
                tyre.v.append(
                    (
                        r * math.cos(t),
                        r * math.sin(t),
                        layer * 0.24 + 0.12 + 0.115 * math.sin(p),
                    )
                )
        for a in range(20):
            for b in range(10):
                tyre.f.append(
                    (
                        j + a * 10 + b,
                        j + ((a + 1) % 20) * 10 + b,
                        j + ((a + 1) % 20) * 10 + (b + 1) % 10,
                        j + a * 10 + (b + 1) % 10,
                    )
                )
                tyre.m.append(0)
    ob = tyre.object("LIB_Tyre_stack", [B.MATS["Rubber"]], "Asset_library", True)
    ob.hide_render = True
    placements = []
    for middle, side in [(1850, -1), (2250, 1), (2570, 1), (3650, -1), (4900, 1)]:
        for j in range(45):
            s = middle + (j - 22) * 0.68
            p, _t, _n = B.station_point(s, side * (barrier_offset(s, side) - 1.0))
            p.z = B.terrain(p.x, p.y) + 0.01
            placements.append((p, (1, 1, 1), 0))
    instances("Impact tyre stacks", ob, placements, "Safety_barriers")
    pole = Batch()
    pole.rod((0, 0, 0), (0, 0, 8), 0.08, sides=8, tip=0.043)
    pole.rod((0, 0, 8), (0, 1, 8.2), 0.043)
    pole.cube((0, 1, 8.2), (0.45, 0.65, 0.15), mat=1)
    ob = pole.object(
        "LIB_Paddock_light", [B.MATS["Armco"], B.MATS["Glass"]], "Asset_library"
    )
    ob.hide_render = True
    placements = []
    for s in [5490, 5580, 5660, 5740, 90, 170, 280]:
        p, t, _n = B.station_point(s, 52)
        p.z = B.terrain(p.x, p.y)
        placements.append((p, (1, 1, 1), math.atan2(t.y, t.x)))
    instances("Paddock and main stand light poles", ob, placements, "Signage")
    # Pit-lane working apron behind the fast lane, clipped to the mapped pit complex.
    pit = next(f for f in B.SURVEY["features"] if f["osm_way"] == 38168747)
    apron = []
    for p in pit["points"]:
        _, i, _d = B.TREE.find((p[0], p[1], 0))
        if i * B.STEP > 5480 or i * B.STEP < 70:
            apron.append(p)
    if len(apron) > 2:
        B.ribbon(
            "Pit working apron", apron, 15.0, B.MATS["Asphalt"], "Service_roads", 0.021
        )
    southern_details(module)


def southern_details(module):
    global B
    B = module
    if bpy.data.objects.get("Mapped paddock parking bay markings"):
        return
    # Thin shelterbelts visible in the south-venue aerial are absent from OSM forest areas.
    # Treat them explicitly as image-inferred planting, never as surveyed individual trees.
    trees = [[] for _ in range(6)]
    exclusions = [
        f["points"]
        for f in B.SURVEY["features"]
        if f["closed"]
        and (f["tags"].get("building") or f["tags"].get("amenity") == "parking")
    ]
    for k in range(92):
        s = 4000 + k * 8.1
        for row in range(2):
            off = 32 + row * 9 + 2.5 * math.sin(k * 1.43)
            p, _t, _n = B.station_point(s, off)
            if any(inside(p.x, p.y, poly) for poly in exclusions):
                continue
            p.z = B.terrain(p.x, p.y)
            scale = 0.83 + 0.17 * math.sin(k * 0.74 + row)
            trees[(k + row) % 6].append((p, (scale, scale, scale), k * 2.39))
    for i, points in enumerate(trees):
        ob = instances(
            f"Back straight aerial-inferred tree belt {i}",
            bpy.data.objects[f"LIB_Tree_{i:02d}"],
            points,
            "Forest",
        )
        if ob:
            ob["source_confidence"] = (
                "Approximate shelterbelt from south-venue aerial; individual trees unverified"
            )
    markings = Batch()
    for f in B.SURVEY["features"]:
        if f["tags"].get("amenity") != "parking" or not f["closed"]:
            continue
        c, u, v, length, depth = footprint_axes(f)
        _, _idx, dist = B.TREE.find((c.x, c.y, 0))
        if dist > 180:
            continue
        for row in range(max(1, int(depth / 15))):
            for bay in range(max(1, int(length / 2.7))):
                p = c + u * (-length / 2 + bay * 2.7) + v * (-depth / 2 + row * 15 + 3)
                q = p + v * 5
                if inside(p.x, p.y, f["points"]) and inside(q.x, q.y, f["points"]):
                    mid = (p + q) / 2
                    markings.cube(
                        (mid.x, mid.y, B.terrain(mid.x, mid.y) + 0.051),
                        (0.09, 5, 0.004),
                        math.atan2(u.y, u.x),
                    )
    markings.object(
        "Mapped paddock parking bay markings", [B.MATS["White_paint"]], "Service_roads"
    )
