"""The registered red Les Bruyères core and its separate lower planted estate."""
from __future__ import annotations

import math
import random
import struct
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, norm, sub, world
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points

from venues.monaco_foreground_dataclasses import (
    XY,
    BruyeresAudit,
    BruyeresFrame,
    BruyeresGardenAudit,
    BruyeresSpec,
    GardenPrecisionAction,
    GardenPrecisionFace,
    GardenSharedEdge,
)

KIND = 'Building_MonacoBruyeres'
GARDEN_KIND = 'Building_MonacoBruyeresGarden'
RED = 'MonacoBruyeresRed'
STONE = 'MonacoBruyeresStone'
WOOD = 'MonacoBruyeresWood'

def frame(spec: BruyeresSpec) -> BruyeresFrame:
    a, b = spec.front_endpoints_xy_m
    length = math.dist(a, b)
    t = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    return BruyeresFrame(a, t, (t[1], -t[0]), length)


def point(f: BruyeresFrame, u: float, v: float, z: float) -> Point:
    return f.origin[0] + f.tangent[0] * u + f.outward[0] * v, f.origin[1] + f.tangent[1] * u + f.outward[1] * v, z


def facade(scene: MeshScene, f: BruyeresFrame, shape: Polygon, material: str,
           depth: float = 0) -> None:
    for tri in constrained_delaunay_triangles(shape).geoms:
        coordinates = list(orient(tri, 1).exterior.coords)[:3]
        vertices = [point(f, u, depth, z) for u, z in coordinates]
        scene.triangle(KIND, material, vertices[0], vertices[1], vertices[2])


def beam(scene: MeshScene, f: BruyeresFrame, material: str, a: Point, b: Point,
         width: float, depth: float | None = None) -> None:
    scene.beam(KIND, material, point(f, *a), point(f, *b), width, depth)


def arch(center: float, width: float, low: float, height: float,
         arched: bool) -> tuple[XY, ...]:
    left, right = center - width / 2, center + width / 2
    if not arched:
        return ((left, low), (right, low), (right, low + height), (left, low + height))
    radius, spring = width / 2, low + height - width / 2
    return ((left, low), (right, low),
            *((center + radius * math.cos(i * math.pi / 24),
               spring + radius * math.sin(i * math.pi / 24)) for i in range(25)))


def opening(scene: MeshScene, f: BruyeresFrame, contour: tuple[XY, ...], recess: float,
            shutter_fraction: float) -> None:
    shape = Polygon(contour)
    facade(scene, f, shape, 'Glass', -recess)
    for a, b in pairwise((*contour, contour[0])):
        scene.quad(KIND, STONE, point(f, a[0], 0, a[1]), point(f, b[0], 0, b[1]),
                   point(f, b[0], -recess, b[1]), point(f, a[0], -recess, a[1]))
        beam(scene, f, STONE, (a[0], .055, a[1]), (b[0], .055, b[1]), .13, .15)
    x0, z0, x1, z1 = shape.bounds
    if shutter_fraction:
        shutter_low = z1 - (z1 - z0) * shutter_fraction
        shutter = shape.intersection(box(x0 - .01, shutter_low, x1 + .01, z1 + .01))
        if not isinstance(shutter, Polygon):
            raise ValueError('The photographed roller shutter must fit its aperture')
        facade(scene, f, shutter, STONE, -recess + .025)
        z = shutter_low + .06
        while z < z1 - .05:
            section = shutter.intersection(box(x0, z - .009, x1, z + .009))
            if isinstance(section, Polygon) and not section.is_empty:
                facade(scene, f, section, 'White', -recess + .035)
            z += .13
    center = (x0 + x1) / 2
    beam(scene, f, WOOD, (center, -.14, z0), (center, -.14, z1), .08)
    beam(scene, f, WOOD, (x0, -.14, z0 + 1.0), (x1, -.14, z0 + 1.0), .065)
    beam(scene, f, STONE, (x0 - .25, .13, z0 - .10), (x1 + .25, .13, z0 - .10), .14, .25)
    if len(contour) == 4:
        beam(scene, f, STONE, (x0 - .22, .12, z1 + .17), (x1 + .22, .12, z1 + .17), .13, .23)
        beam(scene, f, STONE, (center, .12, z1 + .18), (center, .12, z1 + .35), .22, .22)


def baluster(scene: MeshScene, f: BruyeresFrame, u: float, v: float, z: float) -> None:
    sections = ((0, .085), (.12, .085), (.22, .055), (.42, .105), (.61, .055), (.78, .065), (.84, .085))
    sides = 8
    for (low, r0), (high, r1) in pairwise(sections):
        for side in range(sides):
            a, b = side * 2 * math.pi / sides, (side + 1) * 2 * math.pi / sides
            scene.quad(KIND, STONE, point(f, u + r0 * math.cos(b), v + r0 * math.sin(b), z + low),
                       point(f, u + r0 * math.cos(a), v + r0 * math.sin(a), z + low),
                       point(f, u + r1 * math.cos(a), v + r1 * math.sin(a), z + high),
                       point(f, u + r1 * math.cos(b), v + r1 * math.sin(b), z + high))


def rail(scene: MeshScene, f: BruyeresFrame, path: tuple[XY, ...], z: float,
         stone: bool) -> None:
    for a, b in pairwise(path):
        for dz, thickness in ((.06, .15 if stone else .035), (.99, .14 if stone else .045)):
            beam(scene, f, STONE if stone else 'Steel', (*a, z + dz), (*b, z + dz), thickness)
    total = sum(math.dist(a, b) for a, b in pairwise(path))
    count = max(2, round(total / (.40 if stone else .19)))
    distances = [0.0]
    for a, b in pairwise(path):
        distances.append(distances[-1] + math.dist(a, b))
    for i in range(count + 1):
        at = total * i / count
        j = next((j for j in range(len(path) - 1) if distances[j + 1] >= at), len(path) - 2)
        a, b = path[j], path[j + 1]
        t = (at - distances[j]) / (distances[j + 1] - distances[j])
        u, v = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        if stone:
            baluster(scene, f, u, v, z + .12)
        else:
            beam(scene, f, 'Steel', (u, v, z + .10), (u, v, z + .98), .025)
            if i < count:
                angle_points = tuple((u + .09 * math.sin(j * math.pi / 8), v,
                                      z + .55 + .28 * math.cos(j * math.pi / 8)) for j in range(17))
                for first, last in pairwise(angle_points):
                    beam(scene, f, 'Steel', first, last, .018)


def balcony(scene: MeshScene, f: BruyeresFrame, center: float, halfwidth: float,
            depth: float, z: float, curved: bool, stone: bool, corbels: bool = True) -> None:
    path = (tuple((center + halfwidth * math.cos(math.pi - i * math.pi / 36),
                   -.08 + (depth + .08) * math.sin(math.pi - i * math.pi / 36)) for i in range(37)) if curved
            else ((center - halfwidth, -.08), (center - halfwidth, depth),
                  (center + halfwidth, depth), (center + halfwidth, -.08)))
    plan = Polygon(path)
    for tri in constrained_delaunay_triangles(plan).geoms:
        points = list(orient(tri, -1).exterior.coords)[:3]
        top = [point(f, p[0], p[1], z) for p in points]
        bottom = [point(f, p[0], p[1], z - .22) for p in points]
        scene.triangle(KIND, STONE, top[0], top[1], top[2])
        scene.triangle(KIND, STONE, bottom[2], bottom[1], bottom[0])
    for a, b in pairwise(path):
        scene.quad(KIND, STONE, point(f, *a, z - .22), point(f, *b, z - .22),
                   point(f, *b, z), point(f, *a, z))
        beam(scene, f, STONE, (*a, z - .26), (*b, z - .26), .12, .16)
    rail(scene, f, path, z + .03, stone)
    if not curved and corbels:
        for u in (center - halfwidth + .36, center + halfwidth - .36):
            profile = ((u - .17, z - .22), (u + .17, z - .22),
                       (u + .10, z - .75), (u - .08, z - .78))
            for a, b in pairwise((*profile, profile[0])):
                scene.quad(KIND, STONE, point(f, a[0], .1, a[1]), point(f, b[0], .1, b[1]),
                           point(f, b[0], depth * .65, b[1]), point(f, a[0], depth * .65, a[1]))


def core_plan(spec: BruyeresSpec) -> Polygon:
    core = Polygon(spec.owner_xy_m).intersection(Polygon(spec.roof_xy_m))
    if not isinstance(core, Polygon) or core.is_empty:
        raise ValueError('Measured Les Bruyères upper core must be one valid owner intersection')
    return orient(core, 1)


def emit_bruyeres(scene: MeshScene, spec: BruyeresSpec,
                  support: Callable[[float, float], float]) -> BruyeresAudit:
    core, f = core_plan(spec), frame(spec)
    if f.outward[1] > -.99 or spec.floor_count != 4:
        raise ValueError('The photographed four-band south elevation changed')
    ring = tuple((x, y) for x, y in core.exterior.coords[:-1])
    base, roof = spec.core_base_relative_m, spec.main_roof_relative_m
    floor = (roof - base) / spec.floor_count
    centers = (f.span_m * .17, f.span_m * .50, f.span_m * .83)
    bay_frames: dict[int, tuple[BruyeresFrame, float]] = {}
    opening_count = 0
    for a, b in pairwise((*ring, ring[0])):
        span = math.dist(a, b)
        tangent = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        outward = tangent[1], -tangent[0]
        front_edge = (outward[0] * f.outward[0] + outward[1] * f.outward[1] > .99
                      and all(abs((p[0] - f.origin[0]) * f.outward[0]
                                  + (p[1] - f.origin[1]) * f.outward[1]) < 1 for p in (a, b)))
        if front_edge:
            local = BruyeresFrame(a, tangent, outward, span)
            holes: list[tuple[XY, ...]] = []
            shutters: list[float] = []
            for bay, center in enumerate(centers):
                target = point(f, center, 0, 0)
                u = (target[0] - a[0]) * tangent[0] + (target[1] - a[1]) * tangent[1]
                if not 0 < u < span:
                    continue
                bay_frames[bay] = local, u
                for level in range(spec.floor_count):
                    holes.append(arch(u, 2.05 if bay != 1 else 3.2,
                                      base + level * floor + .30, 2.65, level == 3))
                    shutter = 0.0
                    if bay != 1 and level in (1, 3):
                        shutter = 1.0
                    elif bay == 2 and level == 0:
                        shutter = .25
                    shutters.append(shutter)
            wall = Polygon(((0, base), (span, base), (span, roof), (0, roof)), holes)
            if not wall.is_valid:
                raise ValueError('Bruyères apertures must be contained in the actual clipped front edges')
            facade(scene, local, wall, RED)
            for contour, shutter in zip(holes, shutters):
                opening(scene, local, contour, spec.recess_m, shutter)
            opening_count += len(holes)
            for level in range(spec.floor_count):
                z = base + (level + 1) * floor + .08
                beam(scene, local, STONE, (0, .12, z), (span, .12, z), .15, .24)
                frieze = box(0, z - .63, span, z - .05)
                facade(scene, local, frieze, STONE, .025)
        else:
            scene.quad(KIND, RED, (*a, base), (*b, base), (*b, roof), (*a, roof))
        low_a, low_b = min(base - .12, support(*a) - .12), min(base - .12, support(*b) - .12)
        scene.quad(KIND, STONE, (*a, low_a), (*b, low_b), (*b, base), (*a, base))
    if set(bay_frames) != {0, 1, 2} or opening_count != 12:
        raise ValueError('All three photographed bays must register to the qualified front')
    for tri in constrained_delaunay_triangles(core).geoms:
        points = list(orient(tri, 1).exterior.coords)[:3]
        top = [(x, y, roof) for x, y in points]
        scene.triangle(KIND, STONE, top[0], top[1], top[2])
    for level in range(spec.floor_count):
        z = base + level * floor + .18
        center_frame, center_u = bay_frames[1]
        balcony(scene, center_frame, center_u, spec.curved_balcony_width_m / 2,
                spec.curved_balcony_depth_m, z, True, True)
        for side in (0, 2):
            side_frame, side_u = bay_frames[side]
            if level == 3:
                rail(scene, side_frame, ((side_u - 1.08, .30), (side_u + 1.08, .30)),
                     z + .12, False)
            else:
                balcony(scene, side_frame, side_u, spec.side_balcony_width_m / 2,
                        spec.side_balcony_depth_m, z, False, level < 2)
        offsets = (-2.30, 2.30) if level < 3 else (-2.30, -2.07, 2.07, 2.30)
        for offset in offsets:
            u = center_u + offset
            beam(scene, center_frame, STONE, (u, .40, z + .10), (u, .40, z + floor - .20), .15)
            beam(scene, center_frame, STONE, (u, .40, z + floor - .33), (u, .40, z + floor - .15), .25)
    balcony(scene, center_frame, center_u, 2.95, 1.5, roof, False, True, corbels=False)
    for a, b in pairwise((*ring, ring[0])):
        span = math.dist(a, b)
        if span < .3:
            continue
        local = BruyeresFrame(a, ((b[0] - a[0]) / span, (b[1] - a[1]) / span),
                              ((b[1] - a[1]) / span, -(b[0] - a[0]) / span), span)
        if a == center_frame.origin and math.dist(local.tangent, center_frame.tangent) < 1e-6:
            for lo, hi in ((0, center_u - 2.95), (center_u + 2.95, span)):
                if hi - lo > .2:
                    rail(scene, local, ((lo, .06), (hi, .06)), roof + .03, True)
        else:
            rail(scene, local, ((0, .06), (span, .06)), roof + .03, True)
    return BruyeresAudit(spec.osm_id, Polygon(spec.owner_xy_m).area, core.area,
                        Polygon(spec.owner_xy_m).difference(core).area, base, spec.core_base_uncertainty_m, roof,
                        roof + spec.datum_m, spec.floor_count, opening_count, 4, 6,
                        tuple((*p, roof) for p in ring), (
                            'Four photographed bands and the 11.3 m IGN ground anchor determine estimated floor thresholds.',
                            'Roof maximum 30.5 m is not used as a uniform roof or an invented enclosed belvedere.',
                            'Balcony widths, projection, recesses and columns are photo-based metric estimates.',
                            'The photographed flat upper canopy and paired top columns are separate estimated overhangs, not a measured roof-body expansion.',
                            'Pale roller shutters are photographed details; their current closure fractions are estimated movable states.',
                            'Sub-metre source/owner front-edge offsets remain clipped rather than expanding the body over the mapped estate.',
                            'Side and rear openings, lower garage footprint and enclosed roof pavilion remain held.',
                            'The lower garden must receive a separate bounded support/landscape closure before integration.',
                        ))


def emit_garden(scene: MeshScene, spec: BruyeresSpec, boundary_xy: tuple[XY, ...],
                old_surface: Callable[[float, float], float]) -> BruyeresGardenAudit:
    estate = Polygon(boundary_xy)
    core = core_plan(spec)
    garden = estate.difference(core)
    components = (garden,) if isinstance(garden, Polygon) else tuple(garden.geoms)
    if not estate.is_valid or estate.symmetric_difference(Polygon(spec.owner_xy_m)).area > .03:
        raise ValueError('Garden must stay within the exact old packed owner boundary')
    if any(not isinstance(p, Polygon) for p in components):
        raise ValueError('Lower-estate remainder must contain polygons only')
    segments = 0
    triangles = 0
    max_join = 0.0
    minimum_burial = math.inf
    precision_faces: list[GardenPrecisionFace] = []
    primitive_rejections = 0
    shared_body_edges: list[GardenSharedEdge] = []

    def ulp(value: float) -> float:
        bits = struct.unpack('<I', struct.pack('<f', abs(value)))[0]
        return struct.unpack('<f', struct.pack('<I', bits + 1))[0] - abs(value)

    def packed(point: Point) -> Point:
        value = struct.unpack('<3f', struct.pack('<3f', *world(point)))
        return -value[1] / 100, -value[0] / 100, value[2] / 100

    def height(x: float, y: float) -> float:
        p = ShapePoint(x, y)
        outer = nearest_points(p, estate.boundary)[1]
        outer_distance, core_distance = p.distance(estate.boundary), p.distance(core)
        toe = old_surface(outer.x, outer.y) + .95
        if outer_distance + core_distance < 1e-5:
            return toe
        weight = outer_distance / (outer_distance + core_distance)
        return toe * (1 - weight) + spec.core_base_relative_m * weight

    def triangle(points: tuple[XY, XY, XY], depth: int = 0) -> None:
        nonlocal triangles, primitive_rejections
        a, b, c = points
        lengths = (math.dist(a, b), math.dist(b, c), math.dist(c, a))
        longest = max(lengths)
        if longest > 1.1 and depth < 12:
            edge = lengths.index(longest)
            first, last, other = ((a, b, c), (b, c, a), (c, a, b))[edge]
            middle = ((first[0] + last[0]) / 2, (first[1] + last[1]) / 2)
            triangle((first, middle, other), depth + 1)
            triangle((middle, last, other), depth + 1)
            return
        vertices = [(p[0], p[1], height(*p)) for p in points]
        source_normal = cross(sub(vertices[1], vertices[0]), sub(vertices[2], vertices[0]))
        if sum(v * v for v in source_normal) < 1e-12:
            primitive_rejections += 1
            return
        encoded = tuple(packed(v) for v in vertices)
        encoded_normal = cross(sub(encoded[1], encoded[0]), sub(encoded[2], encoded[0]))
        uv = tuple((p[0] / 8, p[1] / 8) for p in encoded)
        normals: tuple[Point, ...] | None = None
        if encoded_normal[2] <= 0 or sum(a * b for a, b in zip(encoded_normal, source_normal)) <= 0:
            width = source_normal[2] / longest
            xy_bound = max(math.hypot(ulp(world(v)[0]), ulp(world(v)[1])) / 100 for v in encoded)
            xy_error = max(math.dist(a[:2], b[:2]) for a, b in zip(vertices, encoded))
            z_error = max(abs(a[2] - b[2]) for a, b in zip(vertices, encoded))
            if width > 2 * xy_bound or xy_error > .501 * xy_bound or any(
                    abs(a[2] - b[2]) > .501 * ulp(world(b)[2]) / 100 for a, b in zip(vertices, encoded)):
                raise ValueError('A resolved garden top changed orientation or exceeded Float32 precision')
            area_3d = math.sqrt(sum(v * v for v in encoded_normal)) / 2
            collapsed = area_3d == 0
            if encoded_normal[2] == 0 and not collapsed:
                raise ValueError('A noncollapsed vertical garden sliver requires separate classification')
            action: GardenPrecisionAction = 'normal_aligned'
            if collapsed:
                action = 'collapsed'
            elif encoded_normal[2] < 0:
                action = 'reoriented'
            precision_faces.append(GardenPrecisionFace(
                action,
                (vertices[0], vertices[1], vertices[2]), (encoded[0], encoded[1], encoded[2]),
                width, xy_bound, xy_error, z_error, source_normal[2] / 2, area_3d))
            if collapsed:
                return
            if encoded_normal[2] < 0:
                vertices[1], vertices[2] = vertices[2], vertices[1]
                uv = (uv[0], uv[2], uv[1])
                encoded_normal = (-encoded_normal[0], -encoded_normal[1], -encoded_normal[2])
            normal = norm(encoded_normal)
            normals = (normal, normal, normal)
        scene.triangle(GARDEN_KIND, 'MonacoIvyGround', vertices[0], vertices[1], vertices[2], uv, normals)
        triangles += 1

    def split_edge(a: XY, b: XY) -> tuple[tuple[XY, XY], ...]:
        dx, dy = b[0] - a[0], b[1] - a[1]
        squared = dx * dx + dy * dy
        cuts = {0., 1.}
        for x, y in core.exterior.coords[:-1]:
            t = ((x - a[0]) * dx + (y - a[1]) * dy) / squared
            if not 0 < t < 1:
                continue
            p = a[0] + t * dx, a[1] + t * dy
            encoded = packed((*p, 0))
            bound = math.hypot(ulp(world(encoded)[0]), ulp(world(encoded)[1])) / 100
            if math.dist(p, (x, y)) <= 2 * bound:
                cuts.add(t)
        ordered = sorted(cuts)
        return tuple((((a[0] + lo * dx), (a[1] + lo * dy)),
                      ((a[0] + hi * dx), (a[1] + hi * dy)))
                     for lo, hi in pairwise(ordered))

    for component in components:
        if not isinstance(component, Polygon):
            continue
        component = orient(component, 1)
        for face in constrained_delaunay_triangles(component).geoms:
            coordinates = list(orient(face, 1).exterior.coords)[:3]
            triangle(((coordinates[0][0], coordinates[0][1]),
                      (coordinates[1][0], coordinates[1][1]), (coordinates[2][0], coordinates[2][1])))
        ring = tuple((x, y) for x, y in component.exterior.coords[:-1])
        edges: list[tuple[XY, XY]] = []
        for a, b in pairwise((*ring, ring[0])):
            edges.extend(split_edge(a, b))
        for a, b in edges:
            samples = (a, b, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            xy_bound = max(math.hypot(ulp(world(packed((*p, 0)))[0]),
                                      ulp(world(packed((*p, 0)))[1])) / 100 for p in samples)
            distance = max(ShapePoint(*p).distance(core.boundary) for p in samples)
            if distance <= 2 * xy_bound:
                shared_body_edges.append(GardenSharedEdge((a, b), distance, xy_bound, distance >= 1e-6))
                for p in (a, b):
                    if ShapePoint(*p).distance(estate.boundary) > 1e-5:
                        max_join = max(max_join, abs(height(*p) - spec.core_base_relative_m))
                continue
            span = math.dist(a, b)
            count = max(1, math.ceil(span / .70))
            for i in range(count):
                first = (a[0] + (b[0] - a[0]) * i / count, a[1] + (b[1] - a[1]) * i / count)
                last = (a[0] + (b[0] - a[0]) * (i + 1) / count, a[1] + (b[1] - a[1]) * (i + 1) / count)
                low_a, low_b = old_surface(*first) - .10, old_surface(*last) - .10
                top_a, top_b = height(*first), height(*last)
                scene.quad(GARDEN_KIND, STONE, (*first, low_a), (*last, low_b), (*last, top_b), (*first, top_a))
                scene.beam(GARDEN_KIND, STONE, (*first, top_a + .04), (*last, top_b + .04), .16, .10)
                minimum_burial = min(minimum_burial, old_surface(*first) - low_a, old_surface(*last) - low_b)
                segments += 1
    planted = garden.intersection(Polygon(((24, 283), (35, 283), (35, 292.8), (24, 292.8))))
    rng = random.Random(94400108)
    # Photos establish dense planting; these positions and stem details are estimates.
    for i in range(220):
        x, y = rng.uniform(25.4, 34.2), rng.uniform(284.6, 291.5)
        if not planted.buffer(-.25).covers(ShapePoint(x, y)):
            continue
        z = height(x, y)
        stem_height = rng.uniform(1.8, 3.6)
        scene.beam(GARDEN_KIND, 'Trunk', (x, y, z - .05), (x, y, z + stem_height), .025)
        for level in range(6):
            theta = rng.random() * math.tau
            dz = stem_height * (.24 + .14 * level)
            length = rng.uniform(.35, .70)
            tip = (x + math.cos(theta) * length, y + math.sin(theta) * length, z + dz + .12)
            mid: Point = ((x + tip[0]) / 2, (y + tip[1]) / 2, z + dz + .15)
            side = (-math.sin(theta) * .10, math.cos(theta) * .10)
            scene.triangle(GARDEN_KIND, 'Leaves', (x, y, z + dz), (mid[0] + side[0], mid[1] + side[1], mid[2]), tip)
            scene.triangle(GARDEN_KIND, 'Leaves', tip, (mid[0] - side[0], mid[1] - side[1], mid[2]), (x, y, z + dz))
    for i, (x, y) in enumerate((
            (27.0, 286.4), (30.0, 286.4), (33.0, 286.4),
            (27.0, 289.7), (30.0, 289.7), (33.0, 289.7))):
        shrub_height = 3.0 + .18 * (i % 3)
        if not planted.covers(ShapePoint(x, y).buffer(shrub_height * .41)):
            raise ValueError('Photographed understory estimate escaped its lower planted domain')
        scene.broadleaf((x, y, height(x, y) - shrub_height * .46), shrub_height, 94400 + i)
    palms = ((27.5, 285.7), (32.5, 285.9))
    for i, (x, y) in enumerate(palms):
        if not planted.covers(ShapePoint(x, y)):
            raise ValueError('Private garden palm estimate escaped the planted lower estate')
        scene.palm((x, y, height(x, y)), 9.0 + i * 1.5)
    return BruyeresGardenAudit(garden.area, triangles, segments, len(boundary_xy), max_join,
                              minimum_burial, palms, tuple(precision_faces), primitive_rejections,
                              tuple(shared_body_edges), (
                                  'The .95 m raised garden toe and transition to the 11.3 m absolute core threshold are photo-based support estimates.',
                                  'Exact old outside floor planes and native ground remain fixed; this fills only the previous incorrect body void.',
                                  'Dense lower planting and palms are source-observed; exact instances, species and heights are estimated.',
                                  'A detailed enclosed garage remains held: its east-gap footprint is not registered to this literal estate.',
                              ))
