"""Sepang's double-frontage leaf roofs, wide plantation circuit and pit terraces."""

from __future__ import annotations

import math

from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.east_architecture import (
    facade,
    footprint_stand,
    frame,
    layered_pit_roofs,
    mapped,
    trees,
)
from venues.west_architecture import apron_band


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in (
        (500, 610, 1),
        (655, 730, -1),
        (770, 850, 1),
        (940, 1020, 1),
        (1420, 1550, 1),
        (1810, 1940, -1),
        (2045, 2170, 1),
        (2390, 2490, 1),
        (2520, 2630, 1),
        (3020, 3120, -1),
        (3155, 3260, 1),
        (3380, 3480, 1),
        (3710, 3820, -1),
        (3910, 4020, 1),
        (4070, 4190, 1),
        (4980, 5130, -1),
    ):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in (
        (475, 630, -1, 18, "Gravel"),
        (620, 755, 1, 13, "Gravel"),
        (1390, 1570, -1, 15, "Gravel"),
        (1780, 1960, 1, 14, "Gravel"),
        (2350, 2660, -1, 18, "Gravel"),
        (2970, 3150, 1, 18, "Gravel"),
        (3330, 3520, -1, 13, "Gravel"),
        (3860, 4220, -1, 17, "Gravel"),
        (4940, 5170, 1, 18, "Gravel"),
    ):
        scene.runoff(start, end, side, width, material)

    for start, end, side in (
        (770, 850, 1),
        (1420, 1550, 1),
        (1810, 1940, -1),
        (2045, 2170, 1),
        (2390, 2630, 1),
        (3155, 3260, 1),
        (3380, 3480, 1),
        (3710, 3820, -1),
        (3910, 4190, 1),
    ):
        scene.runoff(start, end, side, 2.6, "RunoffGreen")

    for apex, side, distances in (
        (567, -1, (150, 100, 50)),
        (1495, -1, (150, 100, 50)),
        (3077, 1, (150, 100, 50)),
        (5068, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5290, 5543, -1, 'PanelPetronas'),
        (0, 320, -1, 'PanelPetronas'),
        (5290, 5543, 1, 'PanelPetronas'),
        (0, 320, 1, 'PanelPetronas'),
        (500, 650, -1, 'PanelPetronas'),
    ):
        scene.branding(start, end, side, material)


    apron_band(scene, 1420, 1550, 1, 2.35, 2.55, 'White')
    apron_band(scene, 2390, 2630, 1, 2.35, 2.55, 'White')
    apron_band(scene, 3910, 4190, 1, 2.35, 2.55, 'White')

def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    main = mapped(scene, 144247993)
    if main is not None:
        center, axis, side_axis, length, width = frame(main)
        z = scene.ground(center[0], center[1])
        row_count = 25
        available = Polygon(main.ring).difference(scene.road_mask.buffer(3))
        modules = max(1, round(length / 25))
        for face in (-1, 1):
            for module in range(modules):
                along = -length / 2 + length * module / modules
                for row in range(row_count):
                    lane = face * (width * 0.48 - row * 0.91)
                    rise = row * 0.47
                    a = add(
                        (center[0], center[1], z + 0.8 + rise),
                        add(mul(axis, along), mul(side_axis, lane)),
                    )
                    b = add(a, mul(axis, length / modules))
                    d, e = (
                        add(b, mul(side_axis, -face * 0.91)),
                        add(a, mul(side_axis, -face * 0.91)),
                    )
                    if not available.covers(
                        Polygon([(p[0], p[1]) for p in (a, b, d, e)])
                    ):
                        continue
                    scene.quad("Building_SepangStand", "Concrete", a, b, d, e)
                    scene.beam(
                        "Building_SepangStand",
                        "SeatBlue" if module % 6 < 4 else "SeatRed",
                        add(a, (0, 0, 0.1)),
                        add(b, (0, 0, 0.1)),
                        0.45,
                        0.14,
                    )
                    scene.spectators(
                        add(a, (0, 0, 0.25)),
                        add(b, (0, 0, 0.25)),
                        row,
                        "Building_Crowd_Sepang",
                    )
        for module in range(modules):
            c = add(
                (center[0], center[1], z + 18),
                mul(axis, -length / 2 + length * (module + 0.5) / modules),
            )
            half = length / modules / 2
            depth = width * 0.52
            for face in (-1, 1):
                for along_step in range(8):
                    for depth_step in range(8):

                        def point(
                            u: float,
                            v: float,
                            c: tuple[float, float, float] = c,
                            half: float = half,
                            face: int = face,
                            depth: float = depth,
                        ) -> tuple[float, float, float]:
                            return add(
                                c,
                                add(
                                    add(
                                        mul(axis, -half + 2 * half * u),
                                        mul(side_axis, face * depth * v),
                                    ),
                                    (
                                        0,
                                        0,
                                        3.8 * math.sin(math.pi * u) * (1 - 0.35 * v)
                                        + 2.8 * v * v,
                                    ),
                                ),
                            )

                        u0, u1, v0, v1 = (
                            along_step / 8,
                            (along_step + 1) / 8,
                            depth_step / 8,
                            (depth_step + 1) / 8,
                        )
                        a, b, d, e = (
                            point(u0, v0),
                            point(u1, v0),
                            point(u1, v1),
                            point(u0, v1),
                        )
                        scene.quad("Building_SepangLeafRoof", "Cream", a, b, d, e)
                        scene.quad(
                            "Building_SepangLeafRoof",
                            "Concrete",
                            add(e, (0, 0, -0.2)),
                            add(d, (0, 0, -0.2)),
                            add(b, (0, 0, -0.2)),
                            add(a, (0, 0, -0.2)),
                        )
                mast = add(c, (0, 0, 8))
                root = add(c, (0, 0, -18))
                scene.beam("Building_SepangMasts", "Steel", root, mast, 0.5)
                for sign in (-1, 1):
                    tip = add(
                        c, add(mul(side_axis, face * depth), mul(axis, sign * half))
                    )
                    scene.beam(
                        "Building_SepangMasts",
                        "Steel",
                        mast,
                        add(tip, (0, 0, 2.8)),
                        0.10,
                    )
                    scene.beam(
                        "Building_SepangMasts",
                        "Steel",
                        add(root, (0, 0, 11)),
                        add(tip, (0, 0, 2.8)),
                        0.2,
                    )
        scene.modeled_buildings.add(main.osm_id)
        scene.landmarks.append(
            {
                "name": "Sepang double-frontage main grandstand",
                "osm_id": main.osm_id,
                "roof": "Repeated curved palm-leaf shells with branching masts",
                "roof_bays": modules,
                "dimensions": "Footprint registered; roof section and steel details estimated from reference.",
            }
        )
    for osm_id in (107364038, 107364100):
        footprint_stand(scene, osm_id, 22, "cantilever")
    scene.modeled_buildings.add(144362327)
    scene.pit_building(5290, 320, 1, depth=24, height=14.5, levels=3, bay=8)
    layered_pit_roofs(scene, 5290, 320, 1, 3, 17, 40)
    facade(scene, 1105232836, 8, "modern", "White")
    for osm_id in (107364040, 1106756634, 144359492):
        facade(scene, osm_id, 8, "modern", "Cream")
    for start, end, side, offset, spacing in (
        (650, 1450, -1, 30, 29),
        (650, 1450, 1, 55, 33),
        (1500, 2250, -1, 28, 29),
        (2000, 2850, 1, 43, 31),
        (2850, 3550, -1, 38, 30),
        (3550, 4250, 1, 40, 31),
        (4050, 4800, -1, 34, 29),
        (4800, 5100, -1, 35, 30),
    ):
        trees(scene, start, end, side, offset, spacing, 11, palm=True)
    for start, end, side, offset in (
        (850, 1450, -1, 70),
        (1800, 2450, 1, 100),
        (3100, 3600, -1, 85),
        (3800, 4600, 1, 80),
    ):
        trees(scene, start, end, side, offset, 27, 13)
