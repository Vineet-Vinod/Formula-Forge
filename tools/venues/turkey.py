"""Istanbul Park's sloping spectator banks and angular pit hospitality."""
from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import triangulate

from venues.east_architecture import trees
from venues.west_architecture import apron_band


def circuit_edges(scene: CircuitScene) -> None:
    t8_runoff(scene)
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((315, 405, -1), (500, 580, 1), (1040, 1130, -1), (1200, 1290, 1), (1350, 1445, -1), (1950, 2050, 1), (2310, 2450, -1), (2520, 2650, -1), (2720, 2860, -1), (3330, 3420, -1), (3440, 3540, 1), (3940, 4080, 1), (4720, 4820, -1), (4840, 4920, 1), (4940, 5045, -1)):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in ((275, 440, 1, 18, 'Gravel'), (1000, 1160, 1, 15, 'Gravel'), (1910, 2080, -1, 14, 'Gravel'), (3280, 3440, 1, 14, 'RunoffGreen'), (3910, 4110, -1, 13, 'RunoffGreen'), (4660, 4840, 1, 18, 'Gravel'), (4910, 5070, 1, 13, 'RunoffGreen')):
        scene.runoff(start, end, side, width, material)

    for start, end, side in ((500, 580, 1), (1040, 1130, -1), (1200, 1290, 1), (1350, 1445, -1), (1950, 2050, 1), (3330, 3420, -1), (3440, 3540, 1), (3940, 4080, 1)):
        scene.runoff(start, end, side, 2.6, 'RunoffGreen')

    for apex, side, distances in (
        (363, 1, (150, 100, 50)),
        (2004, -1, (150, 100, 50)),
        (3385, 1, (150, 100, 50)),
        (4775, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5130, 5338, -1, 'PanelPurple'),
        (0, 230, -1, 'PanelPurple'),
        (5130, 5338, 1, 'PanelPurple'),
        (0, 230, 1, 'PanelPurple'),
        (4730, 5060, 1, 'PanelPurple'),
        (3550, 3770, 1, 'PanelGreen'),
    ):
        scene.branding(start, end, side, material)


    apron_band(scene, 3440, 3540, 1, 2.35, 2.55, 'White')

def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    pit_garages(scene)
    mainstand_ground(scene)
    scene.stand(5202, 259, 1, rows=29, setback=7, roofed=True, seat_material='SeatRed')
    scene.stand(4600, 4820, 1, rows=21, setback=14, roofed=True, seat_material='SeatRed')
    scene.stand(1100, 1250, 1, rows=16, setback=18, roofed=False, seat_material='SeatRed')
    scene.stand(2860, 3010, 1, rows=16, setback=25, roofed=False, seat_material='SeatRed')
    for start, end, side, setback, spacing in ((500, 1200, -1, 75, 38), (850, 1500, 1, 90, 42), (1500, 2000, -1, 90, 44), (2100, 2800, 1, 105, 43), (2900, 3400, -1, 80, 38), (3550, 4200, 1, 90, 40), (4200, 4550, -1, 80, 42)):
        trees(scene, start, end, side, setback, spacing, 10)


def mainstand_ground(scene: CircuitScene) -> None:
    building = scene.footprint(316361269)
    podium = Polygon(building.ring).buffer(2)
    datum = scene.at(0).z - .015
    # GLO is a surface model: its roof mound buried the actual seating rows.
    scene.ground_patches.append((podium, datum, 'Concrete'))
    span = (259 - 5202) % scene.length
    steps = math.ceil(span / 8)
    for step in range(steps):
        a = scene.at(5202 + span * step / steps)
        b = scene.at(5202 + span * (step + 1) / steps)
        near_a = a.half_width + .95 + a.left_shoulder
        near_b = b.half_width + .95 + b.left_shoulder
        forecourt = Polygon([
            a.point(near_a)[:2], b.point(near_b)[:2],
            b.point(near_b + 9)[:2], a.point(near_a + 9)[:2],
        ]).difference(podium)
        parts = [forecourt] if isinstance(forecourt, Polygon) else (
            list(forecourt.geoms) if isinstance(forecourt, MultiPolygon) else []
        )
        for part in parts:
            if not part.is_empty:
                scene.ground_patches.append((part, datum, 'Grass'))
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({
        'name': 'Main grandstand podium and grass forecourt', 'osm_id': building.osm_id,
        'source_note': 'Actual mapped stand spans native5202–259. Roof-contaminated DSM ground is reconstructed only beneath its footprint plus2m foundation margin and the adjoining protected forecourt. The retained engineering road profile is flat here; its datum grounds the podium. Ground below seats is an estimate, not a classified-ground survey. Reference0329/0333 shows exposed seating rather than a grass mound.',
    })


def pit_garages(scene: CircuitScene) -> None:
    building = scene.footprint(295742112)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon) or footprint.is_empty:
        raise ValueError('Istanbul pit footprint must remain one concave building')
    ring = list(footprint.exterior.coords)[:-1]
    if not footprint.exterior.is_ccw:
        ring.reverse()
    edges = list(zip(ring, ring[1:] + ring[:1]))
    front_edges = []
    for a, b in edges:
        span = math.dist(a, b)
        sample, distance = scene.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        alignment = abs(((b[0] - a[0]) * sample.tx + (b[1] - a[1]) * sample.ty) / max(.01, span))
        if distance < 33 and alignment > .95:
            front_edges.append((a, b))
    origin, end = max(front_edges, key=lambda edge: math.dist(*edge))
    length = math.dist(origin, end)
    axis = (end[0] - origin[0]) / length, (end[1] - origin[1]) / length

    def floor(x: float, y: float) -> float:
        along = (x - origin[0]) * axis[0] + (y - origin[1]) * axis[1]
        return scene.nearest(origin[0] + axis[0] * along,
                             origin[1] + axis[1] * along)[0].z

    kind = 'Building_IstanbulMappedPits'
    for a, b in edges:
        span = math.dist(a, b)
        if span < .1:
            continue
        dx, dy = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        normal = dy, -dx
        front = (a, b) in front_edges
        count = max(1, math.ceil(span / 6.4))
        for bay in range(count):
            def point(u: float, z: float, offset: float = 0, *,
                      edge: tuple[float, float] = a, along: tuple[float, float] = (dx, dy),
                      outward: tuple[float, float] = normal) -> Point:
                x, y = edge[0] + along[0] * u + outward[0] * offset, edge[1] + along[1] * u + outward[1] * offset
                return x, y, floor(x, y) + z
            lo, hi = span * bay / count, span * (bay + 1) / count
            if not front:
                scene.banner(point(lo, 0), point(hi, 0), 16, 'Cream', kind)
                continue
            left, right = point(lo, 0), point(hi, 0)
            road_a, _ = scene.nearest(*left[:2])
            road_b, _ = scene.nearest(*right[:2])
            apron_a = road_a.point(-road_a.half_width - 17.5)
            apron_b = road_b.point(-road_b.half_width - 17.5)
            apron = Polygon([left[:2], right[:2], apron_b[:2], apron_a[:2]])
            if apron.is_valid and apron.area > 1e-6:
                scene.terrain_cutouts.append(apron)
                scene.polygon_surface(apron, 'Runoff', .001, road_a, paved=True)
            scene.banner(point(lo, 4.5), point(hi, 4.5), 11.5, 'Cream', kind)
            scene.banner(point(lo + .25, .1, -1.3), point(hi - .25, .1, -1.3), 4.1, 'Black', kind)
            scene.quad(kind, 'Concrete', point(lo, 0), point(hi, 0),
                       point(hi, 0, -1.3), point(lo, 0, -1.3), up=True)
            for u in (lo, hi):
                scene.beam(kind, 'White', point(u, 0), point(u, 16), .34)
            middle, radius = (lo + hi) / 2, (hi - lo) * .43
            spring = 12.7
            scene.banner(point(middle - radius, 6.2, .035),
                         point(middle + radius, 6.2, .035), spring - 6.2, 'Glass', kind)
            center = point(middle, spring, .035)
            for segment in range(12):
                first, last = math.pi * segment / 12, math.pi * (segment + 1) / 12
                pa = point(middle + radius * math.cos(first), spring + radius * math.sin(first), .035)
                pb = point(middle + radius * math.cos(last), spring + radius * math.sin(last), .035)
                scene.triangle(kind, 'Glass', center, pa, pb)
                scene.triangle(kind, 'Glass', center, pb, pa)
                scene.beam(kind, 'White', pa, pb, .18)
            scene.beam(kind, 'White', point(middle, 6.2, .08), point(middle, spring + radius, .08), .14)
            scene.beam(kind, 'White', point(lo, 5.7, .15), point(hi, 5.7, .15), .28)
            scene.beam(kind, 'White', point(lo, 16, .8), point(hi, 16, .8), .3)
    for triangle in triangulate(footprint):
        if footprint.covers(triangle):
            points = [(x, y, floor(x, y) + 16) for x, y in list(triangle.exterior.coords)[:3]]
            if not triangle.exterior.is_ccw:
                points.reverse()
            scene.triangle(kind, 'Roof', points[0], points[1], points[2])
            scene.triangle(kind, 'White', add(points[2], (0, 0, -.16)),
                           add(points[1], (0, 0, -.16)), add(points[0], (0, 0, -.16)))
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)
    scene.landmarks.append({'name': 'Istanbul mapped pit garages', 'osm_id': building.osm_id,
                            'garage_front_length_m': sum(math.dist(*edge) for edge in front_edges),
                            'height_m': 16, 'source': 'Supplied reference detail0329 and retained OSM295742112',
                            'dimensions_status': 'Actual concave footprint and three collinear road-facing segments replace a438m station strip and overlapping guessed hospitality boxes. Floors follow the main-straight grade projected from the actual garage front, never the nearby T1 branch or DSM roof. Existing16m height is an estimate; garage bays, upper arched glazing and shallow roof are original reconstruction from329s, not a construction survey. End VIP tower heights remain unverified and are not invented.'})


def t8_runoff(scene: CircuitScene) -> None:
    scene.surface_ranges.extend([
        {'type': 'runoff', 'start_m': 2260, 'end_m': 2910, 'side': 1,
         'requested_width_m': 18, 'material': 'Gravel'},
        {'type': 'runoff', 'start_m': 2310, 'end_m': 2860, 'side': 1,
         'requested_width_m': 6, 'material': 'RunoffGreen'},
    ])

    def paved_width(station: float) -> float:
        t = max(0, min(1, (station - 2310) / 25, (2860 - station) / 25))
        return .15 + 5.85 * t * t * (3 - 2 * t)

    for station in range(2260, 2910, 2):
        a, b = scene.at(station), scene.at(station + 2)
        outer = Polygon([a.point(a.half_width + .15)[:2], b.point(b.half_width + .15)[:2],
                         b.point(b.half_width + 18)[:2], a.point(a.half_width + 18)[:2]])
        if not outer.is_valid:
            continue
        outer = outer.difference(scene.surface_mask(a))
        scene.extra_corridors.extend(p for p in ([outer] if isinstance(outer, Polygon) else getattr(outer, 'geoms', []))
                                     if isinstance(p, Polygon))
        paving = Polygon([a.point(a.half_width + .15)[:2], b.point(b.half_width + .15)[:2],
                          b.point(b.half_width + paved_width(station + 2))[:2],
                          a.point(a.half_width + paved_width(station))[:2]])
        green = paving.intersection(outer) if paving.is_valid else Polygon()
        if not green.is_empty:
            scene.polygon_surface(green, 'RunoffGreen', .001, a, paved=True)
        gravel = outer.difference(green)
        if not gravel.is_empty:
            scene.polygon_surface(gravel, 'Gravel', .001, a)
    scene.landmarks.append({'name': 'T8 outside green apron and gravel',
                            'start_m': 2310, 'end_m': 2860, 'side': 1,
                            'green_maximum_width_m': 6, 'outer_runoff_width_m': 18,
                            'source': 'Continuous supplied detail0281 and0285 frames',
                            'dimensions_status': 'Outside-right green paving precedes pale gravel in the reference; inside-left has grass beyond the kerb. The former inside green band and white stripe are removed. Existing18m outer gravel envelope retained;6m paving and25m end tapers are reference estimates. All heights follow native surface samples. No centreline, width, elevation, bank or handling changes.'})
