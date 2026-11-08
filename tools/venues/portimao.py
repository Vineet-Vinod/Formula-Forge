"""Portimão: faceted grandstand blades and a circular glazed control tower on dry hills."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.west_architecture import apron_band, mapped_building, mast, trees


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(560, 930, 1, 'PanelWhite')
    scene.branding(560, 930, -1, 'PanelWhite')
    scene.branding(2230, 2400, 1, 'PanelWhite')
    scene.branding(2900, 3020, -1, 'PanelWhite')
    scene.braking_boards(1254, -1)  # Opening right-hander
    scene.braking_boards(1602, -1)  # Curva Lagos
    scene.braking_boards(2332, 1)  # Curva da Torre VIP
    scene.braking_boards(2952, -1)  # Curva Samsung
    scene.braking_boards(3327, 1, distances=(100, 50))  # Curva Craig Jones
    mapped_building(scene, 38167081, 12, facade='White', floors=3, roof='canopy')
    mapped_building(scene, 38166697, 17, facade='Concrete', floors=1, roof='blades', enclosed=False)
    scene.stand(470, 1060, -1, rows=23, setback=7, seat_material='SeatRed')
    mapped_building(scene, 157736297, 18, facade='White', floors=5, balconies=True)
    scene.stand(1430, 1540, -1, rows=12, setback=24, seat_material='SeatRed')
    scene.stand(2240, 2380, -1, rows=12, setback=27, seat_material='SeatRed')
    scene.stand(3480, 3570, -1, rows=12, setback=27, seat_material='SeatRed')
    for start, end, side in [(1450, 2120, 1), (1650, 2120, -1), (2430, 2880, 1),
                              (2480, 2860, -1), (3080, 3450, 1), (3220, 3420, -1),
                              (3650, 4100, 1), (3700, 4120, -1)]:
        trees(scene, start, end, side, setback=40, spacing=38, height=5.5, rows=1)
    for station in [400, 1120, 1570, 2320, 2940, 3590, 4260]:
        mast(scene, station, -1, 18)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(4560, 4650, 1), (0, 170, 1), (1210, 1295, 1), (1300, 1360, -1), (1380, 1480, 1), (1560, 1650, 1), (1700, 1800, -1), (2260, 2400, -1), (2750, 2870, 1), (2890, 3000, 1), (3280, 3370, -1), (3500, 3680, 1), (3810, 3920, -1), (4020, 4130, -1), (4230, 4380, 1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    for start, end, side, width, material in [(1170, 1520, -1, 23, 'Gravel'), (1510, 1690, -1, 20, 'Gravel'), (2220, 2450, 1, 22, 'Gravel'), (2700, 3040, -1, 24, 'Gravel'), (3450, 3730, -1, 24, 'Gravel'), (3770, 4170, 1, 23, 'Gravel'), (4180, 4430, -1, 25, 'Gravel')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(1170, 1520, -1), (1510, 1690, -1),
                              (2220, 2450, 1), (2700, 3040, -1),
                              (3450, 3730, -1), (3770, 4170, 1), (4180, 4430, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.8, 'RunoffGreen')
    for start, end, side in [(2220, 2450, 1), (3450, 3730, -1)]:
        apron_band(scene, start, end, side, 3.8, 5.2, 'RunoffRed')
