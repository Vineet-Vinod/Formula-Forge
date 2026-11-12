"""Shanghai lotus canopy terraces and open parkland with the pit roof bridge."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.east_architecture import footprint_stand, trees
from venues.pit_compounds import (
    SHANGHAI,
    mapped_pit,
    shanghai_crossing_wings,
    shanghai_main_stand,
)
from venues.west_architecture import apron_band


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((165, 285, 1), (390, 465, -1), (960, 1040, -1), (1070, 1155, 1), (1180, 1270, 1), (2610, 2750, 1), (2990, 3110, -1), (3930, 4140, 1), (4180, 4300, -1), (4590, 4700, 1), (4865, 4960, 1), (5320, 5430, -1)):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in ((130, 300, -1, 12, 'Gravel'), (920, 1050, 1, 14, 'RunoffGreen'), (1060, 1320, -1, 15, 'Gravel'), (2580, 2780, -1, 16, 'RunoffGreen'), (2960, 3150, 1, 14, 'Gravel'), (3850, 4190, -1, 18, 'Gravel'), (4160, 4330, 1, 13, 'RunoffGreen'), (4840, 5000, -1, 15, 'Gravel')):
        scene.runoff(start, end, side, width, material)

    for start, end, side in ((165, 285, 1), (390, 465, -1), (1070, 1270, 1), (2990, 3110, -1), (3930, 4140, 1), (4180, 4300, -1), (4865, 4960, 1)):
        scene.runoff(start, end, side, 2.6, 'RunoffGreen')

    scene.runoff(1180, 1270, 1, 8.0, 'RunoffViolet')

    for apex, side, distances in (
        (3950, -1, (150, 100, 50)),
        (4920, -1, (150, 100, 50)),
        (1006, 1, (150, 100, 50)),
        (2680, -1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (2530, 2730, -1, 'PanelYellow'),
        (2760, 2940, -1, 'PanelGreen'),
        (2760, 2940, 1, 'PanelGreen'),
    ):
        scene.branding(start, end, side, material)


    apron_band(scene, 1185, 1260, 1, 7.55, 7.75, 'White')
    apron_band(scene, 4170, 4310, 1, 0.15, 2.4, 'RunoffGreen')

def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    for osm_id in (156341844, 156341848, 156341851):
        footprint_stand(scene, osm_id, 22, seat_material='SeatRed')
    for osm_id in (1372223261, 1372223262):
        footprint_stand(scene, osm_id, 19, 'lotus', seat_material='SeatRed')
    # Section A includes the bridge and roof footprint across the straight.
    scene.modeled_buildings.add(107371135)
    shanghai_main_stand(scene)
    mapped_pit(scene, SHANGHAI)
    shanghai_crossing_wings(scene)
    for start, end, side, setback in ((0, 550, -1, 65), (600, 1400, 1, 90), (1450, 2550, 1, 75), (1700, 2500, -1, 110), (4400, 5000, -1, 80), (5000, 5440, 1, 95)):
        trees(scene, start, end, side, setback, 34, 10)
