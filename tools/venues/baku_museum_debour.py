"""Source-fitted De Bour elevations; levels and projecting depths are estimates."""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_museum_dataclasses import (
    DebourDimensions,
    MuseumEdge,
    MuseumFooting,
    MuseumLayout,
)
from venues.baku_museum_geometry import (
    _balcony,
    _glazing,
    _panel,
    _relief,
    _rustication,
    grade,
)


def _column(
    scene: CircuitScene,
    face: CourtFace,
    x: float,
    depth: float,
    foot: float,
    top: float,
) -> None:
    rings = (
        (foot, 0.38),
        (foot + 0.20, 0.38),
        (foot + 0.34, 0.29),
        (top - 0.45, 0.245),
        (top - 0.32, 0.40),
        (top - 0.12, 0.43),
        (top, 0.43),
    )
    for (z0, r0), (z1, r1) in pairwise(rings):
        for i in range(16):
            a, b = i * math.tau / 16, (i + 1) * math.tau / 16
            scene.quad(
                "Building_DebourColumns",
                "Cream",
                _point(face, x + r0 * math.cos(b), z0, depth + r0 * math.sin(b)),
                _point(face, x + r0 * math.cos(a), z0, depth + r0 * math.sin(a)),
                _point(face, x + r1 * math.cos(a), z1, depth + r1 * math.sin(a)),
                _point(face, x + r1 * math.cos(b), z1, depth + r1 * math.sin(b)),
            )
    for z, radius, reverse in ((foot, 0.38, True), (top, 0.43, False)):
        for i in range(16):
            a, b = i * math.tau / 16, (i + 1) * math.tau / 16
            p = _point(face, x + radius * math.cos(a), z, depth + radius * math.sin(a))
            q = _point(face, x + radius * math.cos(b), z, depth + radius * math.sin(b))
            scene.triangle(
                "Building_DebourColumns",
                "Cream",
                _point(face, x, z, depth),
                p if reverse else q,
                q if reverse else p,
            )


def _windows(
    face: CourtFace, edge: MuseumEdge, datum: float, spec: DebourDimensions
) -> list[CourtOpening]:
    result = []
    for floor, (bottom, top) in enumerate(
        (spec.ground_opening_m, spec.upper_opening_m)
    ):
        if edge.ring == "courtyard_xy":
            centers = [face.length_m * (i + 0.5) / 4 for i in range(4)]
        elif edge.edge == 1:
            centers = [face.length_m * (i + 0.5) / 7 for i in range(7)]
        elif edge.edge == 2:
            centers = [
                face.length_m * t
                for t in (
                    0.055,
                    0.117,
                    0.179,
                    0.241,
                    0.303,
                    0.365,
                    0.427,
                    0.489,
                    0.551,
                    0.613333333333,
                    0.680,
                    0.746666666667,
                    0.885,
                )
            ]
        else:
            centers = [face.length_m * (i + 0.5) / 10 for i in range(10)]
        if edge.ring == "outer_xy" and edge.edge == 2 and floor == 0:
            centers = centers[:-1] + [face.length_m * 0.84, face.length_m * 0.95]
        for i, x in enumerate(centers):
            arched = (
                floor == 1
                and edge.ring == "outer_xy"
                and ((edge.edge == 1 and i in (0, 3, 6)) or (edge.edge == 2 and i >= 9))
            )
            door = (
                floor == 0
                and edge.ring == "outer_xy"
                and edge.edge == 1
                and i in (1, 5)
            )
            local = grade(edge, face.length_m - x) - datum
            low = max(bottom, local + 0.35) if floor == 0 else bottom
            if top - low < 0.8:
                continue
            result.append(
                _opening(x, 2.05 if arched else 1.75, low, top - low, arched, door)
            )
    return result


def _column_ground(
    face: CourtFace,
    along: float,
    depth: float,
    ground: Callable[[float, float], float],
) -> float:
    levels = []
    for i in range(16):
        angle = i * math.tau / 16
        x, y, _ = _point(
            face, along + 0.38 * math.cos(angle), 0, depth + 0.38 * math.sin(angle)
        )
        levels.append(ground(x, y))
    return min(levels)


def _front_details(
    scene: CircuitScene,
    face: CourtFace,
    datum: float,
    ground: Callable[[float, float], float],
    spec: DebourDimensions,
) -> None:
    for bay in (1, 5):
        x = face.length_m * (bay + 0.5) / 7
        for along in (x - 1.5, x + 1.5):
            for depth in (0.55, spec.portico_depth_m - 0.20):
                column_foot = _column_ground(face, along, depth, ground) - datum - 0.05
                _column(
                    scene,
                    face,
                    along,
                    depth,
                    column_foot,
                    spec.portico_top_m - 0.22,
                )
        _balcony(
            scene,
            face,
            x - 1.95,
            x + 1.95,
            spec.portico_top_m,
            spec.portico_depth_m + 0.30,
        )
    for bay in (0, 3, 6):
        x = face.length_m * (bay + 0.5) / 7
        for side in (-1, 1):
            _column(scene, face, x + side * 1.45, 0.15, 7.65, 13.55)
    center = face.length_m / 2
    pediment = Polygon(
        [
            (center - 4.4, 14.25),
            (center + 4.4, 14.25),
            (center + 3.6, 14.75),
            (center + 1.1, 16.3),
            (center, 16.55),
            (center - 1.1, 16.3),
            (center - 3.6, 14.75),
        ]
    )
    _relief(scene, face, pediment, 0.38, -0.18)
    for a, b in pairwise(pediment.exterior.coords):
        scene.beam(
            "Building_DebourPediment",
            "Cream",
            _point(face, float(a[0]), float(a[1]), 0.40),
            _point(face, float(b[0]), float(b[1]), 0.40),
            0.20,
            0.24,
        )
    for i in range(32):
        a, b = i * math.tau / 32, (i + 1) * math.tau / 32
        scene.beam(
            "Building_DebourCartouche",
            "Cream",
            _point(face, center + 0.55 * math.cos(a), 15.65 + 0.70 * math.sin(a), 0.68),
            _point(face, center + 0.55 * math.cos(b), 15.65 + 0.70 * math.sin(b), 0.68),
            0.17,
        )
    for side in (-1, 1):
        head = _point(face, center + side * 1.1, 16.7, 0.58)
        hip = _point(face, center + side * 2.0, 15.8, 0.58)
        knee = _point(face, center + side * 2.6, 15.55, 0.78)
        foot = _point(face, center + side * 3.5, 15.2, 0.65)
        scene.beam("Building_DebourStatuary", "Cream", head, hip, 0.35, 0.48)
        scene.beam("Building_DebourStatuary", "Cream", hip, knee, 0.24, 0.28)
        scene.beam("Building_DebourStatuary", "Cream", knee, foot, 0.19, 0.22)
        scene.box(
            "Building_DebourStatuary",
            "Cream",
            head,
            0.32,
            0.36,
            0.40,
            math.atan2(face.tangent[1], face.tangent[0]),
        )
    for z, width, depth in (
        (7.0, 0.40, 0.35),
        (13.1, 0.35, 0.30),
        (13.7, 0.55, 0.50),
        (14.2, 0.28, 0.35),
    ):
        scene.beam(
            "Building_DebourCornice",
            "Cream",
            _point(face, 0, z, 0.10),
            _point(face, face.length_m, z, 0.10),
            width,
            depth,
        )
    for i in range(33):
        x = face.length_m * (i + 0.5) / 33
        scene.box(
            "Building_DebourDentils",
            "Cream",
            _point(face, x, 13.65, 0.30),
            0.23,
            0.45,
            0.30,
            math.atan2(face.tangent[1], face.tangent[0]),
        )
    for i in range(7):
        x = face.length_m * (i + 0.5) / 7
        for side in (-1, 1):
            xx = x + side * 1.45
            scene.beam(
                "Building_DebourPilasters",
                "Cream",
                _point(face, xx, 7.5, 0.08),
                _point(face, xx, 13.0, 0.08),
                0.28,
                0.22,
            )


def _wall(
    scene: CircuitScene,
    face: CourtFace,
    edge: MuseumEdge,
    datum: float,
    ground: Callable[[float, float], float],
    spec: DebourDimensions,
) -> None:
    feet = [(0.0, grade(edge, edge.length_m) - datum - 0.05)]
    feet.extend(
        (edge.length_m - s.along_m[0], s.points[0][2] - datum - 0.05)
        for s in reversed(edge.segments)
    )
    wall = Polygon([*feet, (face.length_m, spec.cornice_m), (0, spec.cornice_m)])
    windows = _windows(face, edge, datum, spec)
    for opening in windows:
        cut = wall.difference(opening.shape)
        if not isinstance(cut, Polygon):
            raise TypeError("De Bour opening split masonry")
        wall = cut
        gallery = (
            edge.ring == "outer_xy"
            and edge.edge == 2
            and opening.shape.bounds[1] > 7
            and face.length_m * 0.58
            < (opening.shape.bounds[0] + opening.shape.bounds[2]) / 2
            < face.length_m * 0.78
        )
        if not gallery:
            _glazing(scene, face, opening)
    _panel(scene, face, wall, 0.0, "Cream")
    _rustication(scene, face, wall)
    if edge.ring == "courtyard_xy":
        return
    if edge.edge == 1:
        _front_details(scene, face, datum, ground, spec)
        _crown(scene, face, spec)
    else:
        for z, width, depth in (
            (6.8, 0.42, 0.36),
            (13.1, 0.40, 0.30),
            (14.0, 0.55, 0.50),
        ):
            scene.beam(
                "Building_DebourCornice",
                "Cream",
                _point(face, 0, z, 0.08),
                _point(face, face.length_m, z, 0.08),
                width,
                depth,
            )
    if edge.edge == 2:
        a, b = face.length_m * 0.58, face.length_m * 0.78
        forward = CourtFace(
            _point(face, 0, 0, spec.gallery_depth_m),
            face.tangent,
            face.outward,
            face.length_m,
            face.length_m,
        )
        front = Polygon([(a, 7.1), (b, 7.1), (b, 14.4), (a, 14.4)])
        for opening in windows:
            x = (opening.shape.bounds[0] + opening.shape.bounds[2]) / 2
            if opening.shape.bounds[1] > 7 and a < x < b:
                front = front.difference(opening.shape)
                _glazing(scene, forward, opening)
        if not isinstance(front, Polygon):
            raise TypeError("Gallery openings split its front masonry")
        _panel(scene, forward, front, 0, "Cream")
        for u, v, low, high in ((a, a, 14.4, 7.1), (b, b, 7.1, 14.4)):
            scene.quad(
                "Building_DebourGallerySides",
                "Cream",
                _point(face, u, low),
                _point(face, v, high),
                _point(face, v, high, spec.gallery_depth_m),
                _point(face, u, low, spec.gallery_depth_m),
            )
        for z, reverse in ((7.1, False), (14.4, True)):
            corners = [
                _point(face, a, z),
                _point(face, b, z),
                _point(face, b, z, spec.gallery_depth_m),
                _point(face, a, z, spec.gallery_depth_m),
            ]
            if reverse:
                corners.reverse()
            scene.quad(
                "Building_DebourGalleryCap",
                "Cream",
                corners[0],
                corners[1],
                corners[2],
                corners[3],
            )
        scene.box(
            "Building_DebourGalleryDeck",
            "Cream",
            _point(face, (a + b) / 2, 7.0, (spec.gallery_depth_m + 0.25) / 2),
            b - a + 0.20,
            spec.gallery_depth_m + 0.25,
            0.30,
            math.atan2(face.tangent[1], face.tangent[0]),
        )
        for z, width, depth in ((7.1, 0.26, 0.28), (7.9, 0.18, 0.16)):
            scene.beam(
                "Building_DebourGalleryFrieze",
                "Cream",
                _point(forward, a, z, 0.08),
                _point(forward, b, z, 0.08),
                width,
                depth,
            )
        for opening in windows:
            x0, z0, x1, _ = opening.shape.bounds
            if z0 <= 7 or not a < (x0 + x1) / 2 < b:
                continue
            top = z0 + 0.75
            scene.beam(
                "Building_DebourGalleryInsetRail",
                "Black",
                _point(forward, x0 + 0.08, top, -0.12),
                _point(forward, x1 - 0.08, top, -0.12),
                0.03,
            )
            count = math.ceil((x1 - x0 - 0.16) / 0.26)
            for i in range(count + 1):
                x = x0 + 0.08 + (x1 - x0 - 0.16) * i / count
                scene.beam(
                    "Building_DebourGalleryInsetRail",
                    "Black",
                    _point(forward, x, z0 + 0.02, -0.12),
                    _point(forward, x, top, -0.12),
                    0.022,
                )
        for x in (a + 0.30, a + (b - a) / 3, a + 2 * (b - a) / 3, b - 0.30):
            _column(
                scene,
                face,
                x,
                spec.gallery_depth_m - 0.12,
                _column_ground(face, x, spec.gallery_depth_m - 0.12, ground)
                - datum
                - 0.05,
                6.9,
            )
        for opening in windows:
            x = (opening.shape.bounds[0] + opening.shape.bounds[2]) / 2
            if opening.shape.bounds[1] > 7 and a < x < b:
                # Gallery glazing remains behind its projecting pilasters.
                for side in (-1, 1):
                    scene.beam(
                        "Building_DebourGalleryPiers",
                        "Cream",
                        _point(face, x + side * 1.16, 7.4, spec.gallery_depth_m),
                        _point(face, x + side * 1.16, 13.1, spec.gallery_depth_m),
                        0.26,
                        0.3,
                    )


def _roof(
    scene: CircuitScene, body: Polygon, datum: float, spec: DebourDimensions
) -> None:
    body = orient(body, sign=1)
    inset = body.buffer(-2.0, join_style="mitre")
    for shape, high in ((body.difference(inset), False), (inset, True)):
        for triangle in constrained_delaunay_triangles(shape).geoms:
            coords = list(orient(triangle, sign=1).exterior.coords)[:3]
            points = []
            for x, y in coords:
                rise = (
                    1.5
                    if high or body.boundary.distance(ShapePoint(x, y)) > 0.01
                    else 0.0
                )
                points.append((float(x), float(y), datum + spec.cornice_m + rise))
            scene.triangle(
                "Building_DebourRoof", "Roof", points[0], points[1], points[2]
            )
            scene.triangle(
                "Building_DebourRoof",
                "Roof",
                (points[2][0], points[2][1], points[2][2] - 0.12),
                (points[1][0], points[1][1], points[1][2] - 0.12),
                (points[0][0], points[0][1], points[0][2] - 0.12),
            )
    for ring in (body.exterior, *body.interiors):
        for a, b in pairwise(ring.coords):
            z = datum + spec.cornice_m
            scene.quad(
                "Building_DebourRoof",
                "Roof",
                (a[0], a[1], z),
                (a[0], a[1], z - 0.12),
                (b[0], b[1], z - 0.12),
                (b[0], b[1], z),
            )


def debour(
    scene: CircuitScene,
    layout: MuseumLayout,
    footing: MuseumFooting,
    datum: float,
    ground: Callable[[float, float], float],
    spec: DebourDimensions,
) -> None:
    body = Polygon(layout.outer_xy, [layout.courtyard_xy])
    if not body.is_valid or body.exterior.is_ccw or footing.total_missing_m > 1e-6:
        raise ValueError(
            "De Bour requires literal clockwise outer ring and supported wall feet"
        )
    for edge in footing.paths:
        ring = layout.outer_xy if edge.ring == "outer_xy" else layout.courtyard_xy
        a, b = ring[edge.edge + 1], ring[edge.edge]
        tx, ty = (b[0] - a[0]) / edge.length_m, (b[1] - a[1]) / edge.length_m
        # Courtyard ring must be opposite to the exterior ring.
        normal = (ty, -tx, 0.0)
        face = CourtFace(
            (*a, datum), (tx, ty, 0.0), normal, edge.length_m, edge.length_m
        )
        if body.covers(
            ShapePoint(
                a[0] + tx * edge.length_m / 2 + ty * 0.01,
                a[1] + ty * edge.length_m / 2 - tx * 0.01,
            )
        ):
            raise ValueError("De Bour facade source normal points inward")
        _wall(scene, face, edge, datum, ground, spec)
    _roof(scene, body, datum, spec)


def _crown(scene: CircuitScene, face: CourtFace, spec: DebourDimensions) -> None:
    center = face.length_m / 2
    levels = (
        (spec.cornice_m + 0.3, 2.6, 1.9),
        (spec.cornice_m + 1.0, 2.65, 2.0),
        (spec.cornice_m + 2.7, 2.0, 1.45),
        (spec.cornice_m + spec.crown_rise_m, 1.35, 0.95),
    )

    def p(z: float, rx: float, ry: float, angle: float) -> Point:
        return _point(
            face, center + rx * math.cos(angle), z, -2.4 + ry * math.sin(angle)
        )

    for (z0, x0, y0), (z1, x1, y1) in pairwise(levels):
        for i in range(32):
            a, b = i * math.tau / 32, (i + 1) * math.tau / 32
            scene.quad(
                "Building_DebourMansard",
                "Roof",
                p(z0, x0, y0, b),
                p(z0, x0, y0, a),
                p(z1, x1, y1, a),
                p(z1, x1, y1, b),
            )
    for z, rx, ry, reverse in ((*levels[0], True), (*levels[-1], False)):
        for i in range(32):
            a, b = i * math.tau / 32, (i + 1) * math.tau / 32
            u, v = p(z, rx, ry, a), p(z, rx, ry, b)
            scene.triangle(
                "Building_DebourMansard",
                "Roof",
                _point(face, center, z, -2.4),
                u if reverse else v,
                v if reverse else u,
            )
    scene.box(
        "Building_DebourLantern",
        "Cream",
        _point(face, center, levels[-1][0] + 0.35, -2.4),
        1.5,
        1.2,
        0.7,
        math.atan2(face.tangent[1], face.tangent[0]),
    )
    scene.beam(
        "Building_DebourFinial",
        "Black",
        _point(face, center, levels[-1][0] + 0.70, -2.4),
        _point(face, center, levels[-1][0] + 2.8, -2.4),
        0.045,
    )
