"""The pit-exit terrace shell must close without extending over the fast lane."""

from __future__ import annotations

import math
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, sub
from shapely.geometry import Polygon
from venues.jeddah_pit_exit_geometry import solid


def test_clipped_exit_slabs_are_closed_and_outward_after_native_packing() -> None:
    shape = Polygon([(0, 0), (20, 0), (20, 6), (11, 8), (7, 6), (0, 6)])
    scene = MeshScene()
    solid(scene, shape, 2.3, 2.78, "JeddahEditionStone", "Building_Roof")
    edges: Counter[tuple[Point, Point]] = Counter()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            values = struct.unpack_from("<I24f", tile.triangles, offset)
            points = [
                (-values[2 + i * 8] / 100, -values[1 + i * 8] / 100,
                 values[3 + i * 8] / 100)
                for i in range(3)
            ]
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = math.sqrt(sum(value * value for value in normal))
            assert length > 0
            stored = (-values[5], -values[4], values[6])
            assert sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .99999
            center = tuple(sum(p[axis] for p in points) / 3 for axis in range(3))
            if abs(normal[2]) > length * .9:
                assert normal[2] * (center[2] - 2.54) > 0
            else:
                outside = (center[0] + normal[0] / length * .001,
                           center[1] + normal[1] / length * .001)
                from shapely.geometry import Point as ShapePoint

                assert not shape.contains(ShapePoint(*outside))
            for a, b in zip(points, points[1:] + points[:1], strict=True):
                edges[(a, b)] += 1
    assert edges
    assert all(count == 1 and edges[(b, a)] == 1 for (a, b), count in edges.items())
