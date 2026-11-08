"""Footprint-based architecture and landscape forms for western venues."""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from circuit_dataclasses import Building, Point
from circuit_mesh import add, mul, sub
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.ops import triangulate

if TYPE_CHECKING:
    from circuit_scene import CircuitScene


def apron_band(scene: CircuitScene, start: float, end: float, side: int,
               inner: float, outer: float, material: str) -> None:
    """Paint an existing apron without changing its physical boundary."""
    span = (end - start) % scene.length
    count = max(1, math.ceil(span / 2))
    for i in range(count):
        a = scene.at(start + span * i / count)
        b = scene.at(start + span * (i + 1) / count)
        points = [a.point(side * (a.half_width + inner)),
                  b.point(side * (b.half_width + inner)),
                  b.point(side * (b.half_width + outer)),
                  a.point(side * (a.half_width + outer))]
        shape = Polygon([(p[0], p[1]) for p in points])
        if shape.is_valid:
            scene.polygon_surface(shape.difference(scene.road_mask), material, lift=.023)
    scene.surface_ranges.append({'type': 'apron paint', 'start_m': start,
                                 'end_m': end, 'side': side, 'inner_m': inner,
                                 'outer_m': outer, 'material': material})


def apron_star(scene: CircuitScene, station: float, side: int,
               offset: float, radius: float, material: str = 'White') -> None:
    from shapely.ops import unary_union

    sample = scene.at(station)
    center = sample.point(side * (sample.half_width + offset))
    points = []
    for i in range(10):
        angle = math.pi / 2 + math.tau * i / 10
        r = radius if i % 2 == 0 else radius * .382
        along, lateral = math.cos(angle) * r, math.sin(angle) * r
        points.append((center[0] + sample.tx * along + sample.ty * lateral,
                       center[1] + sample.ty * along - sample.tx * lateral))
    shape = Polygon(points).intersection(unary_union(scene.extra_corridors))
    scene.polygon_surface(shape.difference(scene.road_mask), material, lift=.027)
    scene.surface_ranges.append({'type': 'apron star', 'station_m': station,
                                 'side': side, 'offset_m': offset, 'radius_m': radius,
                                 'material': material})


def suzuka_service_hut(scene: CircuitScene, building: Building,
                       eaves: float, roof: float) -> None:
    """Reconstruct the two untagged A1 huts as small bank-supported service buildings."""
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon) or footprint.is_empty:
        return
    ring = list(footprint.exterior.coords)[:-1]
    elevations = [scene.ground(x, y) for x, y in ring]
    foundation = sum(elevations) / len(elevations)
    a, b = max(zip(ring, ring[1:] + ring[:1]), key=lambda edge: math.dist(*edge))
    span = math.dist(a, b)
    axis = ((b[0] - a[0]) / span, (b[1] - a[1]) / span)
    across = (-axis[1], axis[0])
    projected = [x * across[0] + y * across[1] for x, y in ring]
    low, high = min(projected), max(projected)

    def roof_z(x: float, y: float) -> float:
        return foundation + eaves + (roof - eaves) * (
            x * across[0] + y * across[1] - low) / max(.1, high - low)

    kind = 'Building_SuzukaService'
    for i, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1])):
        za, zb = roof_z(*a), roof_z(*b)
        ga, gb = elevations[i] - .15, elevations[(i + 1) % len(ring)] - .15
        scene.quad(kind, 'Cream', (a[0], a[1], ga), (b[0], b[1], gb),
                   (b[0], b[1], zb), (a[0], a[1], za))
        scene.beam(kind, 'Steel', (a[0], a[1], za), (b[0], b[1], zb), .09)
    for triangle in triangulate(footprint):
        if footprint.covers(triangle.representative_point()):
            p, q, r = [(float(x), float(y), roof_z(x, y))
                       for x, y in list(triangle.exterior.coords)[:3]]
            scene.triangle(kind, 'Roof', p, q, r)
    # Clip narrow parallel ridges to the actual roof rather than adding a box roof.
    from shapely.geometry import LineString

    bounds = footprint.bounds
    extent = math.hypot(bounds[2] - bounds[0], bounds[3] - bounds[1]) + 1
    center = footprint.centroid
    for i in range(math.ceil(extent / .42) + 1):
        offset = -extent / 2 + i * .42
        x, y = center.x + axis[0] * offset, center.y + axis[1] * offset
        ridge = LineString([(x - across[0] * extent, y - across[1] * extent),
                            (x + across[0] * extent, y + across[1] * extent)]).intersection(footprint)
        if isinstance(ridge, LineString) and not ridge.is_empty:
            p0, p1 = ridge.coords[0], ridge.coords[-1]
            scene.beam(kind, 'Steel', (p0[0], p0[1], roof_z(*p0) + .025),
                       (p1[0], p1[1], roof_z(*p1) + .025), .025)
    # One service door and a high, narrow opening replace invented office floors.
    a, b = min(zip(ring, ring[1:] + ring[:1]),
               key=lambda edge: scene.nearest((edge[0][0] + edge[1][0]) / 2,
                                               (edge[0][1] + edge[1][1]) / 2)[1])
    length = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    winding = 1 if footprint.exterior.is_ccw else -1
    nx, ny = winding * ty * .035, -winding * tx * .035
    x, y = (a[0] + b[0]) / 2 + nx, (a[1] + b[1]) / 2 + ny
    door_base = scene.ground(x, y)
    door_top = min(door_base + 2.05, roof_z(x, y) - .25)
    scene.banner((x - tx * .45, y - ty * .45, door_base),
                 (x + tx * .45, y + ty * .45, door_base),
                 max(.5, door_top - door_base), 'Steel', kind)
    wx, wy = x + tx * 1.5, y + ty * 1.5
    window_base = roof_z(wx, wy) - .75
    if length > 4 and window_base > scene.ground(wx, wy) + .5:
        scene.banner((wx - tx * .45, wy - ty * .45, window_base),
                     (wx + tx * .45, wy + ty * .45, window_base), .35, 'Glass', kind)
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'osm_id': building.osm_id, 'name': 'A1 service hut, use unknown',
                            'eaves_m': eaves, 'roof_m': roof, 'storeys': 1,
                            'source': 'https://www.suzukacircuit.jp/course_s/a1/',
                            'dimensions_status': 'OSM footprint; original conservative reconstruction. Exact height, use, roof pitch and openings unmeasured. Operator A1 aerial shows corrugated service roofs behind open bleachers. Foundation follows local GSI bank rather than racing-road elevation.'})


def mapped_building(scene: CircuitScene, osm_id: int, height: float, *, facade: str = 'Cream',
                    floors: int = 3, roof: str = 'flat', balconies: bool = False,
                    enclosed: bool = True, base_z: float | None = None,
                    elevated: bool = False) -> None:
    building = scene.footprint(osm_id)
    scene.modeled_buildings.add(osm_id)
    footprint = Polygon(building.ring)
    if not footprint.is_valid or footprint.is_empty:
        return
    open_structure = building.use in {'roof', 'grandstand'} or building.tags.get('leisure') == 'grandstand'
    if open_structure:
        enclosed = False
        if roof == 'flat':
            roof = 'canopy'
    original_area = footprint.area
    clipped = footprint if elevated else footprint.difference(scene.road_mask.buffer(1.2))
    removed_area = original_area - clipped.area
    scene.landmarks.append({'osm_id': osm_id, 'name': building.name or str(osm_id),
                            'height_m': height, 'removed_road_area_m2': round(removed_area, 3),
                            'structure': 'enclosed' if enclosed else 'open roof/stand',
                            'road_clearance_exception': 'Authored elevated tunnel/bridge deck' if elevated else 'none',
                            'dimensions_status': 'Mapped footprint; foundation tied to adjacent racing-road level to avoid DSM roof-on-roof. Height/facade/roof reconstructed unless source tags supply height.'})
    center = footprint.centroid
    base = scene.nearest(center.x, center.y)[0].z if base_z is None else base_z
    components = [clipped] if isinstance(clipped, Polygon) else list(getattr(clipped, 'geoms', []))
    for component in components:
        if isinstance(component, Polygon) and component.area > .5:
            _building_part(scene, component, height, facade, floors, roof, balconies, enclosed, base)


def _building_part(scene: CircuitScene, footprint: Polygon, height: float, facade: str,
                   floors: int, roof: str, balconies: bool, enclosed: bool, base_z: float) -> None:
    ring = list(footprint.exterior.coords)[:-1]
    center = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    base = base_z
    winding = 1 if Polygon(ring).exterior.is_ccw else -1
    kind = 'Building_Architecture'
    for a, b in zip(ring, ring[1:] + ring[:1]):
        pa, pb = (a[0], a[1], base), (b[0], b[1], base)
        if not enclosed:
            continue
        scene.banner(pa, pb, height, facade, kind)
        direction = sub(pb, pa)
        span = math.dist(pa, pb)
        bays = max(1, round(span / 4.0))
        for floor in range(floors):
            bottom = height * floor / floors + .8
            top = min(height - .35, height * (floor + 1) / floors - .3)
            if top <= bottom:
                continue
            for bay in range(bays):
                x0 = add(pa, mul(direction, (bay + .12) / bays))
                x1 = add(pa, mul(direction, (bay + .88) / bays))
                outward = (direction[1] / max(span, .001) * .04 * winding,
                           -direction[0] / max(span, .001) * .04 * winding, bottom)
                scene.banner(add(x0, outward), add(x1, outward), top - bottom, 'Glass', kind)
            if balconies:
                edge_a, edge_b = add(pa, (0, 0, bottom - .2)), add(pb, (0, 0, bottom - .2))
                scene.beam(kind, facade, edge_a, edge_b, .8, .18)
                scene.beam(kind, 'Steel', add(edge_a, (0, 0, .9)), add(edge_b, (0, 0, .9)), .06)
        scene.beam(kind, facade, add(pa, (0, 0, height)), add(pb, (0, 0, height)), .3)
    roof_center = (center[0], center[1], base + height)
    if enclosed:
        surface(scene, footprint, base + height, 'Roof', kind)
    if roof == 'flat':
        return
    a, b = max(zip(ring, ring[1:] + ring[:1]), key=lambda edge: math.dist(*edge))
    length = math.dist(a, b)
    axis = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.0)
    side = (-axis[1], axis[0], 0.0)
    local = [(sum((p[i] - center[i]) * axis[i] for i in range(2)),
              sum((p[i] - center[i]) * side[i] for i in range(2))) for p in ring]
    start, end = min(p[0] for p in local), max(p[0] for p in local)
    low, high = min(p[1] for p in local), max(p[1] for p in local)
    def point(u: float, v: float, lift: float) -> Point:
        return add(roof_center, add(mul(axis, u), add(mul(side, v), (0, 0, lift))))
    bays = max(1, round((end - start) / 12))
    for bay in range(bays):
        u0, u1 = start + (end - start) * bay / bays, start + (end - start) * (bay + 1) / bays
        if roof == 'pitched':
            ridge = (low + high) / 2
            scene.quad(kind, 'Roof', point(u0, low, .15), point(u1, low, .15), point(u1, ridge, 3), point(u0, ridge, 3))
            scene.quad(kind, 'Roof', point(u0, ridge, 3), point(u1, ridge, 3), point(u1, high, .15), point(u0, high, .15))
        else:
            lip = 2.8 if roof == 'blades' else 1.2
            corners = (point(u0, low - 2, .1), point(u1 - .25, low - 2, .1), point(u1 - .25, high + 3, lip), point(u0, high + 3, lip))
            scene.quad(kind, 'Red' if roof == 'blades' else 'Roof', *corners)
            if roof == 'blades':
                scene.quad(kind, 'White', add(corners[3], (0, 0, -.08)), add(corners[2], (0, 0, -.08)), add(corners[1], (0, 0, -.08)), add(corners[0], (0, 0, -.08)))
            scene.beam(kind, 'Steel', point(u0, low, 0), point(u0, high + 3, lip), .18)
            scene.beam(kind, 'Steel', point(u0, low, -height), point(u0, low, .1), .25)


def trees(scene: CircuitScene, start: float, end: float, side: int, *, setback: float = 12,
          spacing: float = 13, rows: int = 2, height: float = 11, conifers: bool = False,
          palms: bool = False) -> None:
    scene.vegetation.append({'start_m': start, 'end_m': end, 'side': side,
                             'setback_m': setback, 'rows': rows,
                             'species_form': 'conifer' if conifers else 'palm' if palms else 'broadleaf',
                             'placement_status': 'Reference-observed sector bands; individual positions reconstructed outside protection.'})
    rng = random.Random(round(start * 13 + side * 47))
    water_shapes = water_shapes_at(scene) + scene.water_shapes + scene.extra_corridors
    station = start
    while station < end:
        sample = scene.at(station)
        shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
        for row in range(rows):
            lane = side * (sample.half_width + shoulder + setback + row * 11 + rng.uniform(-2, 2))
            p = sample.point(lane)
            nearest, distance = scene.nearest(p[0], p[1])
            safe = nearest.half_width + max(nearest.left_shoulder, nearest.right_shoulder) + 6
            if distance < safe or any(shape.covers(ShapePoint(p[0], p[1])) for shape in water_shapes):
                continue
            base = (p[0], p[1], scene.ground(p[0], p[1]))
            h = height * rng.uniform(.8, 1.25)
            if conifers:
                conifer(scene, base, h)
            elif palms:
                scene.palm(base, h)
            else:
                scene.broadleaf(base, h, round(station + row * 19))
        station += spacing + rng.uniform(-2, 2)


def conifer(scene: CircuitScene, base: Point, height: float) -> None:
    scene.beam('Building_Trees', 'Trunk', base, add(base, (0, 0, height * .8)), .22)
    for layer in range(4):
        bottom = height * (.16 + layer * .17)
        radius = height * (.28 - layer * .052)
        tip = add(base, (0, 0, min(height, bottom + height * .47)))
        for face in range(9):
            a, b = math.tau * face / 9, math.tau * (face + 1) / 9
            scene.triangle('Building_Trees', 'Leaves',
                           add(base, (math.cos(a) * radius, math.sin(a) * radius, bottom)),
                           add(base, (math.cos(b) * radius, math.sin(b) * radius, bottom)), tip)


def water_shapes_at(scene: CircuitScene) -> list[Polygon]:
    shapes = [Polygon(ring) for ring in scene.area_polygons({'natural': 'water'}) if len(ring) >= 3]
    path = scene.sources / 'water-rings.lonlat.json'
    if path.exists():
        source = TypeAdapter(list[list[tuple[float, float]]]).validate_json(path.read_bytes())
        rings = [[scene.geo(lat, lon) for lon, lat in ring] for ring in source]
        if rings:
            shapes.append(Polygon(rings[0], rings[1:]))
    return shapes


def water(scene: CircuitScene) -> None:
    bounds = box(min(p.x for p in scene.road) - 200, min(p.y for p in scene.road) - 200,
                 max(p.x for p in scene.road) + 200, max(p.y for p in scene.road) + 200)
    for polygon in water_shapes_at(scene):
        if any(polygon.covers(ShapePoint(p.x, p.y)) for p in scene.road[::8]):
            scene.landmarks.append({'name': 'Water polygon excluded', 'reason': 'Outer ring crosses racing road; island holes are not exposed by area_polygons.'})
            continue
        clipped = polygon.intersection(bounds)
        parts = [clipped] if isinstance(clipped, Polygon) else list(getattr(clipped, 'geoms', []))
        for part in parts:
            if isinstance(part, Polygon) and not part.is_empty:
                scene.water_shapes.append(part)
                local_ring = list(part.exterior.coords)[:-1]
                z = min(scene.ground(x, y) for x, y in local_ring) - .15
                for triangle in triangulate(part):
                    if part.covers(triangle):
                        a, b, c = list(triangle.exterior.coords)[:3]
                        scene.triangle('Tile_Water', 'Water', (a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z))


def mast(scene: CircuitScene, station: float, side: int, height: float = 22) -> None:
    sample = scene.at(station)
    p = sample.point(side * (sample.half_width + max(sample.left_shoulder, sample.right_shoulder) + 5))
    base = (p[0], p[1], scene.ground(p[0], p[1]))
    scene.beam('Building_Masts', 'Steel', base, add(base, (0, 0, height)), .25)
    scene.box('Building_Masts', 'White', add(base, (0, 0, height)), 3.0, .7, .4, math.atan2(sample.ty, sample.tx))


def surface(scene: CircuitScene, ring: list[tuple[float, float]] | Polygon, z: float, material: str, kind: str) -> None:
    polygon = ring if isinstance(ring, Polygon) else Polygon(ring)
    if not polygon.is_valid:
        return
    for triangle in triangulate(polygon):
        if polygon.covers(triangle):
            a, b, c = list(triangle.exterior.coords)[:3]
            scene.triangle(kind, material, (a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z))


def dome(scene: CircuitScene, center: Point, radius: float, height: float, material: str = 'Roof') -> None:
    for row in range(8):
        phi0, phi1 = row * math.pi / 16, (row + 1) * math.pi / 16
        for face in range(32):
            a, b = face * math.tau / 32, (face + 1) * math.tau / 32
            def point(angle: float, phi: float) -> Point:
                return add(center, (radius * math.cos(phi) * math.cos(angle), radius * math.cos(phi) * math.sin(angle), height * math.sin(phi)))
            scene.quad('Building_Architecture', material, point(a, phi0), point(b, phi0), point(b, phi1), point(a, phi1))
