from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles, set_precision
from shapely.affinity import affine_transform
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_geometry import frame
from venues.baku_museum_geometry import _glazing
from venues.baku_philharmonic_geometry import solid
from venues.baku_streetscape_dataclasses import UniversitySource, UniversityWall


def foot(side: UniversityWall, along: float) -> float:
    points = side.feet_along_height_m
    for (x0, z0), (x1, z1) in pairwise(points):
        if x1 - x0 > 1e-9 and x0 - 1e-7 <= along <= x1 + 1e-7:
            return z0 + (z1 - z0) * (along - x0) / (x1 - x0)
    raise ValueError("Missing historic facade foot interval")


def occupied_wall(side: UniversityWall, height: float) -> Polygon:
    points = [(x, z - 0.06) for x, z in side.feet_along_height_m]
    return Polygon([*points, (points[-1][0], height), (0, height)])


def relief(
    scene: CircuitScene,
    face: CourtFace,
    shape: Polygon | MultiPolygon,
    front: float,
    back: float,
    material: str = "White",
) -> None:
    shape = set_precision(shape, 0.001).simplify(0.0005, preserve_topology=True)
    if not isinstance(shape, (Polygon, MultiPolygon)):
        raise TypeError("Historic relief lost its polygonal geometry")
    for part in shape.geoms if isinstance(shape, MultiPolygon) else (shape,):
        if part.area > 1e-9:
            solid(scene, face, part, front, back, material, "Building_HistoricRelief")


def iron_balcony(
    scene: CircuitScene, face: CourtFace, left: float, right: float, z: float
) -> None:
    for low, high, front, back in (
        (z - 0.18, z, 0.92, -0.02),
        (z + 0.94, z + 1.0, 0.95, 0.86),
    ):
        relief(
            scene,
            face,
            box(left - 0.1, low, right + 0.1, high),
            front,
            back,
            "Cream" if low < z else "Black",
        )
    for a, da, b, db in (
        (left, 0.9, right, 0.9),
        (left, 0.0, left, 0.9),
        (right, 0.0, right, 0.9),
    ):
        length = math.hypot(b - a, db - da)
        count = max(1, round(length / 0.42))
        for i in range(count + 1):
            t = i / count
            x, depth = a + (b - a) * t, da + (db - da) * t
            scene.beam(
                "Building_HistoricIron",
                "Black",
                _point(face, x, z, depth),
                _point(face, x, z + 0.94, depth),
                0.025,
            )
            if i == count:
                continue
            cx, cd = a + (b - a) * (i + 0.5) / count, da + (db - da) * (i + 0.5) / count
            for j in range(10):
                aa, bb = j * math.tau / 10, (j + 1) * math.tau / 10
                scene.beam(
                    "Building_HistoricIron",
                    "Black",
                    _point(
                        face,
                        cx + 0.16 * math.cos(aa),
                        z + 0.46 + 0.30 * math.sin(aa),
                        cd,
                    ),
                    _point(
                        face,
                        cx + 0.16 * math.cos(bb),
                        z + 0.46 + 0.30 * math.sin(bb),
                        cd,
                    ),
                    0.023,
                )
    for x in (left + 0.3, right - 0.3):
        shape = Polygon(
            [
                (x - 0.12, z - 0.16),
                (x + 0.12, z - 0.16),
                (x + 0.08, z - 0.7),
                (x - 0.04, z - 0.82),
            ]
        )
        relief(scene, face, shape, 0.65, 0.05, "Cream")


def historic_facade(scene: CircuitScene, source: UniversitySource) -> None:
    scene.modeled_buildings.add(source.osm_id)
    front = frame((*source.ring[8], source.datum_m), (*source.ring[11], source.datum_m))
    length = front.length_m
    centers = tuple(
        t * length
        for t in (
            0.05,
            0.145,
            0.205,
            0.265,
            0.325,
            0.41,
            0.5,
            0.59,
            0.675,
            0.735,
            0.795,
            0.855,
            0.95,
        )
    )
    openings = []
    for bay, x in enumerate(centers):
        for row, (low, high) in enumerate(((2.5, 5.8), (7.0, 9.8), (11.0, 13.7))):
            door = bay == 6 and row == 0
            width = 2.1 if door else 1.70 if bay in (0, 12) else 1.25
            opening = _opening(
                x,
                width,
                0.2 if door else low,
                high - (0.2 if door else low),
                row == 0,
                door,
            )
            openings.append(opening)
        if bay != 6:
            openings.append(_opening(x, 0.95, 0.55, 0.8, False, False))
    holes = unary_union([opening.shape for opening in openings])
    front_sides = [side for side in source.walls if side.edge in (8, 9, 10)]
    for side in source.walls:
        face = frame(side.start, side.end)
        wall = occupied_wall(side, source.cornice_m)
        if side.edge in (8, 9, 10):
            start = sum(
                (side.start[j] - front.start[j]) * front.tangent[j] for j in range(2)
            )
            scale = face.length_m / sum(
                (side.end[j] - side.start[j]) * front.tangent[j] for j in range(2)
            )
            cut = affine_transform(holes, [scale, 0, 0, 1, -start * scale, 0])
            wall = wall.difference(cut)
        if not isinstance(wall, (Polygon, MultiPolygon)):
            raise TypeError("Historic wall must retain polygonal masonry")
        relief(scene, face, wall, 0, -0.28, "Cream")
        for z, thick, breadth in (
            (2.0, 0.18, 0.16),
            (6.1, 0.28, 0.32),
            (10.2, 0.18, 0.28),
            (14.15, 0.20, 0.35),
            (14.7, 0.32, 0.55),
        ):
            for (a, za), (b, zb) in pairwise(side.feet_along_height_m):
                if a < b and max(za, zb) < z:
                    relief(scene, face, box(a, z, b, z + thick), breadth, -0.01)
    for x in (centers[0], centers[12]):
        outer = box(x - 1.25, 6.4, x + 1.25, 14.3)
        projected = outer.difference(holes)
        if not isinstance(projected, (Polygon, MultiPolygon)):
            raise TypeError("Terminal oriel must retain its solid masonry")
        relief(scene, front, projected, 0.60, 0, "Cream")
        relief(scene, front, box(x - 1.4, 6.1, x + 1.4, 6.45), 0.72, 0)
        relief(scene, front, box(x - 1.4, 14.0, x + 1.4, 14.4), 0.72, 0)
    for opening in openings:
        x0, z0, x1, z1 = opening.shape.bounds
        clipped = opening.shape
        for side in front_sides:
            start = sum(
                (side.start[j] - front.start[j]) * front.tangent[j] for j in range(2)
            )
            if start <= (x0 + x1) / 2 <= start + math.dist(side.start, side.end):
                ground = max(
                    foot(
                        side, max(0.0, min(math.dist(side.start, side.end), x - start))
                    )
                    for x in (x0, x1)
                )
                clipped = opening.shape.intersection(
                    box(-1, ground + 0.02, length + 1, source.cornice_m)
                )
                break
        if not isinstance(clipped, Polygon) or clipped.area < 0.05:
            continue
        center = (x0 + x1) / 2
        oriel = (
            z0 > 6 and min(abs(center - centers[0]), abs(center - centers[12])) < 0.1
        )
        opening_face = (
            CourtFace(
                _point(front, 0, 0, 0.6),
                front.tangent,
                front.outward,
                front.length_m,
                front.source_length_m,
            )
            if oriel
            else front
        )
        _glazing(
            scene,
            opening_face,
            CourtOpening(clipped, opening.door, opening.arch_spring_m),
        )
        surround = opening.shape.buffer(0.13, join_style="mitre").difference(
            opening.shape
        )
        if isinstance(surround, (Polygon, MultiPolygon)):
            relief(scene, opening_face, surround, 0.13, -0.02)
        if z0 > 6:
            relief(
                scene,
                opening_face,
                box(x0 - 0.17, z1 + 0.10, x1 + 0.17, z1 + 0.23),
                0.24,
                0.02,
            )
            if 6.5 < z0 < 10 and x0 > centers[4] and x1 < centers[8]:
                pediment = Polygon(
                    [
                        (x0 - 0.22, z1 + 0.28),
                        ((x0 + x1) / 2, z1 + 0.77),
                        (x1 + 0.22, z1 + 0.28),
                    ]
                )
                relief(scene, opening_face, pediment, 0.25, 0.02)
    for a, b, z in (
        (centers[1] - 0.85, centers[4] + 0.85, 6.55),
        (centers[8] - 0.85, centers[11] + 0.85, 6.55),
        (centers[5] - 0.95, centers[7] + 0.95, 10.55),
    ):
        iron_balcony(scene, front, a, b, z)
    for x in ((centers[5] + centers[6]) / 2, (centers[6] + centers[7]) / 2):
        panel = box(x - 0.37, 7.05, x + 0.37, 9.55)
        relief(scene, front, panel.buffer(0.09).difference(panel), 0.13, -0.01)
        pediment = Polygon([(x - 0.52, 9.65), (x, 10.08), (x + 0.52, 9.65)])
        relief(scene, front, pediment, 0.20, 0)
    for a, b in (
        (0.0, centers[0] + 1.3),
        (centers[12] - 1.3, length),
        (centers[5] - 1.35, centers[7] + 1.35),
    ):
        for x in (a + 0.16, b - 0.16):
            for z0, z1 in ((2.1, 6.1), (6.4, 10.2), (10.4, 14.1)):
                relief(scene, front, box(x - 0.13, z0, x + 0.13, z1), 0.22, 0.02)
        if a == 0 or b == length:
            pediment = Polygon([(a - 0.1, 14.4), ((a + b) / 2, 15.7), (b + 0.1, 14.4)])
            relief(scene, front, pediment, 0.42, -0.04)
    for i in range(round(length / 0.38)):
        x = i * 0.38
        relief(scene, front, box(x, 14.28, x + 0.16, 14.55), 0.38, 0.12)
    for z in (2.5 + i * 0.38 for i in range(9)):
        bands = box(0, z, length, z + 0.035).difference(holes.buffer(0.02))
        if isinstance(bands, (Polygon, MultiPolygon)):
            relief(scene, front, bands, 0.045, 0.005)
    roof(scene, source, front, centers)


def roof(
    scene: CircuitScene,
    source: UniversitySource,
    face: CourtFace,
    centers: tuple[float, ...],
) -> None:
    occupied = Polygon(source.ring)
    outer = occupied.buffer(0.12, join_style="mitre")
    inner = occupied.buffer(-1.6, join_style="mitre")
    if not isinstance(outer, Polygon) or not isinstance(inner, Polygon):
        raise TypeError("Historic roof must retain one inset deck")
    holes = []
    dormers = []
    for x in centers[5:8]:
        opening = _opening(x, 1.2, source.cornice_m + 0.4, 1.05, False, False)
        dormers.append(opening)
        holes.append(
            Polygon(
                [
                    _point(
                        face,
                        px,
                        pz,
                        0.12 - (pz - source.cornice_m) / source.mansard_m * 1.72,
                    )[:2]
                    for px, pz in opening.shape.buffer(
                        0.18, join_style="mitre"
                    ).exterior.coords
                ]
            )
        )
    for shape in (outer.difference(inner).difference(unary_union(holes)), inner):
        for triangle in constrained_delaunay_triangles(shape).geoms:
            coords = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                coords.reverse()
            points: list[Point] = [
                (
                    float(x),
                    float(y),
                    source.datum_m
                    + source.cornice_m
                    + source.mansard_m
                    * min(1.0, outer.boundary.distance(ShapePoint(x, y)) / 1.72),
                )
                for x, y in coords
            ]
            scene.triangle(
                "Building_HistoricMansard", "Roof", points[0], points[1], points[2]
            )
    for opening in dormers:
        x0, z0, x1, z1 = opening.shape.bounds
        silhouette = Polygon(
            [
                (x0 - 0.18, z0 - 0.15),
                (x1 + 0.18, z0 - 0.15),
                (x1 + 0.18, z1 + 0.12),
                ((x0 + x1) / 2, z1 + 0.5),
                (x0 - 0.18, z1 + 0.12),
            ]
        )
        surround = silhouette.difference(opening.shape)
        if not isinstance(surround, Polygon):
            raise TypeError("Dormer surround invalid")
        relief(scene, face, surround, 0.08, -1.6)
        _glazing(scene, face, opening)
