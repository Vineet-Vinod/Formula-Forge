"""Mapped Court service street with inferred continuous ground, outside the racing road."""
from __future__ import annotations

import math
import random

from circuit_dataclasses import Point
from circuit_mesh import cross, norm, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry import Point as GeoPoint
from shapely.ops import unary_union

from venues.baku_forecourt_dataclasses import ForecourtSource


def court_forecourt(scene: CircuitScene) -> None:
    source = TypeAdapter(ForecourtSource).validate_json(
        (scene.sources / 'castle-forecourt.json').read_bytes()
    )
    if source.blend_extent_m <= source.core_half_width_m:
        raise ValueError('Forecourt blend extent must exceed the street half-width')
    service = LineString([scene.geo(*point) for point in source.service_geo])
    park = Polygon([scene.geo(*point) for point in source.park_geo])
    buildings = unary_union([Polygon(building.ring).buffer(.05) for building in scene.buildings])
    protected = scene.corridor_mask.buffer(.05)
    right_side = LineString([scene.at(station).point(0)[:2]
                             for station in range(2590, 2851, 2)]).buffer(
                                 -80, single_sided=True)
    mask = service.buffer(source.blend_extent_m).intersection(right_side).difference(
        unary_union([protected, buildings, park, *scene.water_shapes])
    )
    pieces = [mask] if isinstance(mask, Polygon) else (
        list(mask.geoms) if isinstance(mask, MultiPolygon) else []
    )
    scene.terrain_cutouts.extend(pieces)
    scene.terrain_cutouts.append(Polygon(scene.footprint(133641457).ring))
    first, last = service.coords[0], service.coords[-1]
    za, zb = scene.nearest(*first)[0].z, scene.nearest(*last)[0].z

    def smooth(value: float) -> float:
        t = max(0., min(1., value))
        return t * t * (3 - 2 * t)

    def height(x: float, y: float) -> float:
        point = GeoPoint(x, y)
        t = service.project(point) / service.length
        street = za + (zb - za) * t
        weight = 1 - smooth((service.distance(point) - source.core_half_width_m)
                            / (source.blend_extent_m - source.core_half_width_m))
        weight *= smooth(park.distance(point) / source.park_transition_m)
        weight *= smooth(protected.distance(point) / 2)
        weight *= smooth(right_side.boundary.distance(point) / 8)
        original = scene.ground(x, y)
        return original + weight * (street - original)

    core = service.buffer(source.core_half_width_m)
    step = 1.5
    for zone, material in ((mask.intersection(core), 'Runoff'), (mask.difference(core), 'Concrete')):
        if zone.is_empty:
            continue
        xmin, ymin, xmax, ymax = zone.bounds
        for row in range(math.floor(ymin / step), math.ceil(ymax / step)):
            for column in range(math.floor(xmin / step), math.ceil(xmax / step)):
                cell = box(column * step, row * step, (column + 1) * step, (row + 1) * step)
                if not zone.intersects(cell):
                    continue
                for triangle in constrained_delaunay_triangles(zone.intersection(cell)).geoms:
                    points: list[Point] = [(x, y, height(x, y))
                                           for x, y in list(triangle.exterior.coords)[:3]]
                    if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                        points.reverse()
                    normals = tuple(norm((height(x - .2, y) - height(x + .2, y),
                                          height(x, y - .2) - height(x, y + .2), .4))
                                    for x, y, _ in points)
                    scene.triangle('Tile_Ground', material, points[0], points[1], points[2],
                                   tuple((p[0] / 8, p[1] / 8) for p in points), normals)
    park_context(scene, source, park, protected, buildings)
    scene.landmarks.append({
        'name': 'Court service street and paved forecourt', 'osm_id': 339124204,
        'source_note': 'Actual mapped one-way asphalt service street and adjoining hardscape, on the driver-right side of the racing road, outside the racing corridor, retained buildings and Sabir Park. Ground is reconstructed from unchanged adjacent road endpoint grades, with a smooth 42 m fade to original scenery and a 16 m fade at the untouched park. About ±2 m vertical uncertainty; this is not a bare-earth survey. Native road, Court facade placement, park heights and physical protection remain unchanged. DSM terrain hidden inside the real Court footprint does not form part of its ground-floor architecture.',
    })


def park_context(
    scene: CircuitScene, source: ForecourtSource, park: Polygon,
    protected: Polygon | MultiPolygon, buildings: Polygon | MultiPolygon,
) -> None:
    paths = unary_union([LineString([scene.geo(*point) for point in path]).buffer(1.4)
                         for path in source.park_paths_geo])
    planted = park.difference(unary_union([protected, buildings, paths, *scene.water_shapes]))
    pieces = [planted] if isinstance(planted, Polygon) else list(planted.geoms)
    scene.terrain_cutouts.extend(piece for piece in pieces if isinstance(piece, Polygon))
    step = scene.grid.step
    xmin, ymin, xmax, ymax = planted.bounds
    for row in range(math.floor((ymin - scene.grid.y) / step),
                     math.ceil((ymax - scene.grid.y) / step)):
        for column in range(math.floor((xmin - scene.grid.x) / step),
                            math.ceil((xmax - scene.grid.x) / step)):
            x, y = scene.grid.x + column * step, scene.grid.y + row * step
            cell = box(x, y, x + step, y + step).intersection(planted)
            if not cell.is_empty:
                scene.polygon_surface(cell, 'Grass', smooth_ground=True)
    safe = planted.buffer(-3.5).difference(unary_union([protected.buffer(6), buildings.buffer(6)]))
    randomizer = random.Random(299424032)
    count = 0
    for row in range(math.floor(ymin / 8), math.ceil(ymax / 8)):
        for column in range(math.floor(xmin / 8), math.ceil(xmax / 8)):
            x = (column + .5) * 8 + randomizer.uniform(-2, 2)
            y = (row + .5) * 8 + randomizer.uniform(-2, 2)
            if not safe.covers(GeoPoint(x, y)):
                continue
            scene.broadleaf((x, y, scene.ground(x, y)),
                            randomizer.uniform(8.5, 12.5), 299424032 + count)
            count += 1
    scene.vegetation.append({
        'name': 'Sabir Park', 'osm_id': 299424032, 'count': count,
        'placement': 'Exact mapped park with retained paths excluded; path half-width 1.4 m, broadleaf heights 8.5–12.5 m and approximately 8 m spacing are visual estimates. Existing joined scenery heights are unchanged. Tree roots are grounded; crown radius clears roads and mapped buildings.',
    })
