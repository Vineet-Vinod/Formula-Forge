"""Spa: valley pit complexes, gabled Eau Rouge chalet and deep Ardennes woodland."""
from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from shapely.ops import triangulate

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
    endurance_garages(scene)
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


def endurance_garages(scene: CircuitScene) -> None:
    building = scene.footprint(77352249)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon) or footprint.is_empty:
        return
    scene.modeled_buildings.add(building.osm_id)
    kind = 'Building_Endurance'
    height = 6.4

    def point(x: float, y: float, lift: float = 0) -> Point:
        return x, y, scene.nearest(x, y)[0].z - .015 + lift

    ring = list(footprint.exterior.coords)[:-1]
    winding = 1 if footprint.exterior.is_ccw else -1
    for a, b in zip(ring, ring[1:] + ring[:1]):
        span = math.dist(a, b)
        if span < .05:
            continue
        dx, dy = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        normal = (dy * winding * .045, -dx * winding * .045, 0.)
        count = max(1, math.ceil(span / 6))
        for bay in range(count):
            left = point(a[0] + dx * span * bay / count, a[1] + dy * span * bay / count)
            right = point(a[0] + dx * span * (bay + 1) / count, a[1] + dy * span * (bay + 1) / count)
            scene.quad(kind, 'Concrete', left, right, add(right, (0, 0, height)), add(left, (0, 0, height)))
            sample, distance = scene.nearest((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)
            front = distance < 24 and abs(dx * sample.tx + dy * sample.ty) > .8
            if not front:
                continue
            inner_left = tuple(left[i] + (right[i] - left[i]) * .07 + normal[i] for i in range(3))
            inner_right = tuple(left[i] + (right[i] - left[i]) * .93 + normal[i] for i in range(3))
            la: Point = inner_left[0], inner_left[1], inner_left[2]
            rb: Point = inner_right[0], inner_right[1], inner_right[2]
            scene.quad(kind, 'Steel', add(la, (0, 0, .25)), add(rb, (0, 0, .25)),
                       add(rb, (0, 0, 3.35)), add(la, (0, 0, 3.35)))
            scene.quad(kind, 'Glass', add(la, (0, 0, 4.1)), add(rb, (0, 0, 4.1)),
                       add(rb, (0, 0, 6.05)), add(la, (0, 0, 6.05)))
            scene.beam(kind, 'Red', left, add(left, (0, 0, height)), .18)
            scene.beam(kind, 'White', add(left, (0, 0, 3.65)), add(right, (0, 0, 3.65)), .22, .34)
            scene.beam(kind, 'Steel', add(left, (0, 0, height)), add(right, (0, 0, height)), .16)

    rectangle = list(footprint.minimum_rotated_rectangle.exterior.coords)
    a, b = max(pairwise(rectangle), key=lambda pair: math.dist(*pair))
    span = math.dist(a, b)
    axis = ((b[0] - a[0]) / span, (b[1] - a[1]) / span)
    side = (-axis[1], axis[0])
    coordinates = [(x * axis[0] + y * axis[1], x * side[0] + y * side[1]) for x, y in ring]
    low, high = min(p[1] for p in coordinates), max(p[1] for p in coordinates)
    start, end = min(p[0] for p in coordinates), max(p[0] for p in coordinates)
    count = math.ceil((end - start) / 6)
    for bay in range(count):
        u0, u1 = start + (end - start) * bay / count, start + (end - start) * (bay + 1) / count
        strip = Polygon([(axis[0] * u + side[0] * v, axis[1] * u + side[1] * v)
                         for u, v in [(u0, low - 1), (u1, low - 1), (u1, high + 1), (u0, high + 1)]])
        roof = footprint.intersection(strip)
        for triangle in triangulate(roof):
            if roof.covers(triangle):
                pa, pb, pc = [point(x, y, height + .12) for x, y in list(triangle.exterior.coords)[:3]]
                if not triangle.exterior.is_ccw:
                    pb, pc = pc, pb
                scene.triangle(kind, 'Roof', pa, pb, pc)
                scene.triangle(kind, 'Roof', pc, pb, pa)
    scene.landmarks.append({'osm_id': building.osm_id, 'name': building.name,
                            'structure': 'Graded Endurance garage row with red piers, grey doors and upper glazing',
                            'height_m': height, 'foundation': 'Each footprint vertex follows adjacent native road grade; no single centroid foundation.',
                            'dimensions_status': 'Mapped footprint retained. Height, six-metre maximum bay spacing and shallow roof reconstructed from SRO2024 briefing p11; not a building survey.'})


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(480, 540, 1), (550, 620, -1), (1115, 1240, 1), (1800, 1870, -1), (1880, 1960, 1), (1980, 2055, -1), (3160, 3220, 1), (3235, 3320, -1), (3400, 3500, 1), (3800, 3935, 1), (4060, 4155, -1), (4670, 4820, -1), (5300, 5375, 1), (5410, 5485, -1), (5700, 5780, 1), (5900, 6030, 1), (6720, 6860, -1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='Yellow')
    for start, end, side, width, material in [(440, 655, -1, 17, 'Runoff'), (1070, 1290, -1, 22, 'Runoff'), (1800, 2100, 1, 24, 'Gravel'), (3100, 3530, -1, 24, 'Gravel'), (3750, 3990, -1, 23, 'Gravel'), (4620, 4890, 1, 24, 'Gravel'), (5250, 5530, -1, 22, 'Gravel'), (6670, 6900, 1, 21, 'Gravel')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(440, 655, -1), (1070, 1290, -1)]:
        apron_band(scene, start, end, side, 1.2, 2.8, 'RunoffGreen')
        apron_band(scene, start, end, side, 2.8, 6.0, 'RunoffRed')
