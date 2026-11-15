"""Original shallow irregular stone facing, separate from natural cliff rock."""
from __future__ import annotations

import random
import struct
from itertools import pairwise

from circuit_mesh import MeshScene, cross, sub
from shapely import constrained_delaunay_triangles, get_parts, voronoi_polygons
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from venues.monaco_terrace_dataclasses import StoneCell, TerraceSpec


class StoneFacing:
    def __init__(self, perimeter_m: float, zmin: float, zmax: float, source: TerraceSpec) -> None:
        rng = random.Random(94399624)
        seeds = []
        y = zmin - 1
        row = 0
        while y < zmax + 1:
            x = -1 + (row % 2) * 0.33
            while x < perimeter_m + 1:
                seeds.append((x + rng.uniform(-0.16, 0.16), y + rng.uniform(-0.11, 0.11)))
                x += rng.uniform(0.53, 0.94)
            y += rng.uniform(0.32, 0.52)
            row += 1
        cells = []
        for index, poly in enumerate(voronoi_polygons(MultiPoint(seeds)).geoms):
            shape = poly.buffer(-source.mortar_joint_m / 2, join_style='bevel')
            for piece in get_parts(shape):
                if not isinstance(piece, Polygon) or piece.area < 0.003:
                    continue
                shade = rng.random()
                material = ('MonacoTerraceStoneLight' if shade < 0.50 else
                            'MonacoTerraceStoneMid' if shade < 0.88 else 'MonacoTerraceStoneDark')
                cells.append(StoneCell(piece, material, rng.uniform(0.012, source.maximum_stone_relief_m)))
        self.cells = tuple(cells)
        self.index = STRtree([cell.plan for cell in cells])
        self.omitted_facing_area_m2 = 0.0
        self.omitted_facing_faces = 0
        self.faces = 0
        self.stones: set[int] = set()
        self.minimum_joint_m = source.mortar_joint_m
        self.maximum_relief_m = 0.0

    def emit(self, scene: MeshScene, a: Point, b: Point,
             lower: list[float], upper: list[float], u0: float, u1: float) -> None:
        strip = Polygon(((u0, lower[0]), (u1, lower[1]), (u1, upper[1]), (u0, upper[0])))
        if strip.area <= 1e-8:
            return
        origin_x, origin_y = a.x, a.y
        length = a.distance(b)
        tx, ty = (b.x - a.x) / length, (b.y - a.y) / length

        def vertex(u: float, z: float, relief: float) -> tuple[float, float, float]:
            distance = (u - u0) / (u1 - u0) * length
            return origin_x + tx * distance + ty * relief, origin_y + ty * distance - tx * relief, z

        for i in self.index.query(strip):
            cell = self.cells[int(i)]
            intersection = cell.plan.intersection(strip)
            for piece in get_parts(intersection):
                if not isinstance(piece, Polygon) or piece.area < 1e-8:
                    continue
                self.stones.add(int(i))
                self.maximum_relief_m = max(self.maximum_relief_m, cell.relief_m)
                for tri in constrained_delaunay_triangles(piece).geoms:
                    points = list(orient(tri).exterior.coords)[:3]
                    self.triangle(scene, cell.material,
                        [vertex(u, z, cell.relief_m) for u, z in points],
                        tuple((u / 2, z / 2) for u, z in points))
                # Close the relief only at real stone boundaries, not retained-plane split seams.
                points = list(orient(piece).exterior.coords)
                for first, second in pairwise(points):
                    mid = Point((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
                    if mid.distance(cell.plan.boundary) > 1e-7:
                        continue
                    a = vertex(first[0], first[1], 0.001)
                    b = vertex(second[0], second[1], 0.001)
                    c = vertex(second[0], second[1], cell.relief_m)
                    d = vertex(first[0], first[1], cell.relief_m)
                    self.triangle(scene, cell.material, [a, b, c])
                    self.triangle(scene, cell.material, [a, c, d])

    def triangle(self, scene: MeshScene, material: str,
                 points: list[tuple[float, float, float]],
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1))) -> None:
        packed = [(struct.unpack('<f', struct.pack('<f', p[0] * 100))[0] / 100,
                   struct.unpack('<f', struct.pack('<f', p[1] * 100))[0] / 100,
                   struct.unpack('<f', struct.pack('<f', p[2] * 100))[0] / 100) for p in points]
        a, b, c = packed
        normal = cross(sub(b, a), sub(c, a))
        length_squared = sum(v * v for v in normal)
        if length_squared < 1e-12:
            original = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            self.omitted_facing_area_m2 += sum(v * v for v in original) ** 0.5 / 2
            self.omitted_facing_faces += 1
            return
        scene.triangle('Building_HermosaStone', material, a, b, c, uv)
        self.faces += 1
