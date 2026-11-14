from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles, set_precision
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_geometry import frame, stone_balcony
from venues.baku_museum_geometry import _glazing
from venues.baku_philharmonic_geometry import solid
from venues.baku_streetscape_dataclasses import PhilharmonicSource


def parts(shape: Polygon | MultiPolygon) -> tuple[Polygon, ...]:
    precise = set_precision(shape, 0.001).simplify(0.0005, preserve_topology=True)
    if isinstance(precise, Polygon):
        return (precise,)
    if isinstance(precise, MultiPolygon):
        return tuple(precise.geoms)
    raise TypeError("Hall facade lost polygonal geometry")


def masonry(
    scene: CircuitScene,
    face: CourtFace,
    shape: Polygon | MultiPolygon,
    material: str,
    front: float = 0,
    back: float = -0.28,
) -> None:
    for part in parts(shape):
        if part.area > 1e-9:
            solid(
                scene, face, part, front, back, material, "Building_PhilharmonicMasonry"
            )


def timber_window(scene: CircuitScene, face: CourtFace, opening: CourtOpening) -> None:
    solid(
        scene,
        face,
        opening.shape,
        -0.10,
        -0.14,
        "Glass",
        "Building_PhilharmonicTimberGlass",
    )
    for a, b in pairwise(opening.shape.exterior.coords):
        scene.beam(
            "Building_PhilharmonicTimberFrames",
            "Trunk",
            _point(face, a[0], a[1], -0.04),
            _point(face, b[0], b[1], -0.04),
            0.09,
        )
    x0, z0, x1, z1 = opening.shape.bounds
    for x in ((x0 + x1) / 2,):
        scene.beam(
            "Building_PhilharmonicTimberMullions",
            "Trunk",
            _point(face, x, z0, -0.02),
            _point(face, x, z1, -0.02),
            0.07,
        )
    for z in (z0 + 1.2, opening.arch_spring_m or z1 - 0.8):
        scene.beam(
            "Building_PhilharmonicTimberMullions",
            "Trunk",
            _point(face, x0, z, -0.02),
            _point(face, x1, z, -0.02),
            0.07,
        )


def hall_body(
    scene: CircuitScene, source: PhilharmonicSource, footprint: Polygon
) -> None:
    building = scene.footprint(152190848)
    original = Polygon(building.ring)
    source_edges = [
        LineString([a, b])
        for a, b in zip(building.ring, building.ring[1:] + building.ring[:1])
    ]
    ring = list(footprint.exterior.coords)
    if not footprint.exterior.is_ccw:
        ring.reverse()
    for a, b in pairwise(ring):
        if math.dist(a, b) < 0.02:
            continue
        face = frame((*a, source.base_m), (*b, source.base_m))
        line = LineString([a, b])
        owner = min(
            range(len(source_edges)),
            key=lambda i: source_edges[i].distance(line.centroid),
        )
        literal_face = all(
            source_edges[owner].distance(ShapePoint(p)) < 0.001 for p in (a, b)
        )
        openings: list[CourtOpening] = []
        oriel = 1 <= owner <= 10
        rotunda = 14 <= owner <= 23
        if oriel:
            openings.extend(
                (
                    _opening(
                        face.length_m / 2,
                        min(1.4, face.length_m * 0.6),
                        1.6,
                        3.0,
                        False,
                        False,
                    ),
                    _opening(
                        face.length_m / 2, face.length_m * 0.8, 6.1, 4.4, True, False
                    ),
                )
            )
        elif owner == 11:
            for i in range(7):
                x = face.length_m * (i + 0.5) / 7
                openings.extend(
                    (
                        _opening(x, 1.25, 1.5, 3.0, False, False),
                        _opening(x, 1.6, 6.1, 4.4, True, False),
                    )
                )
        elif rotunda:
            openings.append(
                _opening(
                    face.length_m / 2,
                    min(1.65, face.length_m * 0.58),
                    1.5,
                    3.1,
                    False,
                    False,
                )
            )
        elif owner == 26:
            for i in range(7):
                x = face.length_m * (0.16 + 0.68 * (i + 0.5) / 7)
                openings.extend(
                    (
                        _opening(x, 2.5, 1.2, 3.0, True, False),
                        _opening(x, 3.25, 6.1, 3.8, True, False),
                    )
                )
            for t in (0.065, 0.935):
                openings.append(
                    _opening(face.length_m * t, 2.2, 6.1, 3.5, False, False)
                )
        elif owner in (0, 12, 13, 24):
            for low, h in ((1.5, 3.1), (6.1, 3.3)):
                openings.append(
                    _opening(
                        face.length_m / 2,
                        min(1.7, face.length_m * 0.5),
                        low,
                        h,
                        False,
                        False,
                    )
                )
        else:
            for i in range(max(1, round(face.length_m / 6))):
                x = face.length_m * (i + 0.5) / max(1, round(face.length_m / 6))
                openings.append(_opening(x, 1.5, 1.5, 3.1, False, False))
        openings = [
            opening
            for opening in openings
            if literal_face
            and face.length_m >= 2.2
            and opening.shape.bounds[0] >= 0.2
            and opening.shape.bounds[2] <= face.length_m - 0.2
            and (owner != 26 or face.length_m >= source_edges[26].length * 0.5)
        ]
        holes = unary_union([opening.shape for opening in openings])
        shape = box(0, 0, face.length_m, source.body_top_m).difference(holes)
        if not isinstance(shape, (Polygon, MultiPolygon)):
            raise TypeError("Hall facade masonry must remain polygonal")
        masonry(scene, face, shape, "BakuPhilharmonicOchre")
        if oriel:
            wood = shape.intersection(box(0, 5.85, face.length_m, 10.85))
            if isinstance(wood, (Polygon, MultiPolygon)):
                masonry(scene, face, wood, "Trunk", 0.025, -0.02)
        for opening in openings:
            if (oriel or owner == 11) and opening.shape.bounds[1] > 5:
                timber_window(scene, face, opening)
            else:
                _glazing(scene, face, opening)
        for z, h, depth in (
            (0.35, 0.18, 0.18),
            (5.1, 0.3, 0.12),
            (5.55, 0.2, 0.10),
            (10.85, 0.22, 0.40),
            (11.15, 0.35, 0.50),
        ):
            masonry(
                scene,
                face,
                box(0, z, face.length_m, z + h),
                "White",
                depth if literal_face else min(depth, 0.02),
                0,
            )
        if literal_face and (owner == 11 or oriel):
            for i in range(8 if owner == 11 else 2):
                x = face.length_m * i / (7 if owner == 11 else 1)
                masonry(
                    scene,
                    face,
                    box(max(0, x - 0.07), 5.9, min(face.length_m, x + 0.07), 10.8),
                    "Trunk",
                    0.08,
                    -0.05,
                )
            for z in (6.0, 9.2, 10.45):
                masonry(
                    scene,
                    face,
                    box(0, z, face.length_m, z + 0.12),
                    "Trunk",
                    0.10,
                    -0.02,
                )
        elif literal_face and owner == 26 and face.length_m > 3:
            stone_balcony(scene, face, 0.1, face.length_m - 0.1, 11.5, 0.26)
    arc_points = building.ring[14:25]
    arc = LineString(
        arc_points if original.exterior.is_ccw else list(reversed(arc_points))
    )
    for i in range(7):
        distance = arc.length * (i + 0.5) / 7
        p = arc.interpolate(distance)
        a, b = (
            arc.interpolate(max(0, distance - 0.05)),
            arc.interpolate(min(arc.length, distance + 0.05)),
        )
        length = math.dist(a.coords[0], b.coords[0])
        tangent = ((b.x - a.x) / length, (b.y - a.y) / length, 0.0)
        outward = (tangent[1], -tangent[0], 0.0)
        start = (p.x - tangent[0] * 2, p.y - tangent[1] * 2, source.base_m)
        face = CourtFace(start, tangent, outward, 4.0, 4.0)
        niche = _opening(2.0, 2.8, 6.1, 3.8, True, False)
        masonry(scene, face, niche.shape, "Cream", 0.035, -0.02)
        surround = niche.shape.buffer(0.18).difference(niche.shape)
        if isinstance(surround, (Polygon, MultiPolygon)):
            masonry(scene, face, surround, "White", 0.16, 0)
        stone_balcony(scene, face, 0.45, 3.55, 6.1, 0.28)
    for triangle in constrained_delaunay_triangles(footprint).geoms:
        coords = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coords.reverse()
        points: list[Point] = [
            (float(x), float(y), source.base_m + source.body_top_m) for x, y in coords
        ]
        scene.triangle(
            "Building_PhilharmonicFlatRoof", "Roof", points[0], points[1], points[2]
        )
