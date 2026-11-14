from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.polygon import orient

from venues.baku_civic import _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_museum_dataclasses import MuseumEdge


def _panel(
    scene: CircuitScene, face: CourtFace, shape: Polygon, depth: float, material: str
) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coords = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coords.reverse()
        points = [_point(face, float(x), float(z), depth) for x, z in coords]
        scene.triangle(
            "Building_MuseumMasonry", material, points[0], points[1], points[2]
        )


def _glazing(scene: CircuitScene, face: CourtFace, opening: CourtOpening) -> None:
    ring = list(opening.shape.exterior.coords)
    pane_depth = -0.18
    _panel(scene, face, opening.shape, pane_depth, "Glass")
    for a, b in pairwise(ring):
        scene.quad(
            "Building_MuseumReveals",
            "Cream",
            _point(face, *a),
            _point(face, *b),
            _point(face, b[0], b[1], pane_depth),
            _point(face, a[0], a[1], pane_depth),
        )
        scene.beam(
            "Building_MuseumWindowSurrounds",
            "White",
            _point(face, a[0], a[1], 0.025),
            _point(face, b[0], b[1], 0.025),
            0.085,
            0.085,
        )
        scene.beam(
            "Building_MuseumFrames",
            "Trunk" if opening.door else "Black",
            _point(face, a[0], a[1], pane_depth + 0.035),
            _point(face, b[0], b[1], pane_depth + 0.035),
            0.055,
        )
    x0, z0, x1, z1 = opening.shape.bounds
    center = (x0 + x1) / 2
    scene.beam(
        "Building_MuseumMullions",
        "Trunk" if opening.door else "Black",
        _point(face, center, z0, pane_depth + 0.035),
        _point(face, center, z1, pane_depth + 0.035),
        0.045,
    )
    if opening.arch_spring_m is not None:
        for t in (0.34, 0.68):
            z = z0 + (opening.arch_spring_m - z0) * t
            scene.beam(
                "Building_MuseumMullions",
                "Black",
                _point(face, x0, z, pane_depth + 0.035),
                _point(face, x1, z, pane_depth + 0.035),
                0.04,
            )
    transom = (
        opening.arch_spring_m
        if opening.arch_spring_m is not None
        else z0 + (z1 - z0) * 0.72
    )
    scene.beam(
        "Building_MuseumMullions",
        "Black",
        _point(face, x0, transom, pane_depth + 0.035),
        _point(face, x1, transom, pane_depth + 0.035),
        0.045,
    )
    if opening.door:
        for x in (x0 - 0.13, x1 + 0.13):
            scene.beam(
                "Building_MuseumDoorPiers",
                "Cream",
                _point(face, x, z0),
                _point(face, x, z1 + 0.12),
                0.24,
                0.25,
            )
        scene.beam(
            "Building_MuseumDoorLintels",
            "White",
            _point(face, x0 - 0.25, z1 + 0.12),
            _point(face, x1 + 0.25, z1 + 0.12),
            0.22,
            0.16,
        )
    else:
        scene.beam(
            "Building_MuseumSills",
            "White",
            _point(face, x0 - 0.12, z0 - 0.09, 0.04),
            _point(face, x1 + 0.12, z0 - 0.09, 0.04),
            0.22,
            0.14,
        )


def grade(edge: MuseumEdge, along: float) -> float:
    for segment in edge.segments:
        low, high = segment.along_m
        if low - 1e-8 <= along <= high + 1e-8:
            t = (along - low) / (high - low)
            return segment.points[0][2] * (1 - t) + segment.points[1][2] * t
    raise ValueError("Missing actual museum wall-foot interval")


def _relief(
    scene: CircuitScene, face: CourtFace, shape: Polygon, front: float, back: float
) -> None:
    shape = orient(shape, sign=1.0)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coords = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coords.reverse()
        a, b, c = [_point(face, float(x), float(z), front) for x, z in coords]
        scene.triangle("Building_MuseumRelief", "Cream", a, b, c)
        a, b, c = [_point(face, float(x), float(z), back) for x, z in coords]
        scene.triangle("Building_MuseumRelief", "Cream", c, b, a)
    for ring in (shape.exterior, *shape.interiors):
        for a, b in pairwise(ring.coords):
            scene.quad(
                "Building_MuseumRelief",
                "Cream",
                _point(face, a[0], a[1], front),
                _point(face, a[0], a[1], back),
                _point(face, b[0], b[1], back),
                _point(face, b[0], b[1], front),
            )


def _rustication(scene: CircuitScene, face: CourtFace, wall: Polygon) -> None:
    first = math.floor(wall.bounds[1] / 0.47)
    for row in range(first, 10):
        bottom = row * 0.47 + 0.014
        top = min(4.55, (row + 1) * 0.47 - 0.014)
        if top <= bottom:
            continue
        shift = 0.625 * (row % 2)
        for column in range(-1, math.ceil(face.length_m / 1.25) + 1):
            left, right = (
                column * 1.25 + shift + 0.014,
                (column + 1) * 1.25 + shift - 0.014,
            )
            clipped = wall.intersection(box(left, bottom, right, top))
            parts = (
                list(clipped.geoms)
                if isinstance(clipped, MultiPolygon)
                else [clipped]
                if isinstance(clipped, Polygon)
                else []
            )
            for part in parts:
                if part.area > 0.012:
                    _relief(scene, face, part, 0.065, -0.02)


def _baluster(
    scene: CircuitScene, face: CourtFace, along: float, level: float, depth: float
) -> None:
    rings = (
        (-0.025, 0.085),
        (0.12, 0.085),
        (0.29, 0.11),
        (0.48, 0.06),
        (0.65, 0.045),
        (0.75, 0.075),
    )

    def point(radius: float, angle: float, z: float) -> Point:
        return _point(
            face,
            along + radius * math.cos(angle),
            level + z,
            depth + radius * math.sin(angle),
        )

    for (z0, r0), (z1, r1) in pairwise(rings):
        for i in range(16):
            a, b = i * math.tau / 16, (i + 1) * math.tau / 16
            scene.quad(
                "Building_MuseumBalusters",
                "Cream",
                point(r0, b, z0),
                point(r0, a, z0),
                point(r1, a, z1),
                point(r1, b, z1),
            )
    for z, r, reverse in (
        (rings[0][0], rings[0][1], True),
        (rings[-1][0], rings[-1][1], False),
    ):
        center = _point(face, along, level + z, depth)
        for i in range(16):
            pa, pb = (
                point(r, i * math.tau / 16, z),
                point(r, (i + 1) * math.tau / 16, z),
            )
            scene.triangle(
                "Building_MuseumBalusters",
                "Cream",
                center,
                pa if reverse else pb,
                pb if reverse else pa,
            )


def _balcony(
    scene: CircuitScene, face: CourtFace, a: float, b: float, level: float, depth: float
) -> None:
    center = _point(face, (a + b) / 2, level - 0.09, depth / 2)
    scene.box(
        "Building_MuseumBalconyDeck",
        "Cream",
        center,
        b - a,
        depth,
        0.18,
        math.atan2(face.tangent[1], face.tangent[0]),
    )
    for x0, d0, x1, d1 in (
        (a, depth, b, depth),
        (a, 0.0, a, depth),
        (b, 0.0, b, depth),
    ):
        scene.beam(
            "Building_MuseumBalustrade",
            "Cream",
            _point(face, x0, level + 0.78, d0),
            _point(face, x1, level + 0.78, d1),
            0.14,
            0.16,
        )
        count = math.ceil(math.hypot(x1 - x0, d1 - d0) / 0.25)
        for i in range(count + 1):
            if x0 == x1 and i == count:
                continue
            t = i / count
            _baluster(scene, face, x0 + (x1 - x0) * t, level, d0 + (d1 - d0) * t)
