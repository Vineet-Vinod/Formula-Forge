"""The named mosque keeps its open arcades and leaves the physical circuit fixed."""

from __future__ import annotations

import csv
import math
import struct
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from circuit_mesh import MeshScene, cross, sub
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from venues.jeddah_return_context import (
    build,
    occupied_plan,
    source_record,
    write_lights,
)
from venues.jeddah_return_context_dataclasses import MosqueOpening
from venues.jeddah_return_geometry import wall


def test_porch_washes_cannot_illuminate_the_racing_surface(tmp_path: Path) -> None:
    scene = CircuitScene("jeddah")
    scene.data = tmp_path
    write_lights(scene)
    rows = list(csv.DictReader((tmp_path / "mosque_lights.csv").open()))
    assert len(rows) == 3
    source = source_record()
    center = scene.geo(source.latitude, source.longitude)
    plan = occupied_plan(source)
    for row in rows:
        origin = -float(row["y"]) / 100, -float(row["x"]) / 100
        target = -float(row["target_y"]) / 100, -float(row["target_x"]) / 100
        road, distance = scene.nearest(*origin)
        assert distance > road.half_width + 35
        assert plan.buffer(.1).covers(ShapePoint(target[0] - center[0], target[1] - center[1]))
        assert float(row["z"]) / 100 > source.floor_relative_m
        assert 0 < float(row["power"]) <= 1


def test_pointed_arcade_is_open_and_the_masonry_shell_is_closed() -> None:
    scene = MeshScene()
    wall(
        scene,
        (0, 0, 0),
        (10, 0, 0),
        5,
        (MosqueOpening(5, 2.5, 0, 2.4, 3.8),),
        "Building_TestArcade",
    )
    edges: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = (
        Counter()
    )
    front_triangles = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            a = struct.unpack_from("<I24f", tile.triangles, offset)
            points = [
                (-a[2 + i * 8] / 100, -a[1 + i * 8] / 100, a[3 + i * 8] / 100)
                for i in range(3)
            ]
            for first, last in zip(points, points[1:] + points[:1], strict=True):
                edges[(first, last)] += 1
            if all(abs(p[1]) < 1e-8 for p in points):
                front_triangles.append(Polygon([(p[0], p[2]) for p in points]))
    assert front_triangles
    assert not any(tri.covers(ShapePoint(5, 2)) for tri in front_triangles)
    assert all(
        count == 1 and edges[(last, first)] == 1
        for (first, last), count in edges.items()
    )


def test_mosque_retains_published_scale_source_registration_and_driving_inputs() -> (
    None
):
    scene = CircuitScene("jeddah")
    before = list(scene.road), scene.grid, list(scene.buildings)
    source = source_record()
    shape = occupied_plan(source)
    assert shape.area == pytest.approx(200.96)
    assert shape.covers(ShapePoint(source.minaret_center_x_m, -6.4))
    assert not shape.covers(ShapePoint(-2.5, -7))
    assert source.minaret_center_x_m < -source.hall_side_m / 2
    assert source.minaret_shaft_m + source.minaret_crown_m + 1.04 == pytest.approx(19)
    assert abs(shape.area / source.published_floor_m2 - 1) < 0.04
    build(scene)
    assert before == (scene.road, scene.grid, scene.buildings)
    assert len(scene.terrain_cutouts) == 1
    assert scene.landmarks[-1]["native_nearest_station_m"] == pytest.approx(
        4195.81448, abs=0.01
    )
    assert scene.landmarks[-1]["distance_from_road_m"] == pytest.approx(
        72.72371, abs=0.01
    )
    count = 0
    highest = -math.inf
    for tile in scene.tiles.values():
        assert set(tile.materials) <= {"Cream", "Trunk"}
        for offset in range(0, len(tile.triangles), 100):
            a = struct.unpack_from("<I24f", tile.triangles, offset)
            points = [
                (-a[2 + i * 8] / 100, -a[1 + i * 8] / 100, a[3 + i * 8] / 100)
                for i in range(3)
            ]
            highest = max(highest, *(p[2] for p in points))
            n = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = math.sqrt(sum(v * v for v in n))
            assert length > 0
            for i in range(3):
                stored = (-a[5 + i * 8], -a[4 + i * 8], a[6 + i * 8])
                assert (
                    sum(x * y for x, y in zip(n, stored, strict=True)) / length > 0.96
                )
            count += 1
    assert count > 5000
    assert source.floor_relative_m + 18.9 < highest <= source.floor_relative_m + 19.001
