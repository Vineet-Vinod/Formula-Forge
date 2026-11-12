"""Retained shoreline polygons and piers in each venue's native vertical datum."""
from __future__ import annotations

from itertools import pairwise

from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from venues.coastal_water_dataclasses import CoastalWater


def coastal_water(scene: CircuitScene) -> None:
    data = TypeAdapter(CoastalWater).validate_json((scene.sources / 'coastal-water.json').read_bytes())
    polygons = [Polygon([scene.geo(lat, lon) for lon, lat in p.outer],
                        [[scene.geo(lat, lon) for lon, lat in ring] for ring in p.holes])
                for p in data.polygons]
    if any(not polygon.is_valid or polygon.is_empty for polygon in polygons):
        raise ValueError('Retained coastline must form valid water polygons with island holes')
    original = unary_union(polygons)
    if any(original.covers(Point(p.x, p.y)) for p in scene.road):
        raise ValueError('Retained coastal water overlaps the racing centreline')
    blocked = unary_union([scene.corridor_mask, *scene.extra_corridors,
                           *[Polygon(b.ring) for b in scene.buildings]])
    decks = [Polygon([scene.geo(lat, lon) for lon, lat in p.ring]) for p in data.piers]
    if any(not deck.is_valid or deck.is_empty for deck in decks):
        raise ValueError('Retained pier footprints must be valid polygons')
    if any(pier.level_m <= data.water_level_m for pier in data.piers):
        raise ValueError('Pier decks must remain above the registered sea level')
    water = original.difference(unary_union([blocked, *decks]))
    for witness in data.witnesses:
        point = Point(*scene.geo(witness.latitude, witness.longitude))
        if water.covers(point) != witness.water:
            raise ValueError(f'Coastal land/water witness failed: {witness.name}')
    components = [water] if isinstance(water, Polygon) else list(getattr(water, 'geoms', []))
    for polygon in components:
        if not isinstance(polygon, Polygon) or polygon.area < .1:
            continue
        scene.water_shapes.append(polygon)
        for triangle in constrained_delaunay_triangles(polygon).geoms:
            points = [(x, y, data.water_level_m) for x, y in list(triangle.exterior.coords)[:3]]
            if not triangle.exterior.is_ccw:
                points[1], points[2] = points[2], points[1]
            scene.triangle('Tile_Water', 'Water', points[0], points[1], points[2])
    for pier, footprint in zip(data.piers, decks):
        clipped = footprint.difference(blocked)
        parts = [clipped] if isinstance(clipped, Polygon) else list(getattr(clipped, 'geoms', []))
        for part in parts:
            if not isinstance(part, Polygon) or part.area < .1:
                continue
            scene.terrain_cutouts.append(part)
            for triangle in constrained_delaunay_triangles(part).geoms:
                points = [(x, y, pier.level_m) for x, y in list(triangle.exterior.coords)[:3]]
                if not triangle.exterior.is_ccw:
                    points[1], points[2] = points[2], points[1]
                scene.triangle('Building_PierDeck', 'Concrete', points[0], points[1], points[2])
            ring = list(part.exterior.coords)
            for a, b in pairwise(ring):
                pa, pb = (a[0], a[1], data.water_level_m - .2), (b[0], b[1], data.water_level_m - .2)
                scene.quad('Building_PierQuay', 'Concrete', pa, pb,
                           (b[0], b[1], pier.level_m), (a[0], a[1], pier.level_m))
                scene.quad('Building_PierQuay', 'Concrete', pb, pa,
                           (a[0], a[1], pier.level_m), (b[0], b[1], pier.level_m))
    scene.landmarks.append({'name': 'Mapped coastal sea, lagoon and pier decks',
                            'water_area_m2': round(water.area, 3), 'water_level_m': data.water_level_m,
                            'mapped_piers': len(data.piers),
                            'water_removed_for_roads_buildings_piers_m2': round(original.area - water.area, 3),
                            'source': 'coastal-water.json and coastal-provenance.json; original shoreline geometry, no game pixels.',
                            'dimensions_status': 'Water is flat in the registered native datum. Pier footprints are mapped; deck levels are estimated from retained shore ground with minimum 0.6 m freeboard. Water only excludes scenery terrain; no physical corridor or native road changes.'})
