"""Measured Sachs front joined to the original exterior terrain planes."""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache

from circuit_dataclasses import Point
from circuit_mesh import norm
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import STRtree, constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.hockenheim_dataclasses import (
    SachsForecourtSource,
    SachsGroundTriangle,
    SachsStandSource,
)
from venues.hockenheim_sachs import SachsFoundation


def weights(points: tuple[Point, Point, Point], x: float, y: float) -> tuple[float, float, float]:
    a, b, c = points
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
    return u, v, 1 - u - v


def plane(points: tuple[Point, Point, Point], x: float, y: float) -> float:
    return sum(weight * point[2] for weight, point in zip(weights(points, x, y), points, strict=True))


def build_sachs_forecourt(scene: CircuitScene) -> None:
    source = TypeAdapter(SachsForecourtSource).validate_json(
        (scene.sources / 'sachs-forecourt-correction.json').read_bytes()
    )
    section = TypeAdapter(SachsStandSource).validate_json(
        (scene.sources / 'sachs-stand-correction.json').read_bytes()
    )
    if abs(scene.provenance.route.uniform_scale - source.uniform_scale) > 1e-10:
        raise ValueError('Sachs retained exterior planes need their registered source frame')
    shape = Polygon(scene.footprint(232009782).ring)
    first, last = section.front_ring_indices
    front = LineString(scene.footprint(232009782).ring[first:last + 1])
    foundation = SachsFoundation(scene, section, front)
    if abs(foundation.datum - source.ground_datum_nhn_m) > 1e-8:
        raise ValueError('Sachs foundation and retained exterior planes need the same NHN datum')
    a, b = front.interpolate(0), front.interpolate(source.taper_end_m)
    tx, ty = (b.x - a.x) / source.taper_end_m, (b.y - a.y) / source.taper_end_m
    short = LineString([a, b])
    zone = short.buffer(source.width_m).difference(shape)
    if zone.intersects(scene.corridor_mask):
        raise ValueError('Sachs low-end forecourt must remain outside the protected corridor')
    cells = unary_union([
        box(source.grid_x_m + column * source.grid_step_m, source.grid_y_m + row * source.grid_step_m,
            source.grid_x_m + (column + 1) * source.grid_step_m,
            source.grid_y_m + (row + 1) * source.grid_step_m)
        for column, row in source.cells
    ]).difference(unary_union([scene.corridor_mask, *scene.extra_corridors]))
    surfaces = [Polygon([p[:2] for p in triangle.points]) for triangle in source.triangles]
    surface_index = STRtree(surfaces)

    @lru_cache(maxsize=4096)
    def legacy(x: float, y: float) -> float:
        point = ShapePoint(x, y)
        covered = surface_index.query(point, predicate='covered_by')
        index = int(min(covered)) if len(covered) else int(surface_index.nearest(point))
        return plane(source.triangles[index].points, x, y)

    @lru_cache(maxsize=4096)
    def rise(x: float, y: float) -> float:
        point = ShapePoint(x, y)
        foot = front.interpolate(front.project(point))
        along = (x - a.x) * tx + (y - a.y) * ty
        taper = max(0., min(1., (source.taper_end_m - along)
                            / (source.taper_end_m - source.full_front_length_m)))
        across = max(0., 1. - point.distance(short) / source.width_m)
        weight = taper * taper * (3 - 2 * taper) * across * across * (3 - 2 * across)
        return (foundation.ground(foot.x, foot.y) - legacy(foot.x, foot.y)) * weight

    def original_normal(original: SachsGroundTriangle, x: float, y: float) -> Point:
        factors = weights(original.points, x, y)
        components = [sum(weight * normal[axis] for weight, normal in zip(factors, original.normals, strict=True))
                      for axis in range(3)]
        return components[0], components[1], components[2]

    def emit(part: Polygon, height: Callable[[float, float], float], original: SachsGroundTriangle) -> None:
        left, bottom, right, top = part.bounds
        for ix in range(max(1, math.ceil((right - left) / .75))):
            for iy in range(max(1, math.ceil((top - bottom) / .75))):
                cell = part.intersection(box(left + ix * .75, bottom + iy * .75,
                                             min(right, left + (ix + 1) * .75),
                                             min(top, bottom + (iy + 1) * .75)))
                for triangle in constrained_delaunay_triangles(cell).geoms:
                    points = [(x, y, height(x, y)) for x, y in list(orient(triangle).exterior.coords)[:3]]
                    normals = []
                    for x, y, _z in points:
                        nx, ny, nz = original_normal(original, x, y)
                        gx, gy = (rise(x + .05, y) - rise(x - .05, y)) / .1, (rise(x, y + .05) - rise(x, y - .05)) / .1
                        normals.append(norm((nx - gx * nz, ny - gy * nz, nz)))
                    scene.triangle('Tile_SachsForecourt', 'Grass', points[0], points[1], points[2],
                                   tuple((p[0] / 8, p[1] / 8) for p in points), tuple(normals))

    for original, surface in zip(source.triangles, surfaces, strict=True):
        restored = surface.intersection(cells)
        if restored.area < 1e-10:
            continue
        overlap = restored.intersection(zone)
        if overlap.area < 1e-10 and restored.symmetric_difference(surface).area < 1e-9:
            scene.triangle('Tile_SachsExterior', original.material, *original.points,
                           uv=original.uv, normals=original.normals)
            continue
        for triangle in constrained_delaunay_triangles(restored.difference(zone)).geoms:
            points = [(x, y, plane(original.points, x, y))
                      for x, y in list(orient(triangle).exterior.coords)[:3]]
            scene.triangle('Tile_SachsExterior', original.material, points[0], points[1], points[2],
                           tuple((sum(w * uv[0] for w, uv in zip(weights(original.points, p[0], p[1]), original.uv, strict=True)),
                                  sum(w * uv[1] for w, uv in zip(weights(original.points, p[0], p[1]), original.uv, strict=True))) for p in points),
                           tuple(original_normal(original, p[0], p[1]) for p in points))
        parts = [overlap] if isinstance(overlap, Polygon) else [
            p for p in getattr(overlap, 'geoms', ()) if isinstance(p, Polygon)
        ]
        for part in parts:
            if part.is_empty or part.area < 1e-9:
                continue
            def height(x: float, y: float, points: tuple[Point, Point, Point] = original.points) -> float:
                return plane(points, x, y) + rise(x, y)

            emit(part, height, original)
    scene.terrain_cutouts.extend(p for p in getattr(cells, 'geoms', (cells,)) if isinstance(p, Polygon))
    scene.landmarks.append({'name': 'Sachs visible low-end foundation forecourt',
                            'source': 'sachs-forecourt-correction.json', 'width_estimate_m': source.width_m,
                            'full_front_length_m': source.full_front_length_m,
                            'taper_end_m': source.taper_end_m,
                            'limitation': 'Only the visible low end is joined. The hidden 1.479m mismatch elsewhere remains pending. Measured terraces and protected racing corridor are unchanged.'})
