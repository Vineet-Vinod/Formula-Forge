"""Bridge-approach joins against the exact original ground triangles."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, norm
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from venues.monaco_bridge import heights
from venues.monaco_dataclasses import ApproachGround, BridgeProfile, CostaGroundFace
from venues.monaco_landcover import interpolate

XY = tuple[float, float]


def ground_sample(ground: ApproachGround, point: XY) -> tuple[float, Point]:
    marker = ShapePoint(point)
    face = next((ground.faces[int(i)] for i in ground.index.query(marker.buffer(1e-8))
                 if ground.polygons[int(i)].distance(marker) < 1e-8), None)
    if face is None:
        raise ValueError(f'The approach boundary has no retained original ground plane at {point}')
    return interpolate(face, *point)


def line_breaks(line: LineString, faces: list[CostaGroundFace]) -> list[float]:
    values = {0., 1.}
    for face in faces:
        part = line.intersection(Polygon([p[:2] for p in face.points]))
        if isinstance(part, LineString) and not part.is_empty:
            values.update(line.project(ShapePoint(p)) / line.length for p in part.coords)
    count = math.ceil(line.length / .5)
    values.update(i / count for i in range(1, count))
    return sorted(values)


def approach_segment(scene: MeshScene, a: XY, b: XY, translation: XY,
                     faces: list[CostaGroundFace], profile: BridgeProfile,
                     retaining_sides: tuple[bool, bool]) -> BaseGeometry:
    dx, dy = translation
    polygons = tuple(Polygon([p[:2] for p in face.points]) for face in faces)
    ground = ApproachGround(tuple(faces), polygons, STRtree(polygons))
    ax, ay = b[0] - a[0], b[1] - a[1]
    determinant = ax * dy - ay * dx
    if abs(determinant) < 1:
        raise ValueError('The approach must extend across the source bridge cap')
    outer = LineString([(a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)])
    across = line_breaks(outer, faces)
    inner_stations = [sum((v - o) * axis for v, o, axis in zip(p, profile.frame.origin, profile.frame.axis, strict=True))
                      for p in (a, b)]
    for station in (0., profile.frame.span):
        if min(inner_stations) < station < max(inner_stations):
            across.append((station - inner_stations[0]) / (inner_stations[1] - inner_stations[0]))
    across = sorted(set(across))
    rows = math.ceil(math.hypot(dx, dy) / .5)

    def vertex(r: float, t: float) -> tuple[Point, Point]:
        inner_point = a[0] + ax * r, a[1] + ay * r
        outer_point = inner_point[0] + dx, inner_point[1] + dy
        deck = heights(profile, inner_point)[0]
        ground_z, ground_normal = ground_sample(ground, outer_point)
        point = inner_point[0] + dx * t, inner_point[1] + dy * t, deck * (1 - t) + ground_z * t
        if t == 1:
            return point, ground_normal
        delta = .0001
        ra, rb = max(0., r - delta), min(1., r + delta)
        side_values = []
        for value in (ra, rb):
            ix, iy = a[0] + ax * value, a[1] + ay * value
            inner_z = heights(profile, (ix, iy))[0]
            outer_z, _normal = ground_sample(ground, (ix + dx, iy + dy))
            side_values.append(inner_z * (1 - t) + outer_z * t)
        dzdr = (side_values[1] - side_values[0]) / (rb - ra)
        dzdt = ground_z - deck
        gx = (dzdr * dy - dzdt * ay) / determinant
        gy = (ax * dzdt - dx * dzdr) / determinant
        return point, norm((-gx, -gy, 1.))

    for first, last in pairwise(across):
        for row in range(rows):
            points = [vertex(r, t) for r, t in ((first, row / rows), (last, row / rows),
                                               (last, (row + 1) / rows), (first, (row + 1) / rows))]
            if determinant < 0:
                points.reverse()
            for indices in ((0, 1, 2), (0, 2, 3)):
                vertices = [points[i][0] for i in indices]
                normals = tuple(points[i][1] for i in indices)
                scene.triangle('Building_LarvottoApproach', 'Runoff', vertices[0], vertices[1], vertices[2],
                               tuple((p[0] / 8, p[1] / 8) for p in vertices), normals)
    # Both sides close against the exact old terrain; the outer end shares its plane and normals.
    for r, enabled in zip((0., 1.), retaining_sides, strict=True):
        if not enabled:
            continue
        start = a[0] + ax * r, a[1] + ay * r
        side = LineString([start, (start[0] + dx, start[1] + dy)])
        breaks = line_breaks(side, faces)
        crossings = []
        for first, last in pairwise(breaks):
            p, _ = vertex(r, first)
            q, _ = vertex(r, last)
            za, _ = ground_sample(ground, p[:2])
            zb, _ = ground_sample(ground, q[:2])
            first_gap, last_gap = p[2] - za, q[2] - zb
            if first_gap * last_gap < -1e-12:
                crossings.append(first + (last - first) * first_gap / (first_gap - last_gap))
        breaks = sorted({*breaks, *crossings})
        for first, last in pairwise(breaks):
            p, _ = vertex(r, first)
            q, _ = vertex(r, last)
            za, _ = ground_sample(ground, p[:2])
            zb, _ = ground_sample(ground, q[:2])
            scene.quad('Building_LarvottoApproachRetaining', 'Concrete', (*p[:2], za), (*q[:2], zb), q, p)
            scene.quad('Building_LarvottoApproachRetaining', 'Concrete', (*q[:2], zb), (*p[:2], za), p, q)
    return Polygon([a, b, (b[0] + dx, b[1] + dy), (a[0] + dx, a[1] + dy)])
