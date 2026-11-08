"""Floodlit Corniche, white framed hospitality and twisting coastal skyline."""
from __future__ import annotations

import math

from circuit_scene import CircuitScene

from venues.east_architecture import facade, frame, layered_pit_roofs, mapped, trees


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((260, 335, -1), (380, 450, 1), (515, 565, -1), (815, 875, -1), (940, 1000, 1), (1135, 1200, -1), (1305, 1365, 1), (1420, 1475, 1), (1545, 1605, -1), (1730, 1800, -1), (2180, 2350, -1), (2575, 2650, 1), (2660, 2720, 1), (2790, 2855, -1), (2895, 2965, 1), (3020, 3090, -1), (3390, 3460, 1), (3590, 3670, -1), (3790, 3860, 1), (3935, 4000, 1), (4100, 4170, -1), (4310, 4385, 1), (4590, 4700, -1), (5330, 5490, -1)):
        scene.kerb(start, end, side, width=.95)
    for start, end, side, width, material in ((245, 365, 1, 10, 'RunoffGreen'), (2150, 2370, 1, 14, 'RunoffGreen'), (2770, 2890, 1, 8, 'RunoffGreen'), (3340, 3490, -1, 8, 'RunoffGreen'), (4250, 4420, -1, 9, 'RunoffGreen'), (5290, 5520, 1, 14, 'RunoffGreen')):
        scene.runoff(start, end, side, width, material)

    for apex, side, distances in (
        (299, 1, (150, 100, 50)),
        (2277, 1, (150, 100, 50)),
        (5412, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5830, 6174, 1, 'PanelGreen'),
        (0, 200, 1, 'PanelGreen'),
        (250, 650, 1, 'PanelYellow'),
        (370, 650, -1, 'PanelYellow'),
        (2150, 2380, 1, 'PanelGreen'),
    ):
        scene.branding(start, end, side, material)


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.stand(5810, 6140, -1, rows=22, setback=5, roofed=True, seat_material='SeatBlue')
    scene.stand(180, 360, -1, rows=15, setback=7, roofed=False, seat_material='SeatBlue')
    scene.pit_building(5830, 210, 1, depth=26, height=17, levels=3)
    layered_pit_roofs(scene, 5830, 210, 1, 2, 18.5, 25)
    for station in range(5840, 6360, 16):
        p = scene.at(station)
        for lane in (p.half_width+14, p.half_width+38):
            scene.beam('Building_CornichePits', 'White', p.point(lane), p.point(lane, 19.5), .45)
        a, b = scene.at(station), scene.at(station+14)
        scene.beam('Building_CornichePits', 'White', a.point(a.half_width+13, 11), b.point(b.half_width+13, 11), .5, .4)
        scene.banner(a.point(a.half_width+12.7, 6.5), b.point(b.half_width+12.7, 6.5), 1.25, 'Fence', 'Building_Balcony')
    tower = mapped(scene, 1244131504)
    if tower is not None:
        center, _, _, length, width = frame(tower)
        z = scene.ground(center[0], center[1])
        radius = max(9., min(length, width)*.48)
        height = tower.height if tower.height > 100 else 432.
        for level in range(84):
            z0, z1 = height*level/84, height*(level+1)/84
            taper0 = 1-.57*(level/84)**2
            taper1 = 1-.57*((level+1)/84)**2
            for face in range(4):
                def point(index: int, t: float, h: float, taper: float) -> tuple[float, float, float]:
                    angle = index*math.pi/2+math.pi/4+t*math.pi*.62
                    return center[0]+radius*taper*math.cos(angle), center[1]+radius*taper*math.sin(angle), z+h
                pa, pb = point(face, level/84, z0, taper0), point(face+1, level/84, z0, taper0)
                pc, pd = point(face+1, (level+1)/84, z1, taper1), point(face, (level+1)/84, z1, taper1)
                scene.quad('Building_DiamondTower', 'Glass', pa, pb, pc, pd)
                scene.beam('Building_DiamondTower', 'White', pa, pd, .32)
                scene.beam('Building_DiamondTower', 'Steel', pa, pb, .18)
        scene.modeled_buildings.add(tower.osm_id)
        scene.landmarks.append({'name': 'Diamond Tower', 'osm_id': tower.osm_id, 'height_m': height, 'shape': 'Twisting tapered four-sided tower, tagged height; facade rotation estimated.'})
    facade(scene, 1258744123, 25, 'modern', 'White')
    for building in scene.buildings:
        if building.osm_id in scene.modeled_buildings or building.use == 'grandstand':
            continue
        center, _, _, _, _ = frame(building)
        _, distance = scene.nearest(center[0], center[1])
        if distance < 220:
            facade(scene, building.osm_id, max(10, min(60, building.height)), 'modern', 'White')
    for start, end, side, setback in ((400, 1200, -1, 11), (1350, 2200, 1, 14), (2250, 2800, -1, 13), (3000, 3850, 1, 15), (3950, 4650, -1, 18), (4800, 5400, 1, 12)):
        trees(scene, start, end, side, setback, 52, 9, palm=True)
