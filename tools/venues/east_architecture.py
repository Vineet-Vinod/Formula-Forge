"""Footprint-registered architecture used by the eastern circuit recipes."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Building, Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry import Point as GeoPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import triangulate, unary_union


def frame(building: Building) -> tuple[Point, Point, Point, float, float]:
    ring = list(Polygon(building.ring).minimum_rotated_rectangle.exterior.coords)[:-1]
    edges = [(math.dist(a, b), a, b) for a, b in zip(ring, ring[1:] + ring[:1])]
    length, a, b = max(edges)
    axis = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.0)
    side = (-axis[1], axis[0], 0.0)
    center = (sum(p[0] for p in ring) / 4, sum(p[1] for p in ring) / 4, 0.0)
    return center, axis, side, length, min(e[0] for e in edges)


def mapped(scene: CircuitScene, osm_id: int) -> Building | None:
    return next((b for b in scene.buildings if b.osm_id == osm_id), None)


def roof_polygon(
    scene: CircuitScene,
    ring: list[tuple[float, float]],
    z: float,
    material: str = "Roof",
) -> None:
    polygon = Polygon(ring)
    for triangle in triangulate(polygon):
        if polygon.covers(triangle):
            a, b, c = list(triangle.exterior.coords)[:3]
            scene.triangle(
                "Building_Roof",
                material,
                (a[0], a[1], z),
                (b[0], b[1], z),
                (c[0], c[1], z),
            )
            scene.triangle(
                "Building_Roof",
                material,
                (c[0], c[1], z - 0.12),
                (b[0], b[1], z - 0.12),
                (a[0], a[1], z - 0.12),
            )


def cylinder(
    scene: CircuitScene,
    base: Point,
    radius_x: float,
    radius_y: float,
    height: float,
    material: str,
    segments: int = 32,
    heading: float = 0.0,
) -> None:
    def point(angle: float, z: float) -> Point:
        x, y = radius_x * math.cos(angle), radius_y * math.sin(angle)
        return (
            base[0] + x * math.cos(heading) - y * math.sin(heading),
            base[1] + x * math.sin(heading) + y * math.cos(heading),
            base[2] + z,
        )

    for i in range(segments):
        a, b = i * math.tau / segments, (i + 1) * math.tau / segments
        scene.quad(
            "Building_Architecture",
            material,
            point(a, 0),
            point(b, 0),
            point(b, height),
            point(a, height),
            1,
            1,
        )
        scene.triangle(
            "Building_Architecture",
            material,
            add(base, (0, 0, height)),
            point(a, height),
            point(b, height),
        )


def oval_canopy(
    scene: CircuitScene,
    center: Point,
    axis: Point,
    side: Point,
    radius_along: float,
    radius_across: float,
    footprint: BaseGeometry | None = None,
) -> None:
    base = center[0], center[1], scene.ground(center[0], center[1])
    scene.beam("Building_Lotus", "Concrete", base, center, 1.15)
    for column in range(32):
        a, b = column * math.tau / 32, (column + 1) * math.tau / 32
        for row in range(5):

            def point(angle: float, radial: float) -> Point:
                offset = add(
                    mul(axis, radius_along * math.cos(angle) * radial),
                    mul(side, radius_across * math.sin(angle) * radial),
                )
                return add(center, add(offset, (0, 0, 0.65 * radial * radial)))

            r0, r1 = row / 5, (row + 1) / 5
            corners = [point(a, r0), point(b, r0), point(b, r1), point(a, r1)]
            if footprint is None:
                pa, pb, pc, pd = corners
                scene.quad("Building_Lotus", "White", pa, pb, pc, pd)
                scene.quad(
                    "Building_Lotus",
                    "Concrete",
                    add(pd, (0, 0, -0.16)),
                    add(pc, (0, 0, -0.16)),
                    add(pb, (0, 0, -0.16)),
                    add(pa, (0, 0, -0.16)),
                )
            else:
                shape = Polygon([(p[0], p[1]) for p in corners])
                if not shape.is_valid or shape.area < 1e-8:
                    continue
                clipped = shape.intersection(footprint)
                for triangle in triangulate(clipped):
                    if not clipped.covers(triangle):
                        continue
                    roof_points = []
                    for x, y in list(triangle.exterior.coords)[:3]:
                        dx, dy = x - center[0], y - center[1]
                        radial = ((dx * axis[0] + dy * axis[1]) / radius_along) ** 2
                        radial += ((dx * side[0] + dy * side[1]) / radius_across) ** 2
                        roof_points.append((x, y, center[2] + 0.65 * radial))
                    pa, pb, pc = roof_points
                    scene.triangle("Building_Lotus", "White", pa, pb, pc)
                    scene.triangle(
                        "Building_Lotus",
                        "Concrete",
                        add(pc, (0, 0, -0.16)),
                        add(pb, (0, 0, -0.16)),
                        add(pa, (0, 0, -0.16)),
                    )
        if column % 4 == 0 and (
            footprint is None
            or footprint.covers(LineString([center[:2], point(a, 1)[:2]]))
        ):
            scene.beam(
                "Building_Lotus", "Steel", add(center, (0, 0, -0.5)), point(a, 1), 0.12
            )


def upward_quad(
    scene: CircuitScene,
    kind: str,
    material: str,
    a: Point,
    b: Point,
    c: Point,
    d: Point,
) -> None:
    winding = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if winding >= 0:
        scene.quad(kind, material, a, b, c, d)
    else:
        scene.quad(kind, material, d, c, b, a)


def double_quad(
    scene: CircuitScene,
    kind: str,
    material: str,
    a: Point,
    b: Point,
    c: Point,
    d: Point,
) -> None:
    scene.quad(kind, material, a, b, c, d)
    scene.quad(kind, material, d, c, b, a)


def tensile_roof(scene: CircuitScene, shape: BaseGeometry, height: float) -> int:
    polygons = [shape] if isinstance(shape, Polygon) else list(shape.geoms)
    panels = 0
    for polygon in polygons:
        if not isinstance(polygon, Polygon) or polygon.area < 10:
            continue
        center = polygon.centroid
        if not polygon.covers(center):
            center = polygon.representative_point()
        peak = center.x, center.y, height + 4.2
        ring = list(polygon.exterior.coords)
        for a, b in pairwise(ring):
            face = Polygon([a, b, (peak[0], peak[1])])
            if not face.is_valid or face.area < 1e-8:
                continue
            clipped = face.intersection(polygon)
            ax, ay = b[0] - a[0], b[1] - a[1]
            length = math.hypot(ax, ay)
            denominator = ax * (peak[1] - a[1]) - ay * (peak[0] - a[0])
            for triangle in triangulate(clipped):
                if not clipped.covers(triangle):
                    continue
                points = []
                for x, y in list(triangle.exterior.coords)[:3]:
                    fraction = (ax * (y - a[1]) - ay * (x - a[0])) / denominator
                    points.append((x, y, height + 4.2 * fraction))
                pa, pb, pc = points
                scene.triangle("Building_TensileRoof", "White", pa, pb, pc)
                scene.triangle(
                    "Building_TensileSoffit",
                    "Cream",
                    add(pc, (0, 0, -0.12)),
                    add(pb, (0, 0, -0.12)),
                    add(pa, (0, 0, -0.12)),
                )
            if length > 2:
                edge_a, edge_b = (a[0], a[1], height), (b[0], b[1], height)
                scene.beam("Building_TensileRim", "White", edge_a, edge_b, 0.14)
                middle = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, height - 0.2
                scene.beam(
                    "Building_TensileRibs",
                    "Steel",
                    middle,
                    add(peak, (0, 0, -0.2)),
                    0.12,
                )
        vertices = ring[:-1]
        support_a = max(vertices, key=lambda point: scene.nearest(*point)[1])
        rear = [
            point
            for point in vertices
            if scene.nearest(*point)[1] > scene.nearest(*support_a)[1] - 3
        ]
        support_b = max(rear, key=lambda point: math.dist(point, support_a))
        for point in (support_a, support_b):
            base = point[0], point[1], scene.ground(*point)
            top = point[0], point[1], height
            scene.beam("Building_TensileColumns", "White", base, top, 0.32)
            scene.beam(
                "Building_TensileBraces",
                "Steel",
                add(top, (0, 0, -2)),
                add(peak, (0, 0, -0.3)),
                0.14,
            )
        panels += 1
    return panels


def curved_footprint_stand(
    scene: CircuitScene,
    building: Building,
    rows: int,
    roof: str,
    seat_material: str,
) -> None:
    polygon = Polygon(building.ring)
    if not polygon.is_valid:
        repaired = polygon.buffer(0)
        if not isinstance(repaired, Polygon):
            raise ValueError(f"Stand {building.osm_id} has disconnected footprint")
        polygon = repaired
    available = polygon
    if hasattr(scene, "road_mask"):
        available = polygon.difference(scene.road_mask.buffer(1.2))
    ring = list(polygon.exterior.coords)[:-1]
    winding = 1 if polygon.exterior.is_ccw else -1
    facing: list[bool] = []
    for pa, pb in zip(ring, ring[1:] + ring[:1]):
        length = math.dist(pa, pb)
        tangent = (pb[0] - pa[0]) / length, (pb[1] - pa[1]) / length
        inward = -tangent[1] * winding, tangent[0] * winding
        x, y = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        road, distance = scene.nearest(x, y)
        toward = (road.x - x) * inward[0] + (road.y - y) * inward[1]
        alignment = abs(road.tx * tangent[0] + road.ty * tangent[1])
        facing.append(toward < -distance * 0.25 and alignment > 0.35)
    if not any(facing):
        raise ValueError(f"Stand {building.osm_id} has no road-facing boundary")
    # Start between chains so a boundary crossing the ring origin stays connected.
    start = next((i + 1 for i, selected in enumerate(facing) if not selected), 0)
    chains: list[list[tuple[float, float]]] = []
    chain: list[tuple[float, float]] = []
    for offset in range(len(ring)):
        index = (start + offset) % len(ring)
        if facing[index]:
            if not chain:
                chain.append(ring[index])
            chain.append(ring[(index + 1) % len(ring)])
        elif chain:
            chains.append(chain)
            chain = []
    if chain:
        chains.append(chain)
    bay_count = 0
    sail_count = 0
    max_wall = 0.0
    for boundary in chains:
        sail_shapes: dict[int, list[Polygon]] = {}
        sail_heights: dict[int, float] = {}
        boundary_length = LineString(boundary).length
        sail_span = boundary_length / max(1, round(boundary_length / 23))
        directions: list[Point] = []
        inward_normals: list[Point] = []
        for pa, pb in pairwise(boundary):
            length = math.dist(pa, pb)
            direction = (pb[0] - pa[0]) / length, (pb[1] - pa[1]) / length, 0.0
            directions.append(direction)
            inward_normals.append(
                (-direction[1] * winding, direction[0] * winding, 0.0)
            )
        miters = [inward_normals[0]]
        for previous, following in pairwise(inward_normals):
            denominator = max(
                0.5, 1 + previous[0] * following[0] + previous[1] * following[1]
            )
            miters.append(mul(add(previous, following), 1 / denominator))
        miters.append(inward_normals[-1])
        chain_distance = 0.0
        next_canopy = 13.5
        for segment, (pa, pb) in enumerate(pairwise(boundary)):
            segment_length = math.dist(pa, pb)
            bays = max(1, math.ceil(segment_length / 7))
            direction = directions[segment]
            normal = inward_normals[segment]
            for bay in range(bays):
                bay_count += 1
                t0, t1 = bay / bays, (bay + 1) / bays
                front_a: Point = (
                    pa[0] + (pb[0] - pa[0]) * t0,
                    pa[1] + (pb[1] - pa[1]) * t0,
                    0.0,
                )
                front_b: Point = (
                    pa[0] + (pb[0] - pa[0]) * t1,
                    pa[1] + (pb[1] - pa[1]) * t1,
                    0.0,
                )
                normal_a = add(
                    mul(miters[segment], 1 - t0), mul(miters[segment + 1], t0)
                )
                normal_b = add(
                    mul(miters[segment], 1 - t1), mul(miters[segment + 1], t1)
                )
                base_a = scene.ground(*front_a[:2]) + 0.25
                base_b = scene.ground(*front_b[:2]) + 0.25
                top_a, top_b = base_a, base_b
                previous_a, previous_b = base_a - 0.46, base_b - 0.46
                roof_shapes: list[Polygon] = []
                for row in range(rows):
                    a = add(front_a, mul(normal_a, row * 0.9))
                    b = add(front_b, mul(normal_b, row * 0.9))
                    c = add(front_b, mul(normal_b, (row + 1) * 0.9))
                    d = add(front_a, mul(normal_a, (row + 1) * 0.9))
                    cell = Polygon([a[:2], b[:2], c[:2], d[:2]])
                    if not cell.is_valid or cell.area < 0.01:
                        continue
                    clipped = cell.intersection(available)
                    if clipped.area < 0.05:
                        continue
                    top_a = max(
                        base_a + row * 0.46,
                        previous_a + 0.46,
                        scene.ground(*a[:2]) + 0.18,
                        scene.ground(*d[:2]) + 0.18,
                    )
                    top_b = max(
                        base_b + row * 0.46,
                        previous_b + 0.46,
                        scene.ground(*b[:2]) + 0.18,
                        scene.ground(*c[:2]) + 0.18,
                    )
                    previous_a, previous_b = top_a, top_b
                    row_a = mul(add(a, d), 0.5)
                    row_b = mul(add(b, c), 0.5)
                    row_dx, row_dy = row_b[0] - row_a[0], row_b[1] - row_a[1]
                    row_length_squared = row_dx * row_dx + row_dy * row_dy

                    def height(
                        x: float,
                        y: float,
                        origin: Point = row_a,
                        z: float = top_a,
                        dz: float = top_b - top_a,
                        dx: float = row_dx,
                        dy: float = row_dy,
                        length_squared: float = row_length_squared,
                    ) -> float:
                        along = ((x - origin[0]) * dx + (y - origin[1]) * dy) / max(
                            length_squared, 1e-8
                        )
                        return z + dz * max(0.0, min(1.0, along))

                    for triangle in triangulate(clipped):
                        if clipped.covers(triangle):
                            points: list[Point] = [
                                (x, y, height(x, y))
                                for x, y in list(triangle.exterior.coords)[:3]
                            ]
                            scene.triangle(
                                "Building_StandTread",
                                "Concrete",
                                points[0],
                                points[1],
                                points[2],
                            )
                    pieces = (
                        [clipped]
                        if isinstance(clipped, Polygon)
                        else list(clipped.geoms)
                    )
                    for piece in pieces:
                        if not isinstance(piece, Polygon):
                            continue
                        roof_shapes.append(piece)
                        edge = list(piece.exterior.coords)
                        for edge_a, edge_b in pairwise(edge):
                            floor_a = edge_a[0], edge_a[1], scene.ground(*edge_a) - 0.05
                            floor_b = edge_b[0], edge_b[1], scene.ground(*edge_b) - 0.05
                            tread_a = edge_a[0], edge_a[1], height(*edge_a)
                            tread_b = edge_b[0], edge_b[1], height(*edge_b)
                            max_wall = max(
                                max_wall,
                                tread_a[2] - floor_a[2],
                                tread_b[2] - floor_b[2],
                            )
                            double_quad(
                                scene,
                                "Building_StandRiser",
                                "Concrete",
                                floor_a,
                                floor_b,
                                tread_b,
                                tread_a,
                            )
                    seat_line = LineString(
                        [
                            add(a, mul(normal_a, 0.45))[:2],
                            add(b, mul(normal_b, 0.45))[:2],
                        ]
                    )
                    seats = seat_line.intersection(clipped.buffer(-0.12))
                    seat_segments = (
                        [seats]
                        if isinstance(seats, LineString)
                        else list(seats.geoms)
                        if isinstance(seats, MultiLineString)
                        else []
                    )
                    for seat in seat_segments:
                        if seat.length < 0.65:
                            continue
                        sx, sy = seat.coords[0]
                        ex, ey = seat.coords[-1]
                        seat_a = sx, sy, height(sx, sy) + 0.15
                        seat_b = ex, ey, height(ex, ey) + 0.15
                        scene.beam(
                            "Building_StandSeats",
                            seat_material,
                            seat_a,
                            seat_b,
                            0.35,
                            0.16,
                        )
                        scene.spectators(
                            add(seat_a, (0, 0, 0.2)),
                            add(seat_b, (0, 0, 0.2)),
                            row,
                            "Building_Crowd_Stand",
                        )
                if roof == "sail":
                    sail = int(
                        (chain_distance + segment_length * (bay + 0.5) / bays) / sail_span
                    )
                    sail_shapes.setdefault(sail, []).extend(roof_shapes)
                    sail_heights[sail] = max(
                        sail_heights.get(sail, -math.inf), top_a + 4, top_b + 4
                    )
                if roof and roof not in ("lotus", "sail"):
                    roof_height = max(top_a, top_b) + 4
                    for shape in roof_shapes:
                        roof_polygon(
                            scene, list(shape.exterior.coords)[:-1], roof_height
                        )
                    rear_a = add(front_a, mul(normal_a, rows * 0.9 - 0.5))
                    rear_b = add(front_b, mul(normal_b, rows * 0.9 - 0.5))
                    for support in (rear_a, rear_b):
                        if available.buffer(-0.25).covers(GeoPoint(*support[:2])):
                            scene.beam(
                                "Building_StandRoofFrame",
                                "Steel",
                                (support[0], support[1], scene.ground(*support[:2])),
                                (support[0], support[1], roof_height),
                                0.28,
                            )
                midpoint_distance = chain_distance + segment_length * (bay + 0.5) / bays
                if roof == "lotus" and midpoint_distance >= next_canopy:
                    next_canopy += 27
                    center = add(
                        mul(add(front_a, front_b), 0.5), mul(normal, rows * 0.45)
                    )
                    if available.buffer(-0.7).covers(GeoPoint(*center[:2])):
                        center = center[0], center[1], max(top_a, top_b) + 4
                        oval_canopy(
                            scene,
                            center,
                            direction,
                            normal,
                            15.3,
                            rows * 0.45 + 2,
                            available,
                        )
            chain_distance += segment_length
        for sail, pieces in sail_shapes.items():
            sail_count += tensile_roof(scene, unary_union(pieces), sail_heights[sail])
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append(
        {
            "name": building.name or "Mapped spectator terrace",
            "osm_id": building.osm_id,
            "roof": roof,
            "rows": rows,
            "seat_material": seat_material,
            "structure": "Footprint-clipped curved terraces on local front-edge ground; road-facing boundary chains and inward rows retain the mapped grass interior.",
            "boundary_chains": len(chains),
            "bays": bay_count,
            "max_foundation_height_m": max_wall,
            "tensile_roof_bays": sail_count,
        }
    )


def footprint_stand(
    scene: CircuitScene,
    osm_id: int,
    rows: int = 18,
    roof: str = "",
    seat_material: str = "SeatBlue",
) -> None:
    building = mapped(scene, osm_id)
    if building is None:
        return
    center, axis, side, length, width = frame(building)
    if length * width / Polygon(building.ring).area > 1.25 or (
        scene.slug == "bahrain" and roof == "sail"
    ):
        curved_footprint_stand(scene, building, rows, roof, seat_material)
        return
    sample, _ = scene.nearest(center[0], center[1])
    if (center[0] - sample.x) * side[0] + (center[1] - sample.y) * side[1] < 0:
        side = mul(side, -1)
    footprint_width = width
    width = min(width, rows * 0.9 + 8)
    z = scene.ground(center[0], center[1])
    rows = min(rows, max(6, int(width / 0.9)))
    steps = max(1, math.ceil(length / 7))
    front = add((center[0], center[1], z + 0.8), mul(side, -footprint_width / 2))

    def ground(point: Point) -> Point:
        return point[0], point[1], scene.ground(point[0], point[1]) - 0.12

    def row_levels(start_a: Point, start_b: Point) -> list[tuple[float, float]]:
        height_a = scene.ground(*start_a[:2]) + 0.8 - 0.46
        height_b = scene.ground(*start_b[:2]) + 0.8 - 0.46
        levels = []
        for row in range(rows):
            a = add(start_a, mul(side, row * 0.9))
            b = add(start_b, mul(side, row * 0.9))
            rear_a, rear_b = add(a, mul(side, 0.9)), add(b, mul(side, 0.9))
            height_a = max(
                height_a + 0.46,
                scene.ground(*a[:2]) + 0.18,
                scene.ground(*rear_a[:2]) + 0.18,
            )
            height_b = max(
                height_b + 0.46,
                scene.ground(*b[:2]) + 0.18,
                scene.ground(*rear_b[:2]) + 0.18,
            )
            levels.append((height_a, height_b))
        return levels

    for step in range(steps):
        along_a = -length / 2 + length * step / steps
        along_b = -length / 2 + length * (step + 1) / steps
        front_a, front_b = (
            add(front, mul(axis, along_a)),
            add(front, mul(axis, along_b)),
        )
        levels = row_levels(front_a, front_b)
        first_a = front_a[0], front_a[1], levels[0][0]
        first_b = front_b[0], front_b[1], levels[0][1]
        previous_rear_a, previous_rear_b = first_a, first_b
        for row, (height_a, height_b) in enumerate(levels):
            a = add(front_a, mul(side, row * 0.9))
            b = add(front_b, mul(side, row * 0.9))
            a, b = (a[0], a[1], height_a), (b[0], b[1], height_b)
            rear_a, rear_b = add(a, mul(side, 0.9)), add(b, mul(side, 0.9))
            upward_quad(scene, "Building_StandTread", "Concrete", a, b, rear_b, rear_a)
            double_quad(
                scene,
                "Building_StandSoffit",
                "Concrete",
                add(a, (0, 0, -0.28)),
                add(b, (0, 0, -0.28)),
                add(rear_b, (0, 0, -0.28)),
                add(rear_a, (0, 0, -0.28)),
            )
            if row > 0:
                double_quad(
                    scene,
                    "Building_StandRiser",
                    "Concrete",
                    previous_rear_a,
                    previous_rear_b,
                    b,
                    a,
                )
            previous_rear_a, previous_rear_b = rear_a, rear_b
            scene.beam(
                "Building_StandSeats",
                seat_material,
                add(a, (0, 0, 0.15)),
                add(b, (0, 0, 0.15)),
                0.4,
                0.16,
            )
            scene.spectators(
                add(a, (0, 0, 0.3)), add(b, (0, 0, 0.3)), row, "Building_Crowd_Stand"
            )
            if step == 0:
                double_quad(
                    scene,
                    "Building_StandEnd",
                    "Concrete",
                    ground(a),
                    ground(rear_a),
                    rear_a,
                    a,
                )
            if step == steps - 1:
                double_quad(
                    scene,
                    "Building_StandEnd",
                    "Concrete",
                    ground(b),
                    ground(rear_b),
                    rear_b,
                    b,
                )
        double_quad(
            scene,
            "Building_StandFoundation",
            "Concrete",
            ground(first_a),
            ground(first_b),
            first_b,
            first_a,
        )
        soffit_rear_a, soffit_rear_b = (
            add(rear_a, (0, 0, -0.28)),
            add(rear_b, (0, 0, -0.28)),
        )
        scene.beam(
            "Building_StandFramework", "Steel", ground(rear_a), soffit_rear_a, 0.3
        )
        scene.beam(
            "Building_StandFramework", "Steel", ground(rear_b), soffit_rear_b, 0.3
        )
        scene.beam(
            "Building_StandFramework", "Steel", ground(rear_a), soffit_rear_b, 0.18
        )
        scene.beam(
            "Building_StandFramework", "Steel", ground(rear_b), soffit_rear_a, 0.18
        )
        scene.beam(
            "Building_StandFramework", "Steel", soffit_rear_a, soffit_rear_b, 0.25
        )
        scene.beam(
            "Building_StandRailing",
            "Steel",
            add(rear_a, (0, 0, 1.1)),
            add(rear_b, (0, 0, 1.1)),
            0.07,
        )
        scene.beam(
            "Building_StandRailing", "Steel", rear_a, add(rear_a, (0, 0, 1.1)), 0.07
        )
    count = max(1, round(length / (23 if roof != "lotus" else 27)))
    for bay in range(count):
        along = -length / 2 + length * (bay + 0.5) / count
        half = length / count / 2
        roof_levels = row_levels(
            add(front, mul(axis, along - half)), add(front, mul(axis, along + half))
        )
        roof_z = max(roof_levels[-1]) + 4
        c = add(
            (center[0], center[1], roof_z),
            mul(axis, -length / 2 + length * (bay + 0.5) / count),
        )
        depth = max(width, rows * 0.9 + 4) / 2
        if roof == "lotus":
            oval_canopy(scene, c, axis, side, half + 1.8, depth + 2)
        elif roof == "sail":
            corners = [
                add(c, add(mul(axis, x), mul(side, y)))
                for x, y in [
                    (-half, -depth),
                    (half, -depth),
                    (half, depth),
                    (-half, depth),
                ]
            ]
            peak = add(c, (0, 0, 5))
            for a, b in zip(corners, corners[1:] + corners[:1]):
                scene.triangle("Building_Tensile", "White", a, b, peak)
                scene.triangle("Building_Tensile", "Cream", peak, b, a)
                scene.beam("Building_Tensile", "Steel", a, peak, 0.10)
            scene.beam(
                "Building_Tensile",
                "White",
                ground(corners[2]),
                add(corners[2], (0, 0, 6)),
                0.25,
            )
        elif roof:
            front_a = add(c, add(mul(axis, -half), mul(side, -depth)))
            front_b = add(c, add(mul(axis, half), mul(side, -depth)))
            rear_a = add(add(front_a, mul(side, 2 * depth)), (0, 0, 1.4))
            rear_b = add(add(front_b, mul(side, 2 * depth)), (0, 0, 1.4))
            upward_quad(
                scene, "Building_StandRoof", "Roof", front_a, front_b, rear_b, rear_a
            )
            double_quad(
                scene,
                "Building_StandRoofSoffit",
                "Concrete",
                add(front_a, (0, 0, -0.22)),
                add(front_b, (0, 0, -0.22)),
                add(rear_b, (0, 0, -0.22)),
                add(rear_a, (0, 0, -0.22)),
            )
            double_quad(
                scene,
                "Building_StandRoofEdge",
                "White",
                front_a,
                front_b,
                add(front_b, (0, 0, -0.22)),
                add(front_a, (0, 0, -0.22)),
            )
            for front_point, rear_point in ((front_a, rear_a), (front_b, rear_b)):
                scene.beam(
                    "Building_StandRoofFrame",
                    "Steel",
                    ground(rear_point),
                    rear_point,
                    0.38,
                )
                scene.beam(
                    "Building_StandRoofFrame",
                    "Steel",
                    add(front_point, (0, 0, -0.45)),
                    rear_point,
                    0.26,
                )
                scene.beam(
                    "Building_StandRoofFrame",
                    "Steel",
                    add(rear_point, (0, 0, -3)),
                    add(front_point, (0, 0, -0.45)),
                    0.18,
                )
            scene.beam("Building_StandRoofFrame", "Steel", front_a, front_b, 0.22)
            scene.beam("Building_StandRoofFrame", "Steel", rear_a, rear_b, 0.28)
    scene.modeled_buildings.add(osm_id)
    scene.landmarks.append(
        {
            "name": building.name or "Mapped spectator terrace",
            "osm_id": osm_id,
            "roof": roof,
            "rows": rows,
            "seat_material": seat_material,
            "structure": "Closed concrete treads and risers, end walls, sloping soffit, grounded braced rear columns and two-sided roof soffit.",
        }
    )


def facade(
    scene: CircuitScene,
    osm_id: int,
    height: float | None = None,
    style: str = "classical",
    material: str = "Cream",
) -> None:
    building = mapped(scene, osm_id)
    if building is None:
        return
    center, axis, _side, length, width = frame(building)
    z = min(scene.ground(x, y) for x, y in building.ring)
    h = height if height is not None else max(8.0, building.height)
    original = Polygon(building.ring)
    available = original.difference(scene.road_mask.buffer(1.2))
    polygons = (
        [available]
        if isinstance(available, Polygon)
        else [p for p in available.geoms if isinstance(p, Polygon)]
    )
    if original.area - available.area > 0.1:
        scene.landmarks.append(
            {
                "name": building.name or "Mapped footprint clearance",
                "osm_id": osm_id,
                "footprint_clip_m2": round(original.area - available.area, 2),
                "note": "Retained footprint overlaps native lane; ground walls clipped to preserve road clearance.",
            }
        )
    for polygon in polygons:
        ring = list(polygon.exterior.coords)[:-1]
        classical = style in ("classical", "mansard")
        winding = 1 if Polygon(ring).exterior.is_ccw else -1
        floors = max(2, min(40, round(h / (4.2 if classical else 3.8))))
        for a, b in zip(ring, ring[1:] + ring[:1]):
            span = math.dist(a, b)
            if span < 0.3:
                continue
            tangent = ((b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.0)
            normal = (tangent[1] * winding * 0.065, -tangent[0] * winding * 0.065, 0.0)
            pa, pb = (a[0], a[1], z), (b[0], b[1], z)
            scene.banner(pa, pb, h, material, "Building_Facade")
            bays = max(1, round(span / (3.6 if classical else 4.5)))
            for floor in range(floors):
                level = h * (floor + 0.18) / floors
                if classical:
                    scene.beam(
                        "Building_Cornice",
                        "White",
                        add(pa, (0, 0, h * (floor + 1) / floors)),
                        add(pb, (0, 0, h * (floor + 1) / floors)),
                        0.32,
                        0.20,
                    )
                for bay in range(bays):
                    c = add(add(pa, normal), mul(tangent, span * (bay + 0.5) / bays))
                    w = min(2.0, span / bays * 0.53)
                    left = add(c, add(mul(tangent, -w / 2), (0, 0, level)))
                    right = add(c, add(mul(tangent, w / 2), (0, 0, level)))
                    if scene.nearest(c[0], c[1])[1] < 16:
                        continue
                    scene.banner(
                        left,
                        right,
                        h / floors * 0.60,
                        "WarmGlass" if scene.slug == "singapore" else "Glass",
                        "Building_Windows",
                    )
                    if classical:
                        for edge in (left, right):
                            scene.beam(
                                "Building_WindowTrim",
                                "White",
                                edge,
                                add(edge, (0, 0, h / floors * 0.63)),
                                0.12,
                            )
                        scene.beam(
                            "Building_WindowTrim",
                            "White",
                            add(left, (0, 0, -0.12)),
                            add(right, (0, 0, -0.12)),
                            0.22,
                            0.15,
                        )
                        if floor == 0:
                            last = add(
                                c,
                                add(
                                    mul(tangent, -w * 0.65),
                                    (0, 0, level + h / floors * 0.65),
                                ),
                            )
                            for step in range(1, 9):
                                angle = math.pi * (1 - step / 8)
                                nxt = add(
                                    c,
                                    add(
                                        mul(tangent, math.cos(angle) * w * 0.65),
                                        (
                                            0,
                                            0,
                                            level
                                            + h / floors * 0.65
                                            + math.sin(angle) * 0.65,
                                        ),
                                    ),
                                )
                                scene.beam("Building_Arches", "White", last, nxt, 0.16)
                                last = nxt
            scene.beam(
                "Building_Parapet",
                "White",
                add(pa, (0, 0, h)),
                add(pb, (0, 0, h)),
                0.8,
                0.5,
            )
        roof_polygon(scene, ring, z + h)
    if style == "mansard":
        heading = math.atan2(axis[1], axis[0])
        for layer in range(5):
            scene.box(
                "Building_Mansard",
                "Roof",
                (center[0], center[1], z + h + layer * 0.65),
                max(3.0, length - layer * 1.5),
                max(3.0, width - layer * 1.5),
                0.7,
                heading,
            )
    scene.modeled_buildings.add(osm_id)
    scene.landmarks.append(
        {
            "name": building.name or "Mapped building",
            "osm_id": osm_id,
            "height_m": h,
            "facade": style,
        }
    )


def trees(
    scene: CircuitScene,
    start: float,
    end: float,
    side: int,
    setback: float,
    spacing: float = 24.0,
    height: float = 11.0,
    palm: bool = False,
) -> None:
    count = max(1, math.ceil((end - start) / spacing))
    placed = 0
    footprints = [Polygon(b.ring).buffer(2) for b in scene.buildings]
    for i in range(count):
        sample = scene.at(start + (end - start) * (i + 0.5) / count)
        lane = side * (
            sample.half_width
            + 0.95
            + (sample.left_shoulder if side > 0 else sample.right_shoulder)
            + setback
            + (i % 3) * 2.5
        )
        p = sample.point(lane)
        nearest, distance = scene.nearest(p[0], p[1])
        if distance < nearest.half_width + 5:
            continue
        base = p[0], p[1], scene.ground(p[0], p[1])
        if any(polygon.contains(GeoPoint(base[0], base[1])) for polygon in footprints):
            continue
        if palm:
            scene.palm(base, height + (i % 3) * 0.8)
        else:
            scene.broadleaf(base, height + (i % 4) * 0.6, i + round(start))
        placed += 1
    scene.vegetation.append(
        {
            "type": "palms" if palm else "broadleaf",
            "start_m": start,
            "end_m": end,
            "side": side,
            "count": placed,
            "setback_m": setback,
            "placement": "Reference-sector visual estimate, checked against all road arms and building footprints.",
        }
    )


def layered_pit_roofs(
    scene: CircuitScene,
    start: float,
    end: float,
    side: int,
    levels: int = 3,
    height: float = 15.0,
    bay: float = 36.0,
) -> None:
    span = (end - start) % scene.length
    count = max(1, round(span / bay))
    for i in range(count):
        a, b = (
            scene.at(start + span * i / count),
            scene.at(start + span * (i + 1) / count),
        )
        for level in range(levels):
            z = height - level * 3.2
            near_a, near_b = (
                side * (a.half_width + 9 - level * 0.6),
                side * (b.half_width + 9 - level * 0.6),
            )
            far_a, far_b = near_a + side * 27, near_b + side * 27
            scene.quad(
                "Building_PitRoof",
                "Roof",
                a.point(near_a, z),
                b.point(near_b, z),
                b.point(far_b, z + 1),
                a.point(far_a, z + 1),
            )
            scene.quad(
                "Building_PitRoof",
                "Concrete",
                a.point(far_a, z + 0.8),
                b.point(far_b, z + 0.8),
                b.point(near_b, z - 0.2),
                a.point(near_a, z - 0.2),
            )
            scene.beam(
                "Building_PitRoof",
                "White",
                a.point(near_a, z),
                b.point(near_b, z),
                0.25,
            )
