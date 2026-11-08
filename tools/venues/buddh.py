"""Buddh's layered roof slabs, long open straights and bowl grandstands."""

from __future__ import annotations

import math

from circuit_mesh import add, mul
from circuit_scene import CircuitScene

from venues.east_architecture import (
    double_quad,
    facade,
    footprint_stand,
    frame,
    mapped,
    trees,
    upward_quad,
)
from venues.east_paint import apron_hatching
from venues.west_architecture import apron_band


def mapped_garage_front(scene: CircuitScene) -> None:
    building = scene.footprint(188019421)
    for index in range(9, 15):
        start, end = building.ring[index], building.ring[index + 1]
        length = math.dist(start, end)
        axis = (end[0] - start[0]) / length, (end[1] - start[1]) / length, 0.0
        normal = -axis[1], axis[0], 0.0
        midpoint = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        road, _ = scene.nearest(*midpoint)
        if (road.x - midpoint[0]) * normal[0] + (road.y - midpoint[1]) * normal[1] < 0:
            normal = mul(normal, -1)
        bays = max(1, round(length / 8))
        for bay in range(bays):
            pa = add((start[0], start[1], 0.0), mul(axis, length * bay / bays))
            pb = add((start[0], start[1], 0.0), mul(axis, length * (bay + 1) / bays))
            pa = pa[0], pa[1], scene.nearest(*pa[:2])[0].z + 0.05
            pb = pb[0], pb[1], scene.nearest(*pb[:2])[0].z + 0.05
            pa, pb = add(pa, mul(normal, 0.15)), add(pb, mul(normal, 0.15))
            scene.banner(pa, pb, 4.4, "Black", "Building_BuddhGaragePortals")
            for point in (pa, pb):
                scene.beam(
                    "Building_BuddhGaragePiers",
                    "White",
                    point,
                    add(point, (0.0, 0.0, 4.7)),
                    0.45,
                )
            scene.beam(
                "Building_BuddhGarageHeaders",
                "White",
                add(pa, (0.0, 0.0, 4.55)),
                add(pb, (0.0, 0.0, 4.55)),
                0.6,
                0.3,
            )
            for height in (4.1, 4.24, 4.38):
                scene.beam(
                    "Building_BuddhGarageRollerBoxes",
                    "Steel",
                    add(pa, (0.0, 0.0, height)),
                    add(pb, (0.0, 0.0, height)),
                    0.12,
                    0.06,
                )
    scene.landmarks.append(
        {
            "name": "Buddh registered garage portals",
            "osm_id": 188019421,
            "start_m": 470,
            "end_m": 870,
            "registration": "Road-facing retained ring edges9–15; dark full-width ground-floor portals, white structural piers and overhead roller boxes replace office-window appearance. Garage threshold elevations follow the adjacent road/pit apron; heights and bay spacing estimated from reference113–125s.",
        }
    )


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in (
        (260, 345, -1),
        (1000, 1080, 1),
        (1125, 1200, -1),
        (1370, 1475, 1),
        (2650, 2780, 1),
        (3230, 3320, -1),
        (3335, 3410, -1),
        (3450, 3530, 1),
        (3570, 3650, 1),
        (3675, 3750, -1),
        (3950, 4130, 1),
        (4170, 4320, 1),
        (4360, 4450, -1),
        (4595, 4680, -1),
        (4710, 4790, 1),
        (5005, 5100, 1),
    ):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in (
        (230, 370, 1, 13, "RunoffGreen"),
        (1330, 1505, -1, 18, "Runoff"),
        (2600, 2820, -1, 18, "RunoffGreen"),
        (3190, 3430, 1, 15, "RunoffRed"),
        (3500, 3770, -1, 12, "RunoffGreen"),
        (3900, 4340, -1, 18, "RunoffRed"),
        (4550, 4700, 1, 13, "Gravel"),
        (4970, 5130, -1, 17, "RunoffGreen"),
    ):
        scene.runoff(start, end, side, width, material)

    for start, end, side in (
        (260, 345, -1),
        (1370, 1475, 1),
        (2650, 2780, 1),
        (3230, 3410, -1),
        (3450, 3650, 1),
        (3675, 3750, -1),
        (3950, 4320, 1),
        (4360, 4450, -1),
    ):
        scene.runoff(start, end, side, 2.6, "RunoffGreen")

    for apex, side, distances in (
        (1041, -1, (150, 100, 50)),
        (1429, -1, (150, 100, 50)),
        (2719, -1, (150, 100, 50)),
        (3279, 1, (150, 100, 50)),
        (304, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (400, 1000, -1, "PanelAirtel"),
        (400, 1000, 1, "PanelAirtel"),
        (3110, 3310, -1, "PanelAirtel"),
        (3950, 4320, -1, "PanelAirtel"),
    ):
        scene.branding(start, end, side, material)

    apron_band(scene, 1335, 1500, -1, 15.0, 15.7, "RunoffBlue")
    apron_hatching(scene, 3210, 3410, 1, 2.8, 14.7, "Yellow")
    apron_band(scene, 3950, 4320, -1, 0.15, 2.6, "RunoffGreen")
    apron_band(scene, 3950, 4320, -1, 2.6, 2.8, "White")


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    footprint_stand(
        scene, 169886092, rows=30, roof="cantilever", seat_material="SeatBlue"
    )
    facade(scene, 188019421, 11, "modern", "White")
    mapped_garage_front(scene)
    pit = mapped(scene, 188019421)
    if pit is not None:
        center, axis, lateral, length, width = frame(pit)
        z = min(scene.ground(x, y) for x, y in pit.ring)
        heading_sample, _ = scene.nearest(center[0], center[1])
        if (center[0] - heading_sample.x) * lateral[0] + (
            center[1] - heading_sample.y
        ) * lateral[1] < 0:
            lateral = mul(lateral, -1)
        for fraction, roof_height in ((-0.34, 24.0), (0.35, 20.0)):
            c = add((center[0], center[1], z), mul(axis, length * fraction))
            for level in range(4):
                slab_height = roof_height - level * 3.2
                half = 35 + level * 1.2
                near, far = -width * 0.5 - 6 + level * 0.9, width * 0.5 + 2
                a = add(
                    c,
                    add(add(mul(axis, -half), mul(lateral, near)), (0, 0, slab_height)),
                )
                b = add(
                    c,
                    add(add(mul(axis, half), mul(lateral, near)), (0, 0, slab_height)),
                )
                d = add(
                    c,
                    add(
                        add(mul(axis, half + 4), mul(lateral, far)),
                        (0, 0, slab_height + 1.3),
                    ),
                )
                e = add(
                    c,
                    add(
                        add(mul(axis, -half + 4), mul(lateral, far)),
                        (0, 0, slab_height + 1.3),
                    ),
                )
                upward_quad(scene, "Building_BuddhPitRoof", "Roof", a, b, d, e)
                double_quad(
                    scene,
                    "Building_BuddhPitSoffit",
                    "Concrete",
                    add(a, (0, 0, -0.3)),
                    add(b, (0, 0, -0.3)),
                    add(d, (0, 0, -0.3)),
                    add(e, (0, 0, -0.3)),
                )
                scene.beam("Building_BuddhPitRoof", "White", a, b, 0.45, 0.3)
            for offset in (-28, 0, 28):
                top = add(
                    c,
                    add(
                        add(mul(axis, offset), mul(lateral, -width * 0.4)),
                        (0, 0, roof_height - 1),
                    ),
                )
                scene.beam(
                    "Building_BuddhPitColumns",
                    "White",
                    (top[0], top[1], scene.ground(top[0], top[1])),
                    top,
                    0.6,
                )
        scene.landmarks.append(
            {
                "name": "Buddh mapped pit and projecting control roofs",
                "osm_id": 188019421,
                "start_m": 470,
                "end_m": 870,
                "dimensions": "Registered articulated garage frontage and two angular layered roof groups estimated from 2013 footage.",
            }
        )
    facade(scene, 188028655, 8, "modern", "White")
    facade(scene, 496650379, 8, "modern", "Cream")
    scene.stand(
        1260, 1400, -1, rows=24, setback=12, roofed=False, seat_material="SeatBlue"
    )
    scene.stand(
        2640, 2800, -1, rows=20, setback=20, roofed=False, seat_material="SeatBlue"
    )
    scene.stand(
        3950, 4390, -1, rows=24, setback=22, roofed=True, seat_material="SeatBlue"
    )
    scene.stand(
        4550, 4700, -1, rows=19, setback=12, roofed=True, seat_material="SeatBlue"
    )
    p = scene.at(3080)
    c = p.point(-(p.half_width + p.left_shoulder + 23))
    base = c[0], c[1], scene.ground(c[0], c[1])
    scene.box("Building_BuddhTimingPylon", "White", add(base, (0, 0, 13)), 3.6, 3.6, 26)
    scene.box("Building_BuddhTimingPanel", "Black", add(base, (0, 0, 19)), 3.8, 3.8, 11)
    for level in range(10):
        scene.box(
            "Building_BuddhTimingPanel",
            "White",
            add(base, (0, 0, 14 + level)),
            3.9,
            3.9,
            0.09,
        )
    scene.landmarks.append(
        {
            "name": "Buddh timing pylon",
            "station_m": 3080,
            "height_m": 26,
            "dimensions": "White timing pylon and dark position panel observed near the infield braking approach; placement estimated.",
        }
    )
    for start, end, side, setback, spacing in (
        (700, 1250, 1, 35, 42),
        (1500, 2450, -1, 28, 45),
        (1550, 2450, 1, 40, 48),
        (2800, 3250, -1, 55, 55),
        (3450, 3800, 1, 60, 50),
        (4400, 4660, 1, 45, 45),
    ):
        trees(scene, start, end, side, setback, spacing, 8, palm=True)
    for start, end, side, setback in (
        (1000, 1300, -1, 90),
        (2000, 2600, 1, 95),
        (3100, 3600, -1, 95),
        (3700, 3900, 1, 100),
    ):
        trees(scene, start, end, side, setback, 45, 9)
