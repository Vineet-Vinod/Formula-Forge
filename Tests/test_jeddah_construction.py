"""The unfinished tower keeps its site and contains real closed concrete geometry."""

from __future__ import annotations

import json
import math
import struct
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from circuit_dataclasses import MeshTile, Point
from circuit_mesh import MeshScene, cross, sub
from circuit_scene import CircuitScene
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.geometry import Point as PlanPoint
from venues.east_architecture import frame, mapped
from venues.jeddah_construction import (
    build_construction,
    floor_plate,
    slab,
    source_record,
)


class ConstructionScene(MeshScene):
    def tile(self, kind: str, point: Point) -> MeshTile:
        return self.tiles.setdefault(kind, MeshTile())


def packed_faces(tile: MeshTile) -> Iterator[tuple[list[Point], list[Point]]]:
    for offset in range(0, len(tile.triangles), 100):
        values = [struct.unpack_from('<8f', tile.triangles, offset + 4 + 32 * i) for i in range(3)]
        yield ([(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in values],
               [(-v[4], -v[3], v[5]) for v in values])


def test_actual_site_construction_is_closed_concrete_and_keeps_road_exact() -> None:
    scene = CircuitScene('jeddah')
    recipe = source_record()
    building = mapped(scene, recipe.osm_id)
    assert building is not None
    before = list(scene.road), scene.grid, list(scene.buildings), list(scene.terrain_cutouts)
    center, _axis, _normal, _length, _width = frame(building)
    road, _distance = scene.nearest(center[0], center[1])
    mesh = ConstructionScene()
    report = build_construction(mesh, building, road.z, recipe)
    assert before == (scene.road, scene.grid, scene.buildings, scene.terrain_cutouts)
    assert not scene.tiles
    assert report.height_m == 300 and report.height_uncertainty_m == 80
    assert report.maximum_plate_outside_footprint_m2 < 1e-6
    assert report.core_outside_footprint_m2 == 0
    assert 70 < report.side_crane_tip_relative_m < 80
    assert report.floor_count == 67
    footprint = Polygon(building.ring).buffer(.0002)
    vertices: list[tuple[float, float]] = []
    triangles = 0
    for kind, tile in mesh.tiles.items():
        for points, normals in packed_faces(tile):
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = math.sqrt(sum(v * v for v in normal))
            assert length > 1e-9
            assert all(sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .995
                       for stored in normals)
            if 'Crane' not in kind:
                assert all(footprint.covers(PlanPoint(p[:2])) for p in points), kind
            vertices.extend(p[:2] for p in points)
            triangles += 1
    assert mesh.tiles['Building_DiamondExposedCore'].materials == ['Concrete']
    assert {'Building_DiamondSideCraneMast', 'Building_DiamondSideCraneCab',
            'Building_DiamondSideCraneBoom'} <= mesh.tiles.keys()
    materials = {material for tile in mesh.tiles.values() for material in tile.materials}
    assert materials == {'Concrete', 'JeddahConstruction', 'Steel', 'Yellow'}
    road_line = LineString([(s.x, s.y) for s in scene.road])
    assert MultiPoint(vertices).convex_hull.distance(road_line) > max(s.half_width for s in scene.road) + 2
    print(json.dumps({'proof': asdict(report), 'triangles': triangles,
                      'road_clearance_m': MultiPoint(vertices).convex_hull.distance(road_line)}, sort_keys=True))


def test_construction_slab_is_a_closed_outward_solid() -> None:
    scene = CircuitScene('jeddah')
    recipe = source_record()
    building = mapped(scene, recipe.osm_id)
    assert building is not None
    polygon = floor_plate(building, recipe, .3)
    mesh = ConstructionScene()
    slab(mesh, polygon, 100, recipe.slab_depth_m)
    tile = mesh.tiles['Building_DiamondConcreteSlab']
    edges: Counter[tuple[Point, Point]] = Counter()
    center = polygon.centroid.x, polygon.centroid.y, 100 - recipe.slab_depth_m / 2
    for points, normals in packed_faces(tile):
        centroid = tuple(sum(p[i] for p in points) / 3 for i in range(3))
        if abs(normals[0][2]) > .9:
            assert normals[0][2] * (centroid[2] - center[2]) > 0
        else:
            exterior = PlanPoint(centroid[0] + normals[0][0] * .01,
                                 centroid[1] + normals[0][1] * .01)
            assert not polygon.buffer(.0002).covers(exterior)
        for i in range(3):
            a, b = points[i], points[(i + 1) % 3]
            edges[(a, b) if a < b else (b, a)] += 1
    assert set(edges.values()) == {2}
    assert tile.maximum[2] - tile.minimum[2] == pytest.approx(recipe.slab_depth_m * 100)
