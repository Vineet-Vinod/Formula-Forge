"""Legacy Hockenheim: continuous Motodrom bowl, exposed steel roofs and blue aprons."""
from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.ops import polygonize, unary_union

from venues.west_architecture import apron_band, mapped_building, mast, trees


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4400, 4560, -1, 'PanelWhite')
    scene.branding(0, 230, 1, 'PanelWhite')
    scene.branding(0, 230, -1, 'PanelWhite')
    scene.branding(2760, 3040, 1, 'PanelWhite')
    scene.branding(3720, 3900, 1, 'PanelWhite')
    scene.braking_boards(268, -1)  # Nordkurve
    scene.braking_boards(849, -1)  # Einlauf / T2
    scene.braking_boards(2103, -1)  # Spitzkehre
    scene.braking_boards(2828, 1)  # Mercedes Arena entry
    scene.braking_boards(3801, 1)  # Sachs
    boxengebaeude(scene)
    mapped_building(scene, 256789030, 8, facade='White', floors=2, roof='pitched')
    mapped_building(scene, 232009816, 25, facade='Concrete', floors=7, balconies=True)
    scene.stand(0, 180, -1, rows=28, setback=18, roofed=True, seat_material='SeatRed')
    scene.stand(4430, 4574, -1, rows=28, setback=18, roofed=True, seat_material='SeatRed')
    scene.stand(230, 430, -1, rows=24, setback=25, roofed=True, seat_material='SeatRed')
    scene.stand(3280, 3530, -1, rows=24, setback=22, seat_material='SeatRed')
    scene.stand(3660, 3920, -1, rows=27, setback=27, roofed=True, seat_material='SeatRed')
    scene.stand(3970, 4390, -1, rows=29, setback=18, roofed=True, seat_material='SeatRed')
    for start, end, side in [(500, 780, -1), (1020, 1880, -1), (1060, 1830, 1),
                              (2220, 2650, -1), (2320, 2640, 1), (3060, 3290, 1)]:
        trees(scene, start, end, side, setback=42, rows=3, spacing=15, height=16)
    einlauf_woods(scene)
    for station in [170, 800, 1460, 2040, 2770, 3440, 3770, 4240]:
        mast(scene, station, -1, 24)
    # Circular arena control/branding tower, dimensions reconstructed from the race footage.
    sample = scene.at(2930)
    p = sample.point(67)
    base = (p[0], p[1], scene.ground(p[0], p[1]))
    scene.landmarks.append({'name': 'Mercedes arena cylindrical pavilion', 'station_m': 2930,
                            'dimensions_status': 'Approximate67mright offset; original circular pavilion reconstruction from290/330svideo, not a surveyed footprint.'})
    for face in range(36):
        a, b = math.tau * face / 36, math.tau * (face + 1) / 36
        pa, pb = add(base, (math.cos(a) * 10, math.sin(a) * 10, 0)), add(base, (math.cos(b) * 10, math.sin(b) * 10, 0))
        scene.banner(pa, pb, 8, 'White', 'Building_Arena')
        scene.banner(add(pa, (0, 0, 3)), add(pb, (0, 0, 3)), 2, 'Glass', 'Building_Arena')


def einlauf_woods(scene: CircuitScene) -> None:
    outer_lines: list[LineString] = []
    inner_lines: list[LineString] = []
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.type != 'relation' or element.id != 2165864:
                continue
            for member in element.members:
                if member.type != 'way' or len(member.geometry) < 2:
                    continue
                line = LineString([scene.geo(p.lat, p.lon) for p in member.geometry])
                (inner_lines if member.role == 'inner' else outer_lines).append(line)
    outer = unary_union(list(polygonize(unary_union(outer_lines))))
    inner = unary_union(list(polygonize(unary_union(inner_lines))))
    route = [scene.at(station) for station in range(760, 1061, 20)]
    bounds = box(min(p.x for p in route) - 220, min(p.y for p in route) - 220,
                 max(p.x for p in route) + 220, max(p.y for p in route) + 220)
    forest = outer.difference(inner).intersection(bounds)
    if forest.is_empty:
        raise ValueError('Retained Hockenheimer Hardt forest must intersect Einlauf context')
    blocked = unary_union([scene.corridor_mask.buffer(4), *scene.extra_corridors,
                           *scene.water_shapes, *[Polygon(b.ring).buffer(3) for b in scene.buildings]])
    xmin, ymin, xmax, ymax = forest.bounds
    count = 0
    for row in range(math.floor(ymin / 14), math.ceil(ymax / 14)):
        for column in range(math.floor(xmin / 14), math.ceil(xmax / 14)):
            x, y = column * 14 + (row % 2) * 5, row * 14
            point = ShapePoint(x, y)
            if not forest.covers(point) or blocked.covers(point):
                continue
            station = scene.nearest(x, y)[0].station
            if not 780 <= station < 1020:
                continue
            height = 15 + 1.8 * math.sin(column * 1.4 + row * .73)
            scene.broadleaf((x, y, scene.ground(x, y)), height, column + row * 31)
            count += 1
    scene.vegetation.append({'start_m': 780, 'end_m': 1020, 'species_form': 'Mapped woodland canopy',
                             'trees': count, 'osm_relation': 2165864,
                             'placement_status': 'Actual SchwetzingerHardt forest boundary including inner clearings; trunks outside native corridors/water/buildings.14m spacing and13.2–16.8m heights are original reference reconstruction; no extra forest in cleared infield.'})


def boxengebaeude(scene: CircuitScene) -> None:
    building = scene.footprint(202491057)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon):
        raise TypeError('Hockenheim pit footprint must remain connected')
    ring = list(footprint.exterior.coords)[:-1]
    if not footprint.exterior.is_ccw:
        ring.reverse()
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)
    edges = list(zip(ring, ring[1:] + ring[:1]))
    long_edges = sorted(edges, key=lambda e: math.dist(*e), reverse=True)[:2]
    front_a, front_b = min(long_edges, key=lambda e: scene.nearest((e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2)[1])
    length = math.dist(front_a, front_b)
    axis = (front_b[0] - front_a[0]) / length, (front_b[1] - front_a[1]) / length
    normal = axis[1], -axis[0]
    depth = footprint.area / length
    base = scene.nearest(*front_a)[0].z
    kind = 'Building_HockenheimPits'
    def point(u: float, v: float, z: float) -> Point:
        return front_a[0] + axis[0] * u + normal[0] * v, front_a[1] + axis[1] * u + normal[1] * v, base + z
    scene.banner(point(0, -depth, 0), point(length, -depth, 0), 8.8, 'White', kind)
    scene.banner(point(0, 0, 0), point(0, -depth, 0), 8.8, 'White', kind)
    scene.banner(point(length, -depth, 0), point(length, 0, 0), 8.8, 'White', kind)
    count = max(1, round(length / 6.4))
    for bay in range(count):
        left, right = length * bay / count, length * (bay + 1) / count
        scene.banner(point(left + .28, -1.6, .08), point(right - .28, -1.6, .08), 4.0, 'Black', kind)
        scene.banner(point(left, 0, 4.35), point(right, 0, 4.35), 4.45, 'White', kind)
        scene.banner(point(left + .3, .04, 5.7), point(right - .3, .04, 5.7), 1.75, 'Glass', kind)
        for u in (left, right):
            scene.beam(kind, 'White', point(u, 0, 0), point(u, 0, 8.8), .38)
            scene.beam(kind, 'Steel', point(u, 0, 7.9), point(u, 2.5, 8.85), .12)
        scene.quad(kind, 'Concrete', point(left, 0, .03), point(right, 0, .03),
                   point(right, -1.6, .03), point(left, -1.6, .03), up=True)
        scene.quad(kind, 'White', point(left, 0, 4.35), point(right, 0, 4.35),
                   point(right, 1.1, 4.35), point(left, 1.1, 4.35), up=True)
        scene.quad(kind, 'Concrete', point(left, 1.1, 4.15), point(right, 1.1, 4.15),
                   point(right, 0, 4.15), point(left, 0, 4.15), up=False)
        scene.beam(kind, 'White', point(left, 0, 4.35), point(right, 0, 4.35), .5, .3)
        scene.beam(kind, 'White', point(left, 0, 8.45), point(right, 0, 8.45), .65, .3)
    roof_sections = [(2.5, 8.85, -depth / 2, 10.6), (-depth / 2, 10.6, -depth - .7, 8.85)]
    for va, za, vb, zb in roof_sections:
        a, b, c, d = point(0, va, za), point(length, va, za), point(length, vb, zb), point(0, vb, zb)
        scene.quad(kind, 'White', a, b, c, d, up=True)
        scene.quad(kind, 'Concrete', add(d, (0, 0, -.16)), add(c, (0, 0, -.16)),
                   add(b, (0, 0, -.16)), add(a, (0, 0, -.16)), up=False)
        scene.beam(kind, 'White', a, b, .2)
    scene.landmarks.append({'name': 'Hockenheim Boxengebäude', 'osm_id': building.osm_id,
                            'dimensions_status': 'Actual LGL-attributed OSM footprint and tagged white gabled roof retained. Original6.4m-class recessed garage bays, one narrow upper glazing band, white piers/floor slab and2.5m overhang follow supplied48.33s direct reference.8.8m eave/10.6m ridge and facade dimensions estimated, not surveyed; replaces generic13m three-storey glass wall.'})


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(230, 330, 1), (800, 890, 1), (920, 1030, -1), (2040, 2180, 1), (2760, 2870, 1), (2920, 3040, -1), (3400, 3520, 1), (3730, 3870, -1), (4050, 4160, 1), (4220, 4350, 1)]:
        scene.kerb(start, end, side, material='RunoffNavy' if start in (230, 2040) else 'SeatBlue', alternate_material='White')
    for start, end, side, width, material in [(190, 370, -1, 22, 'Runoff'), (760, 1080, -1, 23, 'Runoff'), (1980, 2240, -1, 25, 'Runoff'), (2710, 3090, -1, 22, 'Runoff'), (3360, 3580, -1, 24, 'Gravel'), (3670, 3930, 1, 24, 'Gravel'), (4000, 4390, -1, 20, 'Runoff')]:
        scene.runoff(start, end, side, width, material)

    apron_band(scene, 190, 370, -1, 1.2, 21.8, 'RunoffNavy')
    apron_band(scene, 1980, 2240, -1, 1.2, 24.8, 'RunoffNavy')
