"""The measured hip, level floors and actual ground contacts stay distinct."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path

import pytest
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from venues.monaco_hermosa import (
    configuration,
    finish,
    plane_height,
    prepare,
    roof_triangles,
    support_faces,
)


def test_hip_preserves_the_source_eaves_and_separate_ridge() -> None:
    scene = CircuitScene('monaco')
    source = configuration(scene)
    triangles = roof_triangles(scene, source)
    plan = Polygon([scene.geo(lat, lon) for lon, lat, _z in source.eaves_wgs84])
    assert unary_union([Polygon([p[:2] for p in triangle]) for triangle in triangles]).symmetric_difference(plan).area < 1e-7
    points = {point for triangle in triangles for point in triangle}
    for lon, lat, absolute in source.eaves_wgs84:
        assert (*scene.geo(lat, lon), absolute - source.relative_datum_m) in points
    assert max(point[2] for point in points) == pytest.approx(89.2 - source.relative_datum_m)
    assert min(point[2] for point in points) == pytest.approx(82.1 - source.relative_datum_m)
    assert {triangle[2][2] for triangle in triangles} != {min(point[2] for point in points)}


def test_actual_feet_embed_without_changing_ground_or_tilting_floors() -> None:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    scene.tiles.clear()
    source = configuration(scene)
    body = Polygon(scene.footprint(source.osm_id).ring)
    prepare(scene)
    manifest = json.loads((scene.scratch / 'manifest.json').read_text())
    original = {}
    for record in manifest['tiles']:
        if not record['name'].startswith('Tile_Street_'):
            continue
        b = record['bounds']
        if not box(-b[4] / 100, -b[3] / 100, -b[1] / 100, -b[0] / 100).intersects(body.buffer(.1)):
            continue
        raw = (scene.scratch / record['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == record['sha256']
        scene.tiles[record['name']] = MeshTile(
            materials=list(record['materials']), triangles=bytearray(raw[12:]),
            minimum=list(b[:3]), maximum=list(b[3:]),
        )
        original[record['name']] = raw[12:]
    supports = support_faces(scene, body)
    finish(scene)
    for name, raw in original.items():
        assert bytes(scene.tiles[name].triangles) == raw
    feet: dict[tuple[float, float], float] = {}
    floor_bottoms = []
    roof_edges: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = Counter()
    eave_bottom = min(p[2] for p in source.eaves_wgs84) - source.relative_datum_m - .161
    for name, tile in scene.tiles.items():
        if name in original:
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            points = []
            for corner in range(3):
                wx, wy, wz = struct.unpack_from('<3f', tile.triangles, offset + 4 + corner * 32)
                point = (-wy / 100, -wx / 100, wz / 100)
                points.append(point)
                if material in {'Limestone', 'Cream'} and body.boundary.distance(ShapePoint(point[:2])) < .0002:
                    key = point[:2]
                    feet[key] = min(feet.get(key, point[2]), point[2])
            for a, b in zip(points, points[1:] + points[:1], strict=True):
                if min(a[2], b[2]) >= eave_bottom:
                    edge = (a, b) if a < b else (b, a)
                    roof_edges[edge] += 1
            if material == 'Glass':
                floor_bottoms.append(min(p[2] for p in points))
    assert roof_edges
    assert all(count == 2 for count in roof_edges.values()), [(edge, count) for edge, count in roof_edges.items() if count != 2]
    assert len(feet) > 40
    for (x, y), z in feet.items():
        heights = []
        for support in supports:
            if not support.plan.buffer(.0002).covers(ShapePoint(x, y)):
                continue
            a, b, c = [(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in support.vertices]
            heights.append(plane_height((a, b, c), x, y))
        assert heights
        assert min(heights) - z >= .10
    expected = [source.floor_base_absolute_m - source.relative_datum_m + .75 + i * source.floor_height_m
                for i in range(source.floors)]
    assert floor_bottoms
    for z in floor_bottoms:
        assert min(abs(z - height) for height in expected) < .00002


def test_missing_actual_ground_fails_before_property_emission() -> None:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    prepare(scene)
    scene.tiles.clear()
    with pytest.raises(ValueError, match='actual emitted ground'):
        finish(scene)
    assert not scene.tiles
