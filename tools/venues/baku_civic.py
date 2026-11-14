from __future__ import annotations

import gzip
import math
from collections.abc import Callable, Sequence
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import Point
from circuit_mesh import add, cross, mul, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as GeoPoint
from shapely.ops import nearest_points, unary_union

from venues.baku_civic_dataclasses import (
    CourtFace,
    CourtFrontageSource,
    CourtOpening,
    NorthFrontageSource,
    StreetGrade,
)
from venues.baku_forecourt_dataclasses import ForecourtSource
from venues.baku_ground import barrier_supports, public_height
from venues.baku_ground_dataclasses import ControlFieldSource
from venues.east_architecture import roof_polygon


def civic_frontage(scene: CircuitScene) -> None:
    source = TypeAdapter(ControlFieldSource).validate_json(
        gzip.decompress((scene.sources / "oldcity-control-field.json.gz").read_bytes())
    )
    height = public_height(source)
    court_ground = foundation_profile(scene, 133641457, height)
    steps = court_frontage(scene, scene.sources / "court-frontage.json")
    base_course(scene, 133641457, court_ground, steps)
    north_ground = foundation_profile(scene, 133641456, height)
    north_frontage(scene, scene.sources / "north-frontage.json", north_ground)
    base_course(scene, 133641456, north_ground)
    barrier_supports(scene, source.barrier_supports)


def _point(face: CourtFace, along: float, z: float, depth: float = 0) -> Point:
    return add(
        face.start,
        add(mul(face.tangent, along), add(mul(face.outward, depth), (0, 0, z))),
    )


def _panel(
    scene: CircuitScene, face: CourtFace, shape: Polygon, depth: float, material: str
) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points = [
            _point(face, x, y, depth) for x, y in list(triangle.exterior.coords)[:3]
        ]
        uv = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
        if not triangle.exterior.is_ccw:
            points[1], points[2] = points[2], points[1]
            uv = uv[0], uv[2], uv[1]
        scene.triangle(
            "Building_CourtMasonry", material, points[0], points[1], points[2], uv
        )


def _opening(
    center: float, width: float, bottom: float, height: float, arched: bool, door: bool
) -> CourtOpening:
    left, right = center - width / 2, center + width / 2
    top = bottom + height
    if arched:
        spring = top - width / 2
        ring = [(left, bottom), (right, bottom), (right, spring)]
        ring.extend(
            (
                center + width / 2 * math.cos(i * math.pi / 16),
                spring + width / 2 * math.sin(i * math.pi / 16),
            )
            for i in range(1, 17)
        )
        return CourtOpening(Polygon(ring), door, spring)
    return CourtOpening(
        Polygon([(left, bottom), (right, bottom), (right, top), (left, top)]),
        door,
        None,
    )


def _glazing(scene: CircuitScene, face: CourtFace, opening: CourtOpening) -> None:
    ring = list(opening.shape.exterior.coords)
    pane_depth = -0.18
    _panel(scene, face, opening.shape, pane_depth, "Glass")
    for a, b in pairwise(ring):
        scene.quad(
            "Building_CourtReveals",
            "Cream",
            _point(face, *a),
            _point(face, *b),
            _point(face, b[0], b[1], pane_depth),
            _point(face, a[0], a[1], pane_depth),
        )
        scene.beam(
            "Building_CourtWindowSurrounds",
            "White",
            _point(face, a[0], a[1], 0.025),
            _point(face, b[0], b[1], 0.025),
            0.085,
            0.085,
        )
        scene.beam(
            "Building_CourtFrames",
            "Trunk" if opening.door else "Black",
            _point(face, a[0], a[1], pane_depth + 0.035),
            _point(face, b[0], b[1], pane_depth + 0.035),
            0.055,
        )
    x0, z0, x1, z1 = opening.shape.bounds
    center = (x0 + x1) / 2
    scene.beam(
        "Building_CourtMullions",
        "Trunk" if opening.door else "Black",
        _point(face, center, z0, pane_depth + 0.035),
        _point(face, center, z1, pane_depth + 0.035),
        0.045,
    )
    if opening.arch_spring_m is not None:
        for t in (0.34, 0.68):
            z = z0 + (opening.arch_spring_m - z0) * t
            scene.beam(
                "Building_CourtMullions",
                "Black",
                _point(face, x0, z, pane_depth + 0.035),
                _point(face, x1, z, pane_depth + 0.035),
                0.04,
            )
    transom = (
        opening.arch_spring_m
        if opening.arch_spring_m is not None
        else z0 + (z1 - z0) * 0.72
    )
    scene.beam(
        "Building_CourtMullions",
        "Black",
        _point(face, x0, transom, pane_depth + 0.035),
        _point(face, x1, transom, pane_depth + 0.035),
        0.045,
    )
    if opening.door:
        for x in (x0 - 0.13, x1 + 0.13):
            scene.beam(
                "Building_CourtDoorPiers",
                "Cream",
                _point(face, x, z0),
                _point(face, x, z1 + 0.12),
                0.24,
                0.25,
            )
        scene.beam(
            "Building_CourtDoorLintels",
            "White",
            _point(face, x0 - 0.25, z1 + 0.12),
            _point(face, x1 + 0.25, z1 + 0.12),
            0.22,
            0.16,
        )
    else:
        scene.beam(
            "Building_CourtSills",
            "White",
            _point(face, x0 - 0.12, z0 - 0.09, 0.04),
            _point(face, x1 + 0.12, z0 - 0.09, 0.04),
            0.22,
            0.14,
        )


def _balustrade(scene: CircuitScene, face: CourtFace, height: float) -> None:
    pitch = face.length_m / 7
    x0, x1, depth = 2 * pitch - 0.4, 5 * pitch + 0.4, 0.65
    deck = [
        _point(face, x, height, d)
        for x, d in ((x0, 0.02), (x1, 0.02), (x1, depth), (x0, depth))
    ]
    if Polygon([p[:2] for p in deck]).intersects(scene.road_mask.buffer(0.3)):
        return
    scene.quad(
        "Building_CourtEntranceBalcony",
        "Cream",
        deck[0],
        deck[1],
        deck[2],
        deck[3],
        up=True,
    )
    scene.beam("Building_CourtEntranceBalcony", "Cream", deck[3], deck[2], 0.26, 0.24)
    for a, b in ((deck[3], deck[2]), (deck[0], deck[3]), (deck[2], deck[1])):
        scene.beam(
            "Building_CourtBalustrade",
            "Cream",
            add(a, (0, 0, 0.82)),
            add(b, (0, 0, 0.82)),
            0.16,
            0.14,
        )
        count = max(1, math.ceil(math.dist(a, b) / 0.22))
        for i in range(count + 1):
            t = i / count
            foot = (
                a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t,
                a[2] + (b[2] - a[2]) * t,
            )
            scene.beam(
                "Building_CourtBalustrade", "Cream", foot, add(foot, (0, 0, 0.8)), 0.075
            )


def _entry_steps(scene: CircuitScene, face: CourtFace, bottom: float) -> Polygon:
    pitch = face.length_m / 7
    x0, x1 = 2 * pitch + 0.1, 5 * pitch - 0.1
    for step in range(3):
        front, rear = step * 0.55, (step + 1) * 0.55
        top = -step * 0.15
        corners = [
            _point(face, x, top, d)
            for x, d in ((x0, front), (x1, front), (x1, rear), (x0, rear))
        ]
        if Polygon([p[:2] for p in corners]).intersects(scene.road_mask.buffer(0.3)):
            raise ValueError("Court entry steps enter the protected racing road")
        scene.quad(
            "Building_CourtEntrySteps",
            "Concrete",
            corners[0],
            corners[1],
            corners[2],
            corners[3],
            up=True,
        )
        for a, b in zip(corners, corners[1:] + corners[:1]):
            scene.quad(
                "Building_CourtEntrySteps",
                "Cream",
                a,
                b,
                (b[0], b[1], face.start[2] + bottom),
                (a[0], a[1], face.start[2] + bottom),
            )
    return Polygon(
        [
            _point(face, x, 0, d)[:2]
            for x, d in ((x0, 0), (x1, 0), (x1, 1.65), (x0, 1.65))
        ]
    )


def _front_openings(frame: CourtFace) -> list[CourtOpening]:
    openings: list[CourtOpening] = []
    pitch = frame.length_m / 7
    for bay in range(7):
        center = (bay + 0.5) * pitch
        door = bay in (2, 3, 4)
        openings.append(
            _opening(
                center,
                1.7 if door else 2.9,
                0.04 if door else 1.05,
                4.05 if door else 3.1,
                False,
                door,
            )
        )
        openings.append(
            _opening(center, min(2.35, pitch * 0.5), 12.85, 3.95, True, False)
        )
        for offset in (-0.24, 0.24):
            openings.append(
                _opening(center + pitch * offset, 0.85, 18.55, 1.5, False, False)
            )
        first_centers = (
            [center] if bay == 3 else [center - pitch * 0.24, center + pitch * 0.24]
        )
        for x in first_centers:
            openings.append(_opening(x, 1.05, 6.75, 2.7, False, False))
    return openings


def _road_openings(frame: CourtFace) -> list[CourtOpening]:
    openings: list[CourtOpening] = []
    for bay in range(7):
        center = (bay + 0.5) * frame.length_m / 7
        openings.append(
            _opening(
                center,
                2.3 if bay < 3 else 1.15,
                1.05 if bay < 3 else 1.5,
                3.1 if bay < 3 else 1.7,
                False,
                False,
            )
        )
    for bay in range(13):
        openings.append(
            _opening((bay + 0.5) * frame.length_m / 13, 1.05, 6.75, 2.7, False, False)
        )
    for fraction in (0.60, 0.76, 0.92):
        openings.append(
            _opening(frame.length_m * fraction, 1.65, 12.85, 3.95, True, False)
        )
    for bay in range(6):
        openings.append(
            _opening(
                frame.length_m * (0.035 + bay * 0.074), 0.85, 18.55, 1.5, False, False
            )
        )
    return openings


def _plain_openings(frame: CourtFace) -> list[CourtOpening]:
    openings: list[CourtOpening] = []
    bays = max(1, round(frame.length_m / 3.7))
    for bay in range(bays):
        center = (bay + 0.5) * frame.length_m / bays
        width = min(1.5, frame.length_m / bays * 0.5)
        for bottom, height in ((1.05, 3.1), (6.75, 2.7), (12.85, 3.95), (18.55, 1.5)):
            openings.append(_opening(center, width, bottom, height, False, False))
    return openings


def _canopies(scene: CircuitScene, frame: CourtFace) -> None:
    for fraction in (0.17, 0.34):
        center = frame.length_m * fraction
        corners = [
            _point(frame, x, z, d)
            for x, z, d in (
                (center - 1, 4.6, 0.03),
                (center + 1, 4.6, 0.03),
                (center + 1, 4.46, 0.85),
                (center - 1, 4.46, 0.85),
            )
        ]
        if Polygon([p[:2] for p in corners]).intersects(scene.road_mask.buffer(0.3)):
            continue
        scene.quad(
            "Building_CourtCanopies",
            "Roof",
            corners[0],
            corners[1],
            corners[2],
            corners[3],
            up=True,
        )
        for a, b in zip(corners, corners[1:] + corners[:1]):
            scene.beam("Building_CourtCanopies", "Steel", a, b, 0.045)


def _face(
    scene: CircuitScene,
    frame: CourtFace,
    source: CourtFrontageSource,
    edge: int,
    bottom: float,
) -> Polygon | None:
    full_front = frame.length_m > frame.source_length_m * 0.9
    entrance = edge == source.entrance_edge and full_front
    detailed = edge in source.track_front_edges and full_front
    openings = (
        _front_openings(frame)
        if entrance
        else _road_openings(frame)
        if edge == 10 and full_front
        else _plain_openings(frame)
    )
    wall = Polygon(
        [
            (0, bottom),
            (frame.length_m, bottom),
            (frame.length_m, source.height_m),
            (0, source.height_m),
        ]
    )
    masonry = wall.difference(unary_union([opening.shape for opening in openings]))
    for triangle in constrained_delaunay_triangles(masonry).geoms:
        points = [_point(frame, x, y) for x, y in list(triangle.exterior.coords)[:3]]
        uv = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
        if not triangle.exterior.is_ccw:
            points[1], points[2] = points[2], points[1]
            uv = uv[0], uv[2], uv[1]
        scene.triangle(
            "Building_CourtMasonry", "Cream", points[0], points[1], points[2], uv
        )
    for opening in openings:
        _glazing(scene, frame, opening)
    for z, width, depth in (
        (5.4, 0.28, 0.20),
        (11.5, 0.15, 0.12),
        (17.8, 0.32, 0.22),
        (22.22, 0.42, 0.28),
    ):
        scene.beam(
            "Building_CourtCornices",
            "White",
            _point(frame, 0, z, 0.045),
            _point(frame, frame.length_m, z, 0.045),
            width,
            depth,
        )
    step_footprint = None
    if entrance:
        for i in range(1, 7):
            x = i * frame.length_m / 7
            scene.beam(
                "Building_CourtPilasters",
                "Cream",
                _point(frame, x, 11.8, 0.055),
                _point(frame, x, 21.9, 0.055),
                0.35,
                0.12,
            )
            for z in (11.65, 22.08):
                scene.beam(
                    "Building_CourtPilasterCaps",
                    "White",
                    _point(frame, x - 0.24, z, 0.065),
                    _point(frame, x + 0.24, z, 0.065),
                    0.15,
                    0.14,
                )
        _balustrade(scene, frame, source.floor_bands_m[1])
        step_footprint = _entry_steps(scene, frame, bottom)
    if detailed:
        for z in (i * 0.48 for i in range(1, 45)):
            if abs(z - 5.4) < 0.2 or abs(z - 11.5) < 0.15:
                continue
            seam = Polygon(
                [
                    (0, z),
                    (frame.length_m, z),
                    (frame.length_m, z + 0.008),
                    (0, z + 0.008),
                ]
            )
            visible = seam.intersection(masonry)
            for part in [visible] if isinstance(visible, Polygon) else visible.geoms:
                if isinstance(part, Polygon) and not part.is_empty:
                    _panel(scene, frame, part, 0.004, "Concrete")
    if edge == 10 and full_front:
        _canopies(scene, frame)
    return step_footprint


def court_frontage(scene: CircuitScene, source_path: Path) -> list[Polygon]:
    source = TypeAdapter(CourtFrontageSource).validate_json(source_path.read_bytes())
    building = scene.footprint(source.osm_id)
    old_base = min(scene.ground(x, y) for x, y in building.ring)
    street = _street_grade(scene)
    ea, eb = (
        building.ring[source.entrance_edge],
        building.ring[(source.entrance_edge + 1) % len(building.ring)],
    )
    base = (
        _street_height(street, (ea[0] + eb[0]) / 2, (ea[1] + eb[1]) / 2)
        + source.entrance_rise_m
    )
    shape = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    parts = [shape] if isinstance(shape, Polygon) else list(shape.geoms)
    source_edges = list(zip(building.ring, building.ring[1:] + building.ring[:1]))
    steps: list[Polygon] = []
    for part in parts:
        if not isinstance(part, Polygon):
            continue
        ring = list(part.exterior.coords)[:-1]
        if not part.exterior.is_ccw:
            ring.reverse()
        for a, b in zip(ring, ring[1:] + ring[:1]):
            length = math.dist(a, b)
            if length < 0.3:
                scene.banner(
                    (a[0], a[1], old_base),
                    (b[0], b[1], old_base),
                    base + source.height_m - old_base,
                    "Cream",
                    "Building_CourtMasonry",
                )
                continue
            tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            edge = min(
                range(len(source_edges)),
                key=lambda i: min(
                    math.dist(a, source_edges[i][0]) + math.dist(b, source_edges[i][1]),
                    math.dist(b, source_edges[i][0]) + math.dist(a, source_edges[i][1]),
                ),
            )
            frame = CourtFace(
                (a[0], a[1], base),
                (tx, ty, 0),
                (ty, -tx, 0),
                length,
                math.dist(*source_edges[edge]),
            )
            step = _face(scene, frame, source, edge, old_base - base)
            if step is not None:
                steps.append(step)
        roof_polygon(scene, ring, base + source.height_m)
    scene.modeled_buildings.add(source.osm_id)
    scene.landmarks.append(
        {
            "name": building.name,
            "osm_id": source.osm_id,
            "height_m": source.height_m,
            "entrance_threshold_estimate_m": base,
            "old_renderer_low_footing_retained_m": old_base,
            "height_uncertainty_m": source.height_uncertainty_m,
            "source_note": source.source_note,
            "primary_photos": ", ".join(source.primary_photos),
        }
    )
    return steps


def _street_grade(scene: CircuitScene) -> StreetGrade:
    source = TypeAdapter(ForecourtSource).validate_json(
        (scene.sources / "castle-forecourt.json").read_bytes()
    )
    line = LineString([scene.geo(*point) for point in source.service_geo])
    return StreetGrade(
        line, scene.nearest(*line.coords[0])[0].z, scene.nearest(*line.coords[-1])[0].z
    )


def _street_height(street: StreetGrade, x: float, y: float) -> float:
    t = street.line.project(GeoPoint(x, y)) / street.line.length
    return street.start_z_m + (street.end_z_m - street.start_z_m) * t


def _north_openings(
    frame: CourtFace,
    street: StreetGrade,
    source: NorthFrontageSource,
    roof: float,
    ground_height: Callable[[float, float], float] | None,
) -> list[CourtOpening]:
    openings: list[CourtOpening] = []
    pitch = frame.length_m / source.upper_bays
    attic = 2.7
    upper_height = (roof - source.main_threshold_m - 6.25 - attic) / 3
    if upper_height < 2.4:
        raise ValueError(
            "North frontage threshold and roof cannot contain the observed upper bands"
        )
    for bay in range(source.upper_bays):
        center = (bay + 0.5) * pitch
        point = _point(frame, center, 0)
        ground = (
            ground_height(point[0], point[1])
            if ground_height
            else _street_height(street, point[0], point[1])
        )
        sill = ground + 0.36 - source.main_threshold_m
        openings.append(
            _opening(center, min(1.95, pitch * 0.52), sill, 3.9 - sill, True, False)
        )
        openings.append(_opening(center, 0.88, 4.35, 1.1, False, False))
        for floor in range(3):
            bottom = 6.25 + floor * upper_height + 0.65
            openings.append(
                _opening(
                    center,
                    min(1.8, pitch * 0.5),
                    bottom,
                    min(3.4, upper_height - 1.2),
                    False,
                    False,
                )
            )
        openings.append(
            _opening(
                center,
                min(1.55, pitch * 0.45),
                roof - source.main_threshold_m - 2.1,
                1.35,
                False,
                False,
            )
        )
    return openings


def _north_front(
    scene: CircuitScene,
    frame: CourtFace,
    street: StreetGrade,
    source: NorthFrontageSource,
    roof: float,
    ground_height: Callable[[float, float], float] | None,
) -> None:
    lower = []
    count = math.ceil(frame.length_m / 0.75)
    for i in range(count + 1):
        u = frame.length_m * i / count
        point = _point(frame, u, 0)
        ground = (
            ground_height(point[0], point[1])
            if ground_height
            else _street_height(street, point[0], point[1])
        )
        lower.append((u, ground - 0.03 - source.main_threshold_m))
    wall = Polygon(
        [
            *lower,
            (frame.length_m, roof - source.main_threshold_m),
            (0, roof - source.main_threshold_m),
        ]
    )
    openings = _north_openings(frame, street, source, roof, ground_height)
    masonry = wall.difference(unary_union([opening.shape for opening in openings]))
    for triangle in constrained_delaunay_triangles(masonry).geoms:
        points = [_point(frame, x, y) for x, y in list(triangle.exterior.coords)[:3]]
        uv = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
        if not triangle.exterior.is_ccw:
            points[1], points[2] = points[2], points[1]
            uv = uv[0], uv[2], uv[1]
        scene.triangle(
            "Building_NorthFrontMasonry", "Cream", points[0], points[1], points[2], uv
        )
    for opening in openings:
        _glazing(scene, frame, opening)
    upper_height = (roof - source.main_threshold_m - 6.25 - 2.7) / 3
    for z in (
        6.25,
        6.25 + upper_height,
        6.25 + upper_height * 2,
        roof - source.main_threshold_m - 2.7,
    ):
        scene.beam(
            "Building_NorthFrontCornices",
            "White",
            _point(frame, 0, z, 0.04),
            _point(frame, frame.length_m, z, 0.04),
            0.24,
            0.16,
        )
    scene.beam(
        "Building_NorthFrontCrown",
        "White",
        _point(frame, 0, roof - source.main_threshold_m - 0.18, 0.05),
        _point(frame, frame.length_m, roof - source.main_threshold_m - 0.18, 0.05),
        0.4,
        0.3,
    )
    for bay in range(source.upper_bays + 1):
        x = bay * frame.length_m / source.upper_bays
        scene.beam(
            "Building_NorthFrontPilasters",
            "Cream",
            _point(frame, x, 6.3, 0.06),
            _point(frame, x, roof - source.main_threshold_m - 0.35, 0.06),
            0.32,
            0.14,
        )
        for z in (6.35, roof - source.main_threshold_m - 0.33):
            scene.beam(
                "Building_NorthFrontCapitals",
                "White",
                _point(frame, x - 0.26, z, 0.07),
                _point(frame, x + 0.26, z, 0.07),
                0.20,
                0.17,
            )


def _retained_north_face(
    scene: CircuitScene,
    frame: CourtFace,
    old_base: float,
    roof: float,
    bottom_a: float,
    bottom_b: float,
    ground_height: Callable[[float, float], float] | None,
) -> None:
    top = roof - frame.start[2]
    lower = []
    count = math.ceil(frame.length_m / 0.75)
    for i in range(count + 1):
        u = frame.length_m * i / count
        point = _point(frame, u, 0)
        bottom = (
            ground_height(point[0], point[1]) - 0.03
            if ground_height
            else bottom_a + (bottom_b - bottom_a) * i / count
        )
        lower.append((u, bottom - frame.start[2]))
    wall = Polygon([*lower, (frame.length_m, top), (0, top)])
    bays = max(1, round(frame.length_m / 3.6))
    floor_height = (roof - old_base) / 3
    openings: list[CourtOpening] = []
    for floor in range(3):
        bottom = old_base - frame.start[2] + floor_height * (floor + 0.18)
        for bay in range(bays):
            center = (bay + 0.5) * frame.length_m / bays
            width = min(2, frame.length_m / bays * 0.53)
            sill = bottom
            if ground_height:
                probes = [center - width / 2, center + width / 2]
                probes.extend(
                    u for u, _ in lower if center - width / 2 < u < center + width / 2
                )
                grade = (
                    max(ground_height(*_point(frame, u, 0)[:2]) for u in probes)
                    - frame.start[2]
                )
                sill = max(sill, grade + 0.45)
            height = bottom + floor_height * 0.6 - sill
            if height > 0.45:
                openings.append(_opening(center, width, sill, height, False, False))
    masonry = wall.difference(unary_union([opening.shape for opening in openings]))
    for triangle in constrained_delaunay_triangles(masonry).geoms:
        points = [_point(frame, x, y) for x, y in list(triangle.exterior.coords)[:3]]
        uv = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
        if not triangle.exterior.is_ccw:
            points[1], points[2] = points[2], points[1]
            uv = uv[0], uv[2], uv[1]
        scene.triangle(
            "Building_NorthRetainedMasonry",
            "Cream",
            points[0],
            points[1],
            points[2],
            uv,
        )
    for opening in openings:
        _glazing(scene, frame, opening)
    for floor in range(3):
        z = old_base - frame.start[2] + floor_height * (floor + 1)
        scene.beam(
            "Building_NorthRetainedCornice",
            "White",
            _point(frame, 0, z),
            _point(frame, frame.length_m, z),
            0.32,
            0.20,
        )


def north_frontage(
    scene: CircuitScene,
    source_path: Path,
    ground_height: Callable[[float, float], float] | None = None,
) -> None:
    source = TypeAdapter(NorthFrontageSource).validate_json(source_path.read_bytes())
    building = scene.footprint(source.osm_id)
    old_base = min(scene.ground(x, y) for x, y in building.ring)
    roof = source.main_threshold_m + source.body_height_m
    street = _street_grade(scene)
    source_a, source_b = (
        building.ring[source.street_edge],
        building.ring[(source.street_edge + 1) % len(building.ring)],
    )
    proven_face = LineString([source_a, source_b])
    shape = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    parts = [shape] if isinstance(shape, Polygon) else list(shape.geoms)
    for part in parts:
        if not isinstance(part, Polygon):
            continue
        ring = list(part.exterior.coords)[:-1]
        if not part.exterior.is_ccw:
            ring.reverse()
        for a, b in zip(ring, ring[1:] + ring[:1]):
            length = math.dist(a, b)
            if length < 0.3:
                continue
            tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            frame = CourtFace(
                (a[0], a[1], source.main_threshold_m),
                (tx, ty, 0),
                (ty, -tx, 0),
                length,
                length,
            )
            if (
                proven_face.distance(GeoPoint(a)) < 0.001
                and proven_face.distance(GeoPoint(b)) < 0.001
            ):
                _north_front(scene, frame, street, source, roof, ground_height)
            else:
                bottom_a = (
                    _street_height(street, *a) - 0.03
                    if proven_face.distance(GeoPoint(a)) < 0.001
                    else old_base
                )
                bottom_b = (
                    _street_height(street, *b) - 0.03
                    if proven_face.distance(GeoPoint(b)) < 0.001
                    else old_base
                )
                _retained_north_face(
                    scene, frame, old_base, roof, bottom_a, bottom_b, ground_height
                )
        roof_polygon(scene, ring, roof)
    scene.modeled_buildings.add(source.osm_id)
    scene.landmarks.append(
        {
            "name": building.name,
            "osm_id": source.osm_id,
            "main_front_threshold_estimate_m": source.main_threshold_m,
            "roof_estimate_m": roof,
            "body_height_estimate_m": source.body_height_m,
            "height_uncertainty_m": source.height_uncertainty_m,
            "uncertainty_m": source.uncertainty_m,
            "source_note": source.source_note,
            "primary_photos": ", ".join(source.primary_photos),
        }
    )


def close_native_facade_fragments(scene: CircuitScene, osm_id: int) -> None:
    building = scene.footprint(osm_id)
    base = min(scene.ground(x, y) for x, y in building.ring)
    available = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    parts = [available] if isinstance(available, Polygon) else list(available.geoms)
    for part in parts:
        if not isinstance(part, Polygon):
            continue
        ring = list(part.exterior.coords)
        for a, b in pairwise(ring):
            if 0 < math.dist(a, b) < 0.3:
                scene.banner(
                    (a[0], a[1], base),
                    (b[0], b[1], base),
                    building.height,
                    "Cream",
                    "Building_ClearanceClosure",
                )


def foundation_profile(
    scene: CircuitScene, osm_id: int, public_surface: Callable[[float, float], float]
) -> Callable[[float, float], float]:
    available = Polygon(scene.footprint(osm_id).ring).difference(
        scene.road_mask.buffer(1.2)
    )
    boundary = available.buffer(0.12, join_style="mitre").boundary

    def height(x: float, y: float) -> float:
        point = nearest_points(boundary, GeoPoint(x, y))[0]
        return public_surface(point.x, point.y)

    return height


def base_course(
    scene: CircuitScene,
    osm_id: int,
    ground_height: Callable[[float, float], float],
    entry_steps: Sequence[Polygon] = (),
) -> Polygon:
    building = scene.footprint(osm_id)
    available = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    outer = available.buffer(0.12, join_style="mitre")
    if not isinstance(outer, Polygon):
        raise TypeError("The bounded base course requires one connected body")
    if outer.intersects(scene.road_mask.buffer(0.3)):
        raise ValueError("Base course enters the protected racing road")
    shape = outer.difference(available).difference(unary_union(entry_steps))
    remaining = shape
    strips: list[Polygon] = []
    available_parts = (
        [available] if isinstance(available, Polygon) else list(available.geoms)
    )
    for part in available_parts:
        if not isinstance(part, Polygon):
            continue
        for exterior, ring in [
            (True, part.exterior),
            *((False, ring) for ring in part.interiors),
        ]:
            coordinates = list(ring.coords)
            for a, b in pairwise(coordinates):
                length = math.dist(a, b)
                if length < 1e-12:
                    continue
                nx, ny = (b[1] - a[1]) / length, (a[0] - b[0]) / length
                if exterior != ring.is_ccw:
                    nx, ny = -nx, -ny
                count = max(1, math.ceil(length / 0.75))
                for i in range(count):
                    u, v = i / count, (i + 1) / count
                    pa = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
                    pb = (a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v)
                    rectangle = Polygon(
                        [
                            pa,
                            pb,
                            (pb[0] + nx * 0.12, pb[1] + ny * 0.12),
                            (pa[0] + nx * 0.12, pa[1] + ny * 0.12),
                        ]
                    )
                    piece = remaining.intersection(rectangle)
                    pieces = (
                        [piece]
                        if isinstance(piece, Polygon)
                        else list(piece.geoms)
                        if hasattr(piece, "geoms")
                        else []
                    )
                    strips.extend(
                        item
                        for item in pieces
                        if isinstance(item, Polygon) and item.area > 0
                    )
                    remaining = remaining.difference(rectangle)
    corners = (
        [remaining]
        if isinstance(remaining, Polygon)
        else list(remaining.geoms)
        if hasattr(remaining, "geoms")
        else []
    )
    strips.extend(
        item for item in corners if isinstance(item, Polygon) and item.area > 0
    )
    for part in strips:
        boundary_edges: dict[tuple[Point, Point], tuple[Point, Point] | None] = {}
        xy = list(part.exterior.coords)[:-1]
        if not part.interiors and part.equals(part.convex_hull):
            triangles = [
                Polygon([xy[0], xy[i], xy[i + 1]]) for i in range(1, len(xy) - 1)
            ]
        else:
            triangles = list(constrained_delaunay_triangles(part).geoms)
        for triangle in triangles:
            if triangle.area <= 0:
                continue
            points = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                points.reverse()
            top = [(x, y, ground_height(x, y) + 0.30) for x, y in points]
            bottom = [(x, y, ground_height(x, y) - 0.03) for x, y in points]
            normal = cross(sub(top[1], top[0]), sub(top[2], top[0]))
            if sum(value * value for value in normal) < 1e-12:
                continue
            scene.triangle("Building_StoneBaseTop", "Cream", top[0], top[1], top[2])
            scene.triangle(
                "Building_StoneBaseBottom", "Cream", bottom[2], bottom[1], bottom[0]
            )
            for a, b in zip(top, top[1:] + top[:1]):
                key = (min(a, b), max(a, b))
                boundary_edges[key] = None if key in boundary_edges else (a, b)
        for edge in boundary_edges.values():
            if edge is None:
                continue
            a, b = edge
            scene.quad(
                "Building_StoneBaseSides",
                "Cream",
                a,
                b,
                (b[0], b[1], b[2] - 0.33),
                (a[0], a[1], a[2] - 0.33),
            )
    scene.landmarks.append(
        {
            "name": "Grade-following stone base course",
            "osm_id": osm_id,
            "projection_estimate_m": 0.12,
            "height_estimate_m": 0.30,
            "footprint_area_m2": outer.area,
            "closed_strip_count": len(strips),
            "strip_missing_area_m2": shape.difference(unary_union(strips)).area,
            "strip_excess_area_m2": unary_union(strips).difference(shape).area,
            "source_note": "Low dressed-stone frontage base, reconstructed as an architectural estimate. It follows the bounded actual paving field, with a3cm embed. Entry steps remain distinct. This emitted masonry projection, rather than an arbitrary roof buffer, defines the local Ground cut. Rear ground remains source-held; no surveyed plinth dimensions are claimed.",
        }
    )
    return outer
