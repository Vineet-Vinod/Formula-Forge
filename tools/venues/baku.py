"""Baku's stone street frontage, planted boulevard and narrow castle climb."""
from __future__ import annotations

import math
import random

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon

from venues.baku_flames import flame_towers
from venues.baku_forecourt import court_forecourt
from venues.baku_philharmonic import philharmonic_hall
from venues.baku_skyline import waterfront_skyline
from venues.coastal_water import coastal_water
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
        (2860, 3290, -1, 'PanelNavy'),
        (2820, 3290, 1, 'PanelNavy'),
        (2480, 2850, -1, 'PanelLenovo'),
        (2480, 2850, 1, 'PanelLenovo'),
    ):
        scene.branding(start, end, side, material)


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    coastal_water(scene)
    court_forecourt(scene)
    custom = {299418016, 152190583, 152190848}
    modern = {200195772, 200195781, 286017123, 152192792, 152192676, 152192493, 152192304}
    for building in scene.buildings:
        if building.osm_id in custom or building.use in {'grandstand', 'roof', 'carport'}:
            continue
        center, _, _, _, _ = frame(building)
        sample, distance = scene.nearest(center[0], center[1])
        if distance > (260 if building.name else 100):
            continue
        h = building.height
        if not any(key in building.tags for key in ('height', 'building:levels')):
            h = 19 if sample.station < 2600 else 15 if sample.station < 3800 else 22
        material = 'BakuStone' if building.osm_id in {299424046, 133847240} else 'Concrete' if building.osm_id in modern else 'Cream'
        facade(scene, building.osm_id, h, 'modern' if building.osm_id in modern else 'classical', material)
    oldcity_relief(scene)
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
    castle_ramp(scene)
    philharmonic_hall(scene)
    waterfront_skyline(scene)
    flame_towers(scene)
    scene.stand(5710, 6000, 1, rows=18, setback=8, roofed=False, seat_material='SeatBlue')
    scene.pit_building(5720, 5990, -1, depth=15, height=6.5, levels=1)
    for start, end, side, offset, spacing in ((0, 430, -1, 7, 17), (550, 1250, 1, 9, 18), (550, 1250, -1, 7, 22), (1400, 2050, 1, 8, 18), (2050, 2500, -1, 9, 20), (3100, 3650, -1, 7, 18), (3800, 4450, -1, 8, 18), (4550, 5650, -1, 10, 17), (4700, 5650, 1, 9, 22)):
        trees(scene, start, end, side, offset, spacing, 12)


def castle_ramp(scene: CircuitScene) -> None:
    kind = 'Building_CastleMasonry'
    course_height, thickness = .34, 3.5
    for station in range(2610, 2850, 2):
        a, b = scene.at(station), scene.at(station + 2)
        front, rear = [], []
        for sample in (a, b):
            lane = -(sample.half_width + .95 + sample.right_shoulder + 1.15)
            outer, inner = sample.point(lane), sample.point(lane - thickness)
            z = scene.ground(*outer[:2])
            front.append((outer[0], outer[1], z))
            rear.append((inner[0], inner[1], scene.ground(*inner[:2])))
        footprint = Polygon([front[0][:2], front[1][:2], rear[1][:2], rear[0][:2]])
        if not footprint.is_valid or footprint.intersects(scene.corridor_mask.buffer(.25)):
            raise ValueError('Reconstructed castle masonry must clear the complete protected road')
        scene.terrain_cutouts.append(footprint)
        height = 9.0 if station < 2760 else 8.5
        top_a, top_b = add(front[0], (0, 0, height)), add(front[1], (0, 0, height))
        scene.quad(kind, 'BakuStone', front[0], front[1], top_b, top_a,
                   math.dist(front[0], front[1]) / 4, height / 4)
        back_a, back_b = (rear[0][0], rear[0][1], top_a[2]), (rear[1][0], rear[1][1], top_b[2])
        scene.quad(kind, 'BakuStone', rear[1], rear[0], back_a, back_b,
                   math.dist(rear[0], rear[1]) / 4, height / 4)
        scene.quad(kind, 'BakuStone', top_a, top_b, back_b, back_a, up=True)
        dx, dy = front[1][0] - front[0][0], front[1][1] - front[0][1]
        span = math.hypot(dx, dy)
        tx, ty = dx / span, dy / span
        nx, ny = ty, -tx
        for course in range(1, int(height / course_height)):
            z = course * course_height
            p = add(front[0], (nx * .009, ny * .009, z))
            q = add(front[1], (nx * .009, ny * .009, z))
            scene.beam(kind, 'Black', p, q, .012)
            offset = (.43 if course % 2 else 0) + .06 * math.sin(course * 2.2)
            for joint in range(3):
                u = offset + joint * .86
                if u > span:
                    continue
                p = (front[0][0] + tx * u + nx * .014,
                     front[0][1] + ty * u + ny * .014,
                     front[0][2] + z - course_height)
                scene.beam(kind, 'Black', p, add(p, (0, 0, course_height)), .012)
        scene.beam(kind, 'BakuStone', add(top_a, (0, 0, .22)), add(top_b, (0, 0, .22)), .75, .44)
        scene.box(kind, 'BakuStone', add(top_a, (0, 0, .88)), 1.05, .8, .88, math.atan2(ty, tx))
    for station, radius, height in [(2642, 4.2, 10.5), (2710, 4.4, 10.2), (2790, 3.8, 10.0), (2840, 4.0, 9.7)]:
        castle_turret(scene, station, radius, height)
    scene.landmarks.append({'name': 'Icherisheher castle-ramp masonry', 'start_m': 2610,
                            'end_m': 2850, 'wall_height_m': 9, 'wall_thickness_m': thickness,
                            'dimensions_status': 'Original reconstruction registered to the supplied234/236s forward and238s rear castle views. The ordinary2570m approach is left unobscured. Azerbaijan UNESCO commission documents8–10m walls/3.5m thickness; localcourse size,tower radii/locations and crenellation dimensions are visual estimates, not an OSM trace. The retained city_wall299450006 is a separate palace wall and is explicitly not used. Protected road and native collision remain unchanged.'})


def castle_turret(scene: CircuitScene, station: float, radius: float, height: float) -> None:
    sample = scene.at(station)
    offset = sample.half_width + .95 + sample.right_shoulder + 1.15 + radius - .6
    center = sample.point(-offset)
    base = scene.ground(*center[:2])
    segments, rows = 48, math.ceil(height / .34)
    kind = 'Building_CastleTurret'
    randomizer = random.Random(round(station))
    ring = [(center[0] + math.cos(i * math.tau / segments) * radius,
             center[1] + math.sin(i * math.tau / segments) * radius) for i in range(segments)]
    footprint = Polygon(ring)
    if footprint.intersects(scene.corridor_mask.buffer(.25)):
        raise ValueError(f'Castle turret at{station} overlaps protected road')
    scene.terrain_cutouts.append(footprint)
    for row in range(rows):
        low, high = height * row / rows, height * (row + 1) / rows
        lower_radius, upper_radius = radius - .42 * low / height, radius - .42 * high / height
        for i in range(segments):
            angles = i * math.tau / segments, (i + 1) * math.tau / segments
            relief = randomizer.uniform(-.018, .018)
            points = [(center[0] + math.cos(angle) * (r + relief),
                       center[1] + math.sin(angle) * (r + relief), base + z)
                      for angle, r, z in [(angles[0], lower_radius, low), (angles[1], lower_radius, low),
                                          (angles[1], upper_radius, high), (angles[0], upper_radius, high)]]
            scene.quad(kind, 'BakuStone', points[0], points[1], points[2], points[3],
                       math.tau * lower_radius / segments / 4, (high - low) / 4)
            scene.beam(kind, 'Black', add(points[2], (0, 0, .004)), add(points[3], (0, 0, .004)), .01)
            if (i + row) % 2 == 0:
                scene.beam(kind, 'Black', points[0], points[3], .01)
    top_radius = radius - .42
    for i in range(segments):
        angle, next_angle = i * math.tau / segments, (i + 1) * math.tau / segments
        p = (center[0] + math.cos(angle) * top_radius, center[1] + math.sin(angle) * top_radius, base + height)
        q = (center[0] + math.cos(next_angle) * top_radius, center[1] + math.sin(next_angle) * top_radius, base + height)
        scene.triangle(kind, 'BakuStone', (center[0], center[1], base + height), p, q)
        if i % 3 == 0:
            scene.box(kind, 'BakuStone', (p[0], p[1], base + height + .45), .8, .75, .9, angle + math.pi / 2)
    for angle in [0., math.pi / 2, math.pi, math.pi * 1.5]:
        r = radius - .22
        x, y = center[0] + math.cos(angle) * (r + .03), center[1] + math.sin(angle) * (r + .03)
        slit_a: Point = (x - math.sin(angle) * .09, y + math.cos(angle) * .09, base + height * .56)
        slit_b: Point = (x + math.sin(angle) * .09, y - math.cos(angle) * .09, slit_a[2])
        scene.banner(slit_a, slit_b, .85, 'Black', kind)


def oldcity_relief(scene: CircuitScene) -> None:
    for osm_id in [299424046, 133847240, 133641457]:
        building = scene.footprint(osm_id)
        original = Polygon(building.ring)
        shape = original.difference(scene.road_mask.buffer(1.2))
        parts = [shape] if isinstance(shape, Polygon) else list(getattr(shape, 'geoms', []))
        base = min(scene.ground(x, y) for x, y in building.ring)
        h = building.height if 'building:levels' in building.tags else 19.0
        floors = int(building.tags.get('building:levels', str(max(2, min(40, round(h / 4.2))))))
        for part in parts:
            if not isinstance(part, Polygon):
                continue
            ring = list(part.exterior.coords)[:-1]
            if not part.exterior.is_ccw:
                ring.reverse()
            for a, b in zip(ring, ring[1:] + ring[:1]):
                span = math.dist(a, b)
                if span < 6:
                    continue
                tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
                nx, ny = ty, -tx
                middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                road, distance = scene.nearest(*middle)
                if distance > 35 or (road.x - middle[0]) * nx + (road.y - middle[1]) * ny <= 0:
                    continue
                bays = max(1, round(span / 3.6))
                for bay in range(bays):
                    center = (bay + .5) * span / bays
                    for floor in range(1, floors):
                        z = base + h * (floor + .18) / floors + h / floors * .64
                        last = None
                        for step in range(9):
                            angle = math.pi * step / 8
                            u = center + math.cos(angle) * 1.05
                            point = (a[0] + tx * u + nx * .14, a[1] + ty * u + ny * .14,
                                     z + math.sin(angle) * .4)
                            if last is not None:
                                scene.beam('Building_OldCityArches', 'White', last, point, .15)
                            last = point
                    if bay % 3 != 1:
                        continue
                    z = base + h / floors
                    corners: list[Point] = [(a[0] + tx * u + nx * depth, a[1] + ty * u + ny * depth, z)
                                            for u, depth in [(center - 1.25, .05), (center + 1.25, .05),
                                                             (center + 1.25, .75), (center - 1.25, .75)]]
                    balcony = Polygon([p[:2] for p in corners])
                    if balcony.intersects(scene.road_mask.buffer(.3)):
                        continue
                    scene.quad('Building_OldCityBalconies', 'White', corners[0], corners[1], corners[2], corners[3], up=True)
                    for a3, b3 in zip(corners[1:], corners[2:] + corners[:1]):
                        scene.beam('Building_OldCityBalconies', 'Steel', add(a3, (0, 0, .8)), add(b3, (0, 0, .8)), .045)
                        for step in range(max(2, round(math.dist(a3, b3) / .22))):
                            t = step / max(2, round(math.dist(a3, b3) / .22))
                            p = (a3[0] + (b3[0] - a3[0]) * t, a3[1] + (b3[1] - a3[1]) * t, z)
                            if not scene.road_mask.covers(ShapePoint(p[:2])):
                                scene.beam('Building_OldCityBalconies', 'Steel', p, add(p, (0, 0, .8)), .025)
        scene.landmarks.append({'osm_id': osm_id, 'name': building.name or 'Mapped Old City approach frontage',
                                'detail_status': 'Actual clipped footprint and tagged storeys retained. Supplied234/236s supports articulated arched upper openings, pale stone surrounds and narrow projecting iron balconies. Individual bay/arch/balcony dimensions and placement are original visual estimates; no template office signboard.'})
