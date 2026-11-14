"""bounded visual ground removal under the independently modeled buildings."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.jeddah_context_dataclasses import ContextGroundFace, ContextGroundLookup
from venues.jeddah_context_shapes import skin


def affected_cells(scene: CircuitScene, mask: BaseGeometry) -> list[tuple[int, int, Polygon]]:
    grid = scene.grid
    xmin, ymin, xmax, ymax = mask.bounds
    cells = []
    for row in range(max(0, math.floor((ymin - grid.y) / grid.step)),
                     min(grid.rows - 1, math.ceil((ymax - grid.y) / grid.step))):
        for column in range(max(0, math.floor((xmin - grid.x) / grid.step)),
                            min(grid.columns - 1, math.ceil((xmax - grid.x) / grid.step))):
            x, y = grid.x + column * grid.step, grid.y + row * grid.step
            cell = box(x, y, x + grid.step, y + grid.step)
            if cell.intersection(mask).area > 1e-8:
                cells.append((row, column, cell))
    complete = unary_union([cell for _r, _c, cell in cells])
    deferred = unary_union([*[p for p, _m, _s in scene.verge_patches],
                            *[p for p, _z, _m in scene.ground_patches]])
    if complete.intersection(deferred).area > 1e-8:
        raise ValueError('Context cells overlap an existing verge or ground patch')
    if any((r, c) in scene.emitted_terrain_cells for r, c, _cell in cells):
        raise ValueError('A context terrain cell has already been emitted')
    if mask.intersection(unary_union([scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes])).area > 1e-8:
        raise ValueError('The context building/site masks overlap actual racing ground or water')
    return cells


def original_ground(scene: CircuitScene, cells: list[tuple[int, int, Polygon]]) -> list[ContextGroundFace]:
    voids = unary_union([scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes,
                         *scene.terrain_cutouts, *[p for p, _z, _m in scene.ground_patches]])
    faces = []
    for _row, _column, cell in cells:
        for triangle in constrained_delaunay_triangles(cell.difference(voids)).geoms:
            points = [(x, y, scene.ground(x, y)) for x, y in list(triangle.exterior.coords)[:3]]
            if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                points.reverse()
            normals = [scene._ground_normal(x, y) for x, y, _z in points]
            faces.append(ContextGroundFace((points[0], points[1], points[2]),
                                            (normals[0], normals[1], normals[2])))
    return faces


def sample(face: ContextGroundFace, x: float, y: float) -> tuple[float, tuple[float, float, float]]:
    a, b, c = face.points
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    weights = first, second, 1 - first - second
    z = sum(w * p[2] for w, p in zip(weights, face.points, strict=True))
    normals = [sum(w * n[axis] for w, n in zip(weights, face.normals, strict=True)) for axis in range(3)]
    return z, (normals[0], normals[1], normals[2])


def remove_building_ground(scene: CircuitScene, mask: BaseGeometry) -> tuple[list[ContextGroundFace], int]:
    cells = affected_cells(scene, mask)
    faces = original_ground(scene, cells)
    original = unary_union([Polygon([p[:2] for p in face.points]) for face in faces])
    grid = scene.grid
    grid_extent = box(grid.x, grid.y, grid.x + grid.step * (grid.columns - 1),
                      grid.y + grid.step * (grid.rows - 1))
    if mask.intersection(grid_extent).difference(original).area > 1e-7:
        raise ValueError('The context removal crosses an existing nonterrain surface')
    for face in faces:
        region = Polygon([p[:2] for p in face.points]).difference(mask)
        for triangle in constrained_delaunay_triangles(region).geoms:
            xy = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                xy.reverse()
            points, normals = [], []
            for x, y in xy:
                z, normal = sample(face, x, y)
                points.append((x, y, z))
                normals.append(normal)
            scene.triangle('Tile_JeddahContextGround', 'Runoff', points[0], points[1], points[2],
                           tuple((p[0] / 8, p[1] / 8) for p in points), tuple(normals))
    scene.emitted_terrain_cells.update((r, c) for r, c, _cell in cells)
    return faces, len(cells)


def ground_at(lookup: ContextGroundLookup, point: tuple[float, float]) -> float:
    marker = ShapePoint(point)
    for index in lookup.index.query(marker.buffer(1e-8)):
        if lookup.polygons[int(index)].distance(marker) < 1e-8:
            return sample(lookup.faces[int(index)], *point)[0]
    xmin, ymin, xmax, ymax = lookup.bounds
    edge = min(xmax, max(xmin, point[0])), min(ymax, max(ymin, point[1]))
    if math.dist(edge, point) > 4:
        raise ValueError('The proposed field-edge extension exceeds its bounded four-metre allowance')
    marker = ShapePoint(edge)
    for index in lookup.index.query(marker.buffer(1e-8)):
        if lookup.polygons[int(index)].distance(marker) < 1e-8:
            # Only the small new mall tip uses this declared zero-gradient extension of the old edge.
            return sample(lookup.faces[int(index)], *edge)[0]
    raise ValueError('No actual original boundary plane supports the new coverage')


def ground_breaks(line: LineString, lookup: ContextGroundLookup) -> set[float]:
    breaks = {0., 1.}
    for index in lookup.index.query(line, predicate='intersects'):
        cut = line.intersection(lookup.polygons[int(index)])
        if isinstance(cut, LineString) and not cut.is_empty:
            breaks.update(line.project(ShapePoint(p)) / line.length for p in cut.coords)
    xmin, ymin, xmax, ymax = lookup.bounds
    for first, last in pairwise(sorted(breaks)):
        start, end = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
        projected = LineString([(min(xmax, max(xmin, p.x)), min(ymax, max(ymin, p.y))) for p in (start, end)])
        if projected.length < 1e-8 or projected.equals(LineString([start, end])):
            continue
        # The declared small new tip inherits the actual old boundary's piecewise height rhythm.
        for index in lookup.index.query(projected, predicate='intersects'):
            cut = projected.intersection(lookup.polygons[int(index)])
            if isinstance(cut, LineString) and not cut.is_empty:
                breaks.update(first + (last - first) * projected.project(ShapePoint(p)) / projected.length
                              for p in cut.coords)
    return breaks


def courtyard(scene: CircuitScene, shape: BaseGeometry, level: float,
               lookup: ContextGroundLookup) -> float:
    parts = [shape] if isinstance(shape, Polygon) else list(getattr(shape, 'geoms', ()))
    area = 0.
    for part in parts:
        if not isinstance(part, Polygon) or part.area < .001:
            continue
        area += part.area
        skin(scene, part, level, 'Building_ContextCourtyard', 'Concrete')
        for ring in [part.exterior, *part.interiors]:
            for a, b in pairwise(ring.coords):
                line = LineString([a[:2], b[:2]])
                if line.length < 1e-6:
                    continue
                breaks = ground_breaks(line, lookup)
                ordered = sorted(breaks)
                crossings = []
                for first, last in pairwise(ordered):
                    p, q = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
                    za = ground_at(lookup, (p.x, p.y))
                    zb = ground_at(lookup, (q.x, q.y))
                    if (level - za) * (level - zb) < -1e-12:
                        crossings.append(first + (last - first) * (level - za) / (zb - za))
                for first, last in pairwise(sorted({*breaks, *crossings})):
                    p, q = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
                    za = ground_at(lookup, (p.x, p.y))
                    zb = ground_at(lookup, (q.x, q.y))
                    scene.quad('Building_ContextCourtyardRetaining', 'Concrete',
                               (p.x, p.y, za), (q.x, q.y, zb), (q.x, q.y, level), (p.x, p.y, level))
                    scene.quad('Building_ContextCourtyardRetaining', 'Concrete',
                               (q.x, q.y, zb), (p.x, p.y, za), (p.x, p.y, level), (q.x, q.y, level))
    return area
