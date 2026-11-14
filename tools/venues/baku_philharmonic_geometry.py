from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace
from venues.baku_hotel_geometry import frame, stone_balcony
from venues.baku_streetscape_dataclasses import PhilharmonicSource, PhilharmonicTower


def solid(
    scene: CircuitScene,
    face: CourtFace,
    shape: Polygon,
    front: float,
    back: float,
    material: str,
    kind: str,
) -> None:
    shape = orient(shape, sign=1)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coords = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coords.reverse()
        points = [_point(face, float(p[0]), float(p[1]), front) for p in coords]
        scene.triangle(kind, material, points[0], points[1], points[2])
        points = [_point(face, float(p[0]), float(p[1]), back) for p in coords]
        scene.triangle(kind, material, points[2], points[1], points[0])
    for ring in (shape.exterior, *shape.interiors):
        for a, b in pairwise(ring.coords):
            scene.quad(
                kind,
                material,
                _point(face, a[0], a[1], front),
                _point(face, a[0], a[1], back),
                _point(face, b[0], b[1], back),
                _point(face, b[0], b[1], front),
            )


def column(
    scene: CircuitScene,
    center: Point,
    radius: float,
    height: float,
    material: str,
    kind: str,
) -> None:
    rings = (
        (0.0, radius * 1.32),
        (0.12, radius * 1.35),
        (0.28, radius),
        (0.78 * height, radius * 0.86),
        (height - 0.25, radius),
        (height - 0.12, radius * 1.35),
        (height, radius * 1.35),
    )
    for (z0, r0), (z1, r1) in pairwise(rings):
        for i in range(12):
            a, b = i * math.tau / 12, (i + 1) * math.tau / 12
            scene.quad(
                kind,
                material,
                (
                    center[0] + r0 * math.cos(a),
                    center[1] + r0 * math.sin(a),
                    center[2] + z0,
                ),
                (
                    center[0] + r0 * math.cos(b),
                    center[1] + r0 * math.sin(b),
                    center[2] + z0,
                ),
                (
                    center[0] + r1 * math.cos(b),
                    center[1] + r1 * math.sin(b),
                    center[2] + z1,
                ),
                (
                    center[0] + r1 * math.cos(a),
                    center[1] + r1 * math.sin(a),
                    center[2] + z1,
                ),
            )
    for z, r, reverse in ((0, rings[0][1], True), (height, rings[-1][1], False)):
        c = (center[0], center[1], center[2] + z)
        for i in range(12):
            a, b = i * math.tau / 12, (i + 1) * math.tau / 12
            pa = (
                center[0] + r * math.cos(a),
                center[1] + r * math.sin(a),
                center[2] + z,
            )
            pb = (
                center[0] + r * math.cos(b),
                center[1] + r * math.sin(b),
                center[2] + z,
            )
            scene.triangle(
                kind, material, c, pb if reverse else pa, pa if reverse else pb
            )


def finial(scene: CircuitScene, center: Point, height: float, axis: Point) -> None:
    side = (-axis[1], axis[0], 0.0)
    shape = Polygon(
        [
            (0, 1),
            (-0.14, 0.78),
            (-0.07, 0.53),
            (-0.30, 0.64),
            (-0.40, 0.48),
            (-0.27, 0.33),
            (-0.12, 0.29),
            (-0.10, 0.10),
            (-0.16, 0.04),
            (0.16, 0.04),
            (0.10, 0.10),
            (0.12, 0.29),
            (0.27, 0.33),
            (0.40, 0.48),
            (0.30, 0.64),
            (0.07, 0.53),
            (0.14, 0.78),
        ]
    )
    shape = Polygon([(x * height * 0.75, z * height) for x, z in shape.exterior.coords])
    for tangent in (axis, side):
        start = (
            center[0] - tangent[0] * height,
            center[1] - tangent[1] * height,
            center[2],
        )
        face = CourtFace(
            start, tangent, (tangent[1], -tangent[0], 0), height * 2, height * 2
        )
        shifted = Polygon([(x + height, z) for x, z in shape.exterior.coords])
        solid(
            scene, face, shifted, 0.05, -0.05, "Yellow", "Building_PhilharmonicFinial"
        )


def tower(scene: CircuitScene, source: PhilharmonicTower, base: float) -> None:
    axis = source.axis
    side = (-axis[1], axis[0], 0.0)

    def p(x: float, y: float, z: float) -> Point:
        return (
            source.center[0] + axis[0] * x + side[0] * y,
            source.center[1] + axis[1] * x + side[1] * y,
            base + z,
        )

    w = source.width_m
    corners = [(-w / 2, -w / 2), (w / 2, -w / 2), (w / 2, w / 2), (-w / 2, w / 2)]
    scene.box(
        "Building_PhilharmonicShaft",
        "BakuPhilharmonicOchre",
        p(0, 0, (11.5 + source.shaft_top_m) / 2),
        w,
        w,
        source.shaft_top_m - 11.5,
        math.atan2(axis[1], axis[0]),
    )
    for a, b in pairwise(corners + corners[:1]):
        face = frame(p(*a, 0), p(*b, 0))
        opening = _opening(w / 2, 3.4, source.shaft_top_m + 0.2, 4.6, True, False)
        wall = box(0, source.shaft_top_m, w, source.loggia_top_m).difference(
            opening.shape
        )
        if not isinstance(wall, Polygon):
            raise TypeError("Philharmonic loggia must retain masonry")
        solid(
            scene,
            face,
            wall,
            0.08,
            -0.42,
            "BakuPhilharmonicOchre",
            "Building_PhilharmonicLoggia",
        )
        outline = _opening(
            w / 2, 3.84, source.shaft_top_m + 0.02, 4.96, True, False
        ).shape.difference(opening.shape)
        if not isinstance(outline, Polygon):
            raise TypeError("Philharmonic arch must retain one surround")
        solid(scene, face, outline, 0.30, -0.02, "White", "Building_PhilharmonicArches")
        stone_balcony(
            scene, face, w / 2 - 1.65, w / 2 + 1.65, source.shaft_top_m + 0.1, 0.55
        )
        for z, width, h in (
            (source.shaft_top_m - 0.1, 0.45, 0.30),
            (source.loggia_top_m, 0.64, 0.42),
            (source.loggia_top_m + 0.55, 0.46, 0.24),
        ):
            scene.beam(
                "Building_PhilharmonicTowerCornice",
                "White",
                _point(face, 0, z, 0.12),
                _point(face, w, z, 0.12),
                width,
                h,
            )
        slit = _opening(w / 2, 0.25, 13.0, 2.2, True, False)
        solid(
            scene, face, slit.shape, 0.025, -0.04, "Glass", "Building_PhilharmonicSlits"
        )
    for x, y in corners:
        column(
            scene,
            p(x, y, source.shaft_top_m - 0.2),
            0.24,
            source.loggia_top_m - source.shaft_top_m + 0.4,
            "White",
            "Building_PhilharmonicPiers",
        )
    scene.box(
        "Building_PhilharmonicLoggiaFloor",
        "Cream",
        p(0, 0, source.shaft_top_m - 0.10),
        w,
        w,
        0.22,
        math.atan2(axis[1], axis[0]),
    )
    scene.box(
        "Building_PhilharmonicLanternPlatform",
        "White",
        p(0, 0, source.loggia_top_m + 0.50),
        w + 0.4,
        w + 0.4,
        0.45,
        math.atan2(axis[1], axis[0]),
    )
    lower = source.loggia_top_m + 0.85
    height = source.lantern_top_m - lower
    for i in range(8):
        angle = i * math.tau / 8
        column(
            scene,
            p(1.75 * math.cos(angle), 1.75 * math.sin(angle), lower),
            0.16,
            height,
            "White",
            "Building_PhilharmonicLanternColumns",
        )
    scene.box(
        "Building_PhilharmonicLanternCap",
        "White",
        p(0, 0, source.lantern_top_m + 0.15),
        4.3,
        4.3,
        0.30,
        math.atan2(axis[1], axis[0]),
    )
    finial(
        scene,
        p(0, 0, source.lantern_top_m + 0.3),
        source.peak_m - source.lantern_top_m - 0.3,
        axis,
    )


def roof_forms(scene: CircuitScene, source: PhilharmonicSource) -> None:
    for item in source.towers:
        tower(scene, item, source.base_m)
    cx, cy = source.dome_center[:2]
    base = source.base_m + source.body_top_m
    rings = (
        (0.0, source.dome_radius_m),
        (0.35, source.dome_radius_m * 0.97),
        (2.9, source.dome_radius_m * 0.65),
        (4.5, source.dome_radius_m * 0.32),
        (4.8, source.dome_radius_m * 0.23),
    )
    for (za, ra), (zb, rb) in pairwise(rings):
        for i in range(64):
            a, b = i * math.tau / 64, (i + 1) * math.tau / 64
            scene.quad(
                "Building_PhilharmonicMetalDome",
                "BakuPhilharmonicOchre",
                (cx + ra * math.cos(a), cy + ra * math.sin(a), base + za),
                (cx + ra * math.cos(b), cy + ra * math.sin(b), base + za),
                (cx + rb * math.cos(b), cy + rb * math.sin(b), base + zb),
                (cx + rb * math.cos(a), cy + rb * math.sin(a), base + zb),
            )
    r = source.dome_radius_m * 0.23
    for i in range(12):
        a, b = i * math.tau / 12, (i + 1) * math.tau / 12
        pa = (cx + r * math.cos(a), cy + r * math.sin(a), base + 4.8)
        pb = (cx + r * math.cos(b), cy + r * math.sin(b), base + 4.8)
        face = frame(pa, pb)
        opening = _opening(face.length_m / 2, 0.7, 0.22, 1.45, True, False)
        wall = box(0, 0, face.length_m, 1.9).difference(opening.shape)
        if not isinstance(wall, Polygon):
            raise TypeError("Dome lantern wall invalid")
        solid(
            scene,
            face,
            wall,
            0.05,
            -0.20,
            "BakuPhilharmonicOchre",
            "Building_PhilharmonicDomeLantern",
        )
        solid(
            scene,
            face,
            opening.shape,
            -0.22,
            -0.26,
            "Glass",
            "Building_PhilharmonicDomeLanternGlass",
        )
        scene.triangle(
            "Building_PhilharmonicDomeCap",
            "BakuPhilharmonicOchre",
            (cx, cy, base + 7.3),
            (pa[0], pa[1], base + 6.7),
            (pb[0], pb[1], base + 6.7),
        )
    ox, oy = source.oriel_center[:2]
    oriel_rings = (
        (0.0, source.oriel_radius_m),
        (0.6 * source.oriel_roof_rise_m, source.oriel_radius_m * 0.82),
        (source.oriel_roof_rise_m, source.oriel_radius_m * 0.18),
    )
    for (za, ra), (zb, rb) in pairwise(oriel_rings):
        for i in range(48):
            a, b = i * math.tau / 48, (i + 1) * math.tau / 48
            scene.quad(
                "Building_PhilharmonicOrielRoof",
                "Roof",
                (ox + ra * math.cos(a), oy + ra * math.sin(a), base + za),
                (ox + ra * math.cos(b), oy + ra * math.sin(b), base + za),
                (ox + rb * math.cos(b), oy + rb * math.sin(b), base + zb),
                (ox + rb * math.cos(a), oy + rb * math.sin(a), base + zb),
            )
    z, r = oriel_rings[-1]
    for i in range(48):
        a, b = i * math.tau / 48, (i + 1) * math.tau / 48
        scene.triangle(
            "Building_PhilharmonicOrielCap",
            "Roof",
            (ox, oy, base + z),
            (ox + r * math.cos(a), oy + r * math.sin(a), base + z),
            (ox + r * math.cos(b), oy + r * math.sin(b), base + z),
        )
