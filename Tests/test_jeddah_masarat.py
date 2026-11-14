"""Actual-ground and source-form invariants for the isolated post-terrain Masarat stage."""

from __future__ import annotations

import base64
import hashlib
import math
import struct
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import TypeAdapter, ValidationError
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from venues.jeddah_masarat import LANDMARK, finish_terrain, placement, validate_site
from venues.jeddah_masarat_dataclasses import MasaratSource
from venues.jeddah_masarat_geometry import plans, xy


def proof_metadata() -> dict[str, str]:
    return TypeAdapter(dict[str, str]).validate_json((ROOT / 'Tests/fixtures/jeddah_masarat_proof.json').read_bytes())


def source_config(scene: CircuitScene) -> MasaratSource:
    return TypeAdapter(MasaratSource).validate_json((scene.sources / 'masarat-architecture.json').read_bytes())


def bounded_scene(ground: bool = True) -> CircuitScene:
    scene = CircuitScene('jeddah')
    reserve = max(r.half_width for r in scene.road) + max(
        max(r.left_shoulder, r.right_shoulder) for r in scene.road) + 3
    scene.corridor_mask = LineString([(r.x, r.y) for r in scene.road]).buffer(reserve)
    if ground:
        fixture = TypeAdapter(dict[str, dict[str, list[str]]]).validate_json(
            (ROOT / 'Tests/fixtures/jeddah_masarat_ground.json').read_bytes())
        for name, record in fixture.items():
            tile = MeshTile(materials=record['materials'])
            for encoded in record['rows']:
                raw = base64.b64decode(encoded)
                tile.triangles.extend(raw)
                for i in range(3):
                    point = struct.unpack_from('<3f', raw, 4 + i * 32)
                    for axis in range(3):
                        tile.minimum[axis] = min(tile.minimum[axis], point[axis])
                        tile.maximum[axis] = max(tile.maximum[axis], point[axis])
            scene.tiles[name] = tile
    scene.triangle('Building_ExistingPrefix', 'Steel', (10, -10, 1), (11, -10, 1), (10, -9, 1))
    return scene


def mesh_rows(scene: CircuitScene) -> dict[str, list[tuple[str, bytes]]]:
    return {name: [(tile.materials[struct.unpack_from('<I', tile.triangles, off)[0]],
                    bytes(tile.triangles[off:off + 100])) for off in range(0, len(tile.triangles), 100)]
            for name, tile in scene.tiles.items()}


def geometry_digest(records: list[tuple[str, bytes]]) -> str:
    keys = [material.encode() + b'\0' + b''.join(raw[4 + i * 32:16 + i * 32] for i in range(3))
            for material, raw in records]
    return hashlib.sha256(b''.join(sorted(keys))).hexdigest()


def points(raw: bytes) -> NDArray[np.float64]:
    values = np.array(struct.unpack('<I24f', raw)[1:]).reshape(3, 8)
    return np.column_stack((-values[:, 1] / 100, -values[:, 0] / 100, values[:, 2] / 100))


@pytest.fixture(scope='module')
def promoted() -> tuple[CircuitScene, dict[str, list[tuple[str, bytes]]], list[tuple[str, bytes]]]:
    scene = bounded_scene()
    before = mesh_rows(scene)
    grid, road = scene.grid, list(scene.road)
    native_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scene.data.glob('*.bin')}
    finish_terrain(scene)
    assert scene.grid == grid and scene.road == road
    assert not scene.terrain_cutouts and not scene.emitted_terrain_cells
    assert native_before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scene.data.glob('*.bin')}
    after = mesh_rows(scene)
    added = []
    for name, records in after.items():
        if name.startswith('Building_'):
            prefix = before.get(name, [])
            assert records[:len(prefix)] == prefix
            added.extend(records[len(prefix):])
    return scene, before, added


def test_wgs_controls_and_source_height_are_distinct_from_sail() -> None:
    scene = bounded_scene()
    source = source_config(scene)
    config = placement(scene, source)
    assert config.origin == pytest.approx((139.8261860806418, -137.46551918839174), abs=1e-9)
    assert config.axis == pytest.approx((.9743024679963304, .22524364776006423), abs=1e-12)
    with pytest.raises(ValueError, match='scene scale'):
        placement(scene, replace(source, expected_route_uniform_scale=source.expected_route_uniform_scale + .001))
    bad = replace(source, dimensions=replace(source.dimensions, high_height_m=264.7))
    with pytest.raises(ValidationError):
        TypeAdapter(MasaratSource).validate_python(asdict(bad))


def test_source_reviewed_model_geometry_and_actual_support_remain_fixed(
    promoted: tuple[CircuitScene, dict[str, list[tuple[str, bytes]]], list[tuple[str, bytes]]],
) -> None:
    scene, _before, added = promoted
    meta = proof_metadata()
    assert len(added) == int(meta['canonical_architecture_triangles'])
    assert geometry_digest(added) == meta['canonical_architecture_geometry_sha256']
    certificate = scene.sources / 'architecture/masarat/round-join-proof.json'
    assert hashlib.sha256(certificate.read_bytes()).hexdigest() == meta['round_join_certificate_sha256']
    config = placement(scene, source_config(scene))
    high = max(float(points(raw)[:, 2].max()) for _material, raw in added)
    assert high == pytest.approx(config.entrance_relative_m + config.high_height_m + 1.1, abs=2e-5)
    row = next(row for row in scene.landmarks if row['name'] == LANDMARK)
    assert row['minimum_foundation_burial_m'] >= .1199
    assert row['fence_minimum_ground_burial_m'] > .02
    assert 0 < row['estimated_entry_step_m'] < .6
    assert row['maximum_exposed_basement_m'] < 5
    assert row['maximum_ground_above_first_floor_m'] < 2
    for path in scene.data.glob('*.bin'):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == meta['native_' + path.name + '_sha256']


def test_ground_keeps_ordered_outside_rows_original_planes_normals_and_uvs(
    promoted: tuple[CircuitScene, dict[str, list[tuple[str, bytes]]], list[tuple[str, bytes]]],
) -> None:
    scene, before, _added = promoted
    config = placement(scene, source_config(scene))
    mask = unary_union([plan for _n, plan, _h in plans(config)])
    old = [raw for name, rows in before.items() if name.startswith('Tile_Street_') for _m, raw in rows]
    shapes = [Polygon(points(raw)[:, :2]) for raw in old]
    index = STRtree(shapes)
    before_area = sum(plan.area for plan in shapes)
    after_area = 0.
    intrusion = 0.
    for name, rows in mesh_rows(scene).items():
        if not name.startswith('Tile_Street_'):
            continue
        unchanged = [raw for _m, raw in before[name] if Polygon(points(raw)[:, :2]).intersection(mask).area < 1e-9]
        unchanged_set = set(unchanged)
        assert [raw for _m, raw in rows if raw in unchanged_set] == unchanged
        for _material, raw in rows:
            new_points = points(raw)
            plan = Polygon(new_points[:, :2])
            after_area += plan.area
            intrusion += plan.intersection(mask).area
            center = plan.centroid
            owners = [int(i) for i in index.query(center.buffer(2e-5)) if shapes[int(i)].distance(center) < 2e-5]
            assert owners
            owner = old[owners[0]]
            old_points = points(owner)
            matrix = np.column_stack((old_points[:, :2], np.ones(3)))
            height_plane = np.linalg.solve(matrix, old_points[:, 2])
            old_attributes = np.array(struct.unpack('<I24f', owner)[1:]).reshape(3, 8)[:, 3:8]
            attr_planes = np.linalg.solve(matrix, old_attributes)
            attributes = np.array(struct.unpack('<I24f', raw)[1:]).reshape(3, 8)[:, 3:8]
            for vertex, attrs in zip(new_points, attributes, strict=True):
                coordinate = np.array((vertex[0], vertex[1], 1.))
                assert vertex[2] == pytest.approx(coordinate @ height_plane, abs=2e-5)
                expected = coordinate @ attr_planes
                assert attrs[:3] == pytest.approx(expected[:3], abs=2e-7)
                assert attrs[3:] == pytest.approx(expected[3:], abs=5e-6)
    assert before_area - after_area == pytest.approx(mask.area, abs=.02)
    assert intrusion < .02


def test_all_five_loggias_and_round_core_are_exposed_in_actual_mesh(
    promoted: tuple[CircuitScene, dict[str, list[tuple[str, bytes]]], list[tuple[str, bytes]]],
) -> None:
    scene, _before, added = promoted
    config = placement(scene, source_config(scene))
    triangles = np.array([points(raw) for _m, raw in added])
    e1, e2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]

    def hit(u: float, v: float, z: float) -> tuple[str, NDArray[np.float64]]:
        origin = np.array((*xy(config, u, v), z))
        direction = np.array((*config.normal, 0.))
        h = np.cross(direction, e2)
        a = np.einsum('ij,ij->i', e1, h)
        valid = np.abs(a) > 1e-9
        inverse = np.zeros(len(a))
        inverse[valid] = 1 / a[valid]
        delta = origin - triangles[:, 0]
        first = inverse * np.einsum('ij,ij->i', delta, h)
        q = np.cross(delta, e1)
        second = inverse * np.einsum('j,ij->i', direction, q)
        distance = inverse * np.einsum('ij,ij->i', e2, q)
        valid &= (first >= -1e-8) & (second >= -1e-8) & (first + second <= 1 + 1e-8) & (distance > 0)
        candidates = np.flatnonzero(valid)
        assert len(candidates)
        selected = int(candidates[np.argmin(distance[candidates])])
        return added[selected][0], origin + direction * distance[selected]

    samples = [(w.center - w.width / 2 + 3.1, w.front, w.entry_relative_m + 2 * w.height / w.floors + 2)
               for w in config.wings]
    samples.append((115.6, 24.5, config.entrance_relative_m + 2 * (config.high_height_m - 1.1) / config.high_floors + 2))
    for u, v, z in samples:
        material, actual = hit(u, v - 10, z)
        assert material in ('Glass', 'WarmGlass')
        assert math.dist(tuple(actual[:2]), xy(config, u, v)) == pytest.approx(1.35, abs=2e-5)
    for u in (133.7, 135., 136.3):
        material, actual = hit(u, 14, config.entrance_relative_m + 110)
        assert material == 'White'
        assert math.dist(tuple(actual[:2]), xy(config, 135, 28)) == pytest.approx(3.2, abs=.008)


@pytest.mark.parametrize('conflict', ('cutout', 'street', 'existing_body'))
def test_conflicting_site_input_fails_before_mutating_any_geometry(conflict: str) -> None:
    scene = bounded_scene()
    source = source_config(scene)
    config = placement(scene, source)
    components = plans(config)
    if conflict == 'cutout':
        scene.terrain_cutouts.append(components[0][1])
    elif conflict == 'street':
        street = replace(source.streets[0], path_wgs84_lon_lat=source.frontage_controls_wgs84_lon_lat,
                         estimated_width_m=20)
        source = replace(source, streets=(street,))
    else:
        x, y = components[0][1].centroid.coords[0]
        scene.triangle('Building_Conflict', 'White', (x, y, 10), (x + 1, y, 10), (x, y + 1, 10))
    before = mesh_rows(scene)
    with pytest.raises(ValueError):
        validate_site(scene, source, components)
    assert mesh_rows(scene) == before
    assert not scene.landmarks


def test_wrong_pipeline_order_and_duplicate_finish_fail_without_emission(
    promoted: tuple[CircuitScene, dict[str, list[tuple[str, bytes]]], list[tuple[str, bytes]]],
) -> None:
    empty = bounded_scene(ground=False)
    before = mesh_rows(empty)
    with pytest.raises(ValueError, match='actual emitted terrain'):
        finish_terrain(empty)
    assert mesh_rows(empty) == before
    scene = promoted[0]
    before = mesh_rows(scene)
    with pytest.raises(ValueError, match='already been added'):
        finish_terrain(scene)
    assert mesh_rows(scene) == before
