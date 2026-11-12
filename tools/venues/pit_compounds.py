"""Mapped Sakhir, Shanghai and Singapore garage compounds, without generic blocks."""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable

from circuit_dataclasses import Point, RoadStation
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient

from venues.east_architecture import frame
from venues.pit_compounds_dataclasses import PitCompound

SAKHIR = PitCompound(187123416, "Sakhir", 9.6, 2, 4.3, 8.0, "folded")
SHANGHAI = PitCompound(156328694, "Shanghai", 16.0, 2, 4.5, 8.5, "terrace")
SINGAPORE = PitCompound(49890775, "Singapore", 15.0, 3, 4.6, 8.5, "eaves", 36)


def roof_shell(
    scene: CircuitScene,
    shape: Polygon,
    height: Callable[[float, float], float],
    kind: str,
    material: str,
    soffit_material: str,
    side_material: str,
    thickness: float = 0.18,
    underside: Callable[[float, float], float] | None = None,
    side_writer: Callable[[Point, Point, Point, Point], None] | None = None,
) -> None:
    edges: dict[tuple[Point, Point], tuple[Point, Point, int]] = {}
    left, bottom, right, top = shape.bounds
    for ix in range(math.ceil((right - left) / 4)):
        for iy in range(math.ceil((top - bottom) / 4)):
            cell = shape.intersection(
                box(
                    left + ix * 4,
                    bottom + iy * 4,
                    left + (ix + 1) * 4,
                    bottom + (iy + 1) * 4,
                )
            )
            for triangle in constrained_delaunay_triangles(cell).geoms:
                top_points = [
                    (x, y, height(x, y))
                    for x, y in list(orient(triangle).exterior.coords)[:3]
                ]
                low_points = [
                    (
                        p[0],
                        p[1],
                        underside(p[0], p[1])
                        if underside is not None
                        else p[2] - thickness,
                    )
                    for p in top_points
                ]
                scene.triangle(
                    kind + "Roof", material, top_points[0], top_points[1], top_points[2]
                )
                scene.triangle(
                    kind + "RoofSoffit",
                    soffit_material,
                    low_points[2],
                    low_points[1],
                    low_points[0],
                )
                for a, b in zip(top_points, top_points[1:] + top_points[:1]):
                    ka: Point = (round(a[0], 8), round(a[1], 8), round(a[2], 8))
                    kb: Point = (round(b[0], 8), round(b[1], 8), round(b[2], 8))
                    key = (ka, kb) if ka < kb else (kb, ka)
                    count = edges[key][2] if key in edges else 0
                    edges[key] = (a, b, count + 1)
    for a, b, count in edges.values():
        if count != 1:
            continue
        lower_a = (
            a[0],
            a[1],
            underside(a[0], a[1]) if underside is not None else a[2] - thickness,
        )
        lower_b = (
            b[0],
            b[1],
            underside(b[0], b[1]) if underside is not None else b[2] - thickness,
        )
        if side_writer is None:
            scene.quad(kind + "RoofEdges", side_material, lower_a, lower_b, b, a)
        else:
            side_writer(lower_a, lower_b, b, a)


def mapped_pit(scene: CircuitScene, control: PitCompound) -> None:
    building = scene.footprint(control.osm_id)
    shape = orient(Polygon(building.ring))
    center, axis, normal, length, width = frame(building)
    nearby, _ = scene.nearest(*center[:2])
    toward = (
        1
        if (nearby.x - center[0]) * normal[0] + (nearby.y - center[1]) * normal[1] > 0
        else -1
    )
    roadward = mul(normal, toward)
    ring = list(shape.exterior.coords)
    kind = "Building_" + control.name + "MappedPit"

    def foundation(x: float, y: float) -> float:
        return scene.nearest(x, y)[0].z

    def point(x: float, y: float, height: float) -> Point:
        return x, y, foundation(x, y) + height

    def edges() -> list[tuple[tuple[float, float], tuple[float, float], bool]]:
        result = []
        for a, b in itertools.pairwise(ring):
            span = math.dist(a, b)
            outward = (
                (b[1] - a[1]) / max(0.001, span),
                -(b[0] - a[0]) / max(0.001, span),
            )
            front = (
                span > 18 and outward[0] * roadward[0] + outward[1] * roadward[1] > 0.7
            )
            result.append((a, b, front))
        return result

    front_edges = [(a, b) for a, b, front in edges() if front]
    frontage = sum(math.dist(a, b) for a, b in front_edges)
    front_counts: list[int] = []
    if control.garage_count is not None:
        quotas = [
            control.garage_count * math.dist(a, b) / frontage for a, b in front_edges
        ]
        front_counts = [math.floor(quota) for quota in quotas]
        order = sorted(
            range(len(quotas)), key=lambda i: quotas[i] - front_counts[i], reverse=True
        )
        for index in order[: control.garage_count - sum(front_counts)]:
            front_counts[index] += 1
    front_index = 0
    garages = 0
    scene.terrain_cutouts.append(shape)
    # Small exact strips remove roof DSM within the occupied footprint only.
    for index in range(math.ceil(length / 8)):
        u0 = -length / 2 + index * 8
        u1 = min(length / 2, u0 + 8)
        corners = [
            (
                center[0] + axis[0] * u + normal[0] * v,
                center[1] + axis[1] * u + normal[1] * v,
            )
            for u, v in ((u0, -width), (u1, -width), (u1, width), (u0, width))
        ]
        patch = shape.intersection(Polygon(corners))
        parts = (
            [patch] if isinstance(patch, Polygon) else list(getattr(patch, "geoms", []))
        )
        for part in parts:
            if isinstance(part, Polygon) and not part.is_empty:
                scene.ground_patches.append(
                    (part, foundation(part.centroid.x, part.centroid.y), "Concrete")
                )

    for a, b, front in edges():
        span = math.dist(a, b)
        if span < 0.05:
            continue
        tangent = ((b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.0)
        outward = tangent[1], -tangent[0], 0.0
        bays = max(1, round(span / control.bay_spacing_m))
        if front and control.garage_count is not None:
            bays = front_counts[front_index]
            front_index += 1
        if front:
            garages += bays
        for bay in range(bays):
            edge_a = (
                a[0] + (b[0] - a[0]) * bay / bays,
                a[1] + (b[1] - a[1]) * bay / bays,
            )
            edge_b = (
                a[0] + (b[0] - a[0]) * (bay + 1) / bays,
                a[1] + (b[1] - a[1]) * (bay + 1) / bays,
            )
            scene.quad(
                kind + "Walls",
                "White",
                point(*edge_a, 0),
                point(*edge_b, 0),
                point(*edge_b, control.body_height_m),
                point(*edge_a, control.body_height_m),
            )
            if front:
                door_a = add(
                    point(*edge_a, 0.18), add(mul(tangent, 0.28), mul(outward, 0.025))
                )
                door_b = add(
                    point(*edge_b, 0.18), add(mul(tangent, -0.28), mul(outward, 0.025))
                )
                scene.quad(
                    kind + "GaragePortals",
                    "Black",
                    door_a,
                    door_b,
                    add(door_b, (0, 0, control.garage_height_m - 0.3)),
                    add(door_a, (0, 0, control.garage_height_m - 0.3)),
                )
                for height in (
                    control.garage_height_m - 0.35,
                    control.garage_height_m - 0.21,
                ):
                    scene.beam(
                        kind + "RollerHeaders",
                        "Steel",
                        add(point(*edge_a, height), mul(outward, 0.07)),
                        add(point(*edge_b, height), mul(outward, 0.07)),
                        0.13,
                        0.07,
                    )
                scene.beam(
                    kind + "GaragePiers",
                    "White",
                    point(*edge_a, 0),
                    point(*edge_a, control.garage_height_m + 0.4),
                    0.4,
                )
            for floor in range(1, control.floors):
                floor_height = control.body_height_m * floor / control.floors
                inset = 0.38 if front else 0.65
                left = add(
                    point(*edge_a, floor_height + 0.55),
                    add(mul(tangent, inset), mul(outward, 0.04)),
                )
                right = add(
                    point(*edge_b, floor_height + 0.55),
                    add(mul(tangent, -inset), mul(outward, 0.04)),
                )
                window_height = control.body_height_m / control.floors * 0.57
                scene.quad(
                    kind + "Hospitality",
                    "WarmGlass" if scene.slug == "singapore" else "Glass",
                    left,
                    right,
                    add(right, (0, 0, window_height)),
                    add(left, (0, 0, window_height)),
                )
                if front:
                    balcony_a, balcony_b = (
                        add(point(*edge_a, floor_height), mul(outward, 1.0)),
                        add(point(*edge_b, floor_height), mul(outward, 1.0)),
                    )
                    scene.quad(
                        kind + "Balconies",
                        "White",
                        point(*edge_a, floor_height),
                        point(*edge_b, floor_height),
                        balcony_b,
                        balcony_a,
                        up=True,
                    )
                    scene.quad(
                        kind + "BalconySoffits",
                        "Concrete",
                        add(balcony_a, (0, 0, -0.2)),
                        add(balcony_b, (0, 0, -0.2)),
                        add(point(*edge_b, floor_height), (0, 0, -0.2)),
                        add(point(*edge_a, floor_height), (0, 0, -0.2)),
                        up=False,
                    )
                    scene.beam(
                        kind + "BalconyFascia", "White", balcony_a, balcony_b, 0.28, 0.3
                    )
                    scene.beam(
                        kind + "BalconyRails",
                        "Steel",
                        add(balcony_a, (0, 0, 1.05)),
                        add(balcony_b, (0, 0, 1.05)),
                        0.065,
                    )
            if front and scene.slug in {"china", "singapore"}:
                top = control.body_height_m / control.floors + 0.1
                scene.banner(
                    add(point(*edge_a, top), mul(outward, 1.15)),
                    add(point(*edge_b, top), mul(outward, 1.15)),
                    0.9,
                    "PanelDHL",
                    kind + "DHLFascia",
                )
            for floor in (0, control.floors):
                height = control.body_height_m * floor / control.floors
                scene.beam(
                    kind + "PerimeterFrame",
                    "White",
                    point(*edge_a, height),
                    point(*edge_b, height),
                    0.25,
                    0.22,
                )

    def roof_height(x: float, y: float) -> float:
        u = (x - center[0]) * axis[0] + (y - center[1]) * axis[1]
        v = ((x - center[0]) * normal[0] + (y - center[1]) * normal[1]) * toward
        if control.roof_form == "folded":
            along = 2.7 * math.sin(math.pi * ((u + length / 2) % 24) / 24) ** 2
            cross = 1.2 * max(0, 1 - abs(v) / (width / 2 + 1.5))
            return foundation(x, y) + 10.8 + along + cross
        slope = (
            0.65 * max(0.0, min(1.0, (width / 2 - v) / width))
            if control.roof_form == "eaves"
            else 0.0
        )
        return foundation(x, y) + control.body_height_m + 0.25 + slope

    roof = shape.union(translate(shape, xoff=roadward[0] * 1.5, yoff=roadward[1] * 1.5))
    material = "CanopyFabric" if control.roof_form == "folded" else "White"
    roof_shell(scene, roof, roof_height, kind, material, material, material)
    for index in range(math.ceil(length / 24) + 1):
        u = -length / 2 + min(length, index * 24)
        xy = [
            (
                center[0] + axis[0] * u + normal[0] * v,
                center[1] + axis[1] * u + normal[1] * v,
            )
            for v in (-width, width)
        ]
        paths = roof.intersection(LineString(xy))
        segments = (
            [paths]
            if isinstance(paths, LineString)
            else list(getattr(paths, "geoms", []))
        )
        for segment in segments:
            if (
                not isinstance(segment, LineString)
                or segment.is_empty
                or segment.length < 0.01
            ):
                continue
            count = max(1, math.ceil(segment.length / 3))
            for first, last in zip(range(count), range(1, count + 1)):
                a, b = (
                    segment.interpolate(first / count, normalized=True),
                    segment.interpolate(last / count, normalized=True),
                )
                pa, pb = (
                    (a.x, a.y, roof_height(a.x, a.y) - 0.32),
                    (b.x, b.y, roof_height(b.x, b.y) - 0.32),
                )
                scene.beam(kind + "RoofRibs", "Steel", pa, pb, 0.13)
    if control.roof_form == "folded":
        for offset in (25.0, 50.0, 75.0, 100.0):
            u = -length / 2 + offset
            x, y = center[0] + axis[0] * u, center[1] + axis[1] * u
            if not roof.covers(ShapePoint(x, y)):
                continue
            foot = x, y, roof_height(x, y)
            peak = add(foot, (0, 0, 2.8))
            scene.beam(kind + "EntrySpire", "White", foot, peak, 0.18)
            for du, dv in (
                (-8.0, -width * 0.33),
                (8.0, -width * 0.33),
                (-8.0, width * 0.33),
                (8.0, width * 0.33),
            ):
                px, py = (
                    center[0] + axis[0] * (u + du) + normal[0] * dv,
                    center[1] + axis[1] * (u + du) + normal[1] * dv,
                )
                if roof.covers(ShapePoint(px, py)):
                    scene.beam(
                        kind + "SpireStay",
                        "Steel",
                        (px, py, roof_height(px, py)),
                        peak,
                        0.075,
                    )
    if control.roof_form == "terrace":
        for front_a, front_b in front_edges:
            a_top = point(*front_a, control.body_height_m + 0.35)
            b_top = point(*front_b, control.body_height_m + 0.35)
            scene.beam(
                kind + "RoofTerraceRail",
                "Steel",
                add(a_top, (0, 0, 0.7)),
                add(b_top, (0, 0, 0.7)),
                0.06,
            )
            scene.spectators(a_top, b_top, 0, kind + "RoofTerraceCrowd")
    apron_offset = {187123416: 17.5, 156328694: 18.4, 49890775: 10.9}[control.osm_id]
    pit_side = -1 if control.osm_id == 49890775 else 1
    for front_a, front_b in front_edges:
        count = max(1, math.ceil(math.dist(front_a, front_b) / 5))
        for index in range(count):
            a_xy = tuple(
                front_a[k] + (front_b[k] - front_a[k]) * index / count for k in range(2)
            )
            b_xy = tuple(
                front_a[k] + (front_b[k] - front_a[k]) * (index + 1) / count
                for k in range(2)
            )
            apron_a, _ = scene.nearest(a_xy[0], a_xy[1])
            apron_b, _ = scene.nearest(b_xy[0], b_xy[1])
            inner_a = apron_a.point(pit_side * (apron_a.half_width + apron_offset))
            inner_b = apron_b.point(pit_side * (apron_b.half_width + apron_offset))
            apron = (
                Polygon([inner_a[:2], inner_b[:2], b_xy, a_xy])
                .difference(shape)
                .difference(scene.road_mask)
            )
            if apron.is_empty:
                continue
            scene.terrain_cutouts.append(apron)
            scene.polygon_surface(apron, "Runoff", 0.001, apron_a, paved=True)
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append(
        {
            "name": control.name + " mapped pit compound",
            "osm_id": building.osm_id,
            "mapped_length_m": length,
            "mapped_width_m": width,
            "body_height_m": control.body_height_m,
            "floors": control.floors,
            "garage_bays": garages,
            "roof_form": control.roof_form,
            "source_note": "Actual retained footprint, adjacent-road per-bay foundation and closed roof/soffit. Floors, door/terrace dimensions and roof details are reference reconstructions; see pit-dimension-review.json. No native physical road or profile changes.",
        }
    )


def shanghai_crossing_wings(scene: CircuitScene) -> None:
    """The two real Section A crossings follow its retained 20-point outline."""
    from venues.china_wing_nose import wing_nose, wing_side
    from venues.east_architecture import cylinder

    mapped = Polygon(scene.footprint(107371135).ring)
    for station in (3306.5, 3666.0):
        sample = scene.at(station)
        along = sample.tx, sample.ty, 0.0
        rightward = sample.ty, -sample.tx, 0.0
        corners = [
            add(sample.point(lane), mul(along, offset))[:2]
            for offset, lane in (
                (-20.0, -100.0),
                (20.0, -100.0),
                (20.0, 100.0),
                (-20.0, 100.0),
            )
        ]
        wing = orient(mapped.intersection(Polygon(corners)))
        for side in (1,):
            center = sample.point(side * (sample.half_width + 45))
            base = center[0], center[1], sample.z
            heading = math.atan2(sample.ty, sample.tx)
            ellipse = Polygon(
                [
                    (
                        center[0]
                        + 13 * sample.tx * math.cos(a)
                        + 16.5 * rightward[0] * math.sin(a),
                        center[1]
                        + 13 * sample.ty * math.cos(a)
                        + 16.5 * rightward[1] * math.sin(a),
                    )
                    for a in (i * math.tau / 64 for i in range(64))
                ]
            )
            scene.ground_patches.append((ellipse, sample.z, "Concrete"))
            scene.terrain_cutouts.append(ellipse)
            cylinder(scene, base, 13, 16.5, 23.3, "Glass", 64, heading)
            for floor in range(1, 6):
                cylinder(
                    scene,
                    add(base, (0, 0, floor * 4)),
                    13.05,
                    16.55,
                    0.22,
                    "White",
                    64,
                    heading,
                )

        def wing_height(
            x: float,
            y: float,
            origin: Point = (sample.x, sample.y, sample.z),
            direction: Point = (sample.tx, sample.ty, 0.0),
        ) -> float:
            offset = (x - origin[0]) * direction[0] + (y - origin[1]) * direction[1]
            return (
                scene.nearest(x, y)[0].z + 29 + 3.5 * max(0.0, 1 - (offset / 20) ** 2)
            )

        def wing_floor(x: float, y: float) -> float:
            return scene.nearest(x, y)[0].z + 23.3

        def room_side(
            a: Point, b: Point, c: Point, d: Point, seed: RoadStation = sample
        ) -> None:
            wing_side(scene, seed, a, b, c, d)

        roof_shell(
            scene,
            wing,
            wing_height,
            "Building_ShanghaiMappedWing",
            "White",
            "Concrete",
            "Glass",
            underside=wing_floor,
            side_writer=room_side,
        )
        wing_nose(scene, wing, sample)
        scene.landmarks.append(
            {
                "name": "Shanghai mapped media/hospitality crossing wing",
                "osm_id": 107371135,
                "native_center_station_m": station,
                "road_clearance_m": 23.3,
                "outline_area_m2": wing.area,
                "source_note": "Actual retained Section A footprint crosses the racing centerline at3292–3321m and3651–3681m. Exact crossing outlines replace old50m×166m boxes; original23.3m clearance retained. Curved white roof height29–32.5m and glazed support-tower sections are reference estimates within the tagged35m complex envelope. F1 primary describes two towers and real media/hospitality structures over the track.",
            }
        )


def shanghai_main_stand(scene: CircuitScene) -> None:
    mapped = Polygon(scene.footprint(107371135).ring)
    start, end = 3292.0, 3681.0
    bays = math.ceil((end - start) / 8)
    for bay in range(bays):
        a, b = (
            scene.at(start + (end - start) * bay / bays),
            scene.at(start + (end - start) * (bay + 1) / bays),
        )
        patch = Polygon(
            [a.point(-17)[:2], b.point(-17)[:2], b.point(-69)[:2], a.point(-69)[:2]]
        ).intersection(mapped)
        if isinstance(patch, Polygon) and not patch.is_empty:
            scene.ground_patches.append((patch, (a.z + b.z) / 2, "Concrete"))
        for row in range(34):
            lane = -17 - row * 0.88
            height = 0.8 + row * 0.45
            pa, pb, qa, qb = (
                a.point(lane, height),
                b.point(lane, height),
                a.point(lane - 0.88, height),
                b.point(lane - 0.88, height),
            )
            scene.quad(
                "Building_ShanghaiMappedStandTreads",
                "Concrete",
                pa,
                pb,
                qb,
                qa,
                up=True,
            )
            scene.quad(
                "Building_ShanghaiMappedStandRisers",
                "Concrete",
                add(pa, (0, 0, -0.45)),
                add(pb, (0, 0, -0.45)),
                pb,
                pa,
            )
            scene.beam(
                "Building_ShanghaiMappedStandSeats",
                "SeatRed",
                add(pa, (0, 0, 0.18)),
                add(pb, (0, 0, 0.18)),
                0.35,
                0.12,
            )
            scene.spectators(
                add(pa, (0, 0, 0.25)),
                add(pb, (0, 0, 0.25)),
                row,
                "Building_CrowdShanghaiMappedStand",
            )
            if bay == 0:
                scene.quad(
                    "Building_ShanghaiMappedStandEnd",
                    "Concrete",
                    pa,
                    qa,
                    a.point(lane - 0.88),
                    a.point(lane),
                )
            if bay == bays - 1:
                scene.quad(
                    "Building_ShanghaiMappedStandEnd",
                    "Concrete",
                    qb,
                    pb,
                    b.point(lane),
                    b.point(lane - 0.88),
                )
        scene.quad(
            "Building_ShanghaiMappedStandRear",
            "Concrete",
            qa,
            qb,
            b.point(lane - 0.88),
            a.point(lane - 0.88),
        )
    middle = scene.at((start + end) / 2)
    along = middle.tx, middle.ty, 0.0
    corners = [
        add(middle.point(lane), mul(along, offset))[:2]
        for offset, lane in (
            (-250.0, -17.0),
            (250.0, -17.0),
            (250.0, -100.0),
            (-250.0, -100.0),
        )
    ]
    roof = mapped.intersection(Polygon(corners))

    def main_roof_height(x: float, y: float) -> float:
        sample, _ = scene.nearest(x, y)
        lane = -((x - sample.x) * sample.ty - (y - sample.y) * sample.tx)
        t = max(0.0, min(1.0, (lane - 17) / 52))
        return sample.z + 27 + 7.5 * t**1.35

    roof_shell(
        scene,
        roof,
        main_roof_height,
        "Building_ShanghaiMappedMain",
        "Roof",
        "Concrete",
        "White",
        thickness=0.3,
    )
    for station in range(3300, 3681, 24):
        sample = scene.at(station)
        rear = sample.point(-64)
        scene.beam(
            "Building_ShanghaiMappedMainSupports",
            "White",
            (rear[0], rear[1], sample.z),
            (rear[0], rear[1], main_roof_height(*rear[:2]) - 0.4),
            0.65,
        )
        previous = None
        for lane in range(-64, -16, 4):
            p = sample.point(lane)
            point = p[0], p[1], main_roof_height(*p[:2]) - 0.6
            if previous is not None:
                scene.beam(
                    "Building_ShanghaiMappedMainTruss", "Steel", previous, point, 0.2
                )
            previous = point
    scene.landmarks.append(
        {
            "name": "Shanghai footprint-registered Section A main grandstand",
            "osm_id": 107371135,
            "start_m": start,
            "end_m": end,
            "side": -1,
            "roof_front_height_estimate_m": 27,
            "roof_rear_height_estimate_m": 34.5,
            "source_note": "Retained Section A footprint fixes389m seating/roof extent and17–69m LEFT roof bounds, replacing the450m generic slab. 34rows,27–34.5m gently rising roof, truss pitch and facade details are reference estimates; source overall height35m. The two real crossing wings remain present, with their own unchanged23.3m underclearance.",
        }
    )
