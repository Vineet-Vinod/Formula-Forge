"""Monaco: inhabited terraces, a real tunnel volume and ornate Casino Square masses."""
from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import LineString, box
from shapely.geometry import Point as ShapePoint
from shapely.ops import polygonize, triangulate, unary_union

from venues.west_architecture import dome, mapped_building, mast, trees, water


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(30, 200, 1, 'PanelWhite')
    scene.branding(30, 200, -1, 'PanelWhite')
    scene.branding(250, 340, -1, 'PanelYellow')
    scene.branding(2170, 2440, -1, 'PanelPurple')
    scene.branding(2170, 2400, 1, 'PanelPurple')
    scene.branding(1260, 1370, 1, 'PanelGreen')
    scene.braking_boards(262, -1)  # Sainte-Devote
    scene.braking_boards(1183, -1)  # Mirabeau Haute
    scene.braking_boards(2130, 1)  # Nouvelle chicane / tunnel exit
    scene.braking_boards(2431, 1, distances=(100, 50))  # Tabac
    water(scene)
    harbour(scene)
    for osm_id, height, floors in [(161880705, 61, 18), (94399585, 54, 16),
                                   (94399672, 14, 4), (94400205, 20, 6),
                                   (94399922, 48, 14), (94399524, 81, 26),
                                   (161775596, 11, 3), (94399684, 54, 16),
                                   (94399872, 75, 22), (176722821, 11, 3)]:
        mapped_building(scene, osm_id, height, floors=floors, balconies=True)
    mapped_building(scene, 2093796, 24, floors=7, balconies=True,
                    base_z=scene.at(1750).z + 5.8, elevated=True)
    mapped_building(scene, 8280869, 24, floors=6, roof='pitched', balconies=True, base_z=scene.at(946).z)
    hotel_crowns(scene)
    casino(scene)
    tunnel(scene)
    scene.pit_building(3070, 3330, side=1, depth=12, height=10, levels=3)
    scene.stand(0, 180, -1, rows=15, setback=6, seat_material='Concrete')
    scene.stand(2350, 2490, 1, rows=18, setback=8, seat_material='Concrete')
    scene.stand(2570, 2680, 1, rows=18, setback=8, seat_material='Concrete')
    for start, end, side, setback in [(280, 550, 1, 10), (700, 870, 1, 8),
                                      (1050, 1170, -1, 8), (1280, 1440, -1, 10)]:
        trees(scene, start, end, side, setback=setback, rows=1, spacing=16, height=9)
    trees(scene, 860, 1030, 1, setback=20, rows=1, spacing=20, height=10, palms=True)
    trees(scene, 1250, 1410, 1, setback=16, rows=1, spacing=17, height=10, palms=True)
    for station in [200, 920, 1370, 2200, 2440, 2950, 3260]:
        mast(scene, station, -1, 12)


def tunnel(scene: CircuitScene) -> None:
    scene.landmarks.append({'name': 'Fairmont tunnel', 'start_m': 1520, 'end_m': 2010,
                            'dimensions_status': 'Path follows native road. Walls0.85moutside white line, ceiling5.4mabove road; original reconstruction from414/450/558sframes.'})
    count = 123
    for segment in range(count):
        a, b = scene.at(1520 + 490 * segment / count), scene.at(1520 + 490 * (segment + 1) / count)
        for side in [-1, 1]:
            pa, pb = a.point(side * (a.half_width + .85)), b.point(side * (b.half_width + .85))
            scene.quad('Building_Tunnel', 'Concrete', pa, pb, add(pb, (0, 0, 5.4)), add(pa, (0, 0, 5.4)), 6, 8)
            for z in [.9, 1.8, 2.7, 3.6, 4.5]:
                scene.beam('Building_Tunnel', 'White', add(pa, (0, 0, z)), add(pb, (0, 0, z)), .035)
            scene.beam('Building_Tunnel', 'White', pa, add(pa, (0, 0, 5.4)), .035)
        la, ra = a.point(-a.half_width - .85, 5.4), a.point(a.half_width + .85, 5.4)
        lb, rb = b.point(-b.half_width - .85, 5.4), b.point(b.half_width + .85, 5.4)
        scene.quad('Building_Tunnel', 'Cream', ra, rb, lb, la)
        scene.beam('Building_Tunnel', 'Concrete', la, ra, .07)
        if segment % 2 == 0:
            for side in [-1, 1]:
                p = a.point(side * (a.half_width - .4), 5.15)
                q = b.point(side * (b.half_width - .4), 5.15)
                scene.beam('Building_Tunnel', 'Lamp', p, q, .18, .10)


def hotel_crowns(scene: CircuitScene) -> None:
    building = scene.footprint(8280869)
    ring = building.ring
    center = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    sample, _ = scene.nearest(*center)
    base = sample.z + 24
    # Rounded corner crowns and pronounced cornices distinguish the palace from apartment slabs.
    corners = [min(ring, key=lambda p: p[0] + p[1]), max(ring, key=lambda p: p[0] - p[1])]
    for x, y in corners:
        dome(scene, (x, y, base), 4, 5)
    for a, b in zip(ring, ring[1:] + ring[:1]):
        for z in [8, 16, 23.5]:
            scene.beam('Building_Paris', 'White', (a[0], a[1], base - 24 + z), (b[0], b[1], base - 24 + z), .55, .28)


def casino(scene: CircuitScene) -> None:
    mapped_building(scene, 161769674, 19, facade='Cream', floors=3, roof='pitched', base_z=scene.at(946).z)
    building = scene.footprint(161769674)
    ring = building.ring
    center = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    road, _ = scene.nearest(*center)
    base = (center[0], center[1], road.z)
    a, b = max(zip(ring, ring[1:] + ring[:1]), key=lambda pair: math.dist(*pair))
    heading = math.atan2(b[1] - a[1], b[0] - a[0])
    axis, normal = (math.cos(heading), math.sin(heading), 0.), (-math.sin(heading), math.cos(heading), 0.)
    local = [(sum((p[i] - center[i]) * axis[i] for i in range(2)),
              sum((p[i] - center[i]) * normal[i] for i in range(2))) for p in ring]
    low, high = min(p[0] for p in local), max(p[0] for p in local)
    front = min(p[1] for p in local)
    scene.landmarks.append({'name': 'Casino de Monte Carlo', 'osm_id': 161769674,
                            'dimensions_status': 'Mapped footprint contains casino POI4416197079. Height19m and roof ornament reconstructed from official SBM architecture; no invented rectangular footprint.'})
    def point(u: float, v: float, z: float) -> Point:
        return add(base, add(mul(axis, u), add(mul(normal, v), (0, 0, z))))
    for a, b in zip(ring, ring[1:] + ring[:1]):
        pa, pb = (a[0], a[1], base[2]), (b[0], b[1], base[2])
        for z in [5.6, 11.2, 17.8, 19.2]:
            scene.beam('Building_Casino', 'White', add(pa, (0, 0, z)), add(pb, (0, 0, z)), .5)
        bays = max(1, round(math.dist(pa, pb) / 6))
        for bay in range(bays):
            fraction = (bay + .1) / bays
            x, y = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
            scene.beam('Building_Casino', 'White', (x, y, base[2] + .5), (x, y, base[2] + 18), .45)
    for u in [low + (high - low) * .2, low + (high - low) * .8]:
        scene.box('Building_Casino', 'Cream', point(u, front + 6, 21), 8, 10, 5, heading)
        dome(scene, point(u, front + 6, 23.5), 5, 5)
        scene.beam('Building_Casino', 'White', point(u, front + 6, 28), point(u, front + 6, 30), .25)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(230, 295, 1), (775, 846, -1), (910, 978, 1), (1155, 1220, 1), (1260, 1340, -1), (1373, 1420, 1), (1450, 1510, 1), (2110, 2160, -1), (2180, 2230, 1), (2405, 2460, -1), (2555, 2600, 1), (2605, 2650, -1), (2700, 2750, -1), (2760, 2810, 1), (2835, 2915, 1), (2940, 3000, -1), (3045, 3095, 1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    for start, end, side, width, material in [(210, 275, -1, 6, 'Runoff'), (2100, 2240, -1, 5, 'Runoff')]:
        scene.runoff(start, end, side, width, material)



def harbour(scene: CircuitScene) -> None:
    bounds = box(min(p.x for p in scene.road) - 220, min(p.y for p in scene.road) - 350,
                 max(p.x for p in scene.road) + 450, max(p.y for p in scene.road) + 220)
    lines = [bounds.boundary]
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.tags.get('natural') == 'coastline' and len(element.geometry) > 1:
                line = LineString([scene.geo(p.lat, p.lon) for p in element.geometry]).intersection(bounds)
                if not line.is_empty:
                    lines.append(line)
    cells = list(polygonize(unary_union(lines)))
    witnesses = [ShapePoint(*scene.geo(lat, lon)) for lat, lon in
                 [(43.7358, 7.4251), (43.7358, 7.4312), (43.7385, 7.4318)]]
    sea = [cell for cell in cells if any(cell.covers(point) for point in witnesses)]
    if not sea:
        raise ValueError('Monaco coastline did not close around the retained harbour witnesses')
    sea_z = -2.5
    for shape in sea:
        scene.water_shapes.append(shape)
        for triangle in triangulate(shape):
            if shape.covers(triangle):
                a, b, c = list(triangle.exterior.coords)[:3]
                scene.triangle('Tile_Sea', 'Water', (a[0], a[1], sea_z), (b[0], b[1], sea_z), (c[0], c[1], sea_z))
    boats = 0
    for row in range(9):
        for column in range(9):
            x, y = scene.geo(43.73405 + row * .00035, 7.42275 + column * .00035)
            point = ShapePoint(x, y)
            length = 17 + (row + column) % 3 * 5
            if not any(shape.covers(point.buffer(length * .55)) for shape in sea):
                continue
            _, distance = scene.nearest(x, y)
            if distance < 18:
                continue
            yacht(scene, (x, y, sea_z), length, -.8 + column % 2 * .16, row + column)
            boats += 1
    scene.landmarks.append({'name': 'Port Hercule / Mediterranean shore',
                            'source': 'Retained bounded OSMcoastline; sea cells selected by registered water witnesses',
                            'water_height_m': sea_z, 'yachts': boats,
                            'dimensions_status': 'Coastline mapped. Water2.5mbelowrelativeRascasse road and dynamic17–27myachtfleet are original reference reconstructions; individualboatpositions are not surveyed assets.'})


def yacht(scene: CircuitScene, center: Point, length: float, heading: float, seed: int) -> None:
    axis, side = (math.cos(heading), math.sin(heading), 0.), (-math.sin(heading), math.cos(heading), 0.)
    width = length * .23
    def point(u: float, v: float, z: float) -> Point:
        return add(center, add(mul(axis, u), add(mul(side, v), (0, 0, z))))
    outline = [(-.5, -.34), (-.15, -.5), (.30, -.42), (.5, 0), (.30, .42), (-.15, .5), (-.5, .34)]
    deck = [point(u * length, v * width, 1.6) for u, v in outline]
    keel = [point(u * length * .85, v * width * .5, -.3) for u, v in outline]
    for i in range(len(deck)):
        j = (i + 1) % len(deck)
        scene.quad('Building_Yachts', 'White', keel[i], keel[j], deck[j], deck[i])
        scene.beam('Building_Yachts', 'Steel', add(deck[i], (0, 0, .5)), add(deck[j], (0, 0, .5)), .04)
        scene.triangle('Building_Yachts', 'Cream', point(0, 0, 1.6), deck[i], deck[j])
    scene.box('Building_Yachts', 'White', point(-length * .08, 0, 2.5), length * .48, width * .78, 1.8, heading)
    scene.box('Building_Yachts', 'Glass', point(-length * .04, 0, 3.6), length * .40, width * .70, .8, heading)
    scene.box('Building_Yachts', 'White', point(-length * .04, 0, 4.1), length * .43, width * .76, .18, heading)
    if seed % 4 == 0:
        scene.beam('Building_Yachts', 'Steel', point(0, 0, 4.2), point(0, 0, 14), .08)
        scene.beam('Building_Yachts', 'Steel', point(0, 0, 4.2), point(length * .33, 0, 4.2), .06)
