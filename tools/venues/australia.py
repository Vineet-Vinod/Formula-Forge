"""Albert Park: temporary race architecture inside a mature lakeside city park."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.west_architecture import apron_band, mapped_building, mast, trees, water


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4930, 5270, 1, 'PanelPurple')
    scene.branding(4930, 5270, -1, 'PanelPurple')
    scene.branding(650, 1030, 1, 'PanelYellow')
    scene.branding(650, 1030, -1, 'PanelYellow')
    scene.braking_boards(286, -1)  # T1 / Jones
    scene.braking_boards(1018, -1)  # T3 / Whiteford
    scene.braking_boards(3234, 1, distances=(100, 50))  # T9 high-speed chicane approach
    scene.braking_boards(4065, -1)  # T11
    scene.braking_boards(4578, 1)  # T13
    water(scene)
    scene.pit_building(4940, 5230, side=1, depth=21, height=13, levels=3)
    scene.stand(4900, 5270, -1, rows=20, setback=6, roofed=True, seat_material='Concrete')
    scene.stand(80, 230, -1, rows=18, setback=9, roofed=True, seat_material='Concrete')
    scene.stand(1050, 1130, -1, rows=12, setback=24, seat_material='Concrete')
    scene.stand(1070, 1140, 1, rows=12, setback=26, seat_material='Concrete')
    scene.stand(3900, 4020, -1, rows=13, setback=16, seat_material='Concrete')
    mapped_building(scene, 26811587, 7, floors=2, roof='pitched')
    mapped_building(scene, 154529390, 7, floors=2, roof='pitched')
    mapped_building(scene, 45384591, 70, floors=21, balconies=True)
    mapped_building(scene, 306782098, 16, floors=4, roof='canopy')
    mapped_building(scene, 1081955937, 77.8, floors=23, balconies=True)
    for start, end, side, setback in [(240, 985, 1, 6), (300, 980, -1, 6),
                                      (1120, 1700, 1, 18), (1160, 1720, -1, 17),
                                      (1800, 2860, -1, 18), (2940, 3860, -1, 14),
                                      (3880, 4800, 1, 18), (4100, 4760, -1, 22)]:
        avenue = start in (240, 300)
        trees(scene, start, end, side, setback=setback, height=17 if avenue else 13,
              spacing=11 if avenue else 13, rows=3 if avenue else 2)
    trees(scene, 1900, 2810, 1, setback=24, spacing=39, height=12, rows=1, palms=True)
    for station in [120, 980, 1780, 2440, 3190, 4050, 4620, 5120]:
        mast(scene, station, -1, 18)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(255, 320, 1), (360, 440, -1), (986, 1060, 1), (1125, 1190, -1), (1340, 1415, 1), (1770, 1855, 1), (1900, 1990, -1), (2100, 2250, 1), (3180, 3290, -1), (3320, 3405, 1), (4015, 4110, 1), (4275, 4360, 1), (4535, 4615, -1), (4690, 4780, 1)]:
        scene.kerb(start, end, side, material='SeatYellow', alternate_material='Green',
                   height=-.02 if start == 1900 else .055)
    for start, end, side, width, material in [(245, 355, -1, 9, 'Runoff'), (965, 1110, -1, 12, 'Runoff'), (1740, 1895, -1, 12, 'Runoff'), (3970, 4160, -1, 16, 'Runoff'), (4650, 4830, -1, 11, 'Runoff')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(245, 355, -1), (965, 1110, -1),
                              (1740, 1895, -1), (3970, 4160, -1), (4650, 4830, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.2, 'RunoffGreen')
