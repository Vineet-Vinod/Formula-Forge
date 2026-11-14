"""Keep Villa Hermosa's measured envelope and photographed garden facade."""

from __future__ import annotations

import math
import struct
from itertools import pairwise

from circuit_dataclasses import Point, RetainedTerrainSource, TerrainGrid
from circuit_mesh import add
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles, get_coordinates
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

from venues.monaco_cliff import source_height
from venues.monaco_hermosa_dataclasses import HermosaArchitecture
from venues.monaco_hermosa_details import decorate, frontage
from venues.monaco_hermosa_details import roof as photo_roof
from venues.monaco_surfaces import SurfaceFace, face

RoofTriangle = tuple[Point, Point, Point]


def configuration(scene: CircuitScene) -> HermosaArchitecture:
    config = TypeAdapter(HermosaArchitecture).validate_json(
        (scene.sources / 'architecture/villa-hermosa.json').read_bytes())
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()).relative_datum_m
    if scene.slug != 'monaco' or max(
        abs(config.origin_lat_lon[0] - scene.provenance.origin.latitude),
        abs(config.origin_lat_lon[1] - scene.provenance.origin.longitude),
        abs(config.uniform_scale - scene.provenance.route.uniform_scale),
        abs(config.relative_datum_m - datum),
    ) > 1e-9:
        raise ValueError('Villa Hermosa requires the retained Monaco source frame')
    expected = Polygon([scene.geo(lat, lon) for lon, lat in config.body_wgs84])
    if expected.symmetric_difference(Polygon(scene.footprint(config.osm_id).ring)).area > 1e-7:
        raise ValueError('Villa Hermosa must retain its literal OSM body')
    return config


def prepare(scene: CircuitScene) -> None:
    config = configuration(scene)
    body = Polygon(scene.footprint(config.osm_id).ring)
    if config.osm_id in scene.modeled_buildings or body.intersects(scene.corridor_mask):
        raise ValueError('Villa Hermosa must be registered once, outside the racing corridor')
    scene.modeled_buildings.add(config.osm_id)
    scene.terrain_cutouts.append(body)


def roof_triangles(scene: CircuitScene, config: HermosaArchitecture) -> tuple[RoofTriangle, ...]:
    eaves = [(*scene.geo(lat, lon), z - config.relative_datum_m)
             for lon, lat, z in config.eaves_wgs84]
    facets = photo_roof(scene, config)
    plan = Polygon([p[:2] for p in eaves])
    pieces = [Polygon([p[:2] for p in triangle]) for triangle in facets]
    if (not plan.is_valid or any(not p.is_valid or p.area < .1 for p in pieces)
            or unary_union(pieces).symmetric_difference(plan).area > 1e-7
            or abs(sum(p.area for p in pieces) - plan.area) > 1e-7
            or min(config.ridge_absolute_m - p[2] for p in config.eaves_wgs84) <= 0):
        raise ValueError('The estimated ridge must form one closed hip inside the measured eaves')
    return facets


def plane_height(points: RoofTriangle, x: float, y: float) -> float:
    a, b, c = points
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    return u * a[2] + v * b[2] + (1 - u - v) * c[2]


def roof_height(facets: tuple[RoofTriangle, ...], x: float, y: float) -> float:
    point = ShapePoint(x, y)
    for triangle in facets:
        if Polygon([p[:2] for p in triangle]).buffer(1e-7).covers(point):
            return plane_height(triangle, x, y)
    edge = unary_union([Polygon([p[:2] for p in triangle]) for triangle in facets]).exterior
    closest = edge.interpolate(edge.project(point))
    if point.distance(closest) > 2.5:
        raise ValueError('A body/roof join exceeds the retained IGN plan precision')
    return roof_height(facets, closest.x, closest.y)


def support_faces(scene: CircuitScene, body: Polygon) -> tuple[SurfaceFace, ...]:
    faces = []
    for name, tile in scene.tiles.items():
        if not name.startswith('Tile_Street_'):
            continue
        bounds = box(-tile.maximum[1] / 100, -tile.maximum[0] / 100,
                     -tile.minimum[1] / 100, -tile.minimum[0] / 100)
        if not bounds.intersects(body.buffer(1.7)):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            if material not in {'Grass', 'Runoff', 'MonacoIvyGround', 'MonacoRockGround', 'Concrete', 'Terracotta'}:
                continue
            current = face(tile, offset)
            if current.plan.area > 1e-8 and current.plan.intersects(body.buffer(1.7)):
                faces.append(current)
    if not faces:
        raise ValueError('Villa Hermosa needs actual emitted ground around its body')
    return tuple(faces)


def finish(scene: CircuitScene) -> None:
    config = configuration(scene)
    body = orient(Polygon(scene.footprint(config.osm_id).ring), sign=1)
    if config.osm_id not in scene.modeled_buildings or sum(p.equals(body) for p in scene.terrain_cutouts) != 1:
        raise ValueError('Register the actual Villa Hermosa cutout before terrain emission')
    facets = roof_triangles(scene, config)
    grid = TypeAdapter(TerrainGrid).validate_json((scene.sources / config.ground_grid_file).read_bytes())
    faces = support_faces(scene, body)
    plans = [p.plan for p in faces]
    index = STRtree(plans)

    def ground(x: float, y: float) -> float:
        point = ShapePoint(x, y)
        heights = []
        for raw in index.query(point.buffer(.02)):
            i = int(raw)
            if plans[i].distance(point) > .0002:
                continue
            a, b, c = [(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in faces[i].vertices]
            heights.append(plane_height((a, b, c), x, y))
        if not heights:
            raise ValueError('A Villa Hermosa wall foot has no actual surrounding ground')
        return min(min(heights), source_height(grid, x, y)) - .12

    ring = list(body.exterior.coords)
    boundary: list[Point] = []
    for a, b in pairwise(ring):
        edge = LineString([a, b])
        count = max(1, math.ceil(edge.length / 2))
        stations = {edge.length * i / count for i in range(count)}
        for triangle in facets:
            for xy in get_coordinates(edge.intersection(Polygon([p[:2] for p in triangle]).boundary)):
                stations.add(edge.project(ShapePoint(xy)))
        for support in faces:
            for xy in support.xy:
                point = ShapePoint(xy)
                if edge.distance(point) <= .0002:
                    stations.add(edge.project(point))
        previous = -1.0
        for station in sorted(stations):
            if station - previous < .001 or edge.length - station < .001:
                continue
            point = edge.interpolate(station)
            boundary.append((point.x, point.y, ground(point.x, point.y)))
            previous = station
    base = config.floor_base_absolute_m - config.relative_datum_m
    kind = 'Building_VillaHermosa'
    front_a, front_b = frontage(body)
    for a, b in pairwise(ring):
        if math.dist(a, front_a) < 1e-7 and math.dist(b, front_b) < 1e-7:
            continue
        span = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        bays = max(1, round(span / 3.8))
        for floor in range(config.floors):
            bottom = base + floor * config.floor_height_m + .75
            for bay in range(bays):
                along = span * (bay + .5) / bays
                x, y = a[0] + tx * along, a[1] + ty * along
                top = min(bottom + config.floor_height_m - 1.3, roof_height(facets, x, y) - .5)
                if bottom < ground(x, y) + .37 or top - bottom < 1:
                    continue
                p = (x - tx * .575 + nx * .035, y - ty * .575 + ny * .035, bottom)
                q = add(p, (tx * 1.15, ty * 1.15, 0))
                scene.banner(p, q, top - bottom, 'Glass', kind)
                scene.beam(kind, 'Limestone', add(p, (0, 0, -.12)), add(q, (0, 0, -.12)), .12, .18)
    eaves = [(*scene.geo(lat, lon), z - config.relative_datum_m)
             for lon, lat, z in config.eaves_wgs84]
    roof_plan = Polygon([p[:2] for p in eaves])
    surfaces = list(facets)
    for triangle in constrained_delaunay_triangles(body.difference(roof_plan)).geoms:
        xy = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            xy.reverse()
        vertices = [(x, y, roof_height(facets, x, y)) for x, y in xy]
        surfaces.append((vertices[0], vertices[1], vertices[2]))
    outer = unary_union([body, roof_plan])
    if not isinstance(outer, Polygon):
        raise TypeError('Villa Hermosa roof and body must retain one connected join')
    # One planar subdivision shares hip, wall and eave vertices across every face.
    lines = [Polygon([p[:2] for p in triangle]).boundary for triangle in surfaces]
    lines.append(LineString([p[:2] for p in boundary + boundary[:1]]))
    pieces = [p for p in polygonize(unary_union(lines)) if outer.covers(p.representative_point())]
    nodes = [p[:2] for p in boundary]
    for piece in pieces:
        for xy in get_coordinates(piece.boundary):
            point = (float(xy[0]), float(xy[1]))
            if not any(math.dist(point, old) < 1e-7 for old in nodes):
                nodes.append(point)

    def shared_ring(coordinates: list[tuple[float, float]]) -> list[tuple[float, float]]:
        shared: list[tuple[float, float]] = []
        for a, b in pairwise(coordinates):
            edge = LineString([a, b])
            ordered = sorted((edge.project(ShapePoint(xy)), xy) for xy in nodes
                             if edge.distance(ShapePoint(xy)) < 1e-7)
            for station, xy in ordered:
                if edge.length - station < 1e-7 or shared and math.dist(shared[-1], xy) < 1e-7:
                    continue
                shared.append(xy)
        return shared

    boundary = [(x, y, ground(x, y)) for x, y in shared_ring([p[:2] for p in boundary + boundary[:1]])]
    for a, b in pairwise(boundary + boundary[:1]):
        top_a = roof_height(facets, *a[:2]) - .16
        top_b = roof_height(facets, *b[:2]) - .16
        split_a, split_b = min(top_a, max(a[2], base)), min(top_b, max(b[2], base))
        scene.quad(kind, 'Limestone', a, b, (b[0], b[1], split_b), (a[0], a[1], split_a))
        scene.quad(kind, 'Cream', (a[0], a[1], split_a), (b[0], b[1], split_b),
                   (b[0], b[1], top_b), (a[0], a[1], top_a))
    for piece in pieces:
        overhang = not body.covers(piece.representative_point())
        for triangle in constrained_delaunay_triangles(piece).geoms:
            if triangle.area < 1e-9:
                continue
            xy = shared_ring(list(orient(triangle).exterior.coords))
            if len(xy) < 3:
                raise ValueError('A common Villa Hermosa roof boundary collapsed')
            center = triangle.centroid
            triangles = [xy] if len(xy) == 3 else [
                [(center.x, center.y), a, b] for a, b in pairwise(xy + xy[:1])]
            for face_xy in triangles:
                if Polygon(face_xy).area <= 1e-10:
                    continue
                a, b, c = [(x, y, roof_height(facets, x, y)) for x, y in face_xy]
                scene.triangle(kind, config.roof_material, a, b, c)
                if overhang:
                    scene.triangle(kind, 'Concrete', add(c, (0, 0, -.16)), add(b, (0, 0, -.16)), add(a, (0, 0, -.16)))
    fascia = shared_ring(list(orient(outer).exterior.coords))
    for xy_a, xy_b in pairwise(fascia + fascia[:1]):
        pa, pb = (*xy_a, roof_height(facets, *xy_a)), (*xy_b, roof_height(facets, *xy_b))
        scene.quad(kind, config.roof_material, add(pa, (0, 0, -.16)), add(pb, (0, 0, -.16)), pb, pa)
    decorate(scene, config, ground)
    scene.landmarks.append({
        'name': 'Villa Hermosa measured envelope and photographed garden front',
        'osm_id': config.osm_id, 'ign_id': config.source_id,
        'roof_boundary_min_absolute_m': min(p[2] for p in config.eaves_wgs84),
        'roof_boundary_max_absolute_m': max(p[2] for p in config.eaves_wgs84),
        'ridge_absolute_m': config.ridge_absolute_m,
        'body_area_m2': body.area, 'roof_body_join_area_m2': body.difference(roof_plan).area,
        'source': 'architecture/villa-hermosa.json and villa-hermosa-provenance.json',
        'dimensions_status': 'Literal OSM body and IGN eaves, retained datum and actual emitted wall-foot support. Ridge/profile, horizontal floor schedule, loggia/ornament dimensions, simpler unphotographed sides, roof material and sub-precision body/eave join remain architectural estimates. Garden/pool/L-roof unchanged; native road, field and contact unchanged.',
    })
