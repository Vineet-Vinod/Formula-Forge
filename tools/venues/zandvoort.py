"""Zandvoort: layered pit roofs and scattered scrub on exposed North Sea dunes."""
from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.west_architecture import apron_band, mapped_building, mast


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4050, 4250, 1, 'PanelWhite')
    scene.branding(4050, 4250, -1, 'PanelWhite')
    scene.branding(0, 280, 1, 'PanelWhite')
    scene.branding(0, 280, -1, 'PanelWhite')
    scene.branding(330, 530, -1, 'PanelDHL')
    scene.branding(790, 970, 1, 'PanelDHL')
    scene.branding(2380, 2610, 1, 'PanelDHL')
    scene.branding(2380, 2480, -1, 'PanelDHL')
    scene.branding(2950, 3160, 1, 'PanelYellow')
    scene.branding(2950, 3160, -1, 'PanelYellow')
    scene.braking_boards(400, -1)  # Tarzan
    scene.braking_boards(873, 1, distances=(100, 50))  # Hugenholtz
    scene.braking_boards(2538, 1)  # T10
    scene.braking_boards(3186, -1)  # Hans Ernst first apex
    mapped_building(scene, 52473177, 13, facade='Concrete', floors=3, roof='canopy', garage_front=True)
    scene.stand(3990, 4240, -1, rows=21, setback=6, roofed=True, seat_material='SeatBlue')
    scene.stand(0, 250, -1, rows=21, setback=6, roofed=True, seat_material='SeatBlue')
    scene.stand(300, 480, -1, rows=21, setback=22, seat_material='SeatBlue')
    scene.stand(680, 820, -1, rows=18, setback=25, seat_material='SeatBlue')
    scene.stand(930, 1050, -1, rows=15, setback=26, seat_material='SeatBlue')
    scene.stand(3000, 3140, -1, rows=16, setback=21, seat_material='SeatBlue')
    scene.stand(3500, 3690, -1, rows=20, setback=23, seat_material='SeatBlue')
    for start, end, side in [(1100, 1510, 1), (1120, 1460, -1), (1790, 2050, 1),
                              (1800, 2040, -1), (2160, 2770, 1), (2150, 2780, -1),
                              (3270, 3460, 1)]:
        dune_scrub(scene, start, end, side)
    dune_scrub(scene, 3650, 3960, 1)
    for station in [220, 720, 1050, 1700, 2230, 2990, 3560, 3910]:
        mast(scene, station, -1, 20)


def dune_scrub(scene: CircuitScene, start: float, end: float, side: int) -> None:
    blocked = unary_union([scene.corridor_mask.buffer(1.5), *scene.extra_corridors,
                           *scene.water_shapes, *[Polygon(b.ring).buffer(2) for b in scene.buildings]])
    shrubs, rocks = 0, 0
    count = max(1, math.ceil((end - start) / 11))
    for i in range(count):
        sample = scene.at(start + (end - start) * (i + .35) / count)
        shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
        for row in range(3):
            lane = side * (sample.half_width + scene.kerb_margin(sample.station) + shoulder + 3 + row * 6)
            p = sample.point(lane)
            x, y = p[0] + math.sin(i * 2.3 + row) * 1.8, p[1] + math.cos(i * 1.7 + row) * 1.8
            if blocked.covers(ShapePoint(x, y)):
                continue
            height = 2.4 + .7 * math.sin(i * 1.4 + row * .8)
            ground = scene.ground(x, y)
            # Start the low crown at terrain level; exposed trunks made former tiny trees read as palms.
            scene.broadleaf((x, y, ground - height * .45), height, i + row * 37)
            shrubs += 1
            if (i + row) % 3:
                continue
            ring: list[Point] = []
            for face in range(7):
                angle = math.tau * face / 7
                rx, ry = x + math.cos(angle) * 1.1, y + math.sin(angle) * .7
                ring.append((rx, ry, scene.ground(rx, ry) + .025))
            peak = (x, y, ground + .26)
            for a, b in zip(ring, ring[1:] + ring[:1]):
                scene.triangle('Building_DuneRocks', 'Concrete', a, b, peak)
            rocks += 1
    scene.vegetation.append({'start_m': start, 'end_m': end, 'side': side,
                             'species_form': 'Low windswept scrub with small exposed stone patches',
                             'shrubs': shrubs, 'rock_patches': rocks,
                             'placement_status': 'Reference865/866.5/868s middle dune and872s final bank vegetation character; individual footprints reconstructed beyond protection/buildings/water. Low crowns start at sampled ground; small rock facets follow sampled terrain rather than fixed-Z tiles.'})


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(340, 480, 1), (680, 770, 1), (805, 950, -1), (1670, 1795, 1), (2030, 2130, 1), (2230, 2340, 1), (2490, 2590, -1), (3130, 3210, 1), (3220, 3290, -1), (3500, 3610, 1), (3720, 3940, 1)]:
        scene.kerb(start, end, side, material='RunoffOrange' if start in (340, 805) else 'Red', alternate_material='White')
    for start, end, side, width, material in [(290, 510, -1, 24, 'Gravel'), (780, 995, 1, 20, 'Gravel'), (1630, 1840, -1, 24, 'Gravel'), (1990, 2170, -1, 22, 'Gravel'), (2190, 2380, -1, 20, 'Gravel'), (2500, 2610, 1, 8, 'Gravel'), (3080, 3320, -1, 18, 'Gravel'), (3460, 3650, -1, 20, 'Gravel')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(290, 510, -1), (3080, 3320, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.1, 'RunoffGreen')
