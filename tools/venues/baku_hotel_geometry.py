"""NW rear and photographed returns; metric heights and datum remain estimates."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, box

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_dataclasses import HotelDimensions, HotelLayout
from venues.baku_museum_geometry import _glazing, _panel, _relief


def frame(a: Point, b: Point) -> CourtFace:
    length = math.dist(a[:2], b[:2])
    tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.0)
    return CourtFace(a, tangent, (tangent[1], -tangent[0], 0), length, length)


def stone_balcony(
    scene: CircuitScene, face: CourtFace, a: float, b: float, level: float, depth: float
) -> None:
    heading = math.atan2(face.tangent[1], face.tangent[0])
    scene.box(
        "Building_HotelStoneRailBase",
        "Cream",
        _point(face, (a + b) / 2, level - 0.08, depth / 2),
        b - a + 0.10,
        depth + 0.10,
        0.16,
        heading,
    )
    for x0, d0, x1, d1 in ((a, depth, b, depth), (a, 0, a, depth), (b, 0, b, depth)):
        scene.beam(
            "Building_HotelStoneRailCap",
            "Cream",
            _point(face, x0, level + 0.82, d0),
            _point(face, x1, level + 0.82, d1),
            0.17,
            0.18,
        )
        count = max(1, math.ceil(math.hypot(x1 - x0, d1 - d0) / 0.28))
        for i in range(count + 1):
            t = i / count
            x = x0 + (x1 - x0) * t
            d = d0 + (d1 - d0) * t
            for (z0, r0), (z1, r1) in pairwise(
                ((0, 0.07), (0.15, 0.09), (0.39, 0.045), (0.66, 0.065), (0.74, 0.07))
            ):
                for j in range(6):
                    aa, bb = j * math.tau / 6, (j + 1) * math.tau / 6
                    scene.quad(
                        "Building_HotelStoneBaluster",
                        "Cream",
                        _point(
                            face,
                            x + r0 * math.cos(aa),
                            level + z0,
                            d + r0 * math.sin(aa),
                        ),
                        _point(
                            face,
                            x + r0 * math.cos(bb),
                            level + z0,
                            d + r0 * math.sin(bb),
                        ),
                        _point(
                            face,
                            x + r1 * math.cos(bb),
                            level + z1,
                            d + r1 * math.sin(bb),
                        ),
                        _point(
                            face,
                            x + r1 * math.cos(aa),
                            level + z1,
                            d + r1 * math.sin(aa),
                        ),
                    )


def iron_balcony(
    scene: CircuitScene, face: CourtFace, center: float, level: float
) -> None:
    left, right = center - 1.15, center + 1.15
    scene.box(
        "Building_HotelBalconyDeck",
        "Cream",
        _point(face, center, level - 0.10, 0.43),
        2.48,
        0.94,
        0.20,
        math.atan2(face.tangent[1], face.tangent[0]),
    )
    for a, b, c, d in (
        (left, 0.83, right, 0.83),
        (left, 0, left, 0.83),
        (right, 0, right, 0.83),
    ):
        scene.beam(
            "Building_HotelIronRail",
            "Black",
            _point(face, a, level + 0.93, b),
            _point(face, c, level + 0.93, d),
            0.055,
            0.06,
        )
        count = math.ceil(math.hypot(c - a, d - b) / 0.20)
        for i in range(count + 1):
            t = i / count
            x = a + (c - a) * t
            depth = b + (d - b) * t
            scene.beam(
                "Building_HotelIronRail",
                "Black",
                _point(face, x, level + 0.03, depth),
                _point(face, x, level + 0.93, depth),
                0.028,
                0.035,
            )
    for x in (center - 0.85, center + 0.85):
        _relief(
            scene,
            face,
            Polygon(
                [
                    (x - 0.14, level - 0.75),
                    (x + 0.14, level - 0.75),
                    (x + 0.23, level - 0.14),
                    (x - 0.23, level - 0.14),
                ]
            ),
            0.63,
            0.04,
        )


def visible_glazing(
    scene: CircuitScene, face: CourtFace, opening: CourtOpening, mask: Polygon
) -> None:
    visible = opening.shape.intersection(mask)
    pieces = (
        [visible]
        if isinstance(visible, Polygon)
        else list(visible.geoms)
        if isinstance(visible, MultiPolygon)
        else []
    )
    for piece in pieces:
        if piece.area > 1e-6:
            _panel(scene, face, piece, -0.18, "Glass")
    for a, b in pairwise(opening.shape.exterior.coords):
        segment = LineString([a, b]).intersection(mask)
        parts = (
            [segment]
            if isinstance(segment, LineString)
            else list(segment.geoms)
            if isinstance(segment, MultiLineString)
            else []
        )
        for part in parts:
            if part.length < 0.001:
                continue
            aa, bb = part.coords[0], part.coords[-1]
            scene.quad(
                "Building_HotelWindowReveals",
                "Cream",
                _point(face, aa[0], aa[1]),
                _point(face, bb[0], bb[1]),
                _point(face, bb[0], bb[1], -0.18),
                _point(face, aa[0], aa[1], -0.18),
            )
            scene.beam(
                "Building_HotelWindowTrim",
                "Cream",
                _point(face, aa[0], aa[1], 0.025),
                _point(face, bb[0], bb[1], 0.025),
                0.085,
                0.085,
            )
            scene.beam(
                "Building_HotelWindowFrames",
                "Black",
                _point(face, aa[0], aa[1], -0.145),
                _point(face, bb[0], bb[1], -0.145),
                0.055,
                0.055,
            )
    x0, z0, x1, z1 = opening.shape.bounds
    center = (x0 + x1) / 2
    transom = (
        opening.arch_spring_m
        if opening.arch_spring_m is not None
        else z0 + (z1 - z0) * 0.72
    )
    for line in (
        LineString([(center, z0), (center, z1)]),
        LineString([(x0, transom), (x1, transom)]),
    ):
        segment = line.intersection(mask)
        parts = (
            [segment]
            if isinstance(segment, LineString)
            else list(segment.geoms)
            if isinstance(segment, MultiLineString)
            else []
        )
        for part in parts:
            if part.length < 0.001:
                continue
            aa, bb = part.coords[0], part.coords[-1]
            scene.beam(
                "Building_HotelWindowMullions",
                "Black",
                _point(face, aa[0], aa[1], -0.145),
                _point(face, bb[0], bb[1], -0.145),
                0.045,
                0.045,
            )


def wall(
    scene: CircuitScene,
    face: CourtFace,
    centers: tuple[float, ...],
    dimensions: HotelDimensions,
    lower_known: bool,
    feet: tuple[tuple[float, float], ...] | None = None,
    plain: bool = False,
    rail_start: float = 0.0,
    lower_balustrades: bool | None = None,
    service_grilles: tuple[float, ...] = (),
    ground_width_m: float = 2.0,
) -> None:
    openings: list[CourtOpening] = []
    rows = (
        (
            (1.1, 7.4, True),
            (9.0, 12.0, False),
            (13.2, 16.2, True),
            (17.2, 19.8, False),
            (20.6, 23.2, False),
            (24.0, 26.6, False),
            (27.4, 30.0, True),
            (31.5, 33.0, False),
        )
        if lower_known
        else (
            (17.2, 19.8, False),
            (20.6, 23.2, False),
            (24.0, 26.6, False),
            (27.4, 30.0, True),
            (31.5, 33.0, False),
        )
    )
    for center in centers:
        for low, high, arched in rows:
            width = (
                ground_width_m
                if low < 8
                else (1.4 if plain else 2.0)
                if low < 31
                else 1.2
            )
            openings.append(
                _opening(
                    center,
                    width,
                    low,
                    high - low,
                    arched and (not plain or low < 8 and ground_width_m > 2.0),
                    False,
                )
            )
        for offset in () if plain else (-2.45,):
            x = center + offset
            if 0.6 < x < face.length_m - 0.6:
                for low, high, arched in rows:
                    if low < 15:
                        continue
                    openings.append(
                        _opening(x, 0.78, low + 0.65, high - low - 0.9, arched, False)
                    )
    openings.extend(_opening(x, 1.0, 30.1, 2.9, False, False) for x in service_grilles)
    shape = box(0, -0.10, face.length_m, dimensions.cornice_m)
    mask = (
        Polygon(
            [
                *((x, z + 0.08) for x, z in feet),
                (face.length_m, dimensions.cornice_m + 0.5),
                (0, dimensions.cornice_m + 0.5),
            ]
        )
        if feet
        else box(0, -1, face.length_m, dimensions.cornice_m + 0.5)
    )
    if not mask.is_valid:
        raise ValueError("Invalid actual hotel Ground profile")
    for opening in openings:
        result = shape.difference(opening.shape.intersection(mask))
        if not isinstance(result, Polygon):
            raise TypeError("Hotel openings split masonry")
        shape = result
        visible_glazing(scene, face, opening, mask)
    _panel(scene, face, shape, 0, "Cream")
    _panel(
        scene,
        face,
        box(0, dimensions.cornice_m, face.length_m, dimensions.cornice_m + 0.5),
        0,
        "Cream",
    )
    if plain:
        for level in (8.6, 17.0, 30.7, 34.0):
            scene.beam(
                "Building_HotelPlainCornice",
                "Cream",
                _point(face, 0, level),
                _point(face, face.length_m, level),
                0.30,
                0.22,
            )
        return
    for center in centers:
        for low in (17.2, 20.6, 24.0, 27.4):
            iron_balcony(scene, face, center, low)
        for low in (20.6, 24.0):
            _relief(
                scene,
                face,
                box(center - 1.18, low + 2.72, center + 1.18, low + 2.86),
                0.20,
                0.02,
            )
    for level, width, height in (
        (8.6, 0.43, 0.36),
        (17.0, 0.54, 0.38),
        (30.7, 0.68, 0.43),
        (33.8, 0.82, 0.48),
        (34.12, 0.54, 0.18),
    ):
        scene.beam(
            "Building_HotelCornice",
            "Cream",
            _point(face, 0, level, 0.12),
            _point(face, face.length_m, level, 0.12),
            width,
            height,
        )
    balustrades = lower_known if lower_balustrades is None else lower_balustrades
    if balustrades:
        for level in (8.6, 17.0):
            stone_balcony(scene, face, 0.08, face.length_m - 0.08, level, 0.68)
    for center in centers:
        for x in (center - 1.27, center + 1.27):
            _relief(scene, face, box(x - 0.10, 17.15, x + 0.10, 30.35), 0.16, 0.015)
            _relief(scene, face, box(x - 0.18, 30.2, x + 0.18, 30.48), 0.23, 0.015)
    for left, right in pairwise((0, *centers, face.length_m)):
        left = max(left, rail_start)
        if right - left < 1:
            continue
        stone_balcony(scene, face, left + 0.12, right - 0.12, 30.8, 0.67)


def dormer_profile(
    along: float, dimensions: HotelDimensions, pediment: bool
) -> tuple[CourtOpening, Polygon]:
    low = dimensions.cornice_m + 0.48
    opening = _opening(
        along,
        2.10 if pediment else 1.60,
        low + 0.12,
        4.45 if pediment else 2.20,
        True,
        False,
    )
    outline = (
        Polygon(
            [
                (along - 1.70, low - 0.12),
                (along + 1.70, low - 0.12),
                (along + 1.70, low + 5.0),
                (along, low + 6.10),
                (along - 1.70, low + 5.0),
            ]
        )
        if pediment
        else _opening(along, 2.12, low - 0.12, 2.77, True, False).shape
    )
    return opening, outline


def dormer(
    scene: CircuitScene,
    face: CourtFace,
    along: float,
    dimensions: HotelDimensions,
    pediment: bool = False,
) -> None:
    low = dimensions.cornice_m + 0.48
    opening, outline = dormer_profile(along, dimensions, pediment)
    _relief(
        scene,
        face,
        outline.difference(opening.shape),
        0.32,
        -3.1 if pediment else -0.25,
    )
    _glazing(scene, face, opening)
    if not pediment:
        roof_low = dimensions.cornice_m + 0.45
        for a, b in pairwise(outline.exterior.coords):
            da = 0.08 - (a[1] - roof_low) / dimensions.mansard_m * 3.18
            db = 0.08 - (b[1] - roof_low) / dimensions.mansard_m * 3.18
            scene.quad(
                "Building_HotelDormerCheeks",
                dimensions.roof_material,
                _point(face, a[0], a[1], 0.32),
                _point(face, a[0], a[1], da),
                _point(face, b[0], b[1], db),
                _point(face, b[0], b[1], 0.32),
            )
    half = 1.25 if pediment else 0.89
    stone_balcony(scene, face, along - half, along + half, low, 0.48)
    if pediment:
        coords = list(outline.exterior.coords)
        for a, b in pairwise(coords[2:5]):
            scene.beam(
                "Building_HotelCentralPediment",
                "Cream",
                _point(face, a[0], a[1], 0.44),
                _point(face, b[0], b[1], 0.44),
                0.22,
                0.22,
            )
    else:
        spring = low + 0.12 + 2.20 - 0.80
        for i in range(16):
            a, b = i * math.pi / 16, (i + 1) * math.pi / 16
            scene.beam(
                "Building_HotelDormerCrown",
                "Cream",
                _point(
                    face, along + 1.10 * math.cos(a), spring + 1.10 * math.sin(a), 0.36
                ),
                _point(
                    face, along + 1.10 * math.cos(b), spring + 1.10 * math.sin(b), 0.36
                ),
                0.13,
                0.17,
            )


def cupola(
    scene: CircuitScene,
    center: Point,
    dimensions: HotelDimensions,
    heading: float,
    base_radius_m: float = 5.0,
) -> None:
    scale = base_radius_m / 5.0
    bands = tuple(
        (z, r * scale)
        for z, r in ((0.0, 4.95), (1.2, 4.65), (3.4, 3.55), (5.1, 2.10), (5.5, 1.40))
    )
    domain_width = math.tau * 4.95 * scale
    angle_start = heading - math.pi / 4

    def radius(z: float) -> float:
        for (za, ra), (zb, rb) in pairwise(bands):
            if za - 1e-9 <= z <= zb + 1e-9:
                return ra + (rb - ra) * (z - za) / (zb - za)
        raise ValueError("Cupola surface height outside its profile")

    def point(u: float, z: float) -> Point:
        angle = angle_start + u / (4.95 * scale)
        r = radius(z)
        return (
            center[0] + r * math.cos(angle),
            center[1] + r * math.sin(angle),
            center[2] + z,
        )

    hole_centers = tuple(
        4.95 * scale * (math.pi / 4 + i * math.pi / 2) for i in range(4)
    )
    surface = box(0, 0, domain_width, 5.5)
    for u in hole_centers:
        surface = surface.difference(_opening(u, 2.12, -0.04, 2.77, True, False).shape)
    for i in range(64):
        a, b = domain_width * i / 64, domain_width * (i + 1) / 64
        for (za, _), (zb, _) in pairwise(bands):
            patch = surface.intersection(box(a, za, b, zb))
            for tri in constrained_delaunay_triangles(patch).geoms:
                coords = list(tri.exterior.coords)[:3]
                if not tri.exterior.is_ccw:
                    coords.reverse()
                scene.triangle(
                    "Building_HotelCupolaCopper",
                    dimensions.roof_material,
                    point(float(coords[0][0]), float(coords[0][1])),
                    point(float(coords[1][0]), float(coords[1][1])),
                    point(float(coords[2][0]), float(coords[2][1])),
                )
    for u in hole_centers:
        angle = angle_start + u / (4.95 * scale)
        normal = (math.cos(angle), math.sin(angle))
        tangent = (-normal[1], normal[0])
        start = (
            center[0] + normal[0] * 5.05 * scale - tangent[0] * 1.5,
            center[1] + normal[1] * 5.05 * scale - tangent[1] * 1.5,
            center[2],
        )
        end = (start[0] + tangent[0] * 3, start[1] + tangent[1] * 3, start[2])
        face = frame(start, end)
        opening = _opening(1.5, 1.6, 0.14, 2.20, True, False)
        outline = _opening(1.5, 2.12, -0.04, 2.77, True, False).shape
        _relief(scene, face, outline.difference(opening.shape), 0.23, -0.23)
        _glazing(scene, face, opening)
        for a, b in pairwise(outline.exterior.coords):
            pa, pb = (
                point(u + a[0] - 1.5, max(0, a[1])),
                point(u + b[0] - 1.5, max(0, b[1])),
            )
            scene.quad(
                "Building_HotelCupolaDormerCheeks",
                dimensions.roof_material,
                _point(face, a[0], a[1], 0.23),
                pa,
                pb,
                _point(face, b[0], b[1], 0.23),
            )
    for i in range(24):
        u = domain_width * i / 24
        for (za, _), (zb, _) in pairwise(bands):
            line = surface.intersection(LineString([(u, za), (u, zb)]))
            lines = [line] if isinstance(line, LineString) else list(line.geoms)
            for part in lines:
                if not isinstance(part, LineString) or part.length < 0.04:
                    continue
                a, b = part.coords[0], part.coords[-1]
                scene.beam(
                    "Building_HotelCupolaCopperRibs",
                    dimensions.roof_material,
                    point(*a),
                    point(*b),
                    0.065,
                    0.07,
                )
    for i in range(8):
        a, b = i * math.tau / 8, (i + 1) * math.tau / 8
        r = 1.35 * scale
        pa = (center[0] + r * math.cos(a), center[1] + r * math.sin(a), center[2] + 5.4)
        pb = (center[0] + r * math.cos(b), center[1] + r * math.sin(b), center[2] + 5.4)
        face = frame(pa, pb)
        gap = _opening(face.length_m / 2, 0.65, 0.2, 2.9, True, False)
        _panel(
            scene, face, box(0, 0, face.length_m, 3.3).difference(gap.shape), 0, "Cream"
        )
        _panel(scene, face, gap.shape, -0.3, "Black")
        scene.beam(
            "Building_HotelCupolaPiers",
            "Cream",
            pa,
            (pa[0], pa[1], pa[2] + 3.3),
            0.22,
            0.22,
        )
    for level, r0, r1 in ((5.46, 1.20, 1.52), (8.70, 1.20, 1.55)):
        for i in range(48):
            a, b = i * math.tau / 48, (i + 1) * math.tau / 48
            scene.quad(
                "Building_HotelCupolaCoping",
                "Cream",
                (
                    center[0] + r0 * scale * math.cos(a),
                    center[1] + r0 * scale * math.sin(a),
                    center[2] + level,
                ),
                (
                    center[0] + r1 * scale * math.cos(a),
                    center[1] + r1 * scale * math.sin(a),
                    center[2] + level,
                ),
                (
                    center[0] + r1 * scale * math.cos(b),
                    center[1] + r1 * scale * math.sin(b),
                    center[2] + level,
                ),
                (
                    center[0] + r0 * scale * math.cos(b),
                    center[1] + r0 * scale * math.sin(b),
                    center[2] + level,
                ),
            )
    for i in range(48):
        a, b = i * math.tau / 48, (i + 1) * math.tau / 48
        scene.triangle(
            "Building_HotelCupolaCap",
            dimensions.roof_material,
            (center[0], center[1], center[2] + 11.3),
            (
                center[0] + 1.5 * scale * math.cos(a),
                center[1] + 1.5 * scale * math.sin(a),
                center[2] + 8.7,
            ),
            (
                center[0] + 1.5 * scale * math.cos(b),
                center[1] + 1.5 * scale * math.sin(b),
                center[2] + 8.7,
            ),
        )
    scene.beam(
        "Building_HotelFinial",
        "Black",
        (center[0], center[1], center[2] + 11.3),
        (center[0], center[1], center[2] + 14.8),
        0.055,
        0.055,
    )


def corner_parameters(
    layout: HotelLayout, dimensions: HotelDimensions
) -> tuple[Point, float, float]:
    rear = frame(layout.rear_start, layout.rear_end)
    side = frame(layout.rear_end, layout.southwest_return_end)
    turn = math.atan2(
        rear.tangent[0] * side.tangent[1] - rear.tangent[1] * side.tangent[0],
        sum(rear.tangent[i] * side.tangent[i] for i in range(2)),
    )
    distance = dimensions.corner_radius_m * math.tan(turn / 2)
    center = tuple(
        layout.rear_end[i]
        - rear.tangent[i] * distance
        - rear.outward[i] * dimensions.corner_radius_m
        for i in range(3)
    )
    return (center[0], center[1], layout.datum_m), turn, distance


def rounded_corner(
    scene: CircuitScene, layout: HotelLayout, dimensions: HotelDimensions
) -> Point:
    rear = frame(layout.rear_start, layout.rear_end)
    r = dimensions.corner_radius_m
    center, turn, _ = corner_parameters(layout, dimensions)
    theta = math.atan2(rear.outward[1], rear.outward[0])
    arc_length = turn * r

    def point(u: float, z: float, depth: float = 0) -> Point:
        angle = theta + u / r
        return (
            center[0] + (r + depth) * math.cos(angle),
            center[1] + (r + depth) * math.sin(angle),
            layout.datum_m + z,
        )

    rows = (
        (9.0, 12.0, False),
        (13.2, 16.2, True),
        (17.2, 19.8, False),
        (20.6, 23.2, False),
        (24.0, 26.6, False),
        (27.4, 30.0, True),
        (31.5, 33.0, False),
    )
    openings = [
        _opening(
            arc_length * t, 1.15 if low < 31 else 0.9, low, high - low, arched, False
        )
        for t in (0.25, 0.75)
        for low, high, arched in rows
    ]
    wallshape = box(0, -0.10, arc_length, dimensions.cornice_m + 0.5)
    for opening in openings:
        wallshape = wallshape.difference(opening.shape)
    for i in range(24):
        a, b = arc_length * i / 24, arc_length * (i + 1) / 24
        patch = wallshape.intersection(box(a, -1, b, dimensions.cornice_m + 1))
        for tri in constrained_delaunay_triangles(patch).geoms:
            coords = list(tri.exterior.coords)[:3]
            if not tri.exterior.is_ccw:
                coords.reverse()
            scene.triangle(
                "Building_HotelRoundedCorner",
                "Cream",
                point(float(coords[0][0]), float(coords[0][1])),
                point(float(coords[1][0]), float(coords[1][1])),
                point(float(coords[2][0]), float(coords[2][1])),
            )
    for t in (0.25, 0.75):
        u = arc_length * t
        p = point(u, 0)
        angle = theta + u / r
        tangent = (-math.sin(angle), math.cos(angle), 0.0)
        front_a = (p[0] - tangent[0] * 1.2, p[1] - tangent[1] * 1.2, p[2])
        front_b = (p[0] + tangent[0] * 1.2, p[1] + tangent[1] * 1.2, p[2])
        face = frame(front_a, front_b)
        for low, high, arched in rows:
            _glazing(
                scene,
                face,
                _opening(
                    1.2, 1.15 if low < 31 else 0.9, low, high - low, arched, False
                ),
            )
        for low in (17.2, 20.6, 24.0, 27.4):
            iron_balcony(scene, face, 1.2, low)
    for z, w, h in (
        (8.6, 0.43, 0.36),
        (17.0, 0.54, 0.38),
        (30.7, 0.68, 0.43),
        (33.8, 0.82, 0.48),
    ):
        for i in range(32):
            scene.beam(
                "Building_HotelCurvedCornice",
                "Cream",
                point(arc_length * i / 32, z, 0.12),
                point(arc_length * (i + 1) / 32, z, 0.12),
                w,
                h,
            )
    return (center[0], center[1], layout.datum_m + dimensions.cornice_m + 0.4)
