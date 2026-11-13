"""Three mapped Flame Towers with curved triangular shells and asymmetric crowns."""

from __future__ import annotations

import gzip
import hashlib
import math

from circuit_dataclasses import Building, OsmData, Point
from circuit_mesh import cross, norm, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient

from venues.baku_skyline_dataclasses import FlameTower, FlameTowerRecipe


def flame_towers(scene: CircuitScene) -> None:
    recipe = TypeAdapter(FlameTowerRecipe).validate_json(
        (scene.sources / 'flame-towers.json').read_bytes()
    )
    source_bytes = (scene.sources / recipe.source_file).read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != recipe.source_sha256:
        raise ValueError('Retained Flame Towers footprint source changed')
    source = TypeAdapter(OsmData).validate_json(gzip.decompress(source_bytes))
    mapped = {element.id: element for element in source.elements}
    footprints = {
        record.osm_id: orient(Polygon([scene.geo(point.lat, point.lon)
                                      for point in mapped[record.osm_id].geometry]))
        for record in recipe.towers
    }
    center_x = sum(p.centroid.x for p in footprints.values()) / len(footprints)
    center_y = sum(p.centroid.y for p in footprints.values()) / len(footprints)
    existing = {building.osm_id for building in scene.buildings}
    for record in recipe.towers:
        if record.osm_id in existing:
            raise ValueError(f'Flame Towers must not duplicate an existing property: {record.osm_id}')
        footprint = footprints[record.osm_id]
        if footprint.intersects(scene.corridor_mask.buffer(1.2)):
            raise ValueError('Flame Towers must remain clear of all racing corridors')
        ring = [(x, y) for x, y in list(footprint.exterior.coords)[:-1]]
        building = Building(record.osm_id, record.name, 'commercial', record.height_m,
                            ring, mapped[record.osm_id].tags)
        scene.buildings.append(building)
        scene.modeled_buildings.add(record.osm_id)
        scene.terrain_cutouts.append(footprint)
        _tower(scene, footprint, record, (center_x, center_y))
        scene.landmarks.append({
            'name': record.name, 'osm_id': record.osm_id, 'height_m': record.height_m,
            'floors': record.floors, 'base_relative_m': record.base_relative_m,
            'foundation_uncertainty_m': record.ground_uncertainty_m,
            'source': 'flame-towers.json; HOK architect photographs, CVU architectural height, actual OSM plan',
            'dimensions_status': 'Actual curved triangular ground footprint; upper sections/crown lean are reconstructed from HOK photos. Constant base uses retained coarse GLO90 boundary minimum, not a second sample of the tower roof. About10 m foundation allowance is retained. No source photo pixels or generic rectangular tower templates.',
        })


def _tower(scene: CircuitScene, footprint: Polygon, record: FlameTower,
           cluster_center: tuple[float, float]) -> None:
    center = footprint.centroid
    vertices = [(x, y) for x, y in list(footprint.exterior.coords)[:-1]]
    outward = center.x - cluster_center[0], center.y - cluster_center[1]
    corner = max(vertices, key=lambda p: (p[0] - center.x) * outward[0] + (p[1] - center.y) * outward[1])
    tip = (center.x + (corner[0] - center.x) * record.crown_tip_fraction,
           center.y + (corner[1] - center.y) * record.crown_tip_fraction)
    smoothed = vertices
    for _ in range(3):
        smoothed = [p for a, b in zip(smoothed, smoothed[1:] + smoothed[:1])
                    for p in ((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25),
                              (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))]
    base_ring = LineString(vertices + vertices[:1])
    upper_ring = LineString(smoothed + smoothed[:1])
    count, levels = 96, 72
    parameters = sorted({segment / count for segment in range(count)}
                        | {base_ring.project(ShapePoint(vertex)) / base_ring.length for vertex in vertices})
    spans = list(zip(parameters, parameters[1:] + [1.]))
    kind = f'Building_FlameTower{record.osm_id}'

    def point(u: float, t: float, outset: float = 0.) -> Point:
        u %= 1.
        base = base_ring.interpolate(u * base_ring.length)
        rounded = upper_ring.interpolate(u * upper_ring.length)
        blend = min(1., t / .035)
        blend = blend * blend * (3 - 2 * blend)
        x, y = base.x * (1 - blend) + rounded.x * blend, base.y * (1 - blend) + rounded.y * blend
        crown = max(0., (t - .58) / .42)
        scale = (1 - .07 * t) * math.sqrt(max(0., 1 - crown * crown))
        dx, dy = x - tip[0], y - tip[1]
        span = math.hypot(dx, dy)
        return (tip[0] + dx * scale + dx / span * outset,
                tip[1] + dy * scale + dy / span * outset,
                record.base_relative_m + t * record.height_m)

    def normal(u: float, t: float) -> Point:
        if t >= 1:
            return 0., 0., 1.
        tangent = sub(point(u + .0001, t), point(u - .0001, t))
        vertical = sub(point(u, min(1., t + .0001)), point(u, max(0., t - .0001)))
        return norm(cross(tangent, vertical))

    for level in range(levels):
        low, high = level / levels, (level + 1) / levels
        for segment, (a, b) in enumerate(spans):
            points = point(a, low), point(b, low), point(b, high), point(a, high)
            normals = normal(a, low), normal(b, low), normal(b, high), normal(a, high)
            material = 'BakuSkyGlassLight' if segment % 24 in (0, 1, 2) else 'BakuSkyGlass'
            scene.triangle(kind, material, points[0], points[1], points[2],
                           ((a * 32, low * 80), (b * 32, low * 80), (b * 32, high * 80)),
                           (normals[0], normals[1], normals[2]))
            if high < 1:
                scene.triangle(kind, material, points[0], points[2], points[3],
                               ((a * 32, low * 80), (b * 32, high * 80), (a * 32, high * 80)),
                               (normals[0], normals[2], normals[3]))
    ground = Polygon([point(parameter, 0)[:2] for parameter in parameters])
    for triangle in constrained_delaunay_triangles(ground).geoms:
        coordinates = list(orient(triangle).exterior.coords)[:3]
        base_points = [(x, y, record.base_relative_m) for x, y in coordinates]
        scene.triangle(kind, 'Concrete', base_points[2], base_points[1], base_points[0])
    for floor in range(1, record.floors + 1):
        height = floor / (record.floors + 1) * .87
        band = .10 / record.height_m
        for a, b in spans:
            scene.quad(kind + 'Mullions', 'Steel', point(a, height - band, .025),
                       point(b, height - band, .025), point(b, height + band, .025), point(a, height + band, .025))
    for segment in range(0, count, 2):
        u = segment / count
        for level in range(levels):
            a, b = level / levels, (level + 1) / levels
            width = .0003
            scene.quad(kind + 'Mullions', 'Steel', point(u - width, a, .025),
                       point(u + width, a, .025), point(u + width, b, .025), point(u - width, b, .025))
    for height in record.service_bands:
        half = .65 / record.height_m
        for a, b in spans:
            scene.quad(kind + 'ServiceBelts', 'Steel', point(a, height - half, .04),
                       point(b, height - half, .04), point(b, height + half, .04), point(a, height + half, .04))
