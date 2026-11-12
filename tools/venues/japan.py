"""Suzuka's mapped spectator terraces, pit frontage, wooded banks and Circuit Wheel."""

from __future__ import annotations

import math

from circuit_dataclasses import Point, RunoffRange
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.east_architecture import facade, footprint_stand, frame
from venues.japan_architecture import earthbank_seating
from venues.west_architecture import (
    apron_band,
    mapped_building,
    suzuka_service_hut,
    trees,
)


def build_venue(scene: CircuitScene) -> None:
    for start, end, side in (
        (395, 520, 1),
        (520, 650, 1),
        (560, 685, -1),
        (800, 885, -1),
        (925, 1010, 1),
        (1060, 1165, -1),
        (1250, 1350, 1),
        (1400, 1595, -1),
        (1970, 2080, 1),
        (2140, 2235, 1),
        (2220, 2240, -1),
        (2585, 2705, -1),
        (3475, 3600, -1),
        (3620, 3770, -1),
        (3720, 3810, 1),
        (4620, 4780, -1),
        (4820, 4920, 1),
        (5060, 5140, 1),
        (5145, 5220, -1),
        (5240, 5340, 1),
    ):
        scene.kerb(start, end, side)
    runoffs = TypeAdapter(list[RunoffRange]).validate_json(
        (scene.sources / "runoff-corrections.json").read_bytes()
    )
    for zone in runoffs:
        scene.runoff(zone.start_m, zone.end_m, zone.side, zone.width_m, zone.material)
    degner_apron_taper(scene)
    for start, end, side, inner, outer, material in (
        (2080, 2240, -1, 1.2, 4.5, "RunoffGreen"),
        (3380, 3810, 1, 1.2, 18, "RunoffGreen"),
        (3500, 3630, 1, 18, 23.8, "RunoffPurple"),
        (5000, 5160, -1, 1.2, 7, "RunoffGreen"),
        (5100, 5260, 1, 1.2, 10, "RunoffGreen"),
    ):
        apron_band(scene, start, end, side, inner, outer, material)
    for osm_id, rows, roof in (
        (184120096, 15, ""),
        (184143131, 16, ""),
        (184143132, 24, ""),
        (184143133, 21, ""),
        (469368057, 16, ""),
        (469395390, 14, ""),
        (467982372, 15, ""),
        (184102361, 13, ""),
        (183999779, 12, ""),
        (183393101, 16, ""),
        (183393102, 16, ""),
        (183393103, 16, ""),
        (183393132, 12, ""),
        (183394069, 16, ""),
        (184107052, 14, ""),
        (183394522, 23, "cantilever"),
    ):
        footprint_stand(scene, osm_id, rows, roof)
    earthbank_seating(scene, 184102012, 12)
    pit_paving(scene)
    pit_front(scene)
    facade(scene, 183394524, 14, "modern", "White")
    facade(scene, 184415318, 15, "modern", "White")
    suzuka_service_hut(scene, scene.footprint(184120102), 3.0, 3.4)
    suzuka_service_hut(scene, scene.footprint(184120098), 2.8, 3.2)
    for osm_id in (184423963, 184429429, 184430907, 184430909, 184430911):
        mapped_building(scene, osm_id, 7.5, facade="Cream", floors=2, roof="flat")
    for start, end, side, setback, rows, height in (
        (600, 780, 1, 20, 2, 9),
        (780, 1200, 1, 30, 2, 11),
        (1080, 1400, 1, 65, 3, 13),
        (1440, 1850, 1, 25, 3, 14),
        (1650, 1940, -1, 30, 3, 13),
        (2240, 2530, -1, 20, 3, 13),
        (2370, 2520, 1, 34, 2, 12),
        (2750, 3390, -1, 23, 3, 14),
        (2820, 3370, 1, 28, 3, 12),
        (3830, 4520, -1, 30, 4, 14),
        (3850, 4470, 1, 33, 3, 14),
        (4740, 5000, 1, 35, 3, 12),
        (5300, 5540, -1, 105, 2, 10),
    ):
        trees(
            scene,
            start,
            end,
            side,
            setback=setback,
            spacing=7.5,
            rows=rows + 2,
            height=height,
        )
    for building in scene.buildings:
        if building.osm_id in scene.modeled_buildings or building.use == "grandstand":
            continue
        center, _, _, _, _ = frame(building)
        _, distance = scene.nearest(center[0], center[1])
        if distance < 650 and building.height < 30:
            mapped_building(
                scene,
                building.osm_id,
                building.height,
                facade="Cream",
                floors=max(1, round(building.height / 3.4)),
                roof="pitched" if building.use in ("house", "residential") else "flat",
            )
    for apex, side in ((424, -1), (2028, -1), (2652, 1), (3547, 1), (5111, -1)):
        scene.braking_boards(apex, side)
    for side in (-1, 1):
        scene.branding(5480, 180, side, "PanelGreen")
        scene.branding(4628, 4676, side, "PanelAmericanExpress")
    bridge(scene)
    wheel(scene)


def pit_paving(scene: CircuitScene) -> None:
    span = (180 - 5480) % scene.length
    for i in range(math.ceil(span / 2)):
        a, b = scene.at(5480 + i * 2), scene.at(5482 + i * 2)
        points = (
            a.point(a.half_width + 0.96, -0.005),
            b.point(b.half_width + 0.96, -0.005),
            b.point(b.half_width + 20, -0.005),
            a.point(a.half_width + 20, -0.005),
        )
        polygon = Polygon([(p[0], p[1]) for p in points])
        if polygon.is_valid:
            scene.terrain_cutouts.append(polygon)
            scene.quad("Tile_Pit", "Runoff", *points, u=2, v=4, up=True)
        if i % 4 == 0:
            scene.beam(
                "Tile_Pit",
                "Yellow",
                a.point(a.half_width + 4, 0.016),
                b.point(b.half_width + 4, 0.016),
                0.10,
                0.008,
            )
            scene.beam(
                "Tile_Pit",
                "White",
                a.point(a.half_width + 16, 0.016),
                a.point(a.half_width + 19, 0.016),
                0.10,
                0.008,
            )


def pit_front(scene: CircuitScene) -> None:
    pit = scene.footprint(184422099)
    center, axis, side, length, width = frame(pit)
    road, _ = scene.nearest(center[0], center[1])
    if (road.x - center[0]) * side[0] + (road.y - center[1]) * side[1] < 0:
        side = mul(side, -1)
    base = road.z
    front = add((center[0], center[1], base), mul(side, width / 2))
    scene.terrain_cutouts.append(Polygon(pit.ring).buffer(0.2))
    count = max(1, round(length / 8))
    for i in range(count):
        a = add(front, mul(axis, -length / 2 + length * i / count))
        b = add(front, mul(axis, -length / 2 + length * (i + 1) / count))
        a = (a[0], a[1], scene.nearest(a[0], a[1])[0].z)
        b = (b[0], b[1], scene.nearest(b[0], b[1])[0].z)
        for level in (0.0, 4.8, 8.7):
            scene.beam(
                "Building_SuzukaPits",
                "Concrete",
                add(a, add(mul(side, -width / 2), (0, 0, level))),
                add(b, add(mul(side, -width / 2), (0, 0, level))),
                width,
                0.35,
            )
        scene.banner(
            add(a, (0, 0, 0.3)),
            add(b, (0, 0, 0.3)),
            3.5,
            "Black",
            "Building_SuzukaPits",
        )
        scene.banner(
            add(a, (0, 0, 5)), add(b, (0, 0, 5)), 2.9, "Glass", "Building_SuzukaPits"
        )
        scene.beam("Building_SuzukaPits", "White", a, add(a, (0, 0, 9.2)), 0.45)
        scene.beam(
            "Building_SuzukaPits",
            "White",
            add(a, (0, 0, 4.4)),
            add(b, (0, 0, 4.4)),
            0.65,
            0.45,
        )
        rear_a, rear_b = add(a, mul(side, -width)), add(b, mul(side, -width))
        scene.quad(
            "Building_SuzukaPits",
            "Roof",
            add(a, add(mul(side, 1.6), (0, 0, 10))),
            add(b, add(mul(side, 1.6), (0, 0, 10))),
            add(rear_b, (0, 0, 11.5)),
            add(rear_a, (0, 0, 11.5)),
        )
        scene.quad(
            "Building_SuzukaPits",
            "Concrete",
            add(rear_a, (0, 0, 11.3)),
            add(rear_b, (0, 0, 11.3)),
            add(b, add(mul(side, 1.6), (0, 0, 9.8))),
            add(a, add(mul(side, 1.6), (0, 0, 9.8))),
        )
        scene.beam(
            "Building_SuzukaPits",
            "Steel",
            add(a, (0, 0, 9.8)),
            add(rear_a, (0, 0, 11.3)),
            0.16,
        )
    scene.modeled_buildings.add(pit.osm_id)
    scene.landmarks.append(
        {
            "name": "Suzuka pit building",
            "osm_id": pit.osm_id,
            "height_m": 11.5,
            "model": "Mapped footprint, separated garage level, glazed hospitality, concrete fascia and shallow mono-pitch roof; vertical dimensions estimated from reference.",
        }
    )


def degner_apron_taper(scene: CircuitScene) -> None:
    for station in range(2215, 2255):
        a, b = scene.at(station), scene.at(station + 1)
        points = [a.point(-a.half_width - .14), b.point(-b.half_width - .14),
                  b.point(-b.half_width - b.right_shoulder - .95),
                  a.point(-a.half_width - a.right_shoulder - .95)]
        polygon = Polygon([p[:2] for p in points])
        scene.extra_corridors.append(polygon)
        scene.polygon_surface(polygon.difference(scene.surface_mask(a)), 'Gravel', .001, a, paved=True)
    scene.landmarks.append({'name': 'Degner left apron taper before underpass',
                            'start_m': 2215, 'end_m': 2255,
                            'dimensions_status': 'Visual apron follows exported native LEFT shoulder plus 0.95 m. Reference at 869 s shows gravel before the close underpass wall at 870.5 s; 872 s shows narrow grass. SourceRunoff 22 m ends at 2215 m. Cubic taper comes from shoulder-corrections.json; endpoints estimated within 15 m, with no road profile changes.'})


def bridge_left_abutment(scene: CircuitScene) -> None:
    end, behind = scene.at(4637), scene.at(4628)
    lower = scene.at(2272)
    def base(point: Point) -> Point:
        along = (point[0] - lower.x) * lower.tx + (point[1] - lower.y) * lower.ty
        floor = scene.at(2272 + along).z - .15
        return point[0], point[1], min(floor, scene.raw_ground(point[0], point[1]) - .1)
    left, right = end.point(-end.half_width - 1.35, -.6), end.point(end.half_width + 1.35, -.6)
    pairs = [(left, right)]
    for side, front in [(-1, left), (1, right)]:
        pairs.append((front, behind.point(side * (behind.half_width + 1.35), -.6)))
    for a, b in pairs:
        aa, bb = base(a), base(b)
        scene.quad('Building_BridgeAbutment', 'Concrete', aa, bb, b, a)
        scene.quad('Building_BridgeAbutment', 'Concrete', bb, aa, a, b)
    scene.landmarks.append({'name': 'Degner crossover left concrete abutment and wing walls',
                            'upper_station_m': 4637, 'wing_end_station_m': 4628,
                            'dimensions_status': 'Reference at 869 and 870.5 s shows the left concrete bridge support. End wall follows the actual upper deck end; short 9 m wings are reconstructed. Top follows the unchanged deck underside and bottom reaches below unchanged lower-road grade or retained GSI ground. The upper bridge and both road profiles are preserved.'})


def bridge(scene: CircuitScene) -> None:
    bridge_left_abutment(scene)
    a, b = scene.at(4637), scene.at(4667)
    for side in (-1, 1):
        lane_a, lane_b = side * (a.half_width + 0.6), side * (b.half_width + 0.6)
        scene.beam(
            "Building_Bridge",
            "Concrete",
            a.point(lane_a, -0.6),
            b.point(lane_b, -0.6),
            0.8,
            1.2,
        )
    scene.quad(
        "Building_Bridge",
        "Concrete",
        a.point(-a.half_width - 1.35, -0.6),
        a.point(a.half_width + 1.35, -0.6),
        b.point(b.half_width + 1.35, -0.6),
        b.point(-b.half_width - 1.35, -0.6),
        2,
        2,
        up=False,
    )
    scene.landmarks.append(
        {
            "name": "Back straight over Degner underpass",
            "start_m": 4637,
            "end_m": 4667,
            "road_deck_separation_m": 6.2,
            "minimum_structural_clearance_m": 5.0,
        }
    )


def wheel(scene: CircuitScene) -> None:
    x, y = scene.geo(34.845979, 136.538821)
    ground = scene.ground(x, y)
    base = (x, y, ground)
    hub = add(base, (0, 0, 27))
    axis = (math.cos(0.63), math.sin(0.63), 0.0)
    across = (-axis[1], axis[0], 0.0)
    radius = 24.0
    for sign in (-1, 1):
        center = add(hub, mul(across, sign * 0.9))
        for i in range(144):

            def point(
                angle: float, center: tuple[float, float, float] = center
            ) -> tuple[float, float, float]:
                return add(
                    center,
                    add(
                        mul(axis, math.cos(angle) * radius),
                        (0, 0, math.sin(angle) * radius),
                    ),
                )

            a, b = point(i * math.tau / 144), point((i + 1) * math.tau / 144)
            scene.beam("Building_CircuitWheel", "White", a, b, 0.30)
            if i % 6 == 0:
                scene.beam("Building_CircuitWheel", "Steel", center, a, 0.075)
        for sign2 in (-1, 1):
            foot = add(base, add(mul(axis, sign2 * 11), mul(across, sign * 6)))
            scene.beam("Building_CircuitWheel", "White", foot, center, 0.6)
    scene.beam(
        "Building_CircuitWheel",
        "Steel",
        add(hub, mul(across, -4)),
        add(hub, mul(across, 4)),
        0.8,
    )
    for i in range(40):
        angle = i * math.tau / 40
        p = add(
            hub,
            add(
                mul(axis, math.cos(angle) * radius),
                (0, 0, math.sin(angle) * radius - 1.2),
            ),
        )
        scene.box(
            "Building_CircuitWheel",
            ("Red", "SeatBlue", "SeatYellow", "Green")[i % 4],
            p,
            1.7,
            1.4,
            1.6,
            0.63,
        )
        scene.box(
            "Building_CircuitWheel", "Glass", add(p, (0, 0, 0.1)), 1.74, 1.44, 0.8, 0.63
        )
        scene.box(
            "Building_CircuitWheel", "White", add(p, (0, 0, 0.9)), 1.9, 1.6, 0.18, 0.63
        )
    scene.landmarks.append(
        {
            "name": "Circuit Wheel",
            "latitude": 34.845979,
            "longitude": 136.538821,
            "diameter_m": 48.0,
            "height_m": 51.0,
            "dimensions_status": "Mapped position; original reconstructed wheel, support and cabins. Diameter inferred from operator viewing height, not engineering survey.",
        }
    )
