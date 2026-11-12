"""Mapped North Sea and dune ponds, with individually registered water levels."""
from __future__ import annotations

from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.coastal_water_dataclasses import CoastalWater


def water_bodies(scene: CircuitScene) -> None:
    bodies = TypeAdapter(list[CoastalWater]).validate_json(
        (scene.sources / 'water-bodies.json').read_bytes()
    )
    blocked = unary_union([scene.corridor_mask, *scene.extra_corridors,
                           *[Polygon(building.ring) for building in scene.buildings]])
    total_area = 0.0
    removed_area = 0.0
    for body in bodies:
        polygons = [Polygon([scene.geo(lat, lon) for lon, lat in polygon.outer],
                            [[scene.geo(lat, lon) for lon, lat in ring]
                             for ring in polygon.holes]) for polygon in body.polygons]
        if any(not polygon.is_valid for polygon in polygons):
            raise ValueError('Mapped Zandvoort water polygon is invalid')
        original = unary_union(polygons)
        water = original.difference(blocked)
        removed_area += original.area - water.area
        components = [water] if isinstance(water, Polygon) else list(getattr(water, 'geoms', []))
        for polygon in components:
            if not isinstance(polygon, Polygon) or polygon.area < .1:
                continue
            scene.water_shapes.append(polygon)
            total_area += polygon.area
            for triangle in constrained_delaunay_triangles(polygon).geoms:
                points = [(x, y, body.water_level_m)
                          for x, y in list(triangle.exterior.coords)[:3]]
                if not triangle.exterior.is_ccw:
                    points[1], points[2] = points[2], points[1]
                scene.triangle('Tile_DuneWater', 'Water', points[0], points[1], points[2])
    scene.landmarks.append({'name': 'Mapped North Sea and dune ponds',
                            'water_bodies': len(bodies), 'water_area_m2': total_area,
                            'removed_for_roads_and_buildings_m2': removed_area,
                            'source': 'water-bodies.json and scenery-ground.json',
                            'level_status': 'Sea is NAP0; inland pond planes are separately estimated from valid AHN5 shoreline heights. Water is a scenery cutout only; racing road, protection and physical corridors remain unchanged.'})
