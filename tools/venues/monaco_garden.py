"""Engineered patio and separate stairs, bounded by the registered garden plan."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient

from venues.monaco_approaches import ground_sample, line_breaks
from venues.monaco_dataclasses import ApproachGround

XY = tuple[float, float]


def retaining_edge(scene: MeshScene, a: XY, b: XY, level: float, ground: ApproachGround) -> None:
    line = LineString([a, b])
    breaks = line_breaks(line, list(ground.faces))
    crossings = []
    for first, last in pairwise(breaks):
        p, q = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
        za, _ = ground_sample(ground, (p.x, p.y))
        zb, _ = ground_sample(ground, (q.x, q.y))
        if (level - za) * (level - zb) < -1e-12:
            crossings.append(first + (last - first) * (level - za) / (zb - za))
    for first, last in pairwise(sorted({*breaks, *crossings})):
        p, q = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
        za, _ = ground_sample(ground, (p.x, p.y))
        zb, _ = ground_sample(ground, (q.x, q.y))
        scene.quad('Building_CasaGardenRetaining', 'MonacoRockGround',
                   (p.x, p.y, za), (q.x, q.y, zb), (q.x, q.y, level), (p.x, p.y, level))
        scene.quad('Building_CasaGardenRetaining', 'MonacoRockGround',
                   (q.x, q.y, zb), (p.x, p.y, za), (p.x, p.y, level), (q.x, q.y, level))


def patio(scene: MeshScene, shape: Polygon, level: float,
          ground: ApproachGround, stair_opening: BaseGeometry) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coordinates = list(orient(triangle, sign=1.).exterior.coords)[:3]
        points = [(x, y, level) for x, y in coordinates]
        scene.triangle('Building_CasaGardenPatio', 'Terracotta', points[0], points[1], points[2],
                       tuple((p[0] / 2, p[1] / 2) for p in points))
    for a, b in pairwise(shape.exterior.coords):
        remaining = LineString([a[:2], b[:2]]).difference(stair_opening.buffer(1e-7))
        parts = [remaining] if isinstance(remaining, LineString) else list(getattr(remaining, 'geoms', ()))
        for part in parts:
            if isinstance(part, LineString) and part.length > 1e-6:
                retaining_edge(scene, part.coords[0], part.coords[-1], level, ground)


def stairs(scene: MeshScene, ring: list[XY], top: float, bottom: float,
           ground: ApproachGround) -> dict[str, float]:
    if len(ring) != 4:
        raise ValueError('The registered garden stairs require a four-corner strip')
    a, b, c, d = ring
    first_center = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    last_center = (c[0] + d[0]) / 2, (c[1] + d[1]) / 2
    if not .25 < top - bottom < 5:
        raise ValueError('Garden stair levels must follow the qualified local ground fall')
    count = math.ceil((top - bottom) / .17)
    rise = (top - bottom) / count

    def edges(fraction: float) -> tuple[XY, XY]:
        return ((a[0] + (d[0] - a[0]) * fraction, a[1] + (d[1] - a[1]) * fraction),
                (b[0] + (c[0] - b[0]) * fraction, b[1] + (c[1] - b[1]) * fraction))

    for index in range(count):
        first, last = edges(index / count), edges((index + 1) / count)
        level = top - rise * (index + 1)
        scene.quad('Building_CasaGardenTreads', 'Terracotta', (*first[0], level), (*first[1], level),
                   (*last[1], level), (*last[0], level), up=True)
        scene.quad('Building_CasaGardenRisers', 'Terracotta', (*first[0], level), (*first[1], level),
                   (*first[1], level + rise), (*first[0], level + rise))
        retaining_edge(scene, first[0], last[0], level, ground)
        retaining_edge(scene, first[1], last[1], level, ground)
    return {'top_relative_m': top, 'bottom_relative_m': bottom,
            'riser_height_m': rise, 'step_count': float(count),
            'run_m': math.dist(first_center, last_center)}
