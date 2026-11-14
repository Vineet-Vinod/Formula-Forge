"""low mall, curved glazing and original roof-boulevard reconstruction."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, norm
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union

from venues.jeddah_context_dataclasses import LocalFrame, MallArchitecture
from venues.jeddah_context_shapes import facade_bays, local, rectangle, skin, walls

XY = tuple[float, float]


def catmull(a: XY, b: XY, c: XY, d: XY, t: float) -> XY:
    out = []
    for axis in range(2):
        value = .5 * ((2 * b[axis]) + (-a[axis] + c[axis]) * t
                      + (2 * a[axis] - 5 * b[axis] + 4 * c[axis] - d[axis]) * t * t
                      + (-a[axis] + 3 * b[axis] - 3 * c[axis] + d[axis]) * t * t * t)
        out.append(value)
    return out[0], out[1]


def curved_front(site: Polygon, first: int, last: int, inset: float) -> tuple[Polygon, list[XY]]:
    ring = list(site.exterior.coords)[:-1]
    curve = []
    for index in range(first, last):
        count = math.ceil(math.dist(ring[index], ring[index + 1]))
        for sample in range(count):
            curve.append(catmull(ring[index - 1], ring[index], ring[index + 1],
                                 ring[(index + 2) % len(ring)], sample / count))
    curve.append(ring[last])
    center = site.representative_point()
    moved: list[XY] = []
    clearance = site.buffer(-inset)
    for point in curve:
        distance = math.dist(point, (center.x, center.y))
        candidate = ShapePoint(point[0] + (center.x - point[0]) * inset / distance,
                               point[1] + (center.y - point[1]) * inset / distance)
        if not clearance.covers(candidate):
            candidate = nearest_points(clearance, candidate)[0]
        value = candidate.x, candidate.y
        if not moved or math.dist(moved[-1], value) > 1e-6:
            moved.append(value)
    if any(not site.buffer(-.2).covers(ShapePoint(p)) for p in moved):
        raise ValueError('The smooth mall frontage must stay inside its retained outer envelope')
    body = Polygon([*ring[:first], *moved, *ring[last + 1:]])
    if not body.is_valid or body.difference(site).area > 1e-8:
        raise ValueError('The curved main mall body escaped its retained envelope')
    return body, moved


def validate_service_clearance(body: Polygon, config: MallArchitecture,
                               geo: Callable[[float, float], XY]) -> None:
    for road in config.service_roads:
        line = LineString([geo(lat, lon) for lon, lat in road.path_wgs84])
        required = road.estimated_width_m / 2 + road.facade_clearance_m + 1.8 + .2
        if body.distance(line) < required:
            raise ValueError(f'The bowed mall facade obstructs the estimated service-road reserve: {road.osm_id}')


def display_screen(scene: MeshScene, points: list[XY], street: float, top: float) -> None:
    bottom = street + 2.7
    steps = 14

    def vertex(index: int, fraction: float) -> tuple[Point, Point]:
        previous, following = points[max(0, index - 1)], points[min(len(points) - 1, index + 1)]
        span = math.dist(previous, following)
        tx, ty = (following[0] - previous[0]) / span, (following[1] - previous[1]) / span
        nx, ny = -ty, tx
        bulge = 1.8 * math.sin(math.pi * fraction)
        derivative = 1.8 * math.pi * math.cos(math.pi * fraction) / (top - bottom)
        return ((points[index][0] + nx * bulge, points[index][1] + ny * bulge,
                 bottom + (top - bottom) * fraction), norm((nx, ny, -derivative)))

    for index in range(len(points) - 1):
        for row in range(steps):
            a, na = vertex(index, row / steps)
            b, nb = vertex(index + 1, row / steps)
            c, nc = vertex(index + 1, (row + 1) / steps)
            d, nd = vertex(index, (row + 1) / steps)
            scene.triangle('Building_MallCurvedGlazedScreen', 'Glass', b, a, d, normals=(nb, na, nd))
            scene.triangle('Building_MallCurvedGlazedScreen', 'Glass', b, d, c, normals=(nb, nd, nc))
        if index % 5 == 0:
            previous, following = points[max(0, index - 1)], points[min(len(points) - 1, index + 1)]
            span = math.dist(previous, following)
            tx, ty = (following[0] - previous[0]) / span, (following[1] - previous[1]) / span
            for row in range(steps):
                a, _normal = vertex(index, row / steps)
                b, _normal = vertex(index, (row + 1) / steps)
                scene.quad('Building_MallScreenMullions', 'White',
                           (a[0] + tx * .03, a[1] + ty * .03, a[2]),
                           (a[0] - tx * .03, a[1] - ty * .03, a[2]),
                           (b[0] - tx * .03, b[1] - ty * .03, b[2]),
                           (b[0] + tx * .03, b[1] + ty * .03, b[2]))
        if index % 13 == 0:
            outer, _normal = vertex(index, .2)
            inner = points[index][0], points[index][1], street + .2
            scene.beam('Building_MallScreenDiagonalSupports', 'White', inner, outer, .20, .20)


def barrel_roof(scene: MeshScene, frame: LocalFrame, length: float, width: float,
                rise: float, base: float, bands: int, allowed: BaseGeometry,
                kind: str) -> BaseGeometry:
    plan = rectangle(frame, 0, 0, length, width)
    half = width / 2
    radius = (half * half + rise * rise) / (2 * rise)
    offset = radius - rise

    def roof_height(x: float, y: float) -> float:
        across = (x - frame.center[0]) * frame.normal[0] + (y - frame.center[1]) * frame.normal[1]
        return base + math.sqrt(max(0., radius * radius - across * across)) - offset

    def normal_at(x: float, y: float) -> Point:
        across = (x - frame.center[0]) * frame.normal[0] + (y - frame.center[1]) * frame.normal[1]
        derivative = -across / math.sqrt(max(.001, radius * radius - across * across))
        return norm((-frame.normal[0] * derivative, -frame.normal[1] * derivative, 1.))

    roof_edges: set[tuple[Point, Point]] = set()
    for band in range(bands):
        first = -length / 2 + length * band / bands
        last = -length / 2 + length * (band + 1) / bands
        for u0, u1, material in ((first, first + (last - first) * .7, 'White'),
                                (first + (last - first) * .7, last, 'Glass')):
            for arc in range(24):
                v0, v1 = -half + width * arc / 24, -half + width * (arc + 1) / 24
                quad = Polygon([local(frame, u, v, 0)[:2] for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])
                part = quad.intersection(allowed)
                for triangle in constrained_delaunay_triangles(part).geoms:
                    xy = list(orient(triangle, sign=1.).exterior.coords)[:3]
                    pts = [(x, y, roof_height(x, y)) for x, y in xy]
                    scene.triangle(kind, material, pts[0], pts[1], pts[2],
                                   tuple((p[0] / 8, p[1] / 8) for p in pts), tuple(normal_at(x, y) for x, y in xy))
                    rounded = [(round(p[0], 8), round(p[1], 8), round(p[2], 8)) for p in pts]
                    for a, b in pairwise([*rounded, rounded[0]]):
                        roof_edges.add((a, b))
    for a, b in sorted(roof_edges):
        if (b, a) not in roof_edges:
            scene.quad(kind + 'Clerestory', 'Glass', (a[0], a[1], base), (b[0], b[1], base), b, a)
    return plan.intersection(allowed)


def mall_complex(scene: MeshScene, config: MallArchitecture,
                 geo: Callable[[float, float], XY], ground: Callable[[float, float], float]) -> dict[str, float]:
    ring = [geo(lat, lon) for lon, lat in config.site.outer_wgs84]
    site = Polygon(ring)
    body, frontage = curved_front(site, *config.frontage_source_range, config.frontage_inset_m)
    validate_service_clearance(body, config, geo)
    a, b = [ring[index] for index in config.axis_source_vertices]
    span = math.dist(a, b)
    axis = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    normal = -axis[1], axis[0]
    roof = config.street_relative_m + config.ground_to_first_m + config.first_to_roof_m
    walls(scene, body, config.lower_ground_relative_m, roof, 'Building_MallLowRetailBody', 'Cream', ground)
    skin(scene, body, roof, 'Building_MallFlatServiceRoof', 'White')
    for a, b in pairwise(frontage):
        span = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / span, (b[0] - a[0]) / span
        first = a[0] + nx * .025, a[1] + ny * .025
        last = b[0] + nx * .025, b[1] + ny * .025
        scene.quad('Building_MallRecessedStreetGlazing', 'Glass', (*last, config.lower_ground_relative_m),
                   (*first, config.lower_ground_relative_m), (*first, roof), (*last, roof))
    # Three actual retail levels include the partially buried lower-ground storey.
    for level in (config.street_relative_m, config.street_relative_m + config.ground_to_first_m, roof):
        for a, b in pairwise(orient(body, sign=1.).exterior.coords):
            scene.quad('Building_MallRetailFloorBands', 'White', (*a[:2], level - .12), (*b[:2], level - .12),
                       (*b[:2], level + .12), (*a[:2], level + .12))
    for index in range(3, len(frontage) - 3, 18):
        a, b = frontage[index - 1], frontage[index + 1]
        span = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = -ty, tx
        x, y = frontage[index][0] + nx * .04, frontage[index][1] + ny * .04
        scene.banner((x - tx * .9, y - ty * .9, config.street_relative_m + .4),
                     (x + tx * .9, y + ty * .9, config.street_relative_m + .4), 3.2,
                     'WarmGlass', 'Building_MallOccupiedStorefronts')
    display_screen(scene, frontage, config.street_relative_m, roof + 4.)
    main_center = geo(config.central_roof_center_wgs84[1], config.central_roof_center_wgs84[0])
    main_frame = LocalFrame(main_center, axis, normal)
    primary_plan = barrel_roof(scene, main_frame, config.central_roof_length_m, config.central_roof_width_m,
                               config.central_roof_rise_m, roof, 16, body, 'Building_MallPrimaryGlazedRoof')
    cross_center = geo(config.cross_roof_center_wgs84[1], config.cross_roof_center_wgs84[0])
    cross_frame = LocalFrame(cross_center, normal, (-axis[0], -axis[1]))
    cross_plan = barrel_roof(scene, cross_frame, config.cross_roof_length_m, config.cross_roof_width_m,
                             config.cross_roof_rise_m, roof, 13, body.difference(primary_plan),
                             'Building_MallCrossBoulevardRoof')
    wing_plans = []
    for wing in config.wings:
        center = geo(wing.center_wgs84[1], wing.center_wgs84[0])
        frame = LocalFrame(center, axis, normal)
        shape = rectangle(frame, 0, 0, wing.length_m, wing.width_m)
        if not body.covers(shape):
            raise ValueError(f'The estimated attached mall wing escaped the source envelope: {wing.name}')
        top = config.street_relative_m + wing.floors * wing.floor_pitch_m
        walls(scene, shape, config.street_relative_m, top, 'Building_MallAttachedMidRise', 'Glass', ground)
        facade_bays(scene, shape, config.street_relative_m, top, wing.floor_pitch_m, 3.8,
                    'Building_MallAttachedMidRiseFrames')
        skin(scene, shape, top, 'Building_MallAttachedMidRiseRoof', 'White')
        wing_plans.append(shape)
    plant_area = body.buffer(-5).difference(unary_union([primary_plan.buffer(3), cross_plan.buffer(2), *wing_plans]))
    rng = random.Random(111645517)
    xmin, ymin, xmax, ymax = body.bounds
    count = 0
    for _attempt in range(config.roof_plant_count * 30):
        if count >= config.roof_plant_count:
            break
        x, y = rng.uniform(xmin, xmax), rng.uniform(ymin, ymax)
        width, length = rng.uniform(2.2, 4.0), rng.uniform(3.5, 7.0)
        frame = LocalFrame((x, y), axis, normal)
        footprint = rectangle(frame, 0, 0, length, width)
        if not plant_area.covers(footprint):
            continue
        height = rng.uniform(.8, 1.6)
        scene.box('Building_MallRoofMechanicalPlant', 'Concrete', (x, y, roof + height / 2),
                  length, width, height, math.atan2(axis[1], axis[0]))
        for fraction in (-.25, .25):
            fan = rectangle(frame, length * fraction, 0, 1.4, 1.4)
            skin(scene, fan, roof + height + .015, 'Building_MallRoofPlantFans', 'Black')
        plant_area = plant_area.difference(footprint.buffer(2))
        count += 1
    return {'mapped_site_m2': site.area, 'rendered_body_m2': body.area,
            'flat_roof_relative_m': roof, 'primary_roof_rise_m': config.central_roof_rise_m,
            'roof_mechanical_clusters': float(count), 'attached_wing_count': float(len(wing_plans)),
            'curved_frontage_points': float(len(frontage))}
