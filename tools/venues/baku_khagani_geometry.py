from __future__ import annotations

import math
from itertools import pairwise
from typing import Literal

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import set_precision
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from venues.baku_civic import _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_geometry import frame
from venues.baku_khagani_dataclasses import FrontWall
from venues.baku_museum_geometry import _panel
from venues.baku_philharmonic_geometry import solid


def pointed(
    x: float, width: float, low: float, spring: float, rise: float
) -> CourtOpening:
    half = width / 2
    shift = (rise * rise - half * half) / (2 * half)
    radius = half + shift
    top: list[tuple[float, float]] = []
    angle = math.acos(max(-1.0, min(1.0, shift / radius)))
    for i in range(11):
        t = angle * i / 10
        top.append((x - shift + radius * math.cos(t), spring + radius * math.sin(t)))
    for i in range(1, 11):
        t = angle * (1 - i / 10)
        top.append((x + shift - radius * math.cos(t), spring + radius * math.sin(t)))
    shape = Polygon([(x - half, low), (x + half, low), *top])
    return CourtOpening(shape, low < 0.6, spring)


def relief(
    scene: CircuitScene,
    face: CourtFace,
    shape: Polygon | MultiPolygon,
    front: float = 0.10,
    back: float = -0.02,
    material: str = "White",
) -> None:
    shape = set_precision(shape, 0.001)
    for piece in shape.geoms if isinstance(shape, MultiPolygon) else (shape,):
        if piece.area > 1e-8:
            solid(scene, face, piece, front, back, material, "Building_KhaganiStone")


def foot(wall: FrontWall, along: float) -> float:
    for (a, za), (b, zb) in pairwise(wall.feet_m):
        if b > a and a - 1e-8 <= along <= b + 1e-8:
            return za + (zb - za) * (along - a) / (b - a)
    raise ValueError("Missing actual Khagani wall-foot interval")


def wall_shape(wall: FrontWall, top: float) -> Polygon:
    return Polygon(
        [*((u, z - 0.04) for u, z in wall.feet_m), (wall.face.length_m, top), (0, top)]
    )


def masonry(
    scene: CircuitScene,
    wall: FrontWall,
    top: float,
    openings: list[CourtOpening],
    material: str = "Cream",
    depth: float = 0.32,
) -> None:
    shape = wall_shape(wall, top).difference(
        unary_union([opening.shape for opening in openings])
    )
    if not isinstance(shape, (Polygon, MultiPolygon)):
        raise TypeError("Khagani wall must remain polygonal masonry")
    relief(scene, wall.face, shape, 0, -depth, material)


def glazing(
    scene: CircuitScene,
    face: CourtFace,
    opening: CourtOpening,
    depth: float = -0.28,
    material: str = "Glass",
    stone: bool = True,
) -> None:
    shape = opening.shape
    _panel(scene, face, shape, depth, material)
    for a, b in pairwise(shape.exterior.coords):
        scene.quad(
            "Building_KhaganiReveals",
            "Cream",
            _point(face, *a),
            _point(face, *b),
            _point(face, b[0], b[1], depth),
            _point(face, a[0], a[1], depth),
        )
        scene.beam(
            "Building_KhaganiFrames",
            "Trunk",
            _point(face, a[0], a[1], depth + 0.025),
            _point(face, b[0], b[1], depth + 0.025),
            0.055,
        )
    if stone:
        trim = shape.buffer(0.115, join_style="mitre").difference(shape)
        if not isinstance(trim, (Polygon, MultiPolygon)):
            raise TypeError("Khagani window trim lost its polygonal shape")
        relief(scene, face, trim, 0.09, -0.01)
    x0, z0, x1, z1 = shape.bounds
    for x in ((x0 + x1) / 2,):
        scene.beam(
            "Building_KhaganiMullions",
            "Trunk",
            _point(face, x, z0, depth + 0.03),
            _point(face, x, z1, depth + 0.03),
            0.05,
        )
    z = (
        opening.arch_spring_m
        if opening.arch_spring_m is not None
        else z0 + (z1 - z0) * 0.72
    )
    scene.beam(
        "Building_KhaganiMullions",
        "Trunk",
        _point(face, x0, z, depth + 0.03),
        _point(face, x1, z, depth + 0.03),
        0.05,
    )


def band(
    scene: CircuitScene,
    face: CourtFace,
    low: float,
    thick: float,
    depth: float,
    material: str = "White",
    interval: tuple[float, float] | None = None,
) -> None:
    a, b = interval or (0.0, face.length_m)
    relief(scene, face, box(a, low, b, low + thick), depth, -0.02, material)


def rosette(
    scene: CircuitScene, face: CourtFace, x: float, z: float, radius: float
) -> None:
    points = []
    for i in range(32):
        angle = i * math.tau / 32
        r = radius * (1 if i % 2 == 0 else 0.68)
        points.append((x + r * math.cos(angle), z + r * 0.55 * math.sin(angle)))
    relief(scene, face, Polygon(points), 0.12, 0.025)


def lathe(
    scene: CircuitScene,
    centre: Point,
    rings: tuple[tuple[float, float], ...],
    material: str = "White",
    segments: int = 10,
) -> None:
    for (z0, r0), (z1, r1) in pairwise(rings):
        for i in range(segments):
            a, b = i * math.tau / segments, (i + 1) * math.tau / segments
            scene.quad(
                "Building_KhaganiSculpture",
                material,
                (
                    centre[0] + r0 * math.cos(a),
                    centre[1] + r0 * math.sin(a),
                    centre[2] + z0,
                ),
                (
                    centre[0] + r0 * math.cos(b),
                    centre[1] + r0 * math.sin(b),
                    centre[2] + z0,
                ),
                (
                    centre[0] + r1 * math.cos(b),
                    centre[1] + r1 * math.sin(b),
                    centre[2] + z1,
                ),
                (
                    centre[0] + r1 * math.cos(a),
                    centre[1] + r1 * math.sin(a),
                    centre[2] + z1,
                ),
            )
    for (z, r), reverse in ((rings[0], True), (rings[-1], False)):
        c = (centre[0], centre[1], centre[2] + z)
        for i in range(segments):
            a, b = i * math.tau / segments, (i + 1) * math.tau / segments
            pa = (c[0] + r * math.cos(a), c[1] + r * math.sin(a), c[2])
            pb = (c[0] + r * math.cos(b), c[1] + r * math.sin(b), c[2])
            scene.triangle(
                "Building_KhaganiSculpture",
                material,
                c,
                pb if reverse else pa,
                pa if reverse else pb,
            )


def statue(
    scene: CircuitScene,
    face: CourtFace,
    x: float,
    z: float,
    height: float,
    depth: float = -0.20,
    pose: int = 0,
) -> None:
    centre = _point(face, x, z, depth)
    scale = height / 2.25
    lathe(
        scene,
        centre,
        tuple(
            (a * scale, b * scale)
            for a, b in (
                (0, 0.27),
                (0.12, 0.27),
                (0.18, 0.19),
                (0.88, 0.23),
                (1.22, 0.25),
                (1.68, 0.34),
                (1.85, 0.18),
            )
        ),
    )
    lathe(
        scene,
        (centre[0], centre[1], centre[2] + 1.83 * scale),
        tuple(
            (a * scale, b * scale)
            for a, b in (
                (0, 0.10),
                (0.06, 0.17),
                (0.22, 0.20),
                (0.37, 0.15),
                (0.43, 0.02),
            )
        ),
    )
    for side in (-1, 1):
        a = _point(face, x + side * 0.27 * scale, z + 1.67 * scale, depth)
        b = _point(
            face,
            x + side * (0.12 if pose % 2 else 0.23) * scale,
            z + (1.16 if side < 0 else 1.35) * scale,
            depth + 0.15 * scale,
        )
        scene.beam("Building_KhaganiSculpture", "White", a, b, 0.17 * scale)


def corinthian(
    scene: CircuitScene,
    face: CourtFace,
    x: float,
    low: float,
    high: float,
    radius: float,
    depth: float,
    order: Literal["corinthian", "ionic", "doric"] = "corinthian",
) -> None:
    centre = _point(face, x, low, depth)
    h = high - low
    lathe(
        scene,
        centre,
        (
            (0, radius * 1.35),
            (0.18, radius * 1.4),
            (0.35, radius),
            (h - 0.8, radius * 0.83),
            (h - 0.4, radius * 1.1),
            (h - 0.15, radius * 1.45),
            (h, radius * 1.5),
        ),
    )
    if order != "corinthian":
        if order == "ionic":
            for side in (-1, 1):
                for i in range(16):
                    a, b = i * math.tau / 16, (i + 1) * math.tau / 16
                    ra, rb = (
                        radius * (0.60 - 0.30 * i / 16),
                        radius * (0.60 - 0.30 * (i + 1) / 16),
                    )
                    scene.beam(
                        "Building_KhaganiVolutes",
                        "White",
                        _point(
                            face,
                            x + side * radius + ra * math.cos(a),
                            high - 0.28 + ra * math.sin(a),
                            depth + radius,
                        ),
                        _point(
                            face,
                            x + side * radius + rb * math.cos(b),
                            high - 0.28 + rb * math.sin(b),
                            depth + radius,
                        ),
                        0.055,
                    )
        return
    for row in range(2):
        for i in range(8):
            angle = (i + row * 0.5) * math.tau / 8
            normal = (math.cos(angle), math.sin(angle), 0.0)
            tangent = (-normal[1], normal[0], 0.0)
            p = (
                centre[0] + normal[0] * radius,
                centre[1] + normal[1] * radius,
                centre[2] + h - 0.68 + row * 0.22,
            )
            leaf_face = CourtFace(p, tangent, normal, radius, radius)
            leaf = Polygon(
                [
                    (-0.18, 0),
                    (-0.24, 0.18),
                    (-0.10, 0.38),
                    (0, 0.48),
                    (0.10, 0.38),
                    (0.24, 0.18),
                    (0.18, 0),
                ]
            )
            relief(scene, leaf_face, leaf, 0.13, -0.015)


def projected_oriel(
    scene: CircuitScene,
    face: CourtFace,
    x: float,
    width: float,
    low: float,
    top: float,
    rows: tuple[tuple[float, float], ...],
    depth: float = 0.95,
    material: str = "Cream",
) -> None:
    plan = (
        (x - width / 2, 0),
        (x - width * 0.30, depth),
        (x + width * 0.30, depth),
        (x + width / 2, 0),
    )
    for a, b in pairwise(plan):
        start, end = _point(face, a[0], low, a[1]), _point(face, b[0], low, b[1])
        side = frame(start, end)
        holes = [
            CourtOpening(
                box(side.length_m * 0.16, za - low, side.length_m * 0.84, zb - low),
                False,
                None,
            )
            for za, zb in rows
        ]
        shape = box(0, 0, side.length_m, top - low).difference(
            unary_union([o.shape for o in holes])
        )
        if not isinstance(shape, (Polygon, MultiPolygon)):
            raise TypeError("Khagani oriel must retain masonry")
        relief(scene, side, shape, 0, -0.22, material)
        for opening in holes:
            glazing(scene, side, opening, -0.15)
        for z in (0, *(b - low + 0.12 for _, b in rows), top - low):
            band(scene, side, z, 0.14, 0.15)
    outline = Polygon([_point(face, u, 0, d)[:2] for u, d in plan])
    from shapely import constrained_delaunay_triangles

    for triangle in constrained_delaunay_triangles(outline).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coordinates.reverse()
        for level, reverse in ((top, False), (low, True)):
            points = [(a, b, face.start[2] + level) for a, b in coordinates]
            if reverse:
                points.reverse()
            scene.triangle(
                "Building_KhaganiOrielCap", material, points[0], points[1], points[2]
            )


def roof_step(
    scene: CircuitScene,
    face: CourtFace,
    a: float,
    b: float,
    top: float,
    inherited_top: float,
    depth: float,
    occupied: Polygon,
) -> None:
    from shapely import constrained_delaunay_triangles
    from shapely.geometry.polygon import orient

    plan = Polygon(
        [
            _point(face, x, 0, d)[:2]
            for x, d in ((a, 0), (b, 0), (b, -depth), (a, -depth))
        ]
    ).intersection(occupied)
    pieces = (
        [plan]
        if isinstance(plan, Polygon)
        else list(plan.geoms)
        if isinstance(plan, MultiPolygon)
        else []
    )
    for piece in pieces:
        piece = orient(piece, sign=1)
        for triangle in constrained_delaunay_triangles(piece).geoms:
            coordinates = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                coordinates.reverse()
            points = [(x, y, face.start[2] + top) for x, y in coordinates]
            scene.triangle(
                "Building_KhaganiRoof", "Roof", points[0], points[1], points[2]
            )
            underside = [(x, y, face.start[2] + top - 0.18) for x, y in coordinates]
            scene.triangle(
                "Building_KhaganiRoofSoffit",
                "Cream",
                underside[2],
                underside[1],
                underside[0],
            )
        for aa, bb in pairwise(piece.exterior.coords):
            depths = [
                sum((p[i] - face.start[i]) * face.outward[i] for i in range(2))
                for p in (aa, bb)
            ]
            if max(abs(d) for d in depths) < 1e-7:
                continue
            scene.quad(
                "Building_KhaganiRoofReturn",
                "Cream",
                (*aa, face.start[2] + inherited_top),
                (*bb, face.start[2] + inherited_top),
                (*bb, face.start[2] + top),
                (*aa, face.start[2] + top),
            )


def pediment(
    scene: CircuitScene,
    face: CourtFace,
    a: float,
    b: float,
    base: float,
    rise: float,
    depth: float = 0.36,
) -> None:
    outline = Polygon([(a, base), (b, base), ((a + b) / 2, base + rise)])
    relief(scene, face, outline, depth, -0.12, "Cream")
    inner = Polygon(
        [
            (a + 0.55, base + 0.26),
            (b - 0.55, base + 0.26),
            ((a + b) / 2, base + rise - 0.38),
        ]
    )
    border = outline.difference(inner)
    if not isinstance(border, (Polygon, MultiPolygon)):
        raise TypeError("Historic pediment frame lost its polygon")
    relief(scene, face, border, depth + 0.16, depth, "White")


def mansard(
    scene: CircuitScene,
    face: CourtFace,
    base: float,
    rise: float,
    widths_centres: tuple[tuple[float, float], ...],
    material: str = "Roof",
    arch: bool = True,
) -> None:
    length = face.length_m
    depth = 1.55
    holes = []
    for width, x in widths_centres:
        from venues.baku_civic import _opening

        holes.append(_opening(x, width, base + 0.26, rise * 0.67, arch, False))
    surface = box(0, base, length, base + rise).difference(
        unary_union([opening.shape for opening in holes])
    )
    if not isinstance(surface, (Polygon, MultiPolygon)):
        raise TypeError("Historic mansard lost its roof panels")
    from shapely import constrained_delaunay_triangles

    for part in surface.geoms if isinstance(surface, MultiPolygon) else (surface,):
        for triangle in constrained_delaunay_triangles(part).geoms:
            coordinates = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                coordinates.reverse()
            points = [
                _point(face, x, z, -(z - base) / rise * depth) for x, z in coordinates
            ]
            scene.triangle(
                "Building_KhaganiMansard", material, points[0], points[1], points[2]
            )
    for opening in holes:
        for triangle in constrained_delaunay_triangles(opening.shape).geoms:
            coordinates = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                coordinates.reverse()
            points = [
                _point(face, x, z, -(z - base) / rise * depth - 0.08)
                for x, z in coordinates
            ]
            scene.triangle(
                "Building_KhaganiAtticGlazing",
                "Black" if arch else "Glass",
                points[0],
                points[1],
                points[2],
            )
        for a, b in pairwise(opening.shape.exterior.coords):
            scene.quad(
                "Building_KhaganiDormerReveals",
                material,
                _point(face, a[0], a[1], -(a[1] - base) / rise * depth),
                _point(face, b[0], b[1], -(b[1] - base) / rise * depth),
                _point(face, b[0], b[1], -(b[1] - base) / rise * depth - 0.08),
                _point(face, a[0], a[1], -(a[1] - base) / rise * depth - 0.08),
            )
            scene.beam(
                "Building_KhaganiDormerTrim",
                material,
                _point(face, a[0], a[1], -(a[1] - base) / rise * depth + 0.035),
                _point(face, b[0], b[1], -(b[1] - base) / rise * depth + 0.035),
                0.065,
            )
    if not arch:
        for opening in holes:
            x0, z0, x1, z1 = opening.shape.bounds
            x = (x0 + x1) / 2
            scene.beam(
                "Building_KhaganiAtticMullion",
                "White",
                _point(face, x, z0, -(z0 - base) / rise * depth - 0.035),
                _point(face, x, z1, -(z1 - base) / rise * depth - 0.035),
                0.07,
            )
    scene.quad(
        "Building_KhaganiMansardTop",
        material,
        _point(face, 0, base + rise, -depth),
        _point(face, length, base + rise, -depth),
        _point(face, length, base + rise, -3),
        _point(face, 0, base + rise, -3),
        up=True,
    )
    scene.quad(
        "Building_KhaganiMansardBack",
        material,
        _point(face, length, base, -3),
        _point(face, 0, base, -3),
        _point(face, 0, base + rise, -3),
        _point(face, length, base + rise, -3),
    )
    for x, reverse in ((0, True), (length, False)):
        points = [
            _point(face, x, base),
            _point(face, x, base, -3),
            _point(face, x, base + rise, -3),
            _point(face, x, base + rise, -depth),
        ]
        if reverse:
            points.reverse()
        scene.quad(
            "Building_KhaganiMansardSides",
            material,
            points[0],
            points[1],
            points[2],
            points[3],
        )
