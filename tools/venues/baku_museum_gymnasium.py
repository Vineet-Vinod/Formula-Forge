"""Source-fitted Mariinsky gymnasium; levels remain architectural estimates."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_museum_dataclasses import MuseumEdge, MuseumFooting, MuseumLayout
from venues.baku_museum_geometry import (
    _balcony,
    _glazing,
    _panel,
    _relief,
    _rustication,
    grade,
)


def _openings(face: CourtFace, edge: MuseumEdge, datum: float) -> list[CourtOpening]:
    count = (
        3
        if edge.role == "front_center"
        else 4
        if edge.role in ("front_west", "front_east")
        else 6
        if edge.role == "northwest_side"
        else 18
        if edge.role == "connector_side"
        else 0
    )
    rows = (
        ((0.9, 4.8), (6.5, 11.7), (14.1, 18.6))
        if edge.role == "front_center"
        else ((0.9, 4.4), (6.5, 9.7), (13.2, 16.0))
    )
    result = []
    for bay in range(count):
        center = face.length_m * (bay + 0.5) / count
        local_ground = grade(edge, face.length_m - center) - datum
        for floor, (low, high) in enumerate(rows):
            door = edge.role == "front_center" and floor == 0 and bay == 1
            bottom = (
                local_ground + 0.18
                if door
                else max(low, local_ground + 0.48)
                if floor == 0
                else low
            )
            if high - bottom < 0.8:
                continue
            result.append(
                _opening(
                    center,
                    2.1
                    if door
                    else 2.55
                    if edge.role == "front_center" and floor > 0
                    else 2.15
                    if edge.role == "front_center"
                    else 1.6,
                    bottom,
                    (3.8 if door else high) - bottom,
                    edge.role == "front_center" and (floor == 1 or door),
                    door,
                )
            )
    return result


def _wall(scene: CircuitScene, face: CourtFace, edge: MuseumEdge, datum: float) -> None:
    height = 22.0 if edge.role in ("front_center", "return") else 20.0
    feet = [(0.0, grade(edge, edge.length_m) - datum - 0.05)]
    feet.extend(
        (edge.length_m - segment.along_m[0], segment.points[0][2] - datum - 0.05)
        for segment in reversed(edge.segments)
    )
    wall = Polygon([*feet, (face.length_m, height), (0.0, height)])
    for opening in _openings(face, edge, datum):
        cut = wall.difference(opening.shape)
        if not isinstance(cut, Polygon):
            raise TypeError("Gymnasium opening must leave continuous masonry")
        wall = cut
        _glazing(scene, face, opening)
    _panel(scene, face, wall, 0.0, "Cream")
    if edge.role in (
        "front_west",
        "front_center",
        "front_east",
        "connector_side",
        "northwest_side",
    ):
        _rustication(scene, face, wall)
    for interval in edge.segments:
        a, b = interval.points
        scene.beam(
            "Building_GymnasiumBase",
            "Concrete",
            add(a, (0, 0, -0.015)),
            add(b, (0, 0, -0.015)),
            0.14,
            0.12,
        )
    if edge.role == "held":
        return
    bands = (
        ((5.6, 0.36, 0.32), (12.4, 0.40, 0.34), (20.3, 0.62, 0.52), (21.65, 0.34, 0.34))
        if edge.role == "front_center"
        else (
            (5.6, 0.36, 0.32),
            (11.8, 0.40, 0.34),
            (18.25, 0.58, 0.48),
            (19.65, 0.32, 0.32),
        )
    )
    for z, width, depth in bands:
        scene.beam(
            "Building_GymnasiumCornice",
            "Cream",
            _point(face, 0, z, 0.08),
            _point(face, face.length_m, z, 0.08),
            width,
            depth,
        )
    if edge.role in ("front_west", "front_center", "front_east"):
        for along in (0.0, face.length_m):
            low = max(0.2, grade(edge, face.length_m - along) - datum)
            scene.beam(
                "Building_GymnasiumPiers",
                "Cream",
                _point(face, along, low, 0.1),
                _point(face, along, height - 1.7, 0.1),
                0.48,
                0.40,
            )
    if edge.role == "front_center":
        for i in range(3):
            center = face.length_m * (i + 0.5) / 3
            pediment = Polygon(
                [(center - 1.525, 19.1), (center + 1.525, 19.1), (center, 19.8)]
            )
            _relief(scene, face, pediment, 0.16, -0.2)
            points = [
                _point(face, float(x), float(z), 0.16)
                for x, z in list(pediment.exterior.coords)
            ]
            for a, b in pairwise(points):
                scene.beam("Building_GymnasiumPediments", "Cream", a, b, 0.18, 0.2)
        _balcony(scene, face, 1.1, face.length_m - 1.1, 6.2, 0.8)
        center = face.length_m / 2
        _balcony(scene, face, center - 1.6, center + 1.6, 13.0, 0.6)
        _relief(
            scene,
            face,
            Polygon(
                [
                    (0, 21.95),
                    (face.length_m, 21.95),
                    (face.length_m, 23.0),
                    (face.length_m * 0.73, 23.8),
                    (face.length_m * 0.27, 23.8),
                    (0, 23.0),
                ]
            ),
            0.06,
            -0.3,
        )
    elif edge.role != "return":
        for z in (height + 0.08, height + 0.75):
            scene.beam(
                "Building_GymnasiumRoofIron",
                "Black",
                _point(face, 0.2, z),
                _point(face, face.length_m - 0.2, z),
                0.035,
            )
        for i in range(math.ceil((face.length_m - 0.4) / 0.48) + 1):
            x = 0.2 + (face.length_m - 0.4) * i / math.ceil(
                (face.length_m - 0.4) / 0.48
            )
            scene.beam(
                "Building_GymnasiumRoofIron",
                "Black",
                _point(face, x, height + 0.08),
                _point(face, x, height + 0.75),
                0.025,
            )


def _roof(scene: CircuitScene, shape: Polygon, level: float, raised: bool) -> None:
    shape = orient(shape, sign=1.0)
    inset = shape.buffer(-2.8, join_style="mitre") if not raised else Polygon()
    surfaces = (
        [(shape.difference(inset), False), (inset, True)]
        if not inset.is_empty
        else [(shape, False)]
    )
    for surface, high in surfaces:
        for triangle in constrained_delaunay_triangles(surface).geoms:
            coords = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                coords.reverse()
            points = []
            for x, y in coords:
                rise = (
                    0.0
                    if raised
                    else 1.25
                    if high or shape.boundary.distance(ShapePoint(x, y)) > 0.01
                    else 0.0
                )
                points.append((float(x), float(y), level + rise))
            scene.triangle(
                "Building_GymnasiumRoof", "Roof", points[0], points[1], points[2]
            )
            scene.triangle(
                "Building_GymnasiumRoof",
                "Roof",
                add(points[2], (0, 0, -0.12)),
                add(points[1], (0, 0, -0.12)),
                add(points[0], (0, 0, -0.12)),
            )
    for ring in (shape.exterior, *shape.interiors):
        for a, b in pairwise(ring.coords):
            scene.quad(
                "Building_GymnasiumRoof",
                "Roof",
                (a[0], a[1], level),
                (a[0], a[1], level - 0.12),
                (b[0], b[1], level - 0.12),
                (b[0], b[1], level),
            )


def gymnasium(
    scene: CircuitScene,
    layout: MuseumLayout,
    footing: MuseumFooting,
    datum: float,
) -> None:
    if footing.total_missing_m > 1e-6:
        raise ValueError("Gymnasium lacks actual emitted-ground support")
    body = Polygon(layout.outer_xy)
    if not body.is_valid or body.exterior.is_ccw:
        raise ValueError(
            "Gymnasium study expects the normalized clockwise literal C ring"
        )
    for edge in footing.paths:
        a, b = layout.outer_xy[edge.edge + 1], layout.outer_xy[edge.edge]
        tx, ty = (b[0] - a[0]) / edge.length_m, (b[1] - a[1]) / edge.length_m
        face = CourtFace(
            (a[0], a[1], datum), (tx, ty, 0), (ty, -tx, 0), edge.length_m, edge.length_m
        )
        if body.covers(
            ShapePoint(
                a[0] + tx * edge.length_m / 2 + ty * 0.01,
                a[1] + ty * edge.length_m / 2 - tx * 0.01,
            )
        ):
            raise ValueError("Gymnasium source facade normal points inward")
        _wall(scene, face, edge, datum)
    # Only the literal mapped front projection is raised; rear roof depths remain estimates.
    original = list(reversed(layout.outer_xy))
    projection = Polygon([original[i] for i in (4, 5, 6, 7)])
    if not body.covers(projection):
        raise ValueError("Gymnasium central roof must stay inside literal footprint")
    main = body.difference(projection)
    if not isinstance(main, Polygon):
        raise TypeError("Gymnasium roof split must remain connected")
    _roof(scene, main, datum + 20.0, False)
    _roof(scene, projection, datum + 22.0, True)
    a, b = original[4], original[7]
    face = CourtFace(
        (a[0], a[1], datum),
        ((b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b), 0),
        (0, 0, 0),
        math.dist(a, b),
        math.dist(a, b),
    )
    line = LineString([a, b])
    midpoint = line.interpolate(0.5, normalized=True)
    nx, ny = face.tangent[1], -face.tangent[0]
    if projection.covers(ShapePoint(midpoint.x + nx * 0.01, midpoint.y + ny * 0.01)):
        a, b = b, a
    scene.quad(
        "Building_GymnasiumRoofStep",
        "Cream",
        (*a, datum + 20),
        (*b, datum + 20),
        (*b, datum + 22),
        (*a, datum + 22),
    )
