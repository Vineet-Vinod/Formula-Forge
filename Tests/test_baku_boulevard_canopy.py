"""The striped-crown repair changes lighting without moving the boulevard trees."""
from __future__ import annotations

import math
import struct

import pytest
from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from venues.baku_boulevard_canopy import broadleaf


@pytest.mark.parametrize(('base', 'height', 'seed'), [
    ((-600.0, 100.0, 2.45), 12.0, 550),
    ((-360.0, 360.0, -4.2), 13.8, 5667),
])
def test_existing_tree_geometry_is_preserved(base: Point, height: float, seed: int) -> None:
    original = MeshScene()
    original.broadleaf(base, height, seed)
    corrected = MeshScene()
    broadleaf(corrected, base, height, seed)
    assert corrected.tiles.keys() == original.tiles.keys()
    leaves = 0
    for name, old in original.tiles.items():
        new = corrected.tiles[name]
        assert new.minimum == old.minimum
        assert new.maximum == old.maximum
        assert len(new.triangles) == len(old.triangles)
        for offset in range(0, len(old.triangles), 100):
            old_material = old.materials[struct.unpack_from('<I', old.triangles, offset)[0]]
            new_material = new.materials[struct.unpack_from('<I', new.triangles, offset)[0]]
            old_row = old.triangles[offset + 4:offset + 100]
            new_row = new.triangles[offset + 4:offset + 100]
            if old_material == 'Trunk':
                assert new_material == old_material
                assert new_row == old_row
                continue
            assert old_material == 'TreeCanopy'
            assert new_material == 'BakuSahilCanopy'
            for vertex in range(3):
                start = vertex * 32
                assert new_row[start:start + 12] == old_row[start:start + 12]
                assert new_row[start + 24:start + 32] == old_row[start + 24:start + 32]
                normal = struct.unpack_from('<3f', new_row, start + 12)
                assert math.sqrt(sum(value * value for value in normal)) == pytest.approx(1, abs=1e-6)
                assert normal[2] > .1
            leaves += 1
    assert leaves == 30
