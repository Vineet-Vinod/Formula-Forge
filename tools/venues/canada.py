"""Île Notre-Dame: flat wooded waterways, open hairpin stands and layered paddocks."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.west_architecture import mapped_building, mast, trees, water


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4200, 4355, 1, 'PanelLenovo')
    scene.branding(4200, 4355, -1, 'PanelLenovo')
    scene.branding(0, 170, 1, 'PanelLenovo')
    scene.branding(0, 170, -1, 'PanelLenovo')
    scene.branding(2650, 2880, -1, 'PanelLenovo')
    scene.branding(3380, 3820, 1, 'PanelGreen')
    scene.branding(3380, 3820, -1, 'PanelGreen')
    scene.braking_boards(312, 1)  # T1 / Senna S
    scene.braking_boards(783, -1)  # T3/T4 chicane
    scene.braking_boards(1315, 1)  # T6/T7 chicane
    scene.braking_boards(2071, -1)  # T8/T9 chicane
    scene.braking_boards(2758, -1)  # T10 hairpin
    scene.braking_boards(4001, 1)  # T13/T14 final chicane
    water(scene)
    mapped_building(scene, 42229671, 14, facade='Concrete', floors=3, roof='canopy', garage_front=True)
    mapped_building(scene, 26698931, 28, facade='White', floors=7, balconies=True)
    mapped_building(scene, 439917766, 22, facade='Glass', floors=5, roof='canopy')
    scene.stand(4200, 4350, 1, rows=22, setback=7, roofed=True, seat_material='Concrete')
    scene.stand(200, 330, -1, rows=23, setback=12, seat_material='Concrete')
    scene.stand(440, 610, -1, rows=18, setback=18, seat_material='Concrete')
    scene.stand(2580, 2800, -1, rows=26, setback=22, seat_material='Concrete')
    scene.stand(2800, 2940, -1, rows=22, setback=28, seat_material='Concrete')
    for start, end, side, setback in [(680, 1230, 1, 12), (680, 1200, -1, 14),
                                      (1400, 1980, 1, 12), (1440, 1970, -1, 15),
                                      (2150, 2510, 1, 17), (2160, 2520, -1, 13),
                                      (3000, 3890, 1, 11), (3030, 3880, -1, 13),
                                      (4000, 4160, -1, 20)]:
        trees(scene, start, end, side, setback=setback, spacing=12, rows=3, height=14)
    for station in [180, 770, 1300, 2020, 2710, 3480, 3990, 4280]:
        mast(scene, station, -1, 20)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(275, 339, -1), (357, 449, 1), (750, 818, 1), (822, 886, -1), (1270, 1350, -1), (1355, 1420, 1), (2035, 2108, 1), (2110, 2180, -1), (2700, 2830, 1), (3960, 4035, -1), (4040, 4115, 1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    for start, end, side, width, material in [(265, 455, 1, 9, 'Runoff'), (740, 875, -1, 7, 'Runoff'), (1260, 1435, 1, 8, 'Runoff'), (2020, 2190, -1, 8, 'Runoff'), (2680, 2860, -1, 17, 'Runoff'), (3940, 4140, -1, 8, 'Runoff')]:
        scene.runoff(start, end, side, width, material)
    scene.runoff(2720, 2805, 1, 6.0, 'RunoffBlue')
