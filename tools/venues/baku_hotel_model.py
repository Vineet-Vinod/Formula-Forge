"""Source-fitted Four Seasons; unobserved returns remain architectural estimates."""

from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiLineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.baku_civic import _opening, _point
from venues.baku_ground import _weights
from venues.baku_hotel_dataclasses import HotelSource, HotelWall
from venues.baku_hotel_geometry import (
    cupola,
    dormer,
    dormer_profile,
    frame,
    rounded_corner,
    wall,
)
from venues.baku_museum_geometry import _relief


def dormer_layout(source: HotelSource) -> list[tuple[HotelWall, float]]:
    result: list[tuple[HotelWall, float]] = []
    for side in source.walls:
        if side.edge_name.startswith("rear_") or side.edge_name in (
            "sw_garden",
            "edge_4",
        ):
            result.extend((side, along) for along in side.stack_along_m)
        elif side.edge_name == "edge_10":
            length = math.dist(side.start[:2], side.end[:2])
            result.extend((side, length * t) for t in (0.16, 0.38, 0.62, 0.84))
    northeast = next(side for side in source.walls if side.edge_name == "rear_13")
    result.append((northeast, 3.15))
    return result


def roof(
    scene: CircuitScene, source: HotelSource, layouts: list[tuple[HotelWall, float]]
) -> None:
    occupied = Polygon(source.outer_xy)
    outer = occupied.buffer(0.08, join_style="mitre")
    inner = occupied.buffer(-3.1, join_style="mitre")
    if not isinstance(outer, Polygon) or not isinstance(inner, Polygon):
        raise TypeError("Hotel roof must retain one connected inner deck")
    holes = []
    low = source.dimensions.cornice_m + 0.45
    for side, along in layouts:
        face = frame(side.start, side.end)
        pediment = (
            side.edge_name == "sw_garden" and abs(along - side.stack_along_m[2]) < 1e-6
        )
        _, outline = dormer_profile(along, source.dimensions, pediment)
        holes.append(
            Polygon(
                [
                    _point(
                        face,
                        float(x),
                        float(z),
                        0.08
                        - min(source.dimensions.mansard_m, max(0.0, z - low))
                        / source.dimensions.mansard_m
                        * 3.18,
                    )[:2]
                    for x, z in outline.exterior.coords
                ]
            )
        )
    cutouts = unary_union(holes)
    annulus = outer.difference(inner).difference(cutouts)

    def point(x: float, y: float) -> Point:
        distance = outer.boundary.distance(ShapePoint(x, y))
        z = low + source.dimensions.mansard_m * min(1.0, distance / 3.18)
        return (x, y, source.datum_m + z)

    roof_planes: list[tuple[Polygon, tuple[Point, Point, Point]]] = []
    for shape, material, kind in (
        (annulus, source.dimensions.roof_material, "Building_HotelCopperRoof"),
        (inner, "Roof", "Building_HotelInnerRoof"),
    ):
        for triangle in constrained_delaunay_triangles(shape).geoms:
            coords = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                coords.reverse()
            points = (
                point(float(coords[0][0]), float(coords[0][1])),
                point(float(coords[1][0]), float(coords[1][1])),
                point(float(coords[2][0]), float(coords[2][1])),
            )
            scene.triangle(kind, material, *points)
            if kind == "Building_HotelCopperRoof":
                roof_planes.append((triangle, points))
    plane_index = STRtree([shape for shape, _ in roof_planes])
    for side in source.walls:
        if side.edge_name.startswith("sw_curve_"):
            continue
        face = frame(side.start, side.end)
        length = face.length_m
        for i in range(math.ceil(length / 0.7) + 1):
            along = min(length, i * 0.7)
            if any(other is side and abs(x - along) < 1.14 for other, x in layouts):
                continue
            a = _point(face, along, low, 0.08)
            b = _point(face, along, low + source.dimensions.mansard_m, -3.1)
            line = LineString([a[:2], b[:2]])
            for index in plane_index.query(line, predicate="intersects"):
                shape, points = roof_planes[int(index)]
                intersection = line.intersection(shape)
                parts = (
                    [intersection]
                    if isinstance(intersection, LineString)
                    else list(intersection.geoms)
                    if isinstance(intersection, MultiLineString)
                    else []
                )
                for part in parts:
                    if part.length < 0.02:
                        continue
                    ends = []
                    for x, y in (part.coords[0], part.coords[-1]):
                        z = sum(
                            w * p[2] for w, p in zip(_weights(points, x, y), points)
                        )
                        ends.append((float(x), float(y), z + 0.015))
                    scene.beam(
                        "Building_HotelCopperSeams",
                        source.dimensions.roof_material,
                        ends[0],
                        ends[1],
                        0.035,
                        0.045,
                    )
    for triangle in constrained_delaunay_triangles(occupied).geoms:
        coords = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coords.reverse()
        a, b, c = [(float(x), float(y), source.datum_m - 0.10) for x, y in coords]
        scene.triangle("Building_HotelFoundationCap", "Concrete", a, c, b)


def rear_service(scene: CircuitScene, source: HotelSource) -> None:
    northeast = next(side for side in source.walls if side.edge_name == "rear_13")
    face = frame(northeast.start, northeast.end)
    h = source.dimensions.cornice_m
    for x, width in ((5.15, 1.8), (12.55, 2.2)):
        _relief(
            scene, face, box(x - width / 2, h - 0.45, x + width / 2, h + 6), 0.22, -1.2
        )
        _relief(
            scene,
            face,
            box(x - width / 2 - 0.16, h + 5.95, x + width / 2 + 0.16, h + 6.22),
            0.35,
            -1.3,
        )
    for x in (5.6, 11.0):
        for z in (30.6, 31.55, 32.5):
            for i in range(24):
                a, b = i * math.tau / 24, (i + 1) * math.tau / 24
                ra, rb = 0.65 + 0.35 * math.cos(4 * a), 0.65 + 0.35 * math.cos(4 * b)
                scene.beam(
                    "Building_HotelServiceGrilles",
                    "Cream",
                    _point(
                        face,
                        x + 0.35 * ra * math.cos(a),
                        z + 0.43 * ra * math.sin(a),
                        0.045,
                    ),
                    _point(
                        face,
                        x + 0.35 * rb * math.cos(b),
                        z + 0.43 * rb * math.sin(b),
                        0.045,
                    ),
                    0.045,
                    0.06,
                )
    center = _point(face, 15, h + 3.3, -5)
    scene.box(
        "Building_HotelServicePavilion",
        "Cream",
        center,
        10.5,
        6,
        1.4,
        math.atan2(face.tangent[1], face.tangent[0]),
    )
    middle = next(side for side in source.walls if side.edge_name == "rear_14")
    face = frame(middle.start, middle.end)
    offset = math.dist(source.literal_outer_xy[13], source.literal_outer_xy[14])
    left, right = tuple(x - offset for x in source.rear_layout.blind_mass_along_m)
    _relief(scene, face, box(left, h + 0.05, right, h + 7), 0.17, -3.3)
    for t in (0.18, 0.50, 0.82):
        x = left + (right - left) * t
        outer = _opening(x, 2.04, h + 0.14, 3, True, False).shape
        inner = _opening(x, 1.79, h + 0.25, 2.7, True, False).shape
        _relief(scene, face, outer.difference(inner), 0.36, 0.18)
    x = (left + right) / 2
    _relief(
        scene,
        face,
        Polygon([(x - 1.65, h + 3.35), (x + 1.65, h + 3.35), (x, h + 4.05)]),
        0.42,
        0.19,
    )
    for i in range(7):
        x = left + (right - left) * (i + 0.5) / 7
        _relief(scene, face, box(x - 0.49, h + 7, x + 0.49, h + 8.5), 0.26, -0.8)


def pool_roof(scene: CircuitScene, source: HotelSource) -> None:
    # The rear image and operator explicitly identify the glass-roofed pool atrium.
    side = next(side for side in source.walls if side.edge_name == "rear_14")
    face = frame(side.start, side.end)
    offset = math.dist(source.literal_outer_xy[13], source.literal_outer_xy[14])
    start, end = 48 - offset, 75 - offset
    base = source.dimensions.cornice_m + source.dimensions.mansard_m + 0.40

    def point(along: float, angle: float) -> Point:
        return _point(
            face, along, base + 3.4 * math.sin(angle), -16 + 5.2 * math.cos(angle)
        )

    for j in range(14):
        a, b = j * math.pi / 14, (j + 1) * math.pi / 14
        scene.quad(
            "Building_HotelPoolRoof",
            "Glass",
            point(start, a),
            point(end, a),
            point(end, b),
            point(start, b),
        )
        for u in (start, end):
            scene.beam(
                "Building_HotelPoolRibs", "Black", point(u, a), point(u, b), 0.11, 0.13
            )
    for u, reverse in ((start, False), (end, True)):
        center = _point(face, u, base, -16)
        for j in range(14):
            cap_a, cap_b = point(u, j * math.pi / 14), point(u, (j + 1) * math.pi / 14)
            scene.triangle(
                "Building_HotelPoolEnds",
                "Glass",
                center,
                cap_b if reverse else cap_a,
                cap_a if reverse else cap_b,
            )
    for i in range(1, 13):
        u = start + (end - start) * i / 13
        for j in range(14):
            scene.beam(
                "Building_HotelPoolRibs",
                "Black",
                point(u, j * math.pi / 14),
                point(u, (j + 1) * math.pi / 14),
                0.065,
                0.075,
            )
    for j in range(1, 14):
        scene.beam(
            "Building_HotelPoolRails",
            "Black",
            point(start, j * math.pi / 14),
            point(end, j * math.pi / 14),
            0.055,
            0.065,
        )


def full_hotel(scene: CircuitScene, source: HotelSource) -> None:
    layouts = dormer_layout(source)
    for side in source.walls:
        if side.edge_name.startswith("sw_curve_"):
            continue
        face = frame(side.start, side.end)
        rear = side.edge_name.startswith("rear_")
        plain = side.edge_name in ("edge_8", "edge_9", "edge_10", "edge_11", "edge_12")
        wall(
            scene,
            face,
            side.stack_along_m,
            source.dimensions,
            True,
            side.feet_along_height_m,
            plain,
            14.0 if side.edge_name == "rear_13" else 0.0,
            not rear,
            (5.6, 11.0) if side.edge_name == "rear_13" else (),
            3.6 if side.edge_name in ("sw_garden", "edge_4", "edge_10") else 2.0,
        )
    rounded_corner(scene, source.rear_layout, source.dimensions)
    roof(scene, source, layouts)
    for side, along in layouts:
        pediment = (
            side.edge_name == "sw_garden" and abs(along - side.stack_along_m[2]) < 1e-6
        )
        dormer(scene, frame(side.start, side.end), along, source.dimensions, pediment)
    rear_service(scene, source)
    for crown in source.cupolas:
        cupola(
            scene, crown.center, source.dimensions, crown.heading_rad, crown.radius_m
        )
    pool_roof(scene, source)
