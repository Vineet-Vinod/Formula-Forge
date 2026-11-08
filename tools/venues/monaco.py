"""Monaco: inhabited terraces, a real tunnel volume and ornate Casino Square masses."""
from __future__ import annotations

import math
from itertools import pairwise

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
    heritage_frontage(scene, scene.footprint(8280869), 24, 6, scene.at(876).z)
    hotel_crowns(scene)
    casino(scene)
    tunnel(scene)
    scene.pit_building(3070, 3330, side=1, depth=12, height=10, levels=3)
    harbour_stand(scene, 0, 180, -1, 15, 6)
    harbour_stand(scene, 2350, 2490, 1, 18, 8)
    harbour_stand(scene, 2570, 2680, 1, 18, 8)
    ordinary_city(scene)
    casino_gardens(scene)
    for start, end, side, setback in [(280, 550, 1, 10), (1280, 1440, -1, 10)]:
        trees(scene, start, end, side, setback=setback, rows=1, spacing=16, height=9)
    trees(scene, 1250, 1410, 1, setback=16, rows=1, spacing=17, height=10, palms=True)
    for station in [200, 920, 1370, 2200, 2440, 2950, 3260]:
        mast(scene, station, -1, 12)


def casino_gardens(scene: CircuitScene) -> None:
    bounds = box(*scene.geo(43.738, 7.425), *scene.geo(43.742, 7.432))
    planted: list[Polygon] = []
    for tags in [{'leisure': 'park'}, {'leisure': 'garden'}, {'natural': 'wood'}, {'landuse': 'grass'}]:
        planted.extend(Polygon(ring) for ring in scene.area_polygons(tags))
    buildings = unary_union([Polygon(building.ring) for building in scene.buildings])
    protection = unary_union([scene.corridor_mask, *scene.extra_corridors])
    blocked = unary_union([buildings, protection, *scene.water_shapes])
    paths = []
    trees_by_id = {}
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.type == 'node' and element.tags.get('natural') == 'tree':
                trees_by_id[element.id] = element
            if element.tags.get('highway') not in {'footway', 'pedestrian', 'path', 'steps'} or len(element.geometry) < 2:
                continue
            line = LineString([scene.geo(p.lat, p.lon) for p in element.geometry])
            try:
                width = float(element.tags.get('width', '2').removesuffix(' m'))
            except ValueError:
                width = 2
            paths.append(line.buffer(max(.5, min(8, width)) / 2))
    grass = unary_union(planted).intersection(bounds).difference(unary_union([blocked, *paths]))
    if grass.is_empty:
        raise ValueError('Retained Monaco garden footprints must provide actual planted surfaces')
    components = [grass] if isinstance(grass, Polygon) else list(getattr(grass, 'geoms', []))
    for component in components:
        if isinstance(component, Polygon) and component.area > .1:
            scene.terrain_cutouts.append(component)
    grid = scene.grid
    xmin, ymin, xmax, ymax = grass.bounds
    for row in range(max(0, int((ymin - grid.y) // grid.step)), min(grid.rows - 1, math.ceil((ymax - grid.y) / grid.step))):
        for column in range(max(0, int((xmin - grid.x) // grid.step)), min(grid.columns - 1, math.ceil((xmax - grid.x) / grid.step))):
            x, y = grid.x + column * grid.step, grid.y + row * grid.step
            part = grass.intersection(box(x, y, x + grid.step, y + grid.step))
            if not part.is_empty:
                scene.polygon_surface(part, 'Grass', smooth_ground=True)
    count, skipped = 0, 0
    tree_blocked = unary_union([buildings.buffer(1.2), protection.buffer(2), *scene.water_shapes])
    for osm_id, element in trees_by_id.items():
        x, y = scene.geo(element.lat, element.lon)
        point = ShapePoint(x, y)
        if not bounds.covers(point) or tree_blocked.covers(point):
            skipped += 1
            continue
        try:
            height = float(element.tags.get('height', '11').removesuffix(' m'))
        except ValueError:
            height = 11
        height = max(3, min(24, height))
        base = (x, y, scene.ground(x, y))
        species = (element.tags.get('genus', '') + element.tags.get('species', '')).lower()
        if any(name in species for name in ('phoenix', 'washingtonia', 'trachycarpus', 'palm')):
            scene.palm(base, height)
        else:
            scene.broadleaf(base, height, osm_id % 997)
        count += 1
    scene.landmarks.append({'name': 'Mapped Casino-district gardens and heritage trees',
                            'garden_area_m2': round(grass.area, 3), 'mapped_trees': count,
                            'trees_excluded_for_clearance_or_query_bounds': skipped,
                            'dimensions_status': 'Retained OSM garden/grass footprints, pedestrian paths and individual tree positions. Road/corridor/water/buildings excluded; exact native terrain-grid cell subdivision replaces underlying Concrete. Tagged tree height/species retained; missing heights estimated11m, untagged broadleaf form. No terrain-height changes.'})


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
            scene.banner(pa, pb, wall_height, 'Cream', 'Building_Tunnel', repeat=6)
            for row in range(1, math.ceil(wall_height / .3)):
                z = row * .3
                scene.beam('Building_Tunnel', 'Steel', add(pa, (0, 0, z)), add(pb, (0, 0, z)), .009)
            for column in range(8):
                t = column / 8
                p = add(pa, mul((pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]), t))
                scene.beam('Building_Tunnel', 'Steel', p, add(p, (0, 0, wall_height)), .009)
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


def heritage_frontage(scene: CircuitScene, building: Building,
                      height: float, floors: int, base: float) -> None:
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon):
        raise TypeError('Monaco palace frontage needs a connected mapped footprint')
    ring = list(footprint.exterior.coords)[:-1]
    if not footprint.exterior.is_ccw:
        ring.reverse()
    center = footprint.centroid
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)
    kind = 'Building_MonacoPalace'
    for a, b in zip(ring, ring[1:] + ring[:1]):
        span = math.dist(a, b)
        if span < .35:
            continue
        axis = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        normal = axis[1], -axis[0]
        def point(u: float, outward: float, z: float, *,
                  origin: tuple[float, float] = a,
                  direction: tuple[float, float] = axis,
                  face_normal: tuple[float, float] = normal) -> Point:
            return (origin[0] + direction[0] * u + face_normal[0] * outward,
                    origin[1] + direction[1] * u + face_normal[1] * outward, base + z)
        scene.banner(point(0, 0, 0), point(span, 0, 0), height, 'Cream', kind)
        bays = max(1, round(span / 3.8))
        bay_width = span / bays
        floor_height = height / floors
        for floor in range(floors):
            bottom = floor * floor_height
            scene.beam(kind, 'White', point(0, .12, bottom), point(span, .12, bottom), .65, .24)
            for bay in range(bays):
                u = (bay + .5) * bay_width
                width = min(1.9 if floor else 2.6, bay_width * .63)
                low, spring = bottom + .65, bottom + floor_height - width * .5 - .5
                if spring <= low:
                    continue
                pa, pb = point(u - width / 2, .045, low), point(u + width / 2, .045, low)
                scene.banner(pa, pb, spring - low, 'Glass' if floor else 'Black', kind)
                arc = [point(u + math.cos(math.pi * i / 12) * width / 2, .045,
                             spring + math.sin(math.pi * i / 12) * width / 2) for i in range(13)]
                anchor = point(u, .045, spring)
                for left, right in pairwise(arc):
                    scene.triangle(kind, 'Glass' if floor else 'Black', anchor, left, right)
                    scene.triangle(kind, 'Glass' if floor else 'Black', anchor, right, left)
                    scene.beam(kind, 'White', add(left, (normal[0] * .09, normal[1] * .09, 0)),
                               add(right, (normal[0] * .09, normal[1] * .09, 0)), .11)
                for edge in (-width / 2, width / 2):
                    scene.beam(kind, 'White', point(u + edge, .13, low), point(u + edge, .13, spring), .13)
                pier = bay * bay_width
                scene.beam(kind, 'White', point(pier, .18, bottom + .3), point(pier, .18, bottom + floor_height - .3), .3)
                if floor:
                    left, right = point(u - width * .7, 1, low - .15), point(u + width * .7, 1, low - .15)
                    back_left, back_right = point(u - width * .7, 0, low - .15), point(u + width * .7, 0, low - .15)
                    scene.quad(kind, 'White', back_left, back_right, right, left, up=True)
                    scene.quad(kind, 'Cream', add(left, (0, 0, -.18)), add(right, (0, 0, -.18)),
                               add(back_right, (0, 0, -.18)), add(back_left, (0, 0, -.18)), up=False)
                    for z in (.2, .55, .9):
                        scene.beam(kind, 'Black', add(left, (0, 0, z)), add(right, (0, 0, z)), .035)
                    for rail in range(7):
                        p = add(left, ((right[0] - left[0]) * rail / 6, (right[1] - left[1]) * rail / 6, .12))
                        scene.beam(kind, 'Black', p, add(p, (0, 0, .8)), .025)
        for lift, depth in [(height - .6, .55), (height, .95), (height + .35, .65)]:
            scene.beam(kind, 'White', point(0, .15, lift), point(span, .15, lift), depth, .25)
        roof_points = []
        for x, y in (a, b):
            distance = math.hypot(center.x - x, center.y - y)
            roof_points.append((x + (center.x - x) * 2.5 / max(2.5, distance),
                                y + (center.y - y) * 2.5 / max(2.5, distance), base + height + 3))
        scene.quad(kind, 'Roof', point(0, 0, height), point(span, 0, height), roof_points[1], roof_points[0], up=True)
    inner_ring = []
    for x, y in ring:
        distance = math.hypot(center.x - x, center.y - y)
        inner_ring.append((x + (center.x - x) * 2.5 / max(2.5, distance),
                           y + (center.y - y) * 2.5 / max(2.5, distance)))
    roof = Polygon(inner_ring)
    if not roof.is_valid:
        raise ValueError('Monaco palace mansard outline must be valid')
    for triangle in triangulate(roof):
        if roof.covers(triangle):
            a, b, c = list(triangle.exterior.coords)[:3]
            scene.triangle(kind, 'Roof', (a[0], a[1], base + height + 3),
                           (b[0], b[1], base + height + 3), (c[0], c[1], base + height + 3))
    scene.landmarks.append({'name': 'Hotel de Paris' if building.osm_id == 8280869 else 'Casino heritage frontage',
                            'osm_id': building.osm_id, 'height_m': height,
                            'dimensions_status': 'Actual mapped footprint; original arched openings, relief pilasters/cornices, individual iron balconies and mansard envelope reconstructed from supplied330s and CasinoSquare footage. Storey heights/bay dimensions estimated; no generic office facade.'})


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
    heritage_frontage(scene, scene.footprint(161769674), 19, 3, scene.at(876).z)
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
