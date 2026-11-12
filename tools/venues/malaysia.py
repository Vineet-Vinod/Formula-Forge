"""Sepang's double-frontage leaf roofs, wide plantation circuit and pit terraces."""

from __future__ import annotations

import itertools
import math
from collections import Counter
from functools import lru_cache

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon, box

from venues.east_architecture import (
    facade,
    footprint_stand,
    frame,
    trees,
)
from venues.malaysia_crown import end_umbrella
from venues.west_architecture import apron_band


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in (
        (500, 610, 1),
        (655, 730, -1),
        (770, 850, 1),
        (940, 1020, 1),
        (1420, 1550, 1),
        (1810, 1940, -1),
        (2045, 2170, 1),
        (2390, 2490, 1),
        (2520, 2630, 1),
        (3020, 3120, -1),
        (3155, 3260, 1),
        (3380, 3480, 1),
        (3710, 3820, -1),
        (3910, 4020, 1),
        (4070, 4190, 1),
        (4980, 5130, -1),
    ):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in (
        (475, 630, -1, 18, "Gravel"),
        (620, 755, 1, 13, "Gravel"),
        (1390, 1570, -1, 15, "Gravel"),
        (1780, 1960, 1, 14, "Gravel"),
        (2350, 2660, -1, 18, "Gravel"),
        (2970, 3150, 1, 18, "Gravel"),
        (3330, 3520, -1, 13, "Gravel"),
        (3860, 4220, -1, 17, "Gravel"),
        (4940, 5170, 1, 18, "Gravel"),
    ):
        scene.runoff(start, end, side, width, material)

    for start, end, side in (
        (770, 850, 1),
        (1420, 1550, 1),
        (1810, 1940, -1),
        (2045, 2170, 1),
        (2390, 2630, 1),
        (3155, 3260, 1),
        (3380, 3480, 1),
        (3710, 3820, -1),
        (3910, 4190, 1),
    ):
        scene.runoff(start, end, side, 2.6, "RunoffGreen")

    for apex, side, distances in (
        (567, -1, (150, 100, 50)),
        (1495, -1, (150, 100, 50)),
        (3077, 1, (150, 100, 50)),
        (5068, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5290, 5543, -1, 'PanelPetronas'),
        (0, 320, -1, 'PanelPetronas'),
        (5290, 5543, 1, 'PanelPetronas'),
        (0, 320, 1, 'PanelPetronas'),
        (500, 650, -1, 'PanelPetronas'),
    ):
        scene.branding(start, end, side, material)


    apron_band(scene, 1420, 1550, 1, 2.35, 2.55, 'White')
    apron_band(scene, 2390, 2630, 1, 2.35, 2.55, 'White')
    apron_band(scene, 3910, 4190, 1, 2.35, 2.55, 'White')

def main_grandstand(scene: CircuitScene) -> None:
    building = scene.footprint(144247993)
    center, axis, side, length, _width = frame(building)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(3))
    local = affine_transform(footprint, [axis[0], axis[1], side[0], side[1],
                                       -center[0] * axis[0] - center[1] * axis[1],
                                       -center[0] * side[0] - center[1] * side[1]])
    start, low, end, high = local.bounds
    crown_local = local.intersection(box(268.4, low - 1, end + 1, high + 1))
    crown = affine_transform(crown_local, [axis[0], side[0], axis[1], side[1], center[0], center[1]])
    wing_footprint = footprint.difference(crown)
    roof_edges: Counter[tuple[Point, Point]] = Counter()
    roof_edge_direction: dict[tuple[Point, Point], tuple[Point, Point]] = {}
    modules = max(1, round(length / 25))
    bay = (end - start) / modules
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)

    def xy(u: float, v: float) -> tuple[float, float]:
        return center[0] + axis[0] * u + side[0] * v, center[1] + axis[1] * u + side[1] * v

    @lru_cache(maxsize=8192)
    def sections(u: float) -> tuple[tuple[float, float, int], ...]:
        u = max(start + .001, min(end - .001, u))
        cut = local.intersection(LineString([(u, low - 1), (u, high + 1)]))
        parts = [cut] if isinstance(cut, LineString) else list(getattr(cut, 'geoms', []))
        ranges = sorted((p.bounds[1], p.bounds[3]) for p in parts
                        if isinstance(p, LineString) and p.length > .01)
        if len(ranges) == 1 and ranges[0][1] - ranges[0][0] > 35:
            a, b = ranges[0]
            middle = (a + b) / 2
            return ((a, middle, -1), (middle, b, 1))
        return tuple((a, b, -1 if (a + b) / 2 < 0 else 1) for a, b in ranges)

    def section(u: float, v: float) -> tuple[float, float, int]:
        candidates = sections(round(u, 6))
        if not candidates:
            raise ValueError('Sepang mapped wing section must remain connected')
        return min(candidates, key=lambda p: max(p[0] - v, 0, v - p[1]))

    def floor(u: float, v: float) -> float:
        a, b, face = section(u, v)
        x, y = xy(u, b if face > 0 else a)
        return scene.nearest(x, y)[0].z - .015

    def point(u: float, v: float, lift: float) -> Point:
        x, y = xy(u, v)
        return x, y, floor(u, v) + lift

    def roof_point(u: float, v: float) -> Point:
        a, b, face = section(u, v)
        depth = max(.1, b - a)
        fraction = (v - a) / depth if face > 0 else (b - v) / depth
        fraction = max(0., min(1., fraction))
        progress = max(0., min(1., (u - start) / bay - min(modules - 1, int((u - start) / bay))))
        lift = 18.5 + 2.8 * fraction * fraction + 2.6 * math.sin(math.pi * progress) ** 2 * (.3 + .7 * fraction)
        return point(u, v, lift)

    for triangle in constrained_delaunay_triangles(local).geoms:
        p = [point(u, v, .2) for u, v in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            p[1], p[2] = p[2], p[1]
        scene.triangle('Building_SepangConcourse', 'Concrete', p[0], p[1], p[2])
    for module in range(modules):
        module_start = start + bay * module
        for along in range(8):
            u0, u1 = module_start + bay * along / 8, module_start + bay * (along + 1) / 8
            for across in range(32):
                v0, v1 = low + (high - low) * across / 32, low + (high - low) * (across + 1) / 32
                patch = local.intersection(box(u0, v0, u1, v1))
                if u1 > 268.4:
                    patch = patch.difference(crown_local)
                for triangle in constrained_delaunay_triangles(patch).geoms:
                    p = [roof_point(u, v) for u, v in list(triangle.exterior.coords)[:3]]
                    if not triangle.exterior.is_ccw:
                        p[1], p[2] = p[2], p[1]
                    for edge_a, edge_b in ((p[0], p[1]), (p[1], p[2]), (p[2], p[0])):
                        first = round(edge_a[0], 6), round(edge_a[1], 6), round(edge_a[2], 6)
                        last = round(edge_b[0], 6), round(edge_b[1], 6), round(edge_b[2], 6)
                        key = (first, last) if first < last else (last, first)
                        roof_edges[key] += 1
                        roof_edge_direction[key] = first, last
                    scene.triangle('Building_SepangLeafRoof', 'White', p[0], p[1], p[2])
                    scene.triangle('Building_SepangLeafRoof', 'White', add(p[2], (0, 0, -.18)),
                                   add(p[1], (0, 0, -.18)), add(p[0], (0, 0, -.18)))
        for along in range(4):
            u0, u1 = module_start + bay * along / 4, module_start + bay * (along + 1) / 4
            for lo, hi, face in sections(round((u0 + u1) / 2, 6)):
                first = min(sections(round(u0, 6)), key=lambda p: abs((p[0] + p[1]) / 2 - (lo + hi) / 2))
                last = min(sections(round(u1, 6)), key=lambda p: abs((p[0] + p[1]) / 2 - (lo + hi) / 2))
                count = min(25, max(1, int((min(first[1] - first[0], last[1] - last[0]) - 1) / .91)))
                front0, front1 = (first[1], last[1]) if face > 0 else (first[0], last[0])
                for row in range(count):
                    v0, v1 = front0 - face * (.4 + row * .91), front1 - face * (.4 + row * .91)
                    shape = Polygon([(u0, v0), (u1, v1), (u1, v1 - face * .91), (u0, v0 - face * .91)])
                    if not local.covers(shape):
                        continue
                    a, b = point(u0, v0, .8 + row * .47), point(u1, v1, .8 + row * .47)
                    c, d = point(u1, v1 - face * .91, .8 + row * .47), point(u0, v0 - face * .91, .8 + row * .47)
                    scene.quad('Building_SepangStand', 'Concrete', a, b, c, d, up=True)
                    drop = .6 if row == 0 else .47
                    scene.quad('Building_SepangStandRiser', 'Concrete',
                               add(a, (0, 0, -drop)), add(b, (0, 0, -drop)), b, a)
                    scene.quad('Building_SepangStandRiser', 'Concrete',
                               a, b, add(b, (0, 0, -drop)), add(a, (0, 0, -drop)))
                    scene.beam('Building_SepangStand', 'SeatBlue' if module % 6 < 4 else 'SeatRed',
                               add(a, (0, 0, .1)), add(b, (0, 0, .1)), .45, .14)
                    scene.spectators(add(a, (0, 0, .25)), add(b, (0, 0, .25)), row, 'Building_Crowd_Sepang')
        middle = module_start + bay / 2
        for lo, hi, face in sections(round(middle, 6)):
            rear_v = lo + 1 if face > 0 else hi - 1
            for spread in (-.44, -.22, 0., .22, .44):
                target_u = middle + spread * bay
                target_section = section(target_u, (lo + hi) / 2)
                front_v = target_section[1] - .3 if face > 0 else target_section[0] + .3
                previous = add(roof_point(middle, rear_v), (0, 0, -.30))
                for step in range(1, 9):
                    fraction = step / 8
                    u = middle + (target_u - middle) * fraction
                    v = rear_v + (front_v - rear_v) * fraction
                    point_on_rib = add(roof_point(u, v), (0, 0, -.30))
                    if wing_footprint.covers(LineString([previous[:2], point_on_rib[:2]]).buffer(.065)):
                        scene.beam('Building_SepangMembraneRibs', 'White', previous, point_on_rib, .13)
                    previous = point_on_rib
            rear = lo + 1 if face > 0 else hi - 1
            root, mast = point(middle, rear, .2), point(middle, rear, 27)
            if wing_footprint.covers(LineString([root[:2], mast[:2]]).buffer(.3)):
                scene.beam('Building_SepangMasts', 'Steel', root, mast, .5)
            for delta in [-bay * .4, bay * .4]:
                tip_u = middle + delta
                wing = min(sections(round(tip_u, 6)),
                           key=lambda p: abs((p[0] + p[1]) / 2 - (lo + hi) / 2))
                tip_v = wing[1] - .6 if face > 0 else wing[0] + .6
                tip = roof_point(tip_u, tip_v)
                if wing_footprint.covers(LineString([mast[:2], tip[:2]]).buffer(.08)):
                    scene.beam('Building_SepangMasts', 'Steel', mast, tip, .10)
    for edge, count in roof_edges.items():
        if count != 1:
            continue
        edge_a, edge_b = roof_edge_direction[edge]
        scene.quad('Building_SepangLeafFascia', 'White',
                   add(edge_a, (0, 0, -.18)), add(edge_b, (0, 0, -.18)), edge_b, edge_a)
    if not isinstance(crown, Polygon):
        raise TypeError('Sepang round end must remain one mapped crown footprint')
    end_umbrella(scene, crown, center, axis, side, floor(293.99818933, -6.12008151),
                 lambda u, v: roof_point(u, v)[2])
    scene.landmarks.append({'name': 'Sepang mapped double-frontage palm-leaf grandstand',
                            'osm_id': building.osm_id, 'roof_bays': modules,
                            'road_area_removed_m2': round(Polygon(building.ring).area - footprint.area, 3),
                            'dimensions_status': 'Actual concave wing outlines and open central mall gaps retained, with 3 m road clearance. Each wing follows adjacent retained road/concourse floor grade, not roof-contaminated DSM. White membrane modules retain the actual concave footprint and open central mall. Low front edges and rising rear fabric are supported by visible branching ribs below each canopy and rear masts. Bay spacing around 25 m, front spring 18.5 m and rib thickness are unmeasured reconstructions from supplied 122/130/134 s and the operator architecture photo; no road profile or global material changes.'})


def pit_complex(scene: CircuitScene) -> None:
    building = scene.footprint(144362327)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(3))
    center, axis, side, _length, _width = frame(building)
    local = affine_transform(footprint, [axis[0], axis[1], side[0], side[1],
                                       -center[0] * axis[0] - center[1] * axis[1],
                                       -center[0] * side[0] - center[1] * side[1]])
    start, low, end, high = local.bounds
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)

    def xy(u: float, v: float) -> tuple[float, float]:
        return center[0] + axis[0] * u + side[0] * v, center[1] + axis[1] * u + side[1] * v

    def point(u: float, v: float, height: float) -> Point:
        x, y = xy(u, v)
        return x, y, scene.nearest(x, y)[0].z + height

    def front(u: float) -> float:
        cut = local.intersection(LineString([(u, low - 1), (u, high + 1)]))
        if cut.is_empty:
            raise ValueError('Sepang garage section must intersect its mapped footprint')
        return cut.bounds[1]

    def roof_point(u: float, v: float) -> Point:
        along = (u - start) / 32
        progress = along - math.floor(along)
        depth = max(.1, high - front(max(start + .001, min(end - .001, u))))
        across = max(0., min(1., (v - front(max(start + .001, min(end - .001, u)))) / depth))
        return point(u, v, 12.2 + 2.1 * across + .45 * math.sin(math.pi * progress) ** 2)

    ring = list(footprint.exterior.coords)
    for (ax, ay), (bx, by) in itertools.pairwise(ring):
        a, b = (ax, ay, scene.nearest(ax, ay)[0].z), (bx, by, scene.nearest(bx, by)[0].z)
        scene.quad('Building_SepangPits', 'White', a, b, add(b, (0, 0, 10.2)), add(a, (0, 0, 10.2)))
        scene.quad('Building_SepangPits', 'White', b, a, add(a, (0, 0, 10.2)), add(b, (0, 0, 10.2)))
    for triangle in constrained_delaunay_triangles(local).geoms:
        p = [point(u, v, 10.2) for u, v in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            p[1], p[2] = p[2], p[1]
        scene.triangle('Building_SepangPitTerrace', 'Concrete', p[0], p[1], p[2])

    facade_edges = [(min(a[0], b[0]), max(a[0], b[0]))
                    for a, b in itertools.pairwise(local.exterior.coords)
                    if math.dist(a, b) > 264 and (a[1] + b[1]) / 2 < 0]
    if len(facade_edges) != 1:
        raise ValueError('Sepang garages require the retained long road-facing wall')
    facade_start, facade_end = facade_edges[0]
    garage_start = (facade_start + facade_end - 33 * 8) / 2
    for garage in range(33):
        u0, u1 = garage_start + garage * 8, garage_start + (garage + 1) * 8
        v0, v1 = front(u0) - .025, front(u1) - .025
        a, b = point(u0 + .35, v0, .25), point(u1 - .35, v1, .25)
        scene.banner(a, b, 3.0, 'Black', 'Building_SepangGarages')
        scene.beam('Building_SepangGarages', 'White', point(u0, v0, .1), point(u0, v0, 3.6), .38)
        for level in (4.35, 7.5):
            scene.banner(point(u0 + .6, v0, level), point(u1 - .6, v1, level), 1.8,
                         'Glass', 'Building_SepangPitOffices')
        for level in (3.7, 7.0, 10.2):
            scene.beam('Building_SepangPitBalconies', 'White', point(u0, v0 + .55, level),
                       point(u1, v1 + .55, level), 1.15, .25)
            if level < 10:
                scene.beam('Building_SepangPitBalconies', 'Steel', point(u0, v0 + .1, level + .9),
                           point(u1, v1 + .1, level + .9), .055)

    roof_edges: Counter[tuple[Point, Point]] = Counter()
    edge_direction: dict[tuple[Point, Point], tuple[Point, Point]] = {}
    divisions = math.ceil((end - start) / 4)
    for along in range(divisions):
        u0, u1 = start + (end - start) * along / divisions, start + (end - start) * (along + 1) / divisions
        for across in range(12):
            v0, v1 = low + (high - low) * across / 12, low + (high - low) * (across + 1) / 12
            patch = local.intersection(box(u0, v0, u1, v1))
            for triangle in constrained_delaunay_triangles(patch).geoms:
                p = [roof_point(u, v) for u, v in list(triangle.exterior.coords)[:3]]
                if not triangle.exterior.is_ccw:
                    p[1], p[2] = p[2], p[1]
                scene.triangle('Building_SepangPitCanopy', 'White', p[0], p[1], p[2])
                scene.triangle('Building_SepangPitCanopy', 'White', add(p[2], (0, 0, -.18)),
                               add(p[1], (0, 0, -.18)), add(p[0], (0, 0, -.18)))
                for edge_a, edge_b in ((p[0], p[1]), (p[1], p[2]), (p[2], p[0])):
                    first = round(edge_a[0], 6), round(edge_a[1], 6), round(edge_a[2], 6)
                    last = round(edge_b[0], 6), round(edge_b[1], 6), round(edge_b[2], 6)
                    key = (first, last) if first < last else (last, first)
                    roof_edges[key] += 1
                    edge_direction[key] = first, last
    for edge, count in roof_edges.items():
        if count == 1:
            a, b = edge_direction[edge]
            scene.quad('Building_SepangPitCanopyFascia', 'White',
                       add(a, (0, 0, -.18)), add(b, (0, 0, -.18)), b, a)
    for index in range(1, math.floor((end - start) / 16)):
        u = start + index * 16
        first_v = front(u) + .3
        previous = add(roof_point(u, first_v), (0, 0, -.3))
        for across in range(1, 9):
            v = first_v + (high - .4 - first_v) * across / 8
            current = add(roof_point(u, v), (0, 0, -.3))
            if footprint.covers(LineString([previous[:2], current[:2]]).buffer(.08)):
                scene.beam('Building_SepangPitCanopyFrame', 'White', previous, current, .16)
            previous = current
        rear = point(u, high - .8, 10.2)
        head = add(roof_point(u, high - .8), (0, 0, -.3))
        scene.beam('Building_SepangPitCanopyFrame', 'White', rear, head, .24)
    scene.landmarks.append({'name': 'Sepang mapped pit garages and white upper cantilever terraces',
                            'osm_id': building.osm_id, 'garage_count': 33, 'garage_width_m': 8,
                            'body_height_m': 10.2, 'roof_height_estimate_m': '12.2–14.75',
                            'dimensions_status': 'Mapped 345 m compound replaces an invented 573 m generic building. Operator specifies 33 garages 8 m wide and 24 m deep, three office/paddock levels and a refurbished roof terrace. White body, narrower window bands, exposed terrace edges and pale roof/soffits match supplied122/126/130/134 s. Roof profiles and support spacing are explicitly reconstructed estimates; footprint, whole-road clearance and adjacent road-grade foundation are retained.'})

def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    main_grandstand(scene)
    for osm_id in (107364038, 107364100):
        footprint_stand(scene, osm_id, 22, "cantilever")
    pit_complex(scene)
    facade(scene, 1105232836, 8, "modern", "White")
    for osm_id in (107364040, 1106756634, 144359492):
        facade(scene, osm_id, 8, "modern", "Cream")
    for start, end, side, offset, spacing in (
        (650, 1450, -1, 30, 29),
        (650, 1450, 1, 55, 33),
        (1500, 2250, -1, 28, 29),
        (2000, 2850, 1, 43, 31),
        (2850, 3550, -1, 38, 30),
        (3550, 4250, 1, 40, 31),
        (4050, 4800, -1, 34, 29),
        (4800, 5100, -1, 35, 30),
    ):
        trees(scene, start, end, side, offset, spacing, 11, palm=True)
    for start, end, side, offset in (
        (850, 1450, -1, 70),
        (1800, 2450, 1, 100),
        (3100, 3600, -1, 85),
        (3800, 4600, 1, 80),
    ):
        trees(scene, start, end, side, offset, 27, 13)
