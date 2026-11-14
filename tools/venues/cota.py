"""COTA: rolling spectator hills, stadium stands and the red steel observation veil."""
from __future__ import annotations

import bisect
import math
import struct
from collections.abc import Iterator
from itertools import pairwise

from circuit_dataclasses import Point, RoadStation, WidthControls
from circuit_mesh import add
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import triangulate, unary_union

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
    pit_garages(scene)
    main_grandstand(scene)
    footprint_stand(scene, 460658890, rows=21, seat_material='Concrete')
    scene.stand(1050, 1280, -1, rows=15, setback=28, seat_material='Concrete')
    scene.stand(1850, 1990, -1, rows=15, setback=34, seat_material='Concrete')
    footprint_stand(scene, 460683347, rows=23, seat_material='Concrete')
    footprint_stand(scene, 460658892, rows=22, seat_material='Concrete')
    scene.stand(4840, 4950, -1, rows=17, setback=27, seat_material='Concrete')
    mapped_building(scene, 847781223, 18, facade='Concrete', floors=1, roof='canopy', enclosed=False)
    observation_tower(scene)
    for start, end, side in [(750, 1020, 1), (1200, 1800, -1), (1380, 1810, 1),
                              (1990, 2300, -1), (2660, 3350, 1), (2700, 3300, -1),
                              (4350, 4710, -1), (4780, 5090, 1)]:
        trees(scene, start, end, side, setback=38, spacing=26, rows=2, height=8)
    trees(scene, 2360, 2580, 1, setback=11, spacing=14, rows=2, height=11)
    for station in [220, 490, 1100, 1740, 2390, 3590, 4040, 4510, 4920, 5290]:
        mast(scene, station, -1, 24)


def pit_garages(scene: CircuitScene) -> None:
    building = scene.footprint(376713391)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon):
        raise TypeError('COTA garage footprint must remain connected')
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)
    ring = list(footprint.exterior.coords)[:-1]
    if not footprint.exterior.is_ccw:
        ring.reverse()
    base = scene.at(0).z
    kind = 'Building_CotaPits'
    front_distance = min(scene.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)[1]
                         for a, b in zip(ring, ring[1:] + ring[:1]))
    for a, b in zip(ring, ring[1:] + ring[:1]):
        span = math.dist(a, b)
        if span < .1:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        road, distance = scene.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        front = distance < front_distance + 4 and abs(tx * road.tx + ty * road.ty) > .75
        def point(along: float, outward: float, z: float, *,
                  origin: tuple[float, float] = a, axis: tuple[float, float] = (tx, ty),
                  normal: tuple[float, float] = (nx, ny)) -> Point:
            return (origin[0] + axis[0] * along + normal[0] * outward,
                    origin[1] + axis[1] * along + normal[1] * outward, base + z)
        if not front:
            scene.banner(point(0, 0, 0), point(span, 0, 0), 13.8, 'White', kind)
            continue
        bays = max(1, round(span / 6.5))
        for bay in range(bays):
            left, right = span * bay / bays, span * (bay + 1) / bays
            scene.banner(point(left + .3, -1.4, .05), point(right - .3, -1.4, .05), 4.1, 'Black', kind)
            for u in (left, right):
                scene.beam(kind, 'White', point(u, 0, 0), point(u, 0, 13.8), .38)
            scene.quad(kind, 'Concrete', point(left, 0, .02), point(right, 0, .02),
                       point(right, -1.4, .02), point(left, -1.4, .02), up=True)
            for z in (4.5, 9):
                scene.banner(point(left, 0, z), point(right, 0, z), 4.4, 'White', kind)
                scene.banner(point(left + .35, .045, z + 1.2), point(right - .35, .045, z + 1.2), 1.65, 'Glass', kind)
                scene.quad(kind, 'White', point(left, 0, z), point(right, 0, z),
                           point(right, 2.2, z), point(left, 2.2, z), up=True)
                scene.quad(kind, 'Concrete', point(left, 2.2, z - .25), point(right, 2.2, z - .25),
                           point(right, 0, z - .25), point(left, 0, z - .25), up=False)
                scene.banner(point(left, 2.2, z), point(right, 2.2, z), .32, 'White', kind)
                for lift in (.65, 1.0):
                    scene.beam(kind, 'Steel', point(left, 2.2, z + lift), point(right, 2.2, z + lift), .045)
            front_a, front_b = point(left, 4.8, 14.3), point(right, 4.8, 14.3)
            rear_a, rear_b = point(left, -4, 15.7), point(right, -4, 15.7)
            scene.quad(kind, 'White', front_a, front_b, rear_b, rear_a, up=True)
            scene.quad(kind, 'Concrete', add(front_a, (0, 0, -.18)), add(front_b, (0, 0, -.18)),
                       add(rear_b, (0, 0, -.18)), add(rear_a, (0, 0, -.18)), up=False)
            scene.beam(kind, 'Steel', point(left, 0, 12.8), front_a, .14)
            scene.beam(kind, 'Steel', point(left, 0, 12.8), rear_a, .14)
            scene.beam(kind, 'White', front_a, front_b, .2)
    for triangle in triangulate(footprint):
        if footprint.covers(triangle):
            a, b, c = list(triangle.exterior.coords)[:3]
            scene.triangle(kind, 'Roof', (a[0], a[1], base + 13.8),
                           (b[0], b[1], base + 13.8), (c[0], c[1], base + 13.8))
    scene.landmarks.append({'name': 'COTA pit garages and hospitality', 'osm_id': building.osm_id,
                            'dimensions_status': 'Actual retained footprint; garage6.5m bays, white upper balconies/narrow glass and4.8m projecting roof reconstructed from supplied paint-detail-03 reference. Heights and projections estimated, not surveyed.'})


def main_grandstand(scene: CircuitScene) -> None:
    footprint_stand(scene, 460658889, rows=25, seat_material='Concrete')
    roof = scene.footprint(376713393)
    distances = [scene.nearest(*p)[1] for p in roof.ring]
    low, high = min(distances), max(distances)
    outline = []
    for x, y in roof.ring:
        road, distance = scene.nearest(x, y)
        projection = 16 * max(0, min(1, (high - distance) / max(1, high - low)))
        outline.append((x + (road.x - x) * projection / distance,
                        y + (road.y - y) * projection / distance))
    polygon = Polygon(outline).difference(scene.road_mask.buffer(1.2))
    rectangle = list(polygon.minimum_rotated_rectangle.exterior.coords)
    axis_a, axis_b = max(pairwise(rectangle), key=lambda edge: math.dist(*edge))
    span = math.dist(axis_a, axis_b)
    axis = ((axis_b[0] - axis_a[0]) / span, (axis_b[1] - axis_a[1]) / span)
    normal = (-axis[1], axis[0])
    local_outline = [((x - axis_a[0]) * axis[0] + (y - axis_a[1]) * axis[1],
                      (x - axis_a[0]) * normal[0] + (y - axis_a[1]) * normal[1]) for x, y in outline]
    local = Polygon(local_outline)
    umin, vmin, umax, vmax = local.bounds
    bays = max(1, round((umax - umin) / 10))
    bay_width = (umax - umin) / bays
    def point(x: float, y: float, lift: float = 0) -> Point:
        road, distance = scene.nearest(x, y)
        depth = max(0, min(1, (distance - (low - 16)) / max(1, high - low + 16)))
        along = (x - axis_a[0]) * axis[0] + (y - axis_a[1]) * axis[1]
        phase = ((along - umin) / bay_width) % 1
        scallop = math.sin(math.pi * phase)
        height = 16 + 2 * depth - .8 * scallop * (1 - depth) ** 2 - .45 * scallop * math.sin(math.pi * depth)
        return x, y, road.z + height + lift
    for i in range(math.ceil((umax - umin) / 2)):
        for j in range(math.ceil((vmax - vmin) / 2)):
            cell = local.intersection(box(umin + i * 2, vmin + j * 2,
                                          umin + (i + 1) * 2, vmin + (j + 1) * 2))
            for triangle in triangulate(cell):
                if not cell.covers(triangle):
                    continue
                coordinates = list(triangle.exterior.coords)[:3]
                if not triangle.exterior.is_ccw:
                    coordinates.reverse()
                points = [point(axis_a[0] + u * axis[0] + v * normal[0],
                                axis_a[1] + u * axis[1] + v * normal[1]) for u, v in coordinates]
                scene.triangle('Building_CotaMainRoof', 'White', points[0], points[1], points[2])
                scene.triangle('Building_CotaMainRoof', 'White', add(points[2], (0, 0, -.035)),
                               add(points[1], (0, 0, -.035)), add(points[0], (0, 0, -.035)))
    for a, b in zip(outline, outline[1:] + outline[:1]):
        count = max(1, round(math.dist(a, b) / 10))
        scene.beam('Building_CotaMainRoof', 'Steel', point(*a), point(*b), .24)
        for i in range(count):
            x, y = a[0] + (b[0] - a[0]) * i / count, a[1] + (b[1] - a[1]) * i / count
            road, distance = scene.nearest(x, y)
            if distance < high - 2:
                continue
            base = x, y, scene.ground(x, y)
            scene.beam('Building_CotaMainRoof', 'White', base, point(x, y), .45)
            reach = distance - (low - 16)
            front = x + (road.x - x) * reach / distance, y + (road.y - y) * reach / distance
            upper, lower = point(*front), add(point(*front), (0, 0, -1.1))
            rear_upper, rear_lower = point(x, y), add(point(x, y), (0, 0, -1.1))
            scene.beam('Building_CotaMainRoof', 'Steel', rear_upper, upper, .16)
            scene.beam('Building_CotaMainRoof', 'Steel', rear_lower, lower, .16)
            for cell in range(8):
                t0, t1 = cell / 8, (cell + 1) / 8
                pa = add(rear_lower, ((lower[0] - rear_lower[0]) * t0, (lower[1] - rear_lower[1]) * t0, (lower[2] - rear_lower[2]) * t0))
                pb = add(rear_upper, ((upper[0] - rear_upper[0]) * t1, (upper[1] - rear_upper[1]) * t1, (upper[2] - rear_upper[2]) * t1))
                scene.beam('Building_CotaMainRoof', 'Steel', pa, pb, .1)
    scene.modeled_buildings.add(376713393)
    scene.landmarks.append({'name': 'Mapped main grandstand with cantilever canopy',
                            'osm_id': 460658889, 'roof_osm_id': 376713393,
                            'dimensions_status': 'Actual seating/support footprints retained; rear lounge outline projects16m over the rear seating without extending the uncovered longitudinal end. White tensile fabric has repeating shallow saddle/scalloped bays and a pale underside, replacing the opaque concrete slab. Roof15.2–18m above road,0.8m leading-edge scallop,0.45m interior sag and approximately10m bays are reference-estimated; retained estimated16m reach is unchanged. Original geometry from supplied paint-detail-03 and Walter P Moore structural project description, not a surveyed membrane shape.'})


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
    deck = tower_deck_outline()
    for triangle in triangulate(deck):
        if not deck.covers(triangle):
            continue
        points = [add(base, (x, y, 69.4)) for x, y in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            points.reverse()
        scene.triangle('Building_CotaTower', 'White', points[0], points[1], points[2])
        scene.triangle('Building_CotaTower', 'White', add(points[2], (0, 0, -.8)),
                       add(points[1], (0, 0, -.8)), add(points[0], (0, 0, -.8)))
    deck_ring = list(deck.exterior.coords)
    for a, b in pairwise(deck_ring):
        pa, pb = add(base, (a[0], a[1], 69.4)), add(base, (b[0], b[1], 69.4))
        scene.banner(add(pa, (0, 0, -.8)), add(pb, (0, 0, -.8)), .8, 'White', 'Building_CotaTower')
        scene.banner(pa, pb, 1.3, 'Glass', 'Building_CotaTower')
        scene.beam('Building_CotaTower', 'Steel', add(pa, (0, 0, 1.3)), add(pb, (0, 0, 1.3)), .055)
    scene.landmarks.append({'name': 'Observation tower measured-plan deck',
                            'gross_plan_area_m2': deck.area, 'public_viewing_area_m2': 900 * .3048 ** 2,
                            'source': 'Miró Rivera architect press kit, Viewing Deck Plan p14 and Building Details p20',
                            'dimensions_status': 'Rounded tapered outline digitized from the primary16ft-scale plan, constrained to the architect1362sqft total observation deck/core area. The separately published900sqft is the visitor viewing portion, not the full footprint. Replaces180m² rectangle while retaining original tower position, orientation,69.4m slab top,70.7m rail top and76.5m veil peak. Original plan scale/trace uncertainty approximately0.25m.'})
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


def tower_deck_outline() -> Polygon:
    # Architect p14 scale:150pixels=16ft; pixel551,521 is the elevator/core centre.
    pixels = [(378, 622), (725, 622), (679, 260), (674, 238), (664, 219),
              (648, 201), (625, 189), (596, 182), (552, 180), (508, 182),
              (479, 188), (456, 201), (439, 220), (428, 242), (423, 262)]
    metres = 16 * .3048 / 150
    outline = [((521 - y) * metres, (x - 551) * metres) for x, y in pixels]
    gross_area = 1362 * .3048 ** 2
    correction = math.sqrt(gross_area / Polygon(outline).area)
    return Polygon([(x * correction, y * correction) for x, y in outline])


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(460, 570, -1), (725, 820, 1), (1000, 1075, -1), (1090, 1165, 1), (1180, 1255, -1), (1370, 1460, 1), (1550, 1630, -1), (1725, 1805, 1), (1810, 1890, -1), (2010, 2100, -1), (2400, 2520, -1), (3590, 3720, -1), (3830, 3930, 1), (3940, 4010, 1), (4040, 4140, -1), (4135, 4205, -1), (4360, 4490, 1), (4570, 4700, 1), (4880, 5000, -1), (5170, 5280, -1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    island = t15_island(scene)
    for start, end, side, width, material in [(420, 640, 1, 25, 'Runoff'), (960, 1490, 1, 18, 'Runoff'), (1510, 1930, 1, 18, 'Runoff'), (2350, 2570, 1, 24, 'Runoff'), (3540, 3780, 1, 26, 'Runoff'), (3800, 4170, -1, 24, 'Runoff'), (4200, 4750, -1, 24, 'Runoff'), (4830, 5050, 1, 25, 'Runoff'), (5120, 5330, 1, 23, 'Runoff')]:
        if start not in (2350, 3800, 4200):
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

    star_shapes = [apron_star(scene, 3890, -1, 13, 5.5),
                   apron_star(scene, 4153, -1, 13, 5.5)]
    for station in [4300, 4420, 4540, 4660]:
        star_shapes.append(apron_star(scene, station, -1, 12, 4.5))
    paint_exclusion = unary_union([
        island, *star_shapes, t11_approach_edges(scene), backstraight_edges(scene),
    ])

    for start, end, side, width in [(420, 640, 1, 25), (960, 1490, 1, 18),
                                     (1510, 1930, 1, 18), (2350, 2570, 1, 24),
                                     (3540, 3780, 1, 26), (3800, 4170, -1, 24),
                                     (4200, 4750, -1, 24), (4830, 5050, 1, 25),
                                     (5120, 5330, 1, 23)]:
        paint_band(scene, start, end, side, 1.2, 3.4, 'RunoffGreen', paint_exclusion)
        if start in (3540, 3800, 4200):
            paint_band(scene, start, end, side, 3.4, 4.4, 'RunoffRed', paint_exclusion)
            paint_band(scene, start, end, side, width - 4.4, width - .2, 'RunoffRed', paint_exclusion)
        else:
            paint_band(scene, start, end, side, 3.4, width - .2, 'RunoffRed', paint_exclusion)
    for start, end, side, width in [(3540, 3780, 1, 26), (3800, 3990, -1, 24),
                                     (4200, 4750, -1, 24)]:
        paint_band(scene, start, end, side, 4.4, 5.4, 'White', paint_exclusion)
        paint_band(scene, start, end, side, 5.4, width - 5.4, 'RunoffBlue', paint_exclusion)
        paint_band(scene, start, end, side, width - 5.4, width - 4.4, 'White', paint_exclusion)


def t11_approach_edges(scene: CircuitScene) -> BaseGeometry:
    # The positive-side escape already supplies the base from2350m onward.
    scene.runoff(2220, 2350, 1, 3.4, 'Runoff')
    scene.runoff(2220, 2380, -1, 3.4, 'Runoff')
    shapes: list[Polygon] = []
    for side in (-1, 1):
        scene.kerb(2220, 2380, side, width=.85, height=.045)
        paint_band(scene, 2220, 2380, side, .99, 3.4, 'RunoffRed', Polygon())
        shapes.extend(cell for cell, _sample in apron_cells(scene, 2220, 2380, side, .14, 3.4))
    scene.landmarks.append({
        'name': 'T11 approach legal edges and separate painted apron',
        'start_m': 2220, 'end_m': 2380,
        'source': 'architecture/t11-width/source-review.md and source-index.json',
        'dimensions_status': 'Registered imagery supports an approximately13m legal span at2220–2340m, widening by2380m. Raised0.85m red/white curb and flat red apron reaching3.4m beyond the edge are reconstructed within approximately1m image/epoch uncertainty. Existing barrier corridor, centreline, elevation and banking are retained.',
    })
    return unary_union(shapes)


def backstraight_edges(scene: CircuitScene) -> BaseGeometry:
    scene.runoff(2570, 3540, 1, 3.2, 'Runoff')
    scene.runoff(2520, 3590, -1, 3.2, 'Runoff')
    starts = {name: len(tile.triangles) for name, tile in scene.tiles.items()}
    shapes: list[Polygon] = []
    for side in (-1, 1):
        paint_band(scene, 2520, 3590, side, .15, 3.2, 'RunoffRed', Polygon())
        shapes.extend(cell for cell, _sample in apron_cells(scene, 2520, 3590, side, .15, 3.2))
    collapsed = 0
    for name, tile in scene.tiles.items():
        start = starts.get(name, 0)
        retained = tile.triangles[:start]
        for offset in range(start, len(tile.triangles), 100):
            row = tile.triangles[offset:offset + 100]
            v = struct.unpack_from('<24f', row, 4)
            area = (v[8] - v[0]) * (v[17] - v[1]) - (v[9] - v[1]) * (v[16] - v[0])
            if area == 0:
                collapsed += 1
                continue
            if area > 0:
                row = row[:36] + row[68:100] + row[36:68]
            retained.extend(row)
        tile.triangles = retained
    scene.landmarks.append({
        'name': 'T11–T12 flat red edge strips',
        'start_m': 2520, 'end_m': 3590,
        'paint_faces_collapsed_at_native_precision': collapsed,
        'source': 'architecture/backstraight-width/source-review.md',
        'dimensions_status': 'The middle legal span is estimated at14±1m. The flat painted strips reach3.2m beyond each legal edge, joining the existing T11 exit and T12 approach paving. Extents and paint widths are reference estimates, not a survey. No raised straight kerbs or protection relocation.',
    })
    return unary_union(shapes)


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
    controls = []
    if side == 1 and outer > 20 and start < 2570 and end > 2350:
        controls = TypeAdapter(WidthControls).validate_json(
            (scene.sources / 't11-retained-width.json').read_bytes()).controls_m

    def reach(sample: RoadStation) -> float:
        if not controls or not 2350 <= sample.station <= 2570:
            return outer
        index = bisect.bisect_right(controls, sample.station, key=lambda row: row[0]) - 1
        a, b = controls[index:index + 2]
        t = (sample.station - a[0]) / (b[0] - a[0])
        return outer + (a[1] + (b[1] - a[1]) * t) / 2 - sample.half_width

    count = max(1, math.ceil((end - start) / 2))
    for i in range(count):
        a, b = scene.at(start + (end - start) * i / count), scene.at(start + (end - start) * (i + 1) / count)
        outer_a, outer_b = reach(a), reach(b)
        points = [a.point(side * (a.half_width + inner)), b.point(side * (b.half_width + inner)),
                  b.point(side * (b.half_width + outer_b)), a.point(side * (a.half_width + outer_a))]
        polygon = Polygon([p[:2] for p in points])
        if polygon.is_valid:
            yield polygon, a


def paint_band(scene: CircuitScene, start: float, end: float, side: int,
                inner: float, outer: float, material: str, exclusion: BaseGeometry) -> None:
    for cell, sample in apron_cells(scene, start, end, side, inner, outer):
        scene.paint_surface(cell.difference(scene.surface_mask(sample)).difference(exclusion), material)
    scene.surface_ranges.append({'type': 'apron paint', 'start_m': start, 'end_m': end,
                                 'side': side, 'inner_m': inner, 'outer_m': outer, 'material': material})
