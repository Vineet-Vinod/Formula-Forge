"""Personnel paving follows the real divider without consuming the fast lane."""

from __future__ import annotations

import csv
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

from circuit_dataclasses import Point
from circuit_escapes import build_overlay, load_recipe
from circuit_mesh import MeshScene, cross, sub
from circuit_portals_dataclasses import Barrier
from circuit_route_assets import clip_foreign_protection
from circuit_scene import CircuitScene
from pit_routes import encode_route
from pydantic import TypeAdapter
from shapely.geometry import Polygon
from venues.jeddah_facilities import pavilion_footprint
from venues.jeddah_pit_walkway import (
    build_walkway,
    platform,
    station,
    tube,
    walkway_recipe,
)
from venues.jeddah_pits import pit_route_source

ROOT = Path(__file__).resolve().parents[1]


def packed_faces(scene: MeshScene) -> Iterator[tuple[list[Point], list[Point]]]:
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            values = [struct.unpack_from('<8f', tile.triangles, offset + 4 + 32 * i) for i in range(3)]
            yield ([(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in values],
                   [(-v[4], -v[3], v[5]) for v in values])


def test_actual_composed_divider_preserves_route_and_fastlane() -> None:
    route, recipe = pit_route_source(), walkway_recipe()
    original = encode_route(route), tuple(route.barriers)
    with (ROOT / 'build/circuits/jeddah/barriers.csv').open() as handle:
        base = TypeAdapter(list[Barrier]).validate_python(list(csv.DictReader(handle)))
    circuit = CircuitScene('jeddah')
    occupied = [Polygon(building.ring) for building in circuit.buildings]
    occupied.append(pavilion_footprint(circuit))
    escapes = build_overlay(load_recipe(ROOT / 'Attribution/Sources/jeddah/escape-reconstruction.json'),
                            circuit.road, base, circuit.provenance.route.uniform_scale, occupied=occupied)
    walls = clip_foreign_protection(base, [*route.portals, *escapes.portals])
    walls += clip_foreign_protection(route.barriers, list(escapes.portals))
    walls += clip_foreign_protection(list(escapes.barriers), route.portals)
    scene = MeshScene()
    result = build_walkway(scene, route, walls, recipe)
    assert original == (encode_route(route), tuple(route.barriers))
    assert result.proof.fastlane_overlap_m2 == 0
    assert result.proof.wall_overlap_m2 == 0
    assert result.proof.minimum_width_m >= recipe.minimum_width_m
    assert result.proof.minimum_rail_inner_edge_m == pytest.approx(2.165)
    assert len(result.extra_barriers) == len(result.floor_portals) == 83
    assert set(result.extra_barriers).isdisjoint(route.barriers)
    for portal in result.floor_portals:
        footprint = Polygon(portal.polygon_xy_m)
        assert footprint.is_valid and footprint.exterior.is_ccw
        assert footprint.convex_hull.area == pytest.approx(footprint.area, abs=1e-8)
        assert portal.top_m > portal.bottom_m
    faces = 0
    for points, normals in packed_faces(scene):
        normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        length = math.sqrt(sum(v * v for v in normal))
        assert length > 1e-10
        for stored in normals:
            assert sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .90
        faces += 1
    assert faces > 10000
    assert {material for tile in scene.tiles.values() for material in tile.materials} == {'Concrete', 'Steel'}
    print(json.dumps(asdict(result.proof), sort_keys=True))


def test_platform_is_closed_and_outward() -> None:
    route, recipe = pit_route_source(), walkway_recipe()
    with (ROOT / 'build/circuits/jeddah/barriers.csv').open() as handle:
        walls = TypeAdapter(list[Barrier]).validate_python(list(csv.DictReader(handle)))
    first, last = station(route, walls, recipe, 400), station(route, walls, recipe, 404)
    scene = MeshScene()
    platform(scene, first, last, recipe)
    faces = list(packed_faces(scene))
    vertices = {point for points, _normals in faces for point in points}
    center = tuple(sum(point[i] for point in vertices) / len(vertices) for i in range(3))
    edges: Counter[tuple[Point, Point]] = Counter()
    for points, normals in faces:
        centroid = tuple(sum(point[i] for point in points) / 3 for i in range(3))
        assert sum(normals[0][i] * (centroid[i] - center[i]) for i in range(3)) > 0
        for i in range(3):
            a, b = points[i], points[(i + 1) % 3]
            edges[(a, b) if a < b else (b, a)] += 1
    assert len(faces) == 12
    assert set(edges.values()) == {2}


def test_rail_tube_is_closed_and_has_outward_cap_normals() -> None:
    scene = MeshScene()
    tube(scene, (0, 0, 0), (4, 0, .1), .035)
    edges: Counter[tuple[Point, Point]] = Counter()
    faces = list(packed_faces(scene))
    for points, normals in faces:
        centroid = tuple(sum(point[i] for point in points) / 3 for i in range(3))
        assert sum(normals[0][i] * (centroid[i] - (2, 0, .05)[i]) for i in range(3)) > 0
        for i in range(3):
            a, b = points[i], points[(i + 1) % 3]
            edges[(a, b) if a < b else (b, a)] += 1
    assert len(faces) == 32
    assert set(edges.values()) == {2}
