"""Fine retained ground at the lower quay frontage beneath Beau Rivage."""

from __future__ import annotations

from functools import lru_cache

from circuit_dataclasses import TerrainGrid
from circuit_mesh import norm
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def tabac_frontage_ground(scene: CircuitScene) -> dict[int, tuple[float, float]]:
    if abs(scene.provenance.route.uniform_scale - 1.0099320735128836) > 1e-9:
        raise ValueError('Retained Tabac ground requires registration to the current scene frame')
    grid = TypeAdapter(TerrainGrid).validate_json(
        (scene.sources / 'architecture/tabac-frontage-ground-grid.json').read_bytes()
    )

    def measured(x: float, y: float) -> float:
        column = max(0.0, min(grid.columns - 1.000001, (x - grid.x) / grid.step))
        row = max(0.0, min(grid.rows - 1.000001, (y - grid.y) / grid.step))
        ix, iy = int(column), int(row)
        tx, ty = column - ix, row - iy
        a, b = grid.heights[iy * grid.columns + ix:iy * grid.columns + ix + 2]
        c, d = grid.heights[(iy + 1) * grid.columns + ix:(iy + 1) * grid.columns + ix + 2]
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty

    identifiers = (507048725, 508221117)
    owned = unary_union([Polygon(scene.footprint(identifier).ring) for identifier in identifiers])
    front = [(62.498221998, 257.336754908), (65.463215204, 257.550362644),
             (67.039129401, 257.156874710), (74.130743288, 258.101245752),
             (74.918700387, 257.471665057), (105.770876267, 260.979328931),
             (131.797830326, 265.217756112), (137.809049429, 266.195854691)]
    forecourt = Polygon(front + [(x, y - 6) for x, y in reversed(front)])
    zone = unary_union([owned, forecourt])
    upper = [scene.at(station) for station in range(295, 426, 2)]
    upper_guard = Polygon(
        [p.point(p.half_width + p.left_shoulder + 2)[:2] for p in upper]
        + [p.point(-p.half_width - p.right_shoulder - 2)[:2] for p in reversed(upper)]
    )
    other_buildings = [Polygon(b.ring) for b in scene.buildings if b.osm_id not in identifiers]
    patch = zone.difference(unary_union([
        scene.corridor_mask, upper_guard, *scene.water_shapes, *other_buildings, owned,
    ]))

    @lru_cache(maxsize=8192)
    def height(x: float, y: float) -> float:
        point = ShapePoint(x, y)
        blend = min(1.0, point.distance(zone.boundary) / 2,
                    point.distance(scene.corridor_mask) / 2,
                    point.distance(upper_guard) / 2)
        blend = blend * blend * (3 - 2 * blend)
        return measured(x, y) * blend + scene.ground(x, y) * (1 - blend)

    scene.terrain_cutouts.extend(p for p in getattr(patch, 'geoms', [patch]) if isinstance(p, Polygon))
    for row in range(grid.rows - 1):
        for column in range(grid.columns - 1):
            x, y = grid.x + column * grid.step, grid.y + row * grid.step
            cell = patch.intersection(box(x, y, x + grid.step, y + grid.step))
            for triangle in constrained_delaunay_triangles(cell).geoms:
                points = [(px, py, height(px, py)) for px, py in list(triangle.exterior.coords)[:3]]
                if not triangle.exterior.is_ccw:
                    points.reverse()
                normals = tuple(norm((height(px - .5, py) - height(px + .5, py),
                                      height(px, py - .5) - height(px, py + .5), 1.0))
                                for px, py, _z in points)
                scene.triangle('Tile_TabacFineGround', 'Concrete', points[0], points[1], points[2],
                               tuple((px / 4, py / 4) for px, py, _z in points), normals)
    bases: dict[int, tuple[float, float]] = {}
    for identifier in identifiers:
        building = scene.footprint(identifier)
        original_base = min(scene.ground(x, y) for x, y in building.ring)
        base = min(measured(x, y) for x, y in building.ring)
        bases[identifier] = base, original_base + building.height - base
    scene.landmarks.append({
        'name': 'Lower Miramar and retail quay frontage fine ground',
        'ground_patch_area_m2': patch.area, 'sample_interval_m': grid.step,
        'source': 'architecture/tabac-frontage-ground-source.json',
        'dimensions_status': 'Actual retained hotel/retail footprints and six-metre estimated quay-facing strip. Bounded2m IGN RGE ground sampling replaces coarse12m interpolation; outer two-metre transitions meet unchanged terrain/road boundaries. Upper Beau Rivage arm plus2m guard, all racing corridors and water are excluded. Original approximate roof envelopes retained; lower facade bases follow fine source, not a global hill flattening.',
    })
    return bases
