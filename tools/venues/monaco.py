"""Monaco: inhabited terraces, a real tunnel volume and ornate Casino Square masses."""
from __future__ import annotations

import math

from circuit_dataclasses import Building, Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import LineString, Polygon, box
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
        frontage(scene, scene.footprint(osm_id), height, floors)
    mapped_building(scene, 2093796, 24, floors=7, balconies=True,
                    base_z=scene.at(1750).z + 5.8, elevated=True)
    mapped_building(scene, 8280869, 24, floors=6, roof='pitched', balconies=True, base_z=scene.at(946).z)
    hotel_crowns(scene)
    casino(scene)
    tunnel(scene)
    scene.pit_building(3070, 3330, side=1, depth=12, height=10, levels=3)
    harbour_stand(scene, 0, 180, -1, 15, 6)
    harbour_stand(scene, 2350, 2490, 1, 18, 8)
    harbour_stand(scene, 2570, 2680, 1, 18, 8)
    ordinary_city(scene)
    for start, end, side, setback in [(280, 550, 1, 10), (700, 870, 1, 8),
                                      (1050, 1170, -1, 8), (1280, 1440, -1, 10)]:
        trees(scene, start, end, side, setback=setback, rows=1, spacing=16, height=9)
    trees(scene, 860, 1030, 1, setback=20, rows=1, spacing=20, height=10, palms=True)
    trees(scene, 1250, 1410, 1, setback=16, rows=1, spacing=17, height=10, palms=True)
    for station in [200, 920, 1370, 2200, 2440, 2950, 3260]:
        mast(scene, station, -1, 12)


def ordinary_city(scene: CircuitScene) -> None:
    modeled = [Polygon(scene.footprint(osm_id).ring) for osm_id in scene.modeled_buildings]
    for building in scene.buildings:
        if building.osm_id in scene.modeled_buildings:
            continue
        if building.use in {'roof', 'bridge', 'grandstand'}:
            continue
        polygon = Polygon(building.ring)
        if polygon.area < 8:
            continue
        # Detailed roof parts already belong to an enclosed mapped parent, not more offices.
        if 'building:part' in building.tags or any(
                parent.covers(polygon.representative_point()) for parent in modeled):
            continue
        frontage(scene, building)


def frontage(scene: CircuitScene, building: Building,
             height: float | None = None, floors: int | None = None) -> None:
    original = Polygon(building.ring)
    clipped = original.difference(scene.road_mask.buffer(1.2))
    components = [clipped] if isinstance(clipped, Polygon) else list(getattr(clipped, 'geoms', []))
    h = building.height if height is None else height
    levels = floors if floors is not None else max(1, round(h / 3.4))
    tagged = 'height' in building.tags or 'building:levels' in building.tags
    apartment = building.use in {'apartments', 'residential', 'hotel'} or levels >= 4
    facade = 'White' if building.tags.get('building:colour', '').lower() in {'white', '#ffffff'} else 'Cream'
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'osm_id': building.osm_id, 'name': building.name or 'Mapped Monaco frontage',
                            'height_m': h, 'levels': levels,
                            'height_status': 'Retained height/levels' if tagged else 'Unmeasured conservative retained default; not a verified storey survey',
                            'structure': 'Mapped footprint with narrow recessed windows, projecting street-facing balconies, shop/entrance level and roof parapet',
                            'removed_road_area_m2': round(original.area - clipped.area, 3)})
    for footprint in components:
        if not isinstance(footprint, Polygon) or footprint.area < 4:
            continue
        scene.terrain_cutouts.append(footprint)
        ring = list(footprint.exterior.coords)[:-1]
        if not footprint.exterior.is_ccw:
            ring.reverse()
        closest = min(ring, key=lambda p: scene.nearest(*p)[1])
        base = min(scene.ground(*closest), min(scene.ground(*p) for p in ring))
        winding = 1
        kind = 'Building_MonacoFrontage'
        for a, b in zip(ring, ring[1:] + ring[:1]):
            span = math.dist(a, b)
            if span < .25:
                continue
            tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
            nx, ny = ty * winding, -tx * winding
            pa, pb = (a[0], a[1], base), (b[0], b[1], base)
            bottom_a, bottom_b = min(base, scene.ground(*a) - .12), min(base, scene.ground(*b) - .12)
            scene.quad(kind, facade, (a[0], a[1], bottom_a), (b[0], b[1], bottom_b),
                       (b[0], b[1], base + h), (a[0], a[1], base + h))
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            road, _ = scene.nearest(*middle)
            facing = (road.x - middle[0]) * nx + (road.y - middle[1]) * ny > 0
            bays = max(1, round(span / (3.1 if apartment else 3.8)))
            for floor in range(levels):
                z = base + h * floor / levels
                floor_height = h / levels
                top = min(base + h - .3, z + floor_height - .5)
                low = z + (.35 if floor == 0 else .8)
                if top <= low or span < 1.5:
                    continue
                for bay in range(bays):
                    mid = (bay + .5) * span / bays
                    width = min(1.3 if apartment else 1.65, span / bays * .58)
                    x, y = a[0] + tx * mid + nx * .025, a[1] + ty * mid + ny * .025
                    p, q = (x - tx * width / 2, y - ty * width / 2, low), (x + tx * width / 2, y + ty * width / 2, low)
                    scene.banner(p, q, top - low, 'Glass', kind)
                    scene.banner(add(p, (0, 0, -.10)), add(q, (0, 0, -.10)), .12, 'White', kind)
                    if floor == 0 and bay == bays // 2:
                        scene.banner(p, add(p, (tx * .06, ty * .06, 0)), top - low, 'Steel', kind)
                if apartment and facing and floor > 0:
                    slab_a, slab_b = add(pa, (nx * .85, ny * .85, z - base)), add(pb, (nx * .85, ny * .85, z - base))
                    scene.quad(kind, 'White', add(pa, (0, 0, z - base)), add(pb, (0, 0, z - base)), slab_b, slab_a, up=True)
                    scene.quad(kind, 'Concrete', add(slab_a, (0, 0, -.15)), add(slab_b, (0, 0, -.15)),
                               add(pb, (0, 0, z - base - .15)), add(pa, (0, 0, z - base - .15)), up=False)
                    scene.banner(add(slab_a, (0, 0, .15)), add(slab_b, (0, 0, .15)), .75, 'Glass', kind)
                    scene.beam(kind, 'Steel', add(slab_a, (0, 0, .95)), add(slab_b, (0, 0, .95)), .055)
                    for bay in range(bays + 1):
                        p = add(slab_a, (tx * span * bay / bays, ty * span * bay / bays, .05))
                        scene.banner(p, add(p, (tx * .035, ty * .035, 0)), .9, 'Steel', kind)
            scene.beam(kind, 'White', add(pa, (0, 0, h)), add(pb, (0, 0, h)), .25, .4)
        for triangle in triangulate(footprint):
            if footprint.covers(triangle):
                a, b, c = list(triangle.exterior.coords)[:3]
                scene.triangle(kind, 'Roof', (a[0], a[1], base + h),
                               (b[0], b[1], base + h), (c[0], c[1], base + h))


def harbour_stand(scene: CircuitScene, start: float, end: float,
                   side: int, rows: int, setback: float) -> None:
    scene.stand(start, end, side, rows=rows, setback=setback, seat_material='Concrete')
    steps = max(1, math.ceil((end - start) / 5))
    for i in range(steps):
        a, b = scene.at(start + (end - start) * i / steps), scene.at(start + (end - start) * (i + 1) / steps)
        front, rear = [], []
        for p in (a, b):
            shoulder = p.left_shoulder if side > 0 else p.right_shoulder
            lane = side * (p.half_width + .95 + shoulder + setback)
            front.append(p.point(lane, .52))
            rear.append(p.point(lane + side * rows * .88, .52 + rows * .45))
        scene.quad('Building_StandSoffit', 'Concrete', front[0], front[1], rear[1], rear[0], up=False)
        scene.quad('Building_StandFoundation', 'Concrete',
                   (front[0][0], front[0][1], scene.ground(*front[0][:2]) - .15),
                   (front[1][0], front[1][1], scene.ground(*front[1][:2]) - .15),
                   front[1], front[0])


def tunnel(scene: CircuitScene) -> None:
    scene.landmarks.append({'name': 'Fairmont tunnel', 'start_m': 1520, 'end_m': 2010,
                            'dimensions_status': 'Path follows native road. Walls0.85moutside white line, ceiling5.4mabove road; original reconstruction from414/450/558sframes.'})
    count = 123
    for segment in range(count):
        a, b = scene.at(1520 + 490 * segment / count), scene.at(1520 + 490 * (segment + 1) / count)
        for side in [-1, 1]:
            pa, pb = a.point(side * (a.half_width + .85)), b.point(side * (b.half_width + .85))
            wall_height = 1.15 if side < 0 else 5.4
            scene.quad('Building_Tunnel', 'Cream', pa, pb, add(pb, (0, 0, wall_height)), add(pa, (0, 0, wall_height)), 6, 8)
            for row in range(1, math.ceil(wall_height / .3)):
                z = row * .3
                scene.beam('Building_Tunnel', 'White', add(pa, (0, 0, z)), add(pb, (0, 0, z)), .012)
            for column in range(8):
                t = column / 8
                p = add(pa, mul((pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]), t))
                scene.beam('Building_Tunnel', 'White', p, add(p, (0, 0, wall_height)), .012)
            if side < 0:
                scene.beam('Building_Tunnel', 'Concrete', add(pa, (0, 0, wall_height)), add(pa, (0, 0, 5.4)), .25)
                scene.beam('Building_Tunnel', 'Concrete', add(pa, (0, 0, 5.15)), add(pb, (0, 0, 5.15)), .3, .5)
        la, ra = a.point(-a.half_width - .85, 5.4), a.point(a.half_width + .85, 5.4)
        lb, rb = b.point(-b.half_width - .85, 5.4), b.point(b.half_width + .85, 5.4)
        scene.quad('Building_Tunnel', 'Cream', ra, rb, lb, la, up=False)
        scene.quad('Building_Tunnel', 'Concrete', add(la, (0, 0, .25)),
                   add(lb, (0, 0, .25)), add(rb, (0, 0, .25)),
                   add(ra, (0, 0, .25)), up=True)
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
    witnesses = [ShapePoint(*scene.geo(43.733, 7.4355))]
    sea = [cell for cell in cells if any(cell.covers(point) for point in witnesses)]
    dry = [ShapePoint(*scene.geo(lat, lon)) for lat, lon in
           [(43.7393, 7.4283), (43.7346, 7.4225)]]
    if not sea or any(cell.covers(point) for cell in sea for point in dry):
        raise ValueError('Monaco coastline must separate the sea from Casino Square and the paddocks')
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
