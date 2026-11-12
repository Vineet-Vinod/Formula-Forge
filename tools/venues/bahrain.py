"""Sakhir night venue, registered stands and tiered tower."""

from __future__ import annotations

import math

from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.east_architecture import cylinder, footprint_stand, frame, mapped, trees
from venues.east_paint import apron_fan
from venues.pit_compounds import SAKHIR, mapped_pit
from venues.west_architecture import apron_band


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
        (3130, 3320, 1, 14, "RunoffBlue"),
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
    t11_painted_island(scene)


def t11_painted_island(scene: CircuitScene) -> None:
    apron_band(scene, 3165, 3290, 1, 1.4, 4.0, "Cream")
    for station in range(3165, 3290, 2):
        a, b = scene.at(station), scene.at(min(3290, station + 2))
        shape = Polygon([
            a.point(-a.half_width - 1.4)[:2],
            b.point(-b.half_width - 1.4)[:2],
            b.point(-b.half_width - 11.4)[:2],
            a.point(-a.half_width - 11.4)[:2],
        ]).intersection(scene.corridor_mask).difference(scene.road_mask)
        scene.terrain_cutouts.append(shape)
        scene.polygon_surface(shape, "Cream", lift=.002, sample=a, paved=True)
        blue = Polygon([
            a.point(-a.half_width - 1.4)[:2],
            b.point(-b.half_width - 1.4)[:2],
            b.point(-b.half_width - 5.4)[:2],
            a.point(-a.half_width - 5.4)[:2],
        ]).intersection(shape)
        scene.paint_surface(blue, "RunoffBlue", lift=.007)
    scene.surface_ranges.append({
        "type": "Bahrain T11 blue and cream paving", "start_m": 3165,
        "end_m": 3290, "inside_side": -1, "outer_side": 1,
        "inside_blue_band_estimate_m": 4.0,
        "source_note": "Continuous supplied 109.8/110/110.2 s shows blue paint on the pale inner island and blue/cream paving outside T11. Estimated inner island reach 11.4 m and blue band 1.4–5.4 m are clipped to the existing physical corridor. The outer apron retains its original extent. Native road, protection and driving surfaces are unchanged.",
    })


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
    mapped_pit(scene, SAKHIR)
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
