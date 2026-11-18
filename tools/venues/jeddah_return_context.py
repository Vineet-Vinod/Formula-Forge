"""The source-registered domed Corniche Mosque beside the T22 shoreline."""

from __future__ import annotations

import math
from pathlib import Path

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.affinity import translate
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from venues.jeddah_pit_exit_geometry import solid
from venues.jeddah_return_context_dataclasses import CornicheMosqueSource, MosqueOpening
from venues.jeddah_return_geometry import barrel, dome, finial, profile_solid, wall

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "Attribution/Sources/jeddah/return-context.json"
)


def source_record() -> CornicheMosqueSource:
    source = TypeAdapter(CornicheMosqueSource).validate_json(SOURCE.read_bytes())
    if source.osm_node_id != 608700976 or source.published_floor_m2 != 195:
        raise ValueError(
            "Corniche Mosque requires its registered source and published floor area"
        )
    return source


def occupied_plan(source: CornicheMosqueSource) -> Polygon:
    half = source.hall_side_m / 2
    minaret = source.minaret_side_m
    plan = unary_union(
        [
            box(-half, -half, half, half),
            box(-half - source.loggia_depth_m, -half, -half, half),
            box(-half, half, half, half + source.porch_depth_m),
            box(-1.1 - minaret, -half - minaret, -1.1, -half),
            box(half, -1, half + 1.4, 1),
            box(-1.1, -half - 1.2, half, -half),
        ]
    )
    if (
        not isinstance(plan, Polygon)
        or not 0.9 < plan.area / source.published_floor_m2 < 1.1
    ):
        raise ValueError(
            "Corniche Mosque envelope departed from its published floor-area constraint"
        )
    return plan


def build(scene: CircuitScene) -> None:
    source = source_record()
    center = scene.geo(source.latitude, source.longitude)
    local = occupied_plan(source)
    footprint = translate(local, xoff=center[0], yoff=center[1])
    road, distance = scene.nearest(*center)
    if not 4100 < road.station < 4300 or not 60 < distance < 85:
        raise ValueError(
            "The Corniche Mosque lost its source-registered T22 relationship"
        )
    if hasattr(scene, "road_mask") and footprint.intersects(
        scene.road_mask.buffer(1.2)
    ):
        raise ValueError(
            "The Corniche Mosque cannot intrude into the retained racing corridor"
        )
    floor = source.floor_relative_m
    bottom = min(scene.ground(x, y) for x, y in footprint.exterior.coords) - 0.2

    def point(x: float, y: float, z: float = 0) -> Point:
        return center[0] + x, center[1] + y, floor + z

    solid(scene, footprint, bottom, floor, "Cream", "Building_CornicheFoundation")
    scene.terrain_cutouts.append(footprint)
    half = source.hall_side_m / 2
    ring = ((-half, -half), (half, -half), (half, half), (-half, half))
    for index, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1], strict=True)):
        openings = tuple(MosqueOpening(c, 0.7, 2.7, 3.45, 4.15) for c in (5,))
        if index == 3:
            openings = tuple(MosqueOpening(c, 1, 1.4, 2.6, 3.45) for c in (2.5, 7.5))
        if index == 1:
            profile = box(0, 0, source.hall_side_m, source.hall_wall_m).difference(
                ShapePoint(5, 3.1).buffer(0.32, quad_segs=16)
            )
            if not isinstance(profile, Polygon):
                raise TypeError("The east oculus must remain an opening in one wall")
            profile_solid(
                scene,
                point(*a),
                point(*b),
                profile,
                0.45,
                "Building_CornicheHallOculus",
            )
        else:
            wall(
                scene,
                point(*a),
                point(*b),
                source.hall_wall_m,
                openings,
                "Building_CornicheHallWalls",
            )
    for corner_x, corner_y in ring:
        base_ring = [
            point(corner_x + dx, corner_y + dy, source.hall_wall_m)
            for dx, dy in ((-0.3, -0.3), (0.3, -0.3), (0.3, 0.3), (-0.3, 0.3))
        ]
        peak = point(corner_x, corner_y, source.hall_wall_m + 0.85)
        for first, last in zip(base_ring, base_ring[1:] + base_ring[:1], strict=True):
            scene.triangle("Building_CornicheRoofCornerCaps", "Cream", first, last, peak)
    hall = translate(box(-half, -half, half, half), xoff=center[0], yoff=center[1])
    solid(
        scene,
        hall,
        floor + source.hall_wall_m - 0.24,
        floor + source.hall_wall_m,
        "Cream",
        "Building_CornicheHallRoof",
    )
    drum = translate(
        Polygon(
            [
                (
                    source.dome_radius_m * math.cos(i * math.tau / 48),
                    source.dome_radius_m * math.sin(i * math.tau / 48),
                )
                for i in range(48)
            ]
        ),
        xoff=center[0],
        yoff=center[1],
    )
    solid(
        scene,
        drum,
        floor + source.hall_wall_m,
        floor + source.hall_wall_m + 0.8,
        "Cream",
        "Building_CornicheDomeDrum",
    )
    dome(
        scene,
        point(0, 0, source.hall_wall_m + 0.8),
        source.dome_radius_m,
        source.dome_height_m,
        "Building_CornicheMainDome",
    )
    finial(scene, point(0, 0, source.hall_wall_m + 0.8 + source.dome_height_m))

    west = -half - source.loggia_depth_m
    arcade = tuple(MosqueOpening(c, 3.45, 0, 2.25, 3.65) for c in (2.5, 7.5))
    wall(
        scene,
        point(west, half),
        point(west, -half),
        4.05,
        arcade,
        "Building_CornicheWestLoggia",
    )
    for a, b in (((-half, half), (west, half)), ((west, -half), (-half, -half))):
        wall(
            scene,
            point(*a),
            point(*b),
            4.05,
            (MosqueOpening(source.loggia_depth_m / 2, 2.6, 0, 2.2, 3.5),),
            "Building_CornicheLoggiaReturns",
        )
    gallery = translate(box(west, -half, -half, half), xoff=center[0], yoff=center[1])
    solid(
        scene,
        gallery,
        floor + 3.9,
        floor + 4.15,
        "Cream",
        "Building_CornicheLoggiaRoof",
    )
    for y in (-2.5, 2.5):
        dome(
            scene,
            point((west - half) / 2, y, 4.15),
            2.12,
            1.5,
            "Building_CornicheShallowDomes",
        )

    north = half + source.porch_depth_m
    porch_openings = tuple(MosqueOpening(c, 2.35, 0, 2.35, 3.65) for c in (1.7, 5, 8.3))
    wall(
        scene,
        point(half, north),
        point(-half, north),
        4.2,
        porch_openings,
        "Building_CornicheNorthPorch",
    )
    for a, b in (((half, half), (half, north)), ((-half, north), (-half, half))):
        wall(
            scene,
            point(*a),
            point(*b),
            4.2,
            (MosqueOpening(source.porch_depth_m / 2, 2.2, 0, 2.3, 3.6),),
            "Building_CornichePorchReturns",
        )
    barrel(
        scene,
        point(0, (half + north) / 2, 3.55),
        source.hall_side_m,
        source.porch_depth_m,
    )

    x = -1.1 - source.minaret_side_m / 2
    y = -half - source.minaret_side_m / 2
    shaft = source.minaret_shaft_m
    for radius, low, high, kind in (
        (source.minaret_side_m / 2, 0, shaft, "Building_CornicheMinaretShaft"),
        (1.55, shaft - 0.5, shaft - 0.25, "Building_CornicheMinaretCorbels"),
        (1.7, shaft - 0.25, shaft, "Building_CornicheMinaretCorbels"),
        (1.85, shaft, shaft + 0.65, "Building_CornicheMinaretBalcony"),
    ):
        ring = translate(
            Polygon(
                [
                    (
                        x + radius * math.cos(i * math.tau / 24),
                        y + radius * math.sin(i * math.tau / 24),
                    )
                    for i in range(24)
                ]
            ),
            xoff=center[0],
            yoff=center[1],
        )
        solid(scene, ring, floor + low, floor + high, "Cream", kind)
    lantern = translate(
        Polygon(
            [
                (x + math.cos(i * math.tau / 8), y + math.sin(i * math.tau / 8))
                for i in range(8)
            ]
        ),
        xoff=center[0],
        yoff=center[1],
    )
    lantern_ring = list(lantern.exterior.coords)[:-1]
    for a, b in zip(lantern_ring, lantern_ring[1:] + lantern_ring[:1], strict=True):
        length = math.dist(a, b)
        wall(
            scene,
            (a[0], a[1], floor + shaft),
            (b[0], b[1], floor + shaft),
            2.1,
            (MosqueOpening(length / 2, length * 0.6, 0.25, 1.2, 1.75),),
            "Building_CornicheLantern",
            0.2,
        )
    for index in range(12):
        theta = index * math.tau / 12
        corners = [
            point(
                x + radius * math.cos(theta + angle),
                y + radius * math.sin(theta + angle),
                shaft + 2.1,
            )
            for radius, angle in (
                (1.14, -0.17),
                (1.14, 0.17),
                (0.93, 0.17),
                (0.93, -0.17),
            )
        ]
        peak = point(
            x + 1.03 * math.cos(theta), y + 1.03 * math.sin(theta), shaft + 2.5
        )
        for first, last in zip(corners, corners[1:] + corners[:1], strict=True):
            scene.triangle("Building_CornicheLanternMerlons", "Cream", first, last, peak)
        scene.quad(
            "Building_CornicheLanternMerlons",
            "Cream",
            corners[3],
            corners[2],
            corners[1],
            corners[0],
        )
    dome(
        scene,
        point(x, y, shaft + 2.1),
        1.05,
        source.minaret_crown_m - 2.1,
        "Building_CornicheMinaretCrown",
    )
    finial(scene, point(x, y, shaft + source.minaret_crown_m))
    ramp = Polygon([(0, 3.2), (6.1, 0), (6.1, 0.3), (0, 3.5)])
    profile_solid(
        scene,
        point(-1.1, -half - 1.2),
        point(half, -half - 1.2),
        ramp,
        1.2,
        "Building_CornicheMinaretStairEnvelope",
    )
    mihrab = translate(box(half, -1, half + 1.4, 1), xoff=center[0], yoff=center[1])
    mihrab_front = box(0, 0, 2, 4.25).difference(
        ShapePoint(1, 3.1).buffer(0.32, quad_segs=16)
    )
    if not isinstance(mihrab_front, Polygon):
        raise TypeError("The projected mihrab must retain its circular oculus")
    profile_solid(
        scene,
        point(half + 1.4, -1),
        point(half + 1.4, 1),
        mihrab_front,
        0.25,
        "Building_CornicheMihrabOculus",
    )
    wall(
        scene,
        point(half, -1),
        point(half + 1.4, -1),
        4.25,
        (),
        "Building_CornicheMihrabReturns",
        0.25,
    )
    wall(
        scene,
        point(half + 1.4, 1),
        point(half, 1),
        4.25,
        (),
        "Building_CornicheMihrabReturns",
        0.25,
    )
    solid(
        scene, mihrab, floor + 4.2, floor + 4.4, "Cream", "Building_CornicheMihrabRoof"
    )
    scene.landmarks.append(
        {
            "name": "Corniche Mosque, source-registered T22 shoreline",
            "osm_node_id": source.osm_node_id,
            "native_nearest_station_m": road.station,
            "distance_from_road_m": distance,
            "occupied_footprint_m2": footprint.area,
            "published_floor_m2": source.published_floor_m2,
            "estimated_floor_m": floor,
            "estimated_main_dome_top_m": floor
            + source.hall_wall_m
            + 0.8
            + source.dome_height_m,
            "estimated_minaret_top_m": floor + shaft + source.minaret_crown_m + 1.04,
            "source": source.source_note,
        }
    )
