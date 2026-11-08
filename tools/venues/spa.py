"""Spa: valley pit complexes, gabled Eau Rouge chalet and deep Ardennes woodland."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.west_architecture import apron_band, mapped_building, mast, trees


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(740, 1060, 1, 'PanelWhite')
    scene.branding(740, 1060, -1, 'PanelWhite')
    scene.branding(1560, 1840, 1, 'PanelWhite')
    scene.branding(2860, 3220, -1, 'PanelYellow')
    scene.braking_boards(1177, -1)  # La Source
    scene.braking_boards(3198, -1)  # Les Combes
    scene.braking_boards(3862, -1)  # Bruxelles
    scene.braking_boards(5295, -1, distances=(100, 50))  # Fagnes
    scene.braking_boards(476, -1)  # Bus Stop first apex
    mapped_building(scene, 77352246, 16, facade='Concrete', floors=4, roof='canopy', garage_front=True)
    mapped_building(scene, 77352249, 8, facade='White', floors=2, roof='pitched')
    mapped_building(scene, 176136366, 9, facade='Cream', floors=2, roof='pitched')
    scene.stand(730, 1050, -1, rows=20, setback=10, roofed=True, seat_material='SeatRed')
    scene.stand(1970, 2110, -1, rows=26, setback=23, roofed=True, seat_material='SeatRed')
    scene.stand(3080, 3280, -1, rows=14, setback=32, seat_material='SeatRed')
    scene.stand(6510, 6700, 1, rows=14, setback=30, seat_material='SeatRed')
    for start, end, side, setback in [(1280, 1720, -1, 40), (2160, 3030, 1, 25),
                                      (2160, 3010, -1, 35), (3380, 3760, 1, 32),
                                      (3400, 3750, -1, 38), (3920, 4560, 1, 30),
                                      (3940, 4560, -1, 35), (4820, 5200, 1, 42),
                                      (4820, 5220, -1, 34), (5500, 5860, 1, 35),
                                      (5520, 5850, -1, 32), (6110, 6910, 1, 32),
                                      (6140, 6900, -1, 32)]:
        trees(scene, start, end, side, setback=setback, rows=4, spacing=13,
              height=20, conifers=True)
    for start, end in [(1390, 1690), (3520, 3690), (4150, 4490), (5530, 5770)]:
        trees(scene, start, end, -1, setback=22, spacing=28, rows=1, height=16)
    for station in [520, 1120, 1770, 2040, 3160, 3830, 4710, 5330, 5960, 6750]:
        mast(scene, station, -1, 20)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(480, 540, 1), (550, 620, -1), (1115, 1240, 1), (1800, 1870, -1), (1880, 1960, 1), (1980, 2055, -1), (3160, 3220, 1), (3235, 3320, -1), (3400, 3500, 1), (3800, 3935, 1), (4060, 4155, -1), (4670, 4820, -1), (5300, 5375, 1), (5410, 5485, -1), (5700, 5780, 1), (5900, 6030, 1), (6720, 6860, -1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='Yellow')
    for start, end, side, width, material in [(440, 655, -1, 17, 'Runoff'), (1070, 1290, -1, 22, 'Runoff'), (1800, 2100, 1, 24, 'Gravel'), (3100, 3530, -1, 24, 'Gravel'), (3750, 3990, -1, 23, 'Gravel'), (4620, 4890, 1, 24, 'Gravel'), (5250, 5530, -1, 22, 'Gravel'), (6670, 6900, 1, 21, 'Gravel')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(440, 655, -1), (1070, 1290, -1)]:
        apron_band(scene, start, end, side, 1.2, 2.8, 'RunoffGreen')
        apron_band(scene, start, end, side, 2.8, 6.0, 'RunoffRed')
