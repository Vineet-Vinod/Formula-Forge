"""Actual lower ground body and fine street foreground at Quai Antoine."""

from __future__ import annotations

import math
from functools import lru_cache
from itertools import pairwise

from circuit_dataclasses import Point, RetainedTerrainSource, TerrainGrid
from circuit_mesh import add, norm
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.monaco_dataclasses import PropertyEnvelope, RascasseFrontage
from venues.monaco_properties import arch, balcony_rail
from venues.pit_compounds import roof_shell


def rascasse_frontage(scene: CircuitScene) -> None:
    config = TypeAdapter(RascasseFrontage).validate_json(
        (scene.sources / 'architecture/rascasse-frontage-correction.json').read_bytes()
    )
    if abs(scene.provenance.route.uniform_scale - config.uniform_scale) > 1e-9:
        raise ValueError('Retained lower Rascasse frontage needs its source frame')
    grid = TypeAdapter(TerrainGrid).validate_json(
        (scene.sources / config.ground_grid_file).read_bytes()
    )
    records = TypeAdapter(list[PropertyEnvelope]).validate_json(
        (scene.sources / 'architecture/property-envelopes.json').read_bytes()
    )
    record = next(record for record in records if record.source_id == config.roof_source_id)
    ring = [scene.geo(lat, lon) for lon, lat in record.outer]
    roof = Polygon(ring)
    body = Polygon(scene.footprint(config.ground_body_osm_id).ring)
    first, last = config.roof_front_vertices
    front = LineString(ring[first:last + 1])
    candidates = body.difference(roof).intersection(front.buffer(config.body_search_width_m, cap_style='flat'))
    pieces = [candidates] if isinstance(candidates, Polygon) else [p for p in getattr(candidates, 'geoms', ()) if isinstance(p, Polygon)]
    podium = orient(max(pieces, key=lambda p: p.area))
    region = Polygon([scene.geo(lat, lon) for lon, lat in config.region_wgs84])
    terrain_source = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    )
    deck = record.ground_m - terrain_source.relative_datum_m + config.podium_height_above_source_minimum_m

    def measured(x: float, y: float) -> float:
        column = max(0.0, min(grid.columns - 1.000001, (x - grid.x) / grid.step))
        row = max(0.0, min(grid.rows - 1.000001, (y - grid.y) / grid.step))
        ix, iy = int(column), int(row)
        tx, ty = column - ix, row - iy
        a, b = grid.heights[iy * grid.columns + ix:iy * grid.columns + ix + 2]
        c, d = grid.heights[(iy + 1) * grid.columns + ix:(iy + 1) * grid.columns + ix + 2]
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty

    def threshold(x: float, y: float) -> float:
        road, _distance = scene.nearest(x, y)
        dx, dy = road.x - x, road.y - y
        span = math.hypot(dx, dy)
        offset = config.street_threshold_sample_distance_m / span
        return measured(x + dx * offset, y + dy * offset) + .10

    if podium.intersects(scene.road_mask):
        raise ValueError('The actual Rascasse ground body must clear the racing road')
    scene.terrain_cutouts.append(podium)
    roof_shell(scene, podium, lambda x, y: deck, 'Building_QuaiCornerPodium',
               'Concrete', 'Concrete', 'MonacoRuscinoRose', thickness=.18)
    roof_shell(scene, podium, threshold, 'Building_QuaiCornerFloor',
               'Concrete', 'Concrete', 'Concrete', thickness=.14)
    kind = 'Building_QuaiCornerArcade'
    for a, b in pairwise(podium.exterior.coords):
        scene.quad(kind, 'MonacoRuscinoRose', (*a, threshold(*a) - .14),
                   (*b, threshold(*b) - .14), (*b, deck - .18), (*a, deck - .18))
    outer_front = body.boundary.intersection(podium.buffer(1e-7))
    outer_chains = [outer_front] if isinstance(outer_front, LineString) else [p for p in getattr(outer_front, 'geoms', ()) if isinstance(p, LineString)]
    for chain in outer_chains:
        for a, b in pairwise(chain.coords):
            span = math.dist(a, b)
            if span < .5:
                continue
            tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
            road, _distance = scene.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            nx, ny = ty, -tx
            if nx * (road.x - a[0]) + ny * (road.y - a[1]) < 0:
                a, b = b, a
                tx, ty = -tx, -ty
                nx, ny = -nx, -ny
            bays = max(1, round(span / 3.8))
            for bay in range(bays):
                middle = (bay + .5) * span / bays
                width = min(2.9, span / bays * .75)
                x, y = a[0] + tx * middle, a[1] + ty * middle
                base = threshold(x, y) + .03
                arch_height = deck - .33 - base
                if arch_height < 2:
                    raise ValueError('Primary street threshold leaves insufficient arcade clearance')
                start: Point = x - tx * width / 2 + nx * .035, y - ty * width / 2 + ny * .035, base
                end = add(start, (tx * width, ty * width, 0))
                arch(scene, start, end, arch_height, kind)
            balcony_rail(scene, (*a, deck), (*b, deck), deck + .04, .03, 'Building_QuaiCornerTerrace')

    street_front = max(outer_chains, key=lambda chain: chain.length)
    first_xy, last_xy = street_front.coords[0], street_front.coords[-1]
    midpoint = street_front.interpolate(street_front.length / 2)
    road, _distance = scene.nearest(midpoint.x, midpoint.y)
    dx, dy = last_xy[0] - first_xy[0], last_xy[1] - first_xy[1]
    nx, ny = dy / street_front.length, -dx / street_front.length
    if nx * (road.x - midpoint.x) + ny * (road.y - midpoint.y) < 0:
        nx, ny = -nx, -ny
    width = config.forecourt_width_m
    zone = Polygon([first_xy, last_xy,
                    (last_xy[0] + nx * width, last_xy[1] + ny * width),
                    (first_xy[0] + nx * width, first_xy[1] + ny * width)]).intersection(region)
    outer_seam = zone.boundary.difference(street_front.buffer(.02))
    occupied = [Polygon(b.ring) for b in scene.buildings]
    occupied.extend(Polygon([scene.geo(lat, lon) for lon, lat in r.outer]) for r in records)
    patch = zone.difference(unary_union([scene.corridor_mask, *occupied, *scene.water_shapes]))

    @lru_cache(maxsize=2048)
    def height(x: float, y: float) -> float:
        point = ShapePoint(x, y)
        foot = street_front.interpolate(street_front.project(point))
        along = min(1., point.distance(street_front) / width)
        toe_x, toe_y = foot.x + nx * width, foot.y + ny * width
        paving = threshold(foot.x, foot.y) * (1 - along) + scene.ground(toe_x, toe_y) * along
        blend = min(1., point.distance(outer_seam), point.distance(scene.corridor_mask))
        blend = blend * blend * (3 - 2 * blend)
        return paving * blend + scene.ground(x, y) * (1 - blend)

    patches = [patch] if isinstance(patch, Polygon) else [p for p in getattr(patch, 'geoms', ()) if isinstance(p, Polygon)]
    scene.terrain_cutouts.extend(patches)
    for row in range(grid.rows - 1):
        for column in range(grid.columns - 1):
            x, y = grid.x + column * grid.step, grid.y + row * grid.step
            cell = patch.intersection(box(x, y, x + grid.step, y + grid.step))
            for triangle in constrained_delaunay_triangles(cell).geoms:
                points = [(px, py, height(px, py)) for px, py in list(triangle.exterior.coords)[:3]]
                if not triangle.exterior.is_ccw:
                    points.reverse()
                normals = tuple(norm((height(px - .25, py) - height(px + .25, py),
                                      height(px, py - .25) - height(px, py + .25), .5))
                                for px, py, _z in points)
                scene.triangle('Tile_RascasseForecourt', 'Concrete', points[0], points[1], points[2],
                               tuple((px / 4, py / 4) for px, py, _z in points), normals)
    scene.landmarks.append({
        'name': 'Actual Quai Antoine corner ground body and lower forecourt',
        'osm_id': config.ground_body_osm_id, 'podium_area_m2': podium.area,
        'fine_ground_area_m2': patch.area, 'podium_deck_z_m': deck,
        'source': 'architecture/rascasse-frontage-correction.json',
        'dimensions_status': 'The retained OSM ground-body wedge projects beyond the measured IGN upper roof. The registered496 s view supports a recessed ground arcade and shallow first-floor terrace. Upper roofs/storeys stay unchanged. Local lower-street thresholds use retained IGN ground2.5 m toward the adjacent road; the3.5 m podium storey and railing section are architectural estimates. Only the mapped corner frontage receives a ruled paved forecourt between the local lower-street thresholds and the adjacent road toe. Repeated high terrain cells are not treated as street-level survey points. Actual unoccupied hillsides, occupied upper parcels and upper streets remain untouched.',
    })
