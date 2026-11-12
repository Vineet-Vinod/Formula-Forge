"""Portimão: faceted grandstand blades and a circular glazed control tower on dry hills."""
from __future__ import annotations

import itertools
import math
import random

from circuit_dataclasses import Building, Point, SurfaceProjection
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.east_architecture import footprint_stand, frame
from venues.west_architecture import apron_band, mapped_building, mast, trees


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(560, 930, 1, 'PanelWhite')
    scene.branding(560, 930, -1, 'PanelWhite')
    scene.branding(2230, 2400, 1, 'PanelWhite')
    scene.branding(2900, 3020, -1, 'PanelWhite')
    scene.braking_boards(1281.138157, -1)  # Opening right-hander
    scene.braking_boards(1597.443353, -1)  # Curva Lagos
    scene.braking_boards(2329.251761, 1)  # Curva da Torre VIP
    scene.braking_boards(2950.788150, -1)  # Curva Samsung
    scene.braking_boards(3326.722683, 1, distances=(100, 50))  # Curva Craig Jones
    mapped_building(scene, 38167081, 12, facade='White', floors=3, roof='canopy', garage_front=True)
    mapped_building(scene, 38166697, 17, facade='Concrete', floors=1, roof='blades', enclosed=False)
    main_grandstand(scene)
    torre_vip(scene)
    scene.stand(1425.070832, 1535.296422, -1, rows=12, setback=24, seat_material='SeatRed')
    scene.stand(3480.105667, 3570.330375, -1, rows=12, setback=27, seat_material='SeatRed')
    galp_scenery(scene)
    for start, end, side in [(1450, 2120, 1), (1650, 2120, -1), (2430, 2880, 1),
                              (2480, 2860, -1), (3080, 3450, 1), (3220, 3420, -1),
                              (3650, 4100, 1), (3700, 4120, -1)]:
        trees(scene, start, end, side, setback=40, spacing=38, height=5.5, rows=1)
    for station in [400, 1120, 1570, 2320, 2940, 3590, 4260]:
        mast(scene, station, -1, 18)


def main_grandstand(scene: CircuitScene) -> None:
    building = scene.footprint(38166697)
    center, axis, side, roof_length, width = frame(building)
    footprint = Polygon(building.ring)
    for block in range(4):
        first, last = -180 + block * 90 + .15, -180 + (block + 1) * 90 - .15
        corners = [add(center, add(mul(axis, u), mul(side, v)))
                   for u, v in [(first, -width), (last, -width),
                                (last, width), (first, width)]]
        seats = footprint.intersection(Polygon([p[:2] for p in corners]))
        if not isinstance(seats, Polygon) or seats.is_empty:
            raise ValueError('Portimao mainstand must retain four connected mapped blocks')
        identifier = -381666970 - block
        scene.buildings.append(Building(identifier, f'Bancada Principal block {block + 1}',
                                        'grandstand', 17, list(seats.exterior.coords)[:-1],
                                        {'source': 'Original four90m blocks within mapped roof38166697'}))
        footprint_stand(scene, identifier, rows=23, seat_material='SeatRed')
    scene.landmarks.append({'name': 'Bancada Principal dimension correction',
                            'roof_osm_id': building.osm_id, 'roof_length_m': roof_length,
                            'structural_blocks': 4, 'block_length_m': 90,
                            'seating_length_m': 360, 'expansion_joint_gap_m': .3,
                            'source': 'https://dimeconsult.pt/projectos_desenv2.php?ano=2008&id=9&menu=pp',
                            'dimensions_status': 'Structural consultant gives four90m mainstand blocks. Original seating now fits that360m span and mapped roof axis instead of591m of racing-road stations. Actual mapped375m canopy outline and roof geometry are unchanged; end overhangs,23rows and0.3m expansion gaps are reconstruction estimates.'})


def torre_vip(scene: CircuitScene) -> None:
    building = scene.footprint(157736297)
    polygon = Polygon(building.ring)
    center = polygon.centroid
    base = scene.nearest(center.x, center.y)[0].z
    ring = list(building.ring)
    if not polygon.exterior.is_ccw:
        ring.reverse()

    def point(p: tuple[float, float], scale: float, z: float) -> Point:
        return center.x + (p[0] - center.x) * scale, center.y + (p[1] - center.y) * scale, base + z

    kind = 'Building_TorreVIP'
    for a, b in zip(ring, ring[1:] + ring[:1]):
        for level in range(5):
            z = level * 3.6
            pa, pb = point(a, .84, z), point(b, .84, z)
            scene.banner(add(pa, (0, 0, .25)), add(pb, (0, 0, .25)), 3.1, 'Glass', kind)
            scene.beam(kind, 'White', pa, add(pa, (0, 0, 3.6)), .18)
            if level:
                ia, ib, oa, ob = point(a, .84, z), point(b, .84, z), point(a, .95, z), point(b, .95, z)
                scene.quad(kind, 'White', ia, ib, ob, oa, up=True)
                scene.quad(kind, 'Concrete', add(oa, (0, 0, -.24)), add(ob, (0, 0, -.24)),
                           add(ib, (0, 0, -.24)), add(ia, (0, 0, -.24)), up=False)
                scene.banner(add(oa, (0, 0, -.24)), add(ob, (0, 0, -.24)), .28, 'White', kind)
                scene.banner(add(oa, (0, 0, .15)), add(ob, (0, 0, .15)), .8, 'Glass', kind)
                scene.beam(kind, 'Steel', add(oa, (0, 0, .98)), add(ob, (0, 0, .98)), .055)
        ra, rb = point(a, 1.02, 18), point(b, 1.02, 18)
        scene.triangle(kind, 'White', (center.x, center.y, base + 18), ra, rb)
        scene.triangle(kind, 'Concrete', add(rb, (0, 0, -.3)), add(ra, (0, 0, -.3)), (center.x, center.y, base + 17.7))
        scene.banner(add(ra, (0, 0, -.3)), add(rb, (0, 0, -.3)), .35, 'White', kind)
        scene.beam(kind, 'White', point(a, .95, 14.4), point(a, .95, 17.7), .14)
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'name': 'Torre VIP layered circular terraces', 'osm_id': building.osm_id,
                            'height_m': 18, 'levels': 5,
                            'dimensions_status': 'Mapped24-point circular outline and5OSMlevels. Glazed shaft inset to84%, terraces95%, crown102% of outline reconstruct observed projecting profile in173.63/615.30s;18mheight and exact overhang depths are unmeasured.'})


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(4560, 210, 1), (1250, 1305, 1), (1210, 1360, -1), (1380, 1480, 1), (1560, 1650, 1), (1700, 1800, -1), (2260, 2400, -1), (2750, 2870, 1), (2890, 3000, 1), (3280, 3370, -1), (3500, 3680, 1), (3810, 3920, -1), (4020, 4130, -1), (4230, 4380, 1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    galp_outer_apron(scene)
    apron_band(scene, 4530, 230, -1, .15, 3.0, 'RunoffGreen')
    galp_inner_island(scene)
    for start, end, side, width, material in [(1170, 1520, -1, 23, 'Gravel'), (1510, 1690, -1, 20, 'Gravel'), (2220, 2450, 1, 22, 'Gravel'), (2700, 3040, -1, 24, 'Gravel'), (3450, 3730, -1, 24, 'Gravel'), (3770, 4170, 1, 23, 'Gravel'), (4180, 4430, -1, 25, 'Gravel')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(1170, 1520, -1), (1510, 1690, -1),
                              (2220, 2450, 1), (2700, 3040, -1),
                              (3450, 3730, -1), (3770, 4170, 1), (4180, 4430, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.8, 'RunoffGreen')
    for start, end, side in [(2220, 2450, 1), (3450, 3730, -1)]:
        apron_band(scene, start, end, side, 3.8, 5.2, 'RunoffRed')
    apron_band(scene, 1285, 1340, -1, 3.8, 8.0, 'RunoffBlack')


def galp_outer_apron(scene: CircuitScene) -> None:
    start, end = 4530, scene.length + 230
    count = math.ceil((end - start) / 2)

    def width(station: float) -> float:
        taper = max(0, min(1, (station - start) / 50, (end - station) / 40))
        return 3 + 21 * taper * taper * (3 - 2 * taper)

    for index in range(count):
        first = start + (end - start) * index / count
        last = start + (end - start) * (index + 1) / count
        a, b = scene.at(first), scene.at(last)
        shape = Polygon([
            a.point(-a.half_width - .15)[:2],
            b.point(-b.half_width - .15)[:2],
            b.point(-b.half_width - width(last))[:2],
            a.point(-a.half_width - width(first))[:2],
        ]).difference(scene.road_mask)
        if not isinstance(shape, Polygon) or shape.is_empty:
            continue
        scene.surface_ranges.append({
            'type': 'runoff', 'start_m': first % scene.length,
            'end_m': last % scene.length, 'side': -1,
            'requested_width_m': max(width(first), width(last)), 'material': 'Runoff',
        })
        scene.extra_corridors.append(shape)
        scene.polygon_surface(shape, 'Runoff', .001, a, paved=True)


def galp_inner_island(scene: CircuitScene) -> None:
    cells: list[Polygon] = []
    stations = sorted([*range(10, 131, 2), 65])
    for station, end_station in itertools.pairwise(stations):
        a, b = scene.at(station), scene.at(end_station)

        def depth(distance: float) -> float:
            taper = (distance - 10) / 55 if distance <= 65 else (130 - distance) / 65
            return 1.4 + 21 * max(0, min(1, taper))

        polygon = Polygon([
            a.point(a.half_width + 1.4)[:2],
            b.point(b.half_width + 1.4)[:2],
            b.point(b.half_width + depth(end_station))[:2],
            a.point(a.half_width + depth(station))[:2],
        ])
        shape = polygon.difference(scene.road_mask.buffer(1.3))
        if not isinstance(shape, Polygon) or shape.is_empty:
            continue
        scene.surface_ranges.append({
            'type': 'runoff', 'start_m': station, 'end_m': end_station,
            'side': 1, 'requested_width_m': max(depth(station), depth(end_station)),
            'material': 'RunoffBlack',
        })
        cells.append(shape)
        scene.extra_corridors.append(shape)
        scene.terrain_cutouts.append(shape)
        scene.polygon_surface(shape, 'RunoffBlack', .001, a, paved=True)
    island = unary_union(cells)
    sample = scene.at(65)
    anchor = sample.point(sample.half_width + 11)
    rectangle = Polygon([
        (anchor[0] + sample.tx * u - sample.ty * v,
         anchor[1] + sample.ty * u + sample.tx * v)
        for u, v in ((-18, -3.5), (18, -3.5), (18, 3.5), (-18, 3.5))
    ])
    projection = SurfaceProjection(anchor, (sample.tx, sample.ty, 0), 36, 7)
    scene.paint_surface(rectangle.intersection(island), 'GroundAlgarve', projection=projection)
    scene.landmarks.append({
        'name': 'Galp black inner paved island', 'start_m': 10, 'end_m': 130,
        'side': 1, 'area_m2': island.area,
        'registration': 'Direct supplied 667.5 s apex view shows a tapering black island inside the right red/white kerb. Its 120 m length and 22.4 m maximum depth are reconstruction estimates. Original white PORTIMÃO lettering substitutes for the foreshortened, unidentifiable source wordmark; no sponsor identity or copied pixels are claimed.',
        'surface_contract': 'Actual paved triangles exclude the road and inner kerb. Lettering clips to those triangles at +5 mm. Paving enters extra_corridors for root protection synchronization, while the white-line track limits remain separate.',
    })


def galp_scenery(scene: CircuitScene) -> None:
    for block in range(8):
        start = 4510 + block * 35
        galp_stand_block(scene, start, start + 25, roofed=block < 3)
    occupied = [Polygon(building.ring).buffer(2) for building in scene.buildings]
    rng = random.Random(20201115)
    for index in range(37):
        station = 4490 + index * 12
        sample = scene.at(station)
        offset = 54 + rng.uniform(-3, 3)
        x, y, _ = sample.point(-sample.half_width - offset)
        root = ShapePoint(x, y)
        if scene.road_mask.buffer(5).covers(root) or any(p.covers(root) for p in occupied):
            continue
        if any(p.covers(root) for p in scene.extra_corridors + scene.water_shapes):
            continue
        scene.broadleaf((x, y, scene.ground(x, y)), rng.uniform(5.5, 8.5), index + 1500)
    scene.landmarks.append({
        'name': 'Galp outside Sul spectator banks and tree belt',
        'start_m': 4510, 'end_m': (4510 + 7 * 35 + 25) % scene.length,
        'side': -1, 'stand_blocks': 8,
        'registration': 'Operator 2020 seating plan places Sul blocks outside the final right arc; direct 666/667.5 s views show stepped lower seating, a short roofed upper section and trees behind. No mapped OSM Sul footprint exists in the retained source. Eight 25 m blocks, 10 m gaps, 32 m road-edge setback and 11 rows are bounded reconstructions, with approximately 15 m positional uncertainty. Roofs cover only the first three blocks.',
        'ground_contract': 'Each bay and row follows local ground, with monotone tread heights and closed risers. Tree roots use sampled ground behind the terraces and avoid road, paved escape and mapped buildings.',
    })


def galp_stand_block(scene: CircuitScene, start: float, end: float, *, roofed: bool) -> None:
    kind = 'Building_StandGalpSul'
    bays = math.ceil((end - start) / 6)
    for bay in range(bays):
        a = scene.at(start + (end - start) * bay / bays)
        b = scene.at(start + (end - start) * (bay + 1) / bays)
        front_a = a.point(-a.half_width - 32)
        front_b = b.point(-b.half_width - 32)
        previous_a = scene.ground(*front_a[:2]) + .12
        previous_b = scene.ground(*front_b[:2]) + .12
        for row in range(11):
            near_a = a.point(-a.half_width - 32 - row * .9)
            near_b = b.point(-b.half_width - 32 - row * .9)
            far_a = a.point(-a.half_width - 32 - (row + 1) * .9)
            far_b = b.point(-b.half_width - 32 - (row + 1) * .9)
            top_a = max(previous_a + .38, scene.ground(*near_a[:2]) + .18,
                        scene.ground(*far_a[:2]) + .18)
            top_b = max(previous_b + .38, scene.ground(*near_b[:2]) + .18,
                        scene.ground(*far_b[:2]) + .18)
            pa, pb = (near_a[0], near_a[1], top_a), (near_b[0], near_b[1], top_b)
            qa, qb = (far_a[0], far_a[1], top_a), (far_b[0], far_b[1], top_b)
            scene.quad(kind, 'Concrete', pa, pb, qb, qa, up=True)
            scene.quad(kind, 'Concrete', (pa[0], pa[1], previous_a),
                       (pb[0], pb[1], previous_b), pb, pa)
            if bay == 0:
                scene.quad(kind, 'Concrete', pa, qa,
                           (qa[0], qa[1], scene.ground(*qa[:2])),
                           (pa[0], pa[1], scene.ground(*pa[:2])))
            if bay == bays - 1:
                scene.quad(kind, 'Concrete', qb, pb,
                           (pb[0], pb[1], scene.ground(*pb[:2])),
                           (qb[0], qb[1], scene.ground(*qb[:2])))
            scene.beam(kind, 'SeatBlue', add(pa, (0, 0, .22)), add(pb, (0, 0, .22)), .28, .12)
            scene.spectators(pa, pb, row, 'Building_CrowdGalpSul')
            previous_a, previous_b = top_a, top_b
        scene.quad(kind, 'Concrete', qa, qb,
                   (qb[0], qb[1], scene.ground(*qb[:2])),
                   (qa[0], qa[1], scene.ground(*qa[:2])))
        if roofed:
            roof_a = (qa[0], qa[1], previous_a + 3.1)
            roof_b = (qb[0], qb[1], previous_b + 3.1)
            rear_a = a.point(-a.half_width - 50)
            rear_b = b.point(-b.half_width - 50)
            ra = (rear_a[0], rear_a[1], roof_a[2] + .55)
            rb = (rear_b[0], rear_b[1], roof_b[2] + .55)
            scene.quad(kind, 'Roof', roof_a, roof_b, rb, ra, up=True)
            scene.quad(kind, 'Concrete', add(ra, (0, 0, -.16)), add(rb, (0, 0, -.16)),
                       add(roof_b, (0, 0, -.16)), add(roof_a, (0, 0, -.16)), up=False)
            scene.banner(add(roof_a, (0, 0, -.16)), add(roof_b, (0, 0, -.16)), .16, 'Roof', kind)
            for foot, top in ((rear_a, ra), (rear_b, rb)):
                base = (foot[0], foot[1], scene.ground(*foot[:2]))
                scene.beam(kind, 'Steel', base, top, .16)
            scene.beam(kind, 'Steel', add(roof_a, (0, 0, -.22)), add(ra, (0, 0, -.22)), .16)
