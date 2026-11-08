"""Baku's stone street frontage, planted boulevard and narrow castle climb."""
from __future__ import annotations

import math

from circuit_mesh import add
from circuit_scene import CircuitScene

from venues.east_architecture import cylinder, facade, frame, mapped, trees


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((155, 210, -1), (495, 550, -1), (1360, 1420, -1), (1585, 1645, 1), (1888, 1945, -1), (2000, 2050, 1), (2370, 2435, 1), (2570, 2625, -1), (2680, 2725, 1), (2770, 2820, -1), (3150, 3205, -1), (3360, 3415, -1), (3595, 3660, -1), (3950, 4010, -1), (4155, 4210, 1), (4385, 4450, -1), (4535, 4610, 1)):
        scene.kerb(start, end, side, width=.72)
    for start, end, side, width, material in ((130, 230, 1, 8, 'Runoff'), (470, 565, 1, 8, 'Runoff'), (1320, 1435, 1, 10, 'Runoff'), (2350, 2455, -1, 7, 'Runoff'), (3550, 3680, 1, 8, 'Runoff'), (3910, 4040, 1, 8, 'Runoff')):
        scene.runoff(start, end, side, width, material)

    for apex, side, distances in (
        (185, 1, (150, 100, 50)),
        (523, 1, (150, 100, 50)),
        (1395, 1, (150, 100, 50)),
        (1616, -1, (100, 50)),
        (2404, -1, (150, 100, 50)),
        (2601, 1, (100, 50)),
        (3631, 1, (150, 100, 50)),
        (3985, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5580, 6003, -1, 'PanelPurple'),
        (0, 210, -1, 'PanelPurple'),
        (5580, 6003, 1, 'PanelPurple'),
        (0, 210, 1, 'PanelPurple'),
        (690, 1340, -1, 'PanelYellow'),
        (690, 1340, 1, 'PanelYellow'),
        (2110, 2380, -1, 'PanelNavy'),
        (2110, 2380, 1, 'PanelNavy'),
    ):
        scene.branding(start, end, side, material)


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    custom = {299418016, 152190583}
    modern = {200195772, 200195781, 286017123, 152192792, 152192676, 152192493, 152192304}
    for building in scene.buildings:
        if building.osm_id in custom or building.use == 'grandstand':
            continue
        center, _, _, _, _ = frame(building)
        sample, distance = scene.nearest(center[0], center[1])
        if distance > (260 if building.name else 100):
            continue
        h = max(10., building.height)
        if not any(key in building.tags for key in ('height', 'building:levels')):
            h = 19 if sample.station < 2600 else 15 if sample.station < 3800 else 22
        facade(scene, building.osm_id, h, 'modern' if building.osm_id in modern else 'classical', 'Concrete' if building.osm_id in modern else 'Cream')
    facade(scene, 152190583, 36, 'mansard')
    tower = mapped(scene, 299418016)
    if tower is not None:
        c, axis, side_axis, _, _ = frame(tower)
        z = scene.ground(c[0], c[1])
        cylinder(scene, (c[0], c[1], z), 8.4, 8.4, 29, 'Cream')
        heading = math.atan2(axis[1], axis[0])
        scene.box('Building_MaidenTower', 'Cream', (c[0]+side_axis[0]*7.5, c[1]+side_axis[1]*7.5, z+14), 7, 10, 28, heading)
        for level in range(9):
            cylinder(scene, (c[0], c[1], z+level*3.2), 8.55, 8.55, .14, 'Concrete')
        for level in range(3):
            for angle in (0., 1.7, 3.4, 5.1):
                window_start = c[0]+8.5*math.cos(angle), c[1]+8.5*math.sin(angle), z+7+level*6
                window_end = window_start[0]-.6*math.sin(angle), window_start[1]+.6*math.cos(angle), window_start[2]
                scene.banner(window_start, window_end, 1.4, 'Black', 'Building_MaidenWindows')
        scene.modeled_buildings.add(tower.osm_id)
        scene.landmarks.append({'name': 'Maiden Tower', 'osm_id': tower.osm_id, 'height_m': 29, 'dimensions': 'Footprint registered, upper dimensions visually estimated.'})
    for station in range(2540, 2860, 5):
        a, b = scene.at(station), scene.at(station+5)
        la = a.half_width+.95+a.left_shoulder+1.1
        lb = b.half_width+.95+b.left_shoulder+1.1
        pa, pb = a.point(-la), b.point(-lb)
        za, zb = scene.ground(pa[0], pa[1]), scene.ground(pb[0], pb[1])
        base_a, base_b = (pa[0], pa[1], za), (pb[0], pb[1], zb)
        height = 9 if station < 2690 else 6.5
        scene.quad('Building_CastleWall', 'Cream', base_a, base_b, add(base_b, (0, 0, height)), add(base_a, (0, 0, height)))
        for row in range(int(height/.6)):
            scene.beam('Building_CastleStone', 'Concrete', add(base_a, (0, 0, row*.6)), add(base_b, (0, 0, row*.6)), .045)
        scene.beam('Building_CastleCrenel', 'Cream', add(base_a, (0, 0, height+.55)), add(base_b, (0, 0, height+.55)), .9, 1.1)
        if station % 10 == 0:
            scene.box('Building_CastleCrenel', 'Cream', add(base_a, (0, 0, height+1.4)), 2.1, 1.2, 1.7, math.atan2(a.ty, a.tx))
    for station, height in ((2580, 15), (2720, 12)):
        p = scene.at(station)
        c = p.point(-(p.half_width+p.left_shoulder+9))
        base = c[0], c[1], scene.ground(c[0], c[1])
        cylinder(scene, base, 6, 6, height, 'Cream', 24)
        cylinder(scene, add(base, (0, 0, height-1)), 6.5, 6.5, 1, 'Concrete', 24)
    scene.landmarks.append({'name': 'Old City curtain wall', 'start_m': 2540, 'end_m': 2860, 'dimensions': 'Reference-estimated wall and turret heights, native curve registration.'})
    scene.stand(5710, 6000, 1, rows=18, setback=8, roofed=False, seat_material='SeatBlue')
    scene.pit_building(5720, 5990, -1, depth=15, height=6.5, levels=1)
    for start, end, side, offset, spacing in ((0, 430, -1, 7, 17), (550, 1250, 1, 9, 18), (550, 1250, -1, 7, 22), (1400, 2050, 1, 8, 18), (2050, 2500, -1, 9, 20), (3100, 3650, -1, 7, 18), (3800, 4450, -1, 8, 18), (4550, 5650, -1, 10, 17), (4700, 5650, 1, 9, 22)):
        trees(scene, start, end, side, offset, spacing, 12)
