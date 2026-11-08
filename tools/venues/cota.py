"""COTA: rolling spectator hills, stadium stands and the red steel observation veil."""
from __future__ import annotations

import math
from collections.abc import Iterator

from circuit_dataclasses import Point, RoadStation
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from shapely.ops import triangulate

from venues.east_architecture import footprint_stand
from venues.west_architecture import (
    apron_star,
    mapped_building,
    mast,
    trees,
)


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(900, 1100, 1, 'PanelGreen')
    scene.branding(900, 1100, -1, 'PanelGreen')
    scene.branding(2380, 2510, 1, 'PanelNavy')
    scene.branding(3340, 3630, 1, 'PanelDHL')
    scene.branding(4020, 4160, 1, 'PanelLenovo')
    scene.braking_boards(517, 1)  # T1 uphill hairpin
    scene.braking_boards(2456, 1)  # T11 hairpin
    scene.braking_boards(3650, 1)  # T12 back-straight stop
    scene.braking_boards(4162, 1, distances=(100, 50))  # T15 stadium
    scene.braking_boards(5221, 1)  # T20 pit return
    mapped_building(scene, 376713391, 14, facade='White', floors=3, roof='canopy', garage_front=True)
    main_grandstand(scene)
    scene.stand(330, 540, -1, rows=21, setback=30, seat_material='Concrete')
    scene.stand(1050, 1280, -1, rows=15, setback=28, seat_material='Concrete')
    scene.stand(1850, 1990, -1, rows=15, setback=34, seat_material='Concrete')
    scene.stand(3510, 3700, -1, rows=23, setback=28, seat_material='Concrete')
    footprint_stand(scene, 460658892, rows=22, seat_material='Concrete')
    scene.stand(4840, 4950, -1, rows=17, setback=27, seat_material='Concrete')
    mapped_building(scene, 847781223, 18, facade='Concrete', floors=1, roof='canopy', enclosed=False)
    observation_tower(scene)
    for start, end, side in [(750, 1020, 1), (1200, 1800, -1), (1380, 1810, 1),
                              (1990, 2300, -1), (2660, 3350, 1), (2700, 3300, -1),
                              (4350, 4710, -1), (4780, 5090, 1)]:
        trees(scene, start, end, side, setback=38, spacing=26, rows=2, height=8)
    for station in [220, 490, 1100, 1740, 2390, 3590, 4040, 4510, 4920, 5290]:
        mast(scene, station, -1, 24)


def main_grandstand(scene: CircuitScene) -> None:
    footprint_stand(scene, 460658889, rows=25, seat_material='Concrete')
    roof = scene.footprint(376713393)
    polygon = Polygon(roof.ring).difference(scene.road_mask.buffer(1.2))
    center = Polygon(roof.ring).centroid
    road = scene.nearest(center.x, center.y)[0]
    distances = [scene.nearest(*p)[1] for p in roof.ring]
    low, high = min(distances), max(distances)

    def point(x: float, y: float, lift: float = 0) -> Point:
        distance = scene.nearest(x, y)[1]
        return x, y, road.z + 14 + 2.5 * (distance - low) / max(1, high - low) + lift

    for triangle in triangulate(polygon):
        if polygon.covers(triangle):
            a, b, c = list(triangle.exterior.coords)[:3]
            scene.triangle('Building_CotaMainRoof', 'Roof', point(*a), point(*b), point(*c))
            scene.triangle('Building_CotaMainRoof', 'Concrete', point(c[0], c[1], -.22), point(b[0], b[1], -.22), point(a[0], a[1], -.22))
    for a, b in zip(roof.ring, roof.ring[1:] + roof.ring[:1]):
        count = max(1, round(math.dist(a, b) / 12))
        scene.beam('Building_CotaMainRoof', 'Steel', point(*a), point(*b), .24)
        for i in range(count):
            x, y = a[0] + (b[0] - a[0]) * i / count, a[1] + (b[1] - a[1]) * i / count
            scene.beam('Building_CotaMainRoof', 'Steel', (x, y, scene.ground(x, y)), point(x, y), .3)
    scene.modeled_buildings.add(376713393)
    scene.landmarks.append({'name': 'Mapped main grandstand and rear canopy',
                            'osm_id': 460658889, 'roof_osm_id': 376713393,
                            'dimensions_status': 'Both actual OSM footprints retained. Roof14–16.5m above adjacent road and25rows reconstructed from reference; no generic5100–5450m stand remains.'})


def observation_tower(scene: CircuitScene) -> None:
    x, y = scene.geo(30.134249, -97.6379009)
    base = (x, y, scene.ground(x, y))
    scene.landmarks.append({'name': 'COTA observation tower', 'osm_id': 7911006730,
                            'height_m': 76.5, 'dimensions_status': 'Mapped OSM position/height corroborated by official251ft; platform/veil widths reconstructed from operator photographs.'})
    for offset in [-2.0, 2.0]:
        scene.beam('Building_CotaTower', 'Concrete', add(base, (offset, 0, 0)), add(base, (offset, 0, 69)), 1.0)
    for z in range(5, 69, 5):
        scene.beam('Building_CotaTower', 'Steel', add(base, (-2, 0, z - 5)), add(base, (2, 0, z)), .14)
        scene.beam('Building_CotaTower', 'Steel', add(base, (2, 0, z - 5)), add(base, (-2, 0, z)), .14)
    scene.box('Building_CotaTower', 'White', add(base, (1, 0, 69)), 15, 12, .8)
    scene.box('Building_CotaTower', 'Glass', add(base, (1, 0, 70)), 14.5, 11.5, 1.4)
    for ribbon in range(18):
        lateral = (ribbon - 8.5) * .64
        previous: Point | None = None
        for segment in range(56):
            t = segment / 55
            if t < .75:
                u = t / .75
                point = add(base, (-5 - 2.5 * (1 - u) ** 2, lateral, 76.5 * u))
            else:
                u = (t - .75) / .25
                point = add(base, (-5 + 20 * u, lateral, 76.5 - 7.5 * u * u))
            if previous is not None:
                scene.beam('Building_CotaTower', 'Red', previous, point, .18)
            previous = point


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(460, 570, -1), (725, 820, 1), (1000, 1075, -1), (1090, 1165, 1), (1180, 1255, -1), (1370, 1460, 1), (1550, 1630, -1), (1725, 1805, 1), (1810, 1890, -1), (2010, 2100, -1), (2400, 2520, -1), (3590, 3720, -1), (3830, 3930, 1), (3940, 4010, 1), (4040, 4140, -1), (4135, 4205, -1), (4360, 4490, 1), (4570, 4700, 1), (4880, 5000, -1), (5170, 5280, -1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    island = t15_island(scene)
    for start, end, side, width, material in [(420, 640, 1, 25, 'Runoff'), (960, 1490, 1, 18, 'Runoff'), (1510, 1930, 1, 18, 'Runoff'), (2350, 2570, 1, 24, 'Runoff'), (3540, 3780, 1, 26, 'Runoff'), (3800, 4170, -1, 24, 'Runoff'), (4200, 4750, -1, 24, 'Runoff'), (4830, 5050, 1, 25, 'Runoff'), (5120, 5330, 1, 23, 'Runoff')]:
        if start not in (3800, 4200):
            scene.runoff(start, end, side, width, material)
            continue
        scene.surface_ranges.append({'type': 'runoff', 'start_m': start, 'end_m': end,
                                     'side': side, 'requested_width_m': width, 'material': material})
        for cell, sample in apron_cells(scene, start, end, side, .15, width):
            remaining = cell.difference(scene.surface_mask(sample)).difference(island)
            pieces = [remaining] if isinstance(remaining, Polygon) else list(getattr(remaining, 'geoms', []))
            for piece in pieces:
                if isinstance(piece, Polygon) and piece.area > 1e-8:
                    scene.extra_corridors.append(piece)
                    scene.polygon_surface(piece, material, .001, sample, paved=True)
    scene.extra_corridors.append(island)
    scene.surface_ranges.append({'type': 'runoff', 'start_m': 4120, 'end_m': 4206,
                                 'side': -1, 'requested_width_m': 24, 'material': 'RunoffRed'})
    scene.polygon_surface(island, 'RunoffRed', .001, scene.at(4153), paved=True)
    scene.landmarks.append({'name': 'T15 red paved inner cap', 'start_m': 4120, 'end_m': 4206,
                            'area_m2': round(island.area, 3), 'side': -1,
                            'source': 'Supplied reference158.70s and161–164s; IMSA2024aerial establishes rounded peninsula boundary, later clip establishes red paved cap.',
                            'registration': 'Inside kerb-following head of peninsula; upstream chord and exact extent reconstructed, not surveyed. Star remains at4153m/left13m.'})

    for start, end, side, width in [(420, 640, 1, 25), (960, 1490, 1, 18),
                                     (1510, 1930, 1, 18), (2350, 2570, 1, 24),
                                     (3540, 3780, 1, 26), (3800, 4170, -1, 24),
                                     (4200, 4750, -1, 24), (4830, 5050, 1, 25),
                                     (5120, 5330, 1, 23)]:
        paint_band(scene, start, end, side, 1.2, 3.4, 'RunoffGreen', island)
        if start in (3540, 3800, 4200):
            paint_band(scene, start, end, side, 3.4, 4.4, 'RunoffRed', island)
            paint_band(scene, start, end, side, width - 4.4, width - .2, 'RunoffRed', island)
        else:
            paint_band(scene, start, end, side, 3.4, width - .2, 'RunoffRed', island)
    for start, end, side, width in [(3540, 3780, 1, 26), (3800, 3990, -1, 24),
                                     (4200, 4750, -1, 24)]:
        paint_band(scene, start, end, side, 4.4, 5.4, 'White', island)
        paint_band(scene, start, end, side, 5.4, width - 5.4, 'RunoffBlue', island)
        paint_band(scene, start, end, side, width - 5.4, width - 4.4, 'White', island)
    apron_star(scene, 3890, -1, 13, 5.5)
    apron_star(scene, 4153, -1, 13, 5.5)
    for station in [4300, 4420, 4540, 4660]:
        apron_star(scene, station, -1, 12, 4.5)


def t15_island(scene: CircuitScene) -> Polygon:
    outline = []
    for station in range(4120, 4207, 2):
        sample = scene.at(station)
        point = sample.point(-sample.half_width - 1.24)
        outline.append(point[:2])
    island = Polygon(outline).difference(scene.surface_mask(scene.at(4153)))
    if not isinstance(island, Polygon) or not island.is_valid or island.is_empty:
        raise ValueError('COTA T15 inner cap must remain one valid kerb-bounded polygon')
    return island


def apron_cells(scene: CircuitScene, start: float, end: float, side: int,
                 inner: float, outer: float) -> Iterator[tuple[Polygon, RoadStation]]:
    count = max(1, math.ceil((end - start) / 2))
    for i in range(count):
        a, b = scene.at(start + (end - start) * i / count), scene.at(start + (end - start) * (i + 1) / count)
        points = [a.point(side * (a.half_width + inner)), b.point(side * (b.half_width + inner)),
                  b.point(side * (b.half_width + outer)), a.point(side * (a.half_width + outer))]
        polygon = Polygon([p[:2] for p in points])
        if polygon.is_valid:
            yield polygon, a


def paint_band(scene: CircuitScene, start: float, end: float, side: int,
                inner: float, outer: float, material: str, island: Polygon) -> None:
    for cell, sample in apron_cells(scene, start, end, side, inner, outer):
        scene.paint_surface(cell.difference(scene.surface_mask(sample)).difference(island), material)
    scene.surface_ranges.append({'type': 'apron paint', 'start_m': start, 'end_m': end,
                                 'side': side, 'inner_m': inner, 'outer_m': outer, 'material': material})
