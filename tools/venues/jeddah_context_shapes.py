"""Original geometric details shared by the two private Corniche candidates."""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.jeddah_context_dataclasses import LocalFrame

XY = tuple[float, float]


def local(frame: LocalFrame, x: float, y: float, z: float) -> Point:
    return (frame.center[0] + frame.axis[0] * x + frame.normal[0] * y,
            frame.center[1] + frame.axis[1] * x + frame.normal[1] * y, z)


def rectangle(frame: LocalFrame, x: float, y: float, length: float, width: float) -> Polygon:
    return Polygon([local(frame, x + a * length / 2, y + b * width / 2, 0)[:2]
                    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))])


def skin(scene: MeshScene, shape: Polygon, level: float, kind: str, material: str) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points = [(x, y, level) for x, y in list(orient(triangle, sign=1.).exterior.coords)[:3]]
        scene.triangle(kind, material, points[0], points[1], points[2],
                       tuple((p[0] / 8, p[1] / 8) for p in points))


def walls(scene: MeshScene, shape: Polygon, bottom: float, top: float,
          kind: str, material: str, ground: Callable[[float, float], float] | None = None) -> None:
    for a, b in pairwise(orient(shape, sign=1.).exterior.coords):
        za = min(bottom, ground(*a[:2]) - .08) if ground is not None else bottom
        zb = min(bottom, ground(*b[:2]) - .08) if ground is not None else bottom
        scene.quad(kind, material, (*a[:2], za), (*b[:2], zb), (*b[:2], top), (*a[:2], top))


def slab(scene: MeshScene, shape: Polygon, level: float, thickness: float, kind: str) -> None:
    skin(scene, shape, level, kind, 'White')
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points = [(x, y, level - thickness) for x, y in list(orient(triangle, sign=1.).exterior.coords)[:3]]
        scene.triangle(kind, 'Black', points[2], points[1], points[0])
    walls(scene, shape, level - thickness, level, kind, 'White')


def facade_bays(scene: MeshScene, shape: Polygon, bottom: float, top: float,
                pitch: float, bay: float, kind: str) -> None:
    floors = max(1, round((top - bottom) / pitch))
    for a, b in pairwise(orient(shape, sign=1.).exterior.coords):
        span = math.dist(a[:2], b[:2])
        if span < .2:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        count = max(1, round(span / bay))
        for floor in range(floors):
            low = bottom + (top - bottom) * floor / floors
            high = bottom + (top - bottom) * (floor + 1) / floors
            scene.beam(kind, 'White', (*a[:2], high), (*b[:2], high), .16, .22)
            for index in range(count):
                distance = span * (index + .5) / count
                x, y = a[0] + tx * distance + nx * .015, a[1] + ty * distance + ny * .015
                scene.beam(kind, 'White', (x, y, low + .2), (x, y, high - .2), .11, .11)
