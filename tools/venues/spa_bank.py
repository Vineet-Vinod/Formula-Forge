"""Refine Blanchimont's coarse grass triangles without changing its ground field."""
from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import cross, norm, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.spa_bank_dataclasses import BankRefinement


def polygon_parts(shape: BaseGeometry) -> list[Polygon]:
    if isinstance(shape, Polygon):
        return [shape] if not shape.is_empty else []
    return [part for part in getattr(shape, 'geoms', ()) if isinstance(part, Polygon) and not part.is_empty]


class BankSurface:
    def __init__(self, scene: CircuitScene, source: BankRefinement) -> None:
        self.scene = scene
        self.source = source
        grid = scene.grid
        x0, y0, x1, y1 = source.core_bounds_m
        margin = grid.step * source.transition_cells
        self.column0 = math.floor((x0 - margin - grid.x) / grid.step)
        self.column1 = math.ceil((x1 + margin - grid.x) / grid.step)
        self.row0 = math.floor((y0 - margin - grid.y) / grid.step)
        self.row1 = math.ceil((y1 + margin - grid.y) / grid.step)
        boxes = []
        for row in range(self.row0, self.row1):
            for column in range(self.column0, self.column1):
                x, y = grid.x + column * grid.step, grid.y + row * grid.step
                sample, _distance = scene.nearest(x + grid.step / 2, y + grid.step / 2)
                lane = (x + grid.step / 2 - sample.x) * sample.ty - (y + grid.step / 2 - sample.y) * sample.tx
                if 5500 <= sample.station <= 5920 and lane < -6:
                    boxes.append(box(x, y, x + grid.step, y + grid.step))
        self.region = unary_union(boxes)
        voids = unary_union([scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes,
                             *scene.terrain_cutouts, *[shape for shape, _, _ in scene.ground_patches]])
        self.cells: list[Polygon] = []
        self.old_triangles: list[tuple[Point, Point, Point]] = []
        for cell in boxes:
            shape = cell.difference(voids)
            self.cells.extend(polygon_parts(shape))
            for triangle in constrained_delaunay_triangles(shape).geoms:
                a, b, c = [(x, y, scene.ground(x, y)) for x, y in list(triangle.exterior.coords)[:3]]
                self.old_triangles.append((a, b, c))
        self.old_shapes = [Polygon([point[:2] for point in triangle]) for triangle in self.old_triangles]
        self.index = STRtree(self.old_shapes)
        self.vertices: dict[tuple[float, float], tuple[Point, Point]] = {}

    def vertex(self, x: float, y: float) -> tuple[Point, Point]:
        key = x, y
        if key in self.vertices:
            return self.vertices[key]
        z = self.scene.ground(x, y)
        normal = self.scene._ground_normal(x, y)
        point = ShapePoint(x, y)
        distance = self.region.boundary.distance(point)
        t = min(1., distance / (self.scene.grid.step * self.source.transition_cells))
        blend = t * t * (3 - 2 * t)
        if blend < 1:
            candidates = self.index.query(point.buffer(.0000001), predicate='intersects')
            if len(candidates):
                a, b, c = self.old_triangles[int(candidates[0])]
                denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
                u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
                v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
                weights = (u, v, 1 - u - v)
                old_z = sum(w * p[2] for w, p in zip(weights, (a, b, c), strict=True))
                old_normals = [self.scene._ground_normal(p[0], p[1]) for p in (a, b, c)]
                old_values = [sum(w * n[i] for w, n in zip(weights, old_normals, strict=True)) for i in range(3)]
                old_normal = norm((old_values[0], old_values[1], old_values[2]))
                z = old_z + blend * (z - old_z)
                mixed = [old_normal[i] + blend * (normal[i] - old_normal[i]) for i in range(3)]
                normal = norm((mixed[0], mixed[1], mixed[2]))
        result = (x, y, z), normal
        if len(self.vertices) >= 8192:
            self.vertices.clear()
        self.vertices[key] = result
        return result


def refine_blanchimont_bank(scene: CircuitScene) -> None:
    source = TypeAdapter(BankRefinement).validate_json((scene.sources / 'bank-refinement.json').read_bytes())
    surface = BankSurface(scene, source)
    scene.terrain_cutouts.extend(surface.cells)
    step = scene.grid.step / source.subdivisions
    count = 0
    for cell in surface.cells:
        xmin, ymin, xmax, ymax = cell.bounds
        xs = [xmin] + [scene.grid.x + i * step for i in range(math.floor((xmin - scene.grid.x) / step) + 1, math.ceil((xmax - scene.grid.x) / step))] + [xmax]
        ys = [ymin] + [scene.grid.y + i * step for i in range(math.floor((ymin - scene.grid.y) / step) + 1, math.ceil((ymax - scene.grid.y) / step))] + [ymax]
        for ya, yb in pairwise(ys):
            for xa, xb in pairwise(xs):
                piece = cell.intersection(box(xa, ya, xb, yb))
                for triangle in constrained_delaunay_triangles(piece).geoms:
                    values = [surface.vertex(x, y) for x, y in list(triangle.exterior.coords)[:3]]
                    if cross(sub(values[1][0], values[0][0]), sub(values[2][0], values[0][0]))[2] < 0:
                        values.reverse()
                    points = [value[0] for value in values]
                    scene.triangle('Tile_Ground', 'Grass', points[0], points[1], points[2],
                                   tuple((p[0] / 8, p[1] / 8) for p in points), tuple(value[1] for value in values))
                    count += 1
    scene.landmarks.append({'name': 'Blanchimont classified-ground bank refinement',
                            'source': 'bank-refinement.json', 'triangles': count,
                            'method': 'Same joined classified-ground field and Grass material. Submetre interior mesh; one original-grid-cell ring rejoins the old emitted planes and interpolated normals exactly. No source-grid, native road, physical corridor or lighting changes.'})
