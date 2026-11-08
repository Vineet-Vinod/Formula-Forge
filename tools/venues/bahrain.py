"""Sakhir night venue, registered stands and tiered tower."""

from __future__ import annotations

import math

from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.east_architecture import cylinder, footprint_stand, frame, mapped, trees
from venues.east_paint import apron_fan
from venues.west_architecture import apron_band


def sakhir_pits(scene: CircuitScene) -> None:
    start, end = 5180.0, 220.0
    span = (end - start) % scene.length
    bays = math.ceil(span / 8)
    for index in range(bays):
        a, b = (
            scene.at(start + span * index / bays),
            scene.at(start + span * (index + 1) / bays),
        )
        lane_a, lane_b = a.half_width + 13, b.half_width + 13
        footprint = Polygon(
            [
                a.point(lane_a)[:2],
                b.point(lane_b)[:2],
                b.point(lane_b + 23)[:2],
                a.point(lane_a + 23)[:2],
            ]
        )
        if footprint.is_valid:
            scene.terrain_cutouts.append(footprint.difference(scene.road_mask))
        scene.banner(
            a.point(lane_a + 1.2, 0.15),
            b.point(lane_b + 1.2, 0.15),
            4.3,
            "Black",
            "Building_SakhirGarageRecess",
        )
        for sample, lane in ((a, lane_a), (b, lane_b)):
            scene.beam(
                "Building_SakhirGaragePiers",
                "White",
                sample.point(lane),
                sample.point(lane, 9.5),
                0.45,
            )
            scene.quad(
                "Building_SakhirGarageReveals",
                "Cream",
                sample.point(lane, 0.1),
                sample.point(lane + 1.25, 0.1),
                sample.point(lane + 1.25, 4.5),
                sample.point(lane, 4.5),
            )
        scene.beam(
            "Building_SakhirGarageHeaders",
            "White",
            a.point(lane_a, 4.65),
            b.point(lane_b, 4.65),
            0.7,
            0.45,
        )
        for height in (4.08, 4.22, 4.36):
            scene.beam(
                "Building_SakhirRollerBoxes",
                "Steel",
                a.point(lane_a + 0.1, height),
                b.point(lane_b + 0.1, height),
                0.12,
                0.06,
            )
        scene.beam(
            "Building_SakhirBalcony",
            "Cream",
            a.point(lane_a, 5.15),
            b.point(lane_b, 5.15),
            2.0,
            0.3,
        )
        scene.banner(
            a.point(lane_a + 0.35, 5.3),
            b.point(lane_b + 0.35, 5.3),
            4.2,
            "White",
            "Building_SakhirUpperWall",
        )
        window_a, window_b = scene.at(a.station + 0.5), scene.at(b.station - 0.5)
        scene.banner(
            window_a.point(window_a.half_width + 13.12, 6.0),
            window_b.point(window_b.half_width + 13.12, 6.0),
            2.65,
            "Glass",
            "Building_SakhirHospitalityRibbon",
        )
        scene.beam(
            "Building_SakhirUpperFascia",
            "Cream",
            a.point(lane_a, 9.2),
            b.point(lane_b, 9.2),
            0.55,
            0.5,
        )
        for height in (0.05, 5.05, 9.6):
            scene.quad(
                "Building_SakhirPitFloors",
                "Concrete",
                a.point(lane_a, height),
                b.point(lane_b, height),
                b.point(lane_b + 23, height),
                a.point(lane_a + 23, height),
                up=True,
            )
        scene.banner(
            a.point(lane_a + 23),
            b.point(lane_b + 23),
            9.6,
            "Cream",
            "Building_SakhirPitRear",
        )
    canopies = math.ceil(span / 24)
    for canopy in range(canopies):
        stations = [
            start + span * (canopy + fraction) / canopies
            for fraction in (0.0, 0.5, 1.0)
        ]
        samples = [scene.at(station) for station in stations]
        heights = ((10.8, 12.0, 11.8), (13.3, 15.4, 14.2), (10.8, 12.0, 11.8))
        grid = [
            [
                sample.point(sample.half_width + lane, heights[column][row])
                for row, lane in enumerate((11.0, 25.0, 38.0))
            ]
            for column, sample in enumerate(samples)
        ]
        for column in range(2):
            for row in range(2):
                pa, pb, pc, pd = (
                    grid[column][row],
                    grid[column + 1][row],
                    grid[column + 1][row + 1],
                    grid[column][row + 1],
                )
                scene.quad(
                    "Building_SakhirFoldedRoof", "CanopyFabric", pa, pb, pc, pd, up=True
                )
                scene.quad(
                    "Building_SakhirFoldedSoffit",
                    "CanopyFabric",
                    add(pa, (0, 0, -0.14)),
                    add(pb, (0, 0, -0.14)),
                    add(pc, (0, 0, -0.14)),
                    add(pd, (0, 0, -0.14)),
                    up=False,
                )
        for column in range(2):
            scene.beam(
                "Building_SakhirRoofEdge",
                "White",
                grid[column][0],
                grid[column + 1][0],
                0.16,
            )
            scene.beam(
                "Building_SakhirRoofFrames",
                "Steel",
                add(grid[column][1], (0, 0, -0.25)),
                add(grid[column + 1][1], (0, 0, -0.25)),
                0.14,
            )
        for column in range(3):
            for row in range(2):
                scene.beam(
                    "Building_SakhirRoofFrames",
                    "Steel",
                    add(grid[column][row], (0, 0, -0.25)),
                    add(grid[column][row + 1], (0, 0, -0.25)),
                    0.13,
                )
        if canopy < 4:
            peak = add(grid[1][1], (0, 0, 2.8))
            scene.beam("Building_SakhirPitEntrySpire", "White", grid[1][1], peak, 0.18)
            for corner in (grid[0][0], grid[2][0], grid[0][2], grid[2][2]):
                scene.beam("Building_SakhirPitEntryStay", "Steel", corner, peak, 0.075)
    scene.landmarks.append(
        {
            "name": "Sakhir garage frontage and folded pit canopy",
            "start_m": start,
            "end_m": end,
            "side": 1,
            "garage_front_offset_m": 13,
            "garage_bays": bays,
            "folded_roof_bays": canopies,
            "registration": "Original authored 4.3 m garage recesses, roller headers, white piers, projecting balcony and narrow upper hospitality glazing. Repeated white folded roof/scalloped front edge and four pit-entry spires estimated from reference120/130/185s. No reference pixels or measured architectural survey claimed.",
        }
    )


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in (
        (425, 515, 1),
        (565, 625, -1),
        (665, 735, 1),
        (1235, 1330, 1),
        (1485, 1570, -1),
        (1615, 1685, 1),
        (1735, 1810, -1),
        (1970, 2060, 1),
        (2410, 2555, -1),
        (3165, 3290, -1),
        (3510, 3640, 1),
        (3830, 3920, 1),
        (4630, 4760, 1),
    ):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in (
        (420, 550, -1, 15, "RunoffBlue"),
        (1210, 1360, -1, 14, "RunoffGreen"),
        (1460, 1810, 1, 8, "RunoffBlue"),
        (1940, 2100, -1, 15, "RunoffBlue"),
        (2370, 2580, 1, 16, "RunoffBlue"),
        (3130, 3320, 1, 14, "RunoffGreen"),
        (3820, 3950, -1, 10, "RunoffBlue"),
        (4590, 4810, -1, 16, "RunoffBlue"),
    ):
        scene.runoff(start, end, side, width, material)

    for apex, side, distances in (
        (487, -1, (150, 100, 50)),
        (1293, -1, (150, 100, 50)),
        (2027, -1, (150, 100, 50)),
        (2490, 1, (150, 100, 50)),
        (3233, 1, (150, 100, 50)),
        (4693, -1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5180, 5412, -1, "PanelGulfAir"),
        (0, 220, -1, "PanelGulfAir"),
        (5180, 5412, 1, "PanelGulfAir"),
        (0, 220, 1, "PanelGulfAir"),
    ):
        scene.branding(start, end, side, material)

    apron_fan(scene, 4630, 4760, -1, 5.0, 15.8, "Cream")
    apron_band(scene, 3825, 3940, -1, 0.2, 3.2, "RunoffBlue")


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    for osm_id in (
        187123419,
        271535967,
        271535959,
        271535961,
        271535984,
        271535964,
        271535981,
    ):
        footprint_stand(
            scene,
            osm_id,
            24 if osm_id == 187123419 else 15,
            "sail",
            seat_material="SeatRed",
        )
    footprint_stand(scene, 187123414, 18, "cantilever", seat_material="SeatRed")
    sakhir_pits(scene)
    tower = mapped(scene, 187123438)
    if tower is not None:
        center, _, _, _, _ = frame(tower)
        base = center[0], center[1], scene.ground(center[0], center[1])
        cylinder(scene, base, 18.5, 18.5, 3, "Cream")
        for floor in range(9):
            z = 3 + floor * 3.9
            cylinder(scene, add(base, (0, 0, z)), 16.3, 16.3, 3.1, "Glass")
            cylinder(
                scene,
                add(base, (0, 0, z + 3.05)),
                19.2 - floor * 0.12,
                19.2 - floor * 0.12,
                0.75,
                "Cream",
            )
            if floor in (1, 4, 7):
                cylinder(scene, add(base, (0, 0, z + 2.65)), 16.5, 16.5, 0.35, "Red")
            for column in range(24):
                azimuth = column * math.tau / 24
                column_x, column_y = (
                    base[0] + 16.5 * math.cos(azimuth),
                    base[1] + 16.5 * math.sin(azimuth),
                )
                scene.beam(
                    "Building_SakhirTower",
                    "White",
                    (column_x, column_y, base[2] + z),
                    (column_x, column_y, base[2] + z + 3.1),
                    0.16,
                )
        cylinder(scene, add(base, (0, 0, 38)), 11, 11, 6, "Glass")
        cylinder(scene, add(base, (0, 0, 44)), 13, 13, 0.8, "White")
        scene.modeled_buildings.add(tower.osm_id)
        scene.landmarks.append(
            {
                "name": "Sakhir Tower",
                "osm_id": tower.osm_id,
                "height_m": 44.8,
                "dimensions": "Footprint registered; vertical floor dimensions estimated from reference.",
            }
        )
    for start, end, side, offset in (
        (5050, 5412, -1, 37),
        (0, 350, -1, 50),
        (600, 1100, -1, 65),
        (2950, 3150, 1, 50),
        (4300, 4700, -1, 55),
    ):
        trees(scene, start, end, side, offset, 62, 8, palm=True)
