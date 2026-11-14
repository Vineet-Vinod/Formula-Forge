"""The registered curved belvedere, separate from the held L-shaped terraces."""

from __future__ import annotations

import math
import random
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, norm, sub
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from venues.monaco_approaches import ground_sample
from venues.monaco_dataclasses import ApproachGround
from venues.monaco_west_dataclasses import BelvedereArchitecture

XY = tuple[float, float]


def boundary_sections(ground: ApproachGround, a: tuple[float, float], b: tuple[float, float]) -> list[tuple[Point, Point]]:
    line = LineString([a, b])
    if line.length < 1e-8:
        return []
    breaks = {0., 1.}
    for index in ground.index.query(line, predicate='intersects'):
        cut = line.intersection(ground.polygons[int(index)])
        if isinstance(cut, LineString) and not cut.is_empty:
            breaks.update(line.project(ShapePoint(p)) / line.length for p in cut.coords)
    sections = []
    for first, last in pairwise(sorted(breaks)):
        p, q = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
        za, _normal = ground_sample(ground, (p.x, p.y))
        zb, _normal = ground_sample(ground, (q.x, q.y))
        sections.append(((p.x, p.y, za), (q.x, q.y, zb)))
    return sections


def arc_point(config: BelvedereArchitecture, radius: float, angle: float, z: float) -> Point:
    a, b = radius * math.cos(angle), radius * math.sin(angle)
    return (config.center_xy_m[0] + config.east_axis[0] * a + config.south_axis[0] * b,
            config.center_xy_m[1] + config.east_axis[1] * a + config.south_axis[1] * b, z)


def half_disc(config: BelvedereArchitecture, radius: float) -> Polygon:
    return orient(Polygon([arc_point(config, radius, math.pi * i / config.arc_segments, 0)[:2]
                           for i in range(config.arc_segments + 1)]), sign=1.)


def top_skin(scene: MeshScene, shape: BaseGeometry, z: float, material: str, kind: str) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points = [(x, y, z) for x, y in list(orient(triangle, sign=1.).exterior.coords)[:3]]
        scene.triangle(kind, material, points[0], points[1], points[2],
                       tuple((p[0] / 2, p[1] / 2) for p in points))


def radial_normal(config: BelvedereArchitecture, point: Point) -> Point:
    return norm((point[0] - config.center_xy_m[0], point[1] - config.center_xy_m[1], 0.))


def curved_triangle(scene: MeshScene, config: BelvedereArchitecture,
                    points: tuple[Point, Point, Point], material: str, kind: str) -> None:
    a, b, c = points
    normals = tuple(radial_normal(config, p) for p in points)
    geometric = cross(sub(b, a), sub(c, a))
    if sum(a * b for a, b in zip(geometric, normals[0], strict=True)) < 0:
        b, c = c, b
        normals = normals[0], normals[2], normals[1]
    scene.triangle(kind, material, a, b, c, tuple((p[0] / 2, p[2] / 2) for p in (a, b, c)), normals)


def curved_quad(scene: MeshScene, config: BelvedereArchitecture, a: Point, b: Point,
                 c: Point, d: Point, material: str, kind: str) -> None:
    curved_triangle(scene, config, (a, b, c), material, kind)
    curved_triangle(scene, config, (a, c, d), material, kind)


def polar_skin(scene: MeshScene, config: BelvedereArchitecture, region: BaseGeometry,
                radius: float, material: str, kind: str) -> None:
    for triangle in constrained_delaunay_triangles(region).geoms:
        points = [arc_point(config, radius, s / config.radius_m, z)
                  for s, z in list(triangle.exterior.coords)[:3]]
        curved_triangle(scene, config, (points[0], points[1], points[2]), material, kind)


def stone_courses(scene: MeshScene, config: BelvedereArchitecture, ground: ApproachGround,
                   top: float) -> int:
    rng = random.Random(74074420)
    radius = config.radius_m - .01
    arc_length = math.pi * radius
    samples = [arc_point(config, radius, math.pi * i / config.arc_segments, 0.)
               for i in range(config.arc_segments + 1)]
    lowest = min(ground_sample(ground, p[:2])[0] for p in samples) - config.base_overlap_m
    rows = math.ceil((top - lowest) / config.course_height_m)
    count = 0
    for course in range(rows):
        low = lowest + course * config.course_height_m + config.stone_joint_m / 2
        high = min(top, low + config.course_height_m - config.stone_joint_m)
        start = -.35 if course % 2 else 0.
        while start < arc_length:
            end = start + rng.uniform(.55, .82)
            a, b = max(0., start + config.stone_joint_m / 2), min(arc_length, end - config.stone_joint_m / 2)
            if b <= a:
                start = end
                continue
            material = rng.choices(['MonacoRockGround', 'Limestone'], [1, 4])[0]
            steps = max(1, math.ceil((b - a) / .24))
            for i in range(steps):
                s0, s1 = a + (b - a) * i / steps, a + (b - a) * (i + 1) / steps
                p, q = arc_point(config, radius, s0 / radius, 0), arc_point(config, radius, s1 / radius, 0)
                for first, last in boundary_sections(ground, p[:2], q[:2]):
                    za = min(high, max(low, first[2] - config.base_overlap_m))
                    zb = min(high, max(low, last[2] - config.base_overlap_m))
                    if za >= high and zb >= high:
                        continue
                    curved_quad(scene, config, (first[0], first[1], za), (last[0], last[1], zb),
                                (last[0], last[1], high), (first[0], first[1], high),
                                material, 'Building_WestBelvedereStoneCourses')
                    count += 1
            start = end
    return count


def arcaded_parapet(scene: MeshScene, config: BelvedereArchitecture, paving: float, cap: float) -> None:
    outer = config.radius_m - .01
    inner = outer - config.wall_thickness_m
    pitch = math.pi * config.radius_m / config.arch_bays
    for bay in range(config.arch_bays):
        first, last = pitch * bay, pitch * (bay + 1)
        center = (first + last) / 2
        half_width = config.arch_width_m / 2
        bottom = paving - 1.48
        spring = bottom + config.arch_height_m - half_width
        arch = [(center - half_width, bottom), (center + half_width, bottom)]
        arch += [(center + half_width * math.cos(i * math.pi / 20),
                  spring + half_width * math.sin(i * math.pi / 20)) for i in range(21)]
        opening = Polygon(arch)
        frame = Polygon([(first, paving), (last, paving), (last, paving - .16), (first, paving - .16)])
        polar_skin(scene, config, frame.difference(opening), outer, 'Limestone', 'Building_WestBelvedereArcade')
        polar_skin(scene, config, opening, outer - config.arch_recess_m,
                   'Concrete', 'Building_WestBelvedereBlindRecesses')
        for a, b in pairwise(opening.exterior.coords):
            aa, bb = arc_point(config, outer, a[0] / config.radius_m, a[1]), arc_point(config, outer, b[0] / config.radius_m, b[1])
            cc = arc_point(config, outer - config.arch_recess_m, b[0] / config.radius_m, b[1])
            dd = arc_point(config, outer - config.arch_recess_m, a[0] / config.radius_m, a[1])
            scene.quad('Building_WestBelvedereArchReturns', 'Limestone', aa, bb, cc, dd)
    # The photo separates the blind arcade below the rim from the open balustrade above it.
    for i in range(config.arc_segments):
        a, b = math.pi * i / config.arc_segments, math.pi * (i + 1) / config.arc_segments
        for low, high, kind in ((paving - .16, paving + .10, 'RimSlab'),
                                (cap - .12, cap, 'Coping')):
            scene.quad('Building_WestBelvedere' + kind, 'Limestone',
                       arc_point(config, inner, a, high), arc_point(config, inner, b, high),
                       arc_point(config, outer, b, high), arc_point(config, outer, a, high), up=True)
            curved_quad(scene, config, arc_point(config, outer, a, low),
                        arc_point(config, outer, b, low), arc_point(config, outer, b, high),
                        arc_point(config, outer, a, high), 'Limestone', 'Building_WestBelvedere' + kind)
            scene.quad('Building_WestBelvedere' + kind, 'Limestone',
                       arc_point(config, inner, b, low), arc_point(config, inner, a, low),
                       arc_point(config, inner, a, high), arc_point(config, inner, b, high))
        scene.quad('Building_WestBelvedereCopingSoffit', 'Limestone',
                   arc_point(config, inner, b, cap - .12), arc_point(config, inner, a, cap - .12),
                   arc_point(config, outer, a, cap - .12), arc_point(config, outer, b, cap - .12), up=False)
    count = config.arch_bays * 3
    for i in range(count + 1):
        angle = math.pi * i / count
        baluster_center = arc_point(config, (inner + outer) / 2, angle, (paving + .10 + cap - .12) / 2)
        width = .16 if i % 3 == 0 else .075
        scene.box('Building_WestBelvedereBalusters', 'Limestone', baluster_center,
                  width, config.wall_thickness_m * .65, cap - .12 - paving - .10,
                  math.atan2(config.east_axis[1], config.east_axis[0]) - angle + math.pi / 2)
    for angle in (0., math.pi):
        scene.quad('Building_WestBelvedereEndClosure', 'Limestone',
                   arc_point(config, inner, angle, paving - .16), arc_point(config, outer, angle, paving - .16),
                   arc_point(config, outer, angle, paving + .10), arc_point(config, inner, angle, paving + .10))


def belvedere_preflight(config: BelvedereArchitecture, ground: ApproachGround) -> list[tuple[Point, Point]]:
    paving = config.paving_absolute_m - config.relative_datum_m
    cap = config.cap_absolute_m - config.relative_datum_m
    if not .8 <= cap - paving <= 1.4:
        raise ValueError('Belvedere cap and paving must retain the declared modest parapet')
    body = half_disc(config, config.radius_m - .18)
    sections = []
    for a, b in pairwise(body.exterior.coords):
        sections.extend(boundary_sections(ground, a[:2], b[:2]))
    if not sections or any(max(a[2], b[2]) >= paving - .1 for a, b in sections):
        raise ValueError('Belvedere support/top interpretation intersects unqualified old terrain')
    return sections


def belvedere(scene: MeshScene, config: BelvedereArchitecture, ground: ApproachGround) -> dict[str, float]:
    sections = belvedere_preflight(config, ground)
    paving = config.paving_absolute_m - config.relative_datum_m
    cap = config.cap_absolute_m - config.relative_datum_m
    body = half_disc(config, config.radius_m - .18)
    walk = half_disc(config, config.radius_m - config.wall_thickness_m)
    garden = half_disc(config, config.radius_m - config.rim_walk_width_m)
    for a, b in sections:
        scene.quad('Building_WestBelvedereRetaining', 'Concrete',
                   (a[0], a[1], a[2] - config.base_overlap_m),
                   (b[0], b[1], b[2] - config.base_overlap_m),
                   (b[0], b[1], paving), (a[0], a[1], paving))
    top_skin(scene, walk.difference(garden), paving, 'Limestone', 'Building_WestBelvedereRimWalk')
    top_skin(scene, garden, paving, 'MonacoIvyGround', 'Building_WestBelvedereRetainedGarden')
    # The raised garden is local retained soil above the source-supported wall, not a native terrain edit.
    top_skin(scene, body.difference(walk), paving, 'Limestone', 'Building_WestBelvedereParapetSeat')
    # Tree presence and approximate mature scale are visible in 2012; positions are reconstructed.
    for u, v, height, seed in ((-.8, 1.8, 5.4, 744201), (1.6, 2., 3.7, 744202)):
        p = (config.center_xy_m[0] + config.east_axis[0]*u + config.south_axis[0]*v,
             config.center_xy_m[1] + config.east_axis[1]*u + config.south_axis[1]*v, paving)
        scene.broadleaf(p, height, seed)
    stones = stone_courses(scene, config, ground, paving - 1.50)
    arcaded_parapet(scene, config, paving, cap)
    return {'radius_m': config.radius_m, 'paving_absolute_m': config.paving_absolute_m,
            'cap_absolute_m': config.cap_absolute_m, 'retained_area_m2': body.area,
            'wall_ground_sections': float(len(sections)), 'stone_sections': float(stones),
            'minimum_support_height_m': min(paving - max(a[2], b[2]) for a, b in sections),
            'maximum_support_height_m': max(paving - min(a[2], b[2]) for a, b in sections)}
