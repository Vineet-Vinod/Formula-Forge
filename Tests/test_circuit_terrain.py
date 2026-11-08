"""Retained ground must rebuild exactly and reject corrupt source data before writing."""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from circuit_terrain import materialize_retained_ground


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
