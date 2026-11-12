"""Retained ground must rebuild exactly and reject corrupt source data before writing."""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from circuit_ground import interpolate_ground
from circuit_terrain import materialize_retained_ground


def test_classified_ground_triangles_preserve_a_sloping_ground_plane() -> None:
    xy = np.array([(x, y) for x in (0, 1, 2) for y in (0, 2)], dtype=np.float64)
    xy = np.vstack((xy, [[0.5, 1], [1.5, 1]]))
    points = np.column_stack((xy, 10 + 2 * xy[:, 0] - 0.5 * xy[:, 1]))
    targets = np.array([[0.8, 0.7], [1.2, 1.3]])
    heights, _, triangles = interpolate_ground(points, cKDTree(xy), targets)
    np.testing.assert_allclose(heights, 10 + 2 * targets[:, 0] - 0.5 * targets[:, 1], atol=1e-10)
    assert triangles.all()


def test_ground_outside_a_nearly_collinear_hull_uses_bounded_support() -> None:
    x = np.arange(8, dtype=np.float64)
    points = np.column_stack((x, np.where(x % 2, 1e-9, -1e-9), 10 + x * 0.1))
    heights, _, triangles = interpolate_ground(points, cKDTree(points[:, :2]), np.array([[3.5, 1.0]]))
    assert not triangles[0]
    assert points[:, 2].min() <= heights[0] <= points[:, 2].max()


def retained_source(tmp_path: Path, heights: list[float], step: float = 12) -> tuple[Path, Path]:
    source = tmp_path / 'source'
    source.mkdir()
    encoded = gzip.compress(json.dumps({'x': -12, 'y': 24, 'step': step, 'columns': 3,
                                       'rows': 2, 'heights': heights}).encode(), mtime=0)
    (source / 'ground.json.gz').write_bytes(encoded)
    (source / 'scenery-ground.json').write_text(json.dumps({
        'grid_file': 'ground.json.gz', 'grid_sha256': hashlib.sha256(encoded).hexdigest(),
        'relative_datum_m': 7.5, 'road_join_distance_m': 2,
    }))
    destination = tmp_path / 'terrain.bin'
    return source, destination


def test_retained_ground_preserves_relative_samples_and_binary_contract(tmp_path: Path) -> None:
    heights = [-1.5, 0.0, 2.25, 3.5, 4.0, 9.75]
    source, destination = retained_source(tmp_path, heights)
    assert materialize_retained_ground(source, destination)
    payload = destination.read_bytes()
    assert payload[:8] == b'FFTRN1\0\0'
    assert struct.unpack_from('<ddfII', payload, 8) == (-12.0, 24.0, 12.0, 3, 2)
    assert struct.unpack_from('<6f', payload, 36) == tuple(heights)
    first = payload
    assert materialize_retained_ground(source, destination)
    assert destination.read_bytes() == first


def test_ground_frame_registration_changes_horizontal_coordinates_only(tmp_path: Path) -> None:
    heights = [-1.5, 0.0, 2.25, 3.5, 4.0, 9.75]
    source, destination = retained_source(tmp_path, heights)
    manifest = source / 'scenery-ground.json'
    record = json.loads(manifest.read_text())
    record['grid_uniform_scale'] = 1.0
    manifest.write_text(json.dumps(record))
    (source / 'provenance.json').write_text(json.dumps({
        'origin': {'latitude': 0, 'longitude': 0}, 'route': {'uniform_scale': 1.5},
    }))
    assert materialize_retained_ground(source, destination)
    payload = destination.read_bytes()
    assert struct.unpack_from('<ddfII', payload, 8) == (-18.0, 36.0, 18.0, 3, 2)
    assert struct.unpack_from('<6f', payload, 36) == tuple(heights)
    assert materialize_retained_ground(source, destination)
    assert destination.read_bytes() == payload


@pytest.mark.parametrize(('heights', 'step'), [([1.0], 12.0), ([0.0] * 6, 0.0),
                                               ([0.0] * 5 + [float('nan')], 12.0)])
def test_bad_ground_shape_or_values_preserve_existing_binary(
    tmp_path: Path, heights: list[float], step: float,
) -> None:
    source, destination = retained_source(tmp_path, heights, step)
    destination.write_bytes(b'existing accepted grid')
    with pytest.raises(ValueError, match='invalid dimensions or nonfinite'):
        materialize_retained_ground(source, destination)
    assert destination.read_bytes() == b'existing accepted grid'


def test_changed_ground_source_hash_preserves_existing_binary(tmp_path: Path) -> None:
    source, destination = retained_source(tmp_path, [0.0] * 6)
    (source / 'ground.json.gz').write_bytes(b'damaged source')
    destination.write_bytes(b'existing accepted grid')
    with pytest.raises(ValueError, match='hash does not match'):
        materialize_retained_ground(source, destination)
    assert destination.read_bytes() == b'existing accepted grid'
