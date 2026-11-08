"""Legacy Hockenheim: continuous Motodrom bowl, exposed steel roofs and blue aprons."""
from __future__ import annotations

import math

from circuit_mesh import add
from circuit_scene import CircuitScene

from venues.west_architecture import apron_band, mapped_building, mast, trees


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4400, 4560, -1, 'PanelWhite')
    scene.branding(0, 230, 1, 'PanelWhite')
    scene.branding(0, 230, -1, 'PanelWhite')
    scene.branding(2760, 3040, 1, 'PanelWhite')
    scene.branding(3720, 3900, 1, 'PanelWhite')
    scene.braking_boards(268, -1)  # Nordkurve
    scene.braking_boards(849, -1)  # Einlauf / T2
    scene.braking_boards(2103, -1)  # Spitzkehre
    scene.braking_boards(2828, 1)  # Mercedes Arena entry
    scene.braking_boards(3801, 1)  # Sachs
    mapped_building(scene, 202491057, 13, facade='Concrete', floors=3, roof='canopy', garage_front=True)
    mapped_building(scene, 256789030, 8, facade='White', floors=2, roof='pitched')
    mapped_building(scene, 232009816, 25, facade='Concrete', floors=7, balconies=True)
    scene.stand(0, 180, -1, rows=28, setback=18, roofed=True, seat_material='SeatRed')
    scene.stand(4430, 4574, -1, rows=28, setback=18, roofed=True, seat_material='SeatRed')
    scene.stand(230, 430, -1, rows=24, setback=25, roofed=True, seat_material='SeatRed')
    scene.stand(3280, 3530, -1, rows=24, setback=22, seat_material='SeatRed')
    scene.stand(3660, 3920, -1, rows=27, setback=27, roofed=True, seat_material='SeatRed')
    scene.stand(3970, 4390, -1, rows=29, setback=18, roofed=True, seat_material='SeatRed')
    for start, end, side in [(500, 780, -1), (1020, 1880, -1), (1060, 1830, 1),
                              (2220, 2650, -1), (2320, 2640, 1), (3060, 3290, 1)]:
        trees(scene, start, end, side, setback=42, rows=3, spacing=15, height=16)
    for station in [170, 800, 1460, 2040, 2770, 3440, 3770, 4240]:
        mast(scene, station, -1, 24)
    # Circular arena control/branding tower, dimensions reconstructed from the race footage.
    sample = scene.at(2930)
    p = sample.point(67)
    base = (p[0], p[1], scene.ground(p[0], p[1]))
    scene.landmarks.append({'name': 'Mercedes arena cylindrical pavilion', 'station_m': 2930,
                            'dimensions_status': 'Approximate67mright offset; original circular pavilion reconstruction from290/330svideo, not a surveyed footprint.'})
    for face in range(36):
        a, b = math.tau * face / 36, math.tau * (face + 1) / 36
        pa, pb = add(base, (math.cos(a) * 10, math.sin(a) * 10, 0)), add(base, (math.cos(b) * 10, math.sin(b) * 10, 0))
        scene.banner(pa, pb, 8, 'White', 'Building_Arena')
        scene.banner(add(pa, (0, 0, 3)), add(pb, (0, 0, 3)), 2, 'Glass', 'Building_Arena')


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(230, 330, 1), (800, 890, 1), (920, 1030, -1), (2040, 2180, 1), (2760, 2870, 1), (2920, 3040, -1), (3400, 3520, 1), (3730, 3870, -1), (4050, 4160, 1), (4220, 4350, 1)]:
        scene.kerb(start, end, side, material='SeatBlue', alternate_material='White')
    for start, end, side, width, material in [(190, 370, -1, 22, 'Runoff'), (760, 1080, -1, 23, 'Runoff'), (1980, 2240, -1, 25, 'Runoff'), (2710, 3090, -1, 22, 'Runoff'), (3360, 3580, -1, 24, 'Gravel'), (3670, 3930, 1, 24, 'Gravel'), (4000, 4390, -1, 20, 'Runoff')]:
        scene.runoff(start, end, side, width, material)

    apron_band(scene, 190, 370, -1, 1.2, 21.8, 'RunoffBlue')
    apron_band(scene, 1980, 2240, -1, 1.2, 24.8, 'RunoffBlue')
