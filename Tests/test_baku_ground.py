from __future__ import annotations

import gzip
import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from venues.baku_ground import finish_terrain, public_height
from venues.baku_ground_dataclasses import (
    ControlFieldSource,
    GroundPatchSource,
    PackedPatchRow,
)
from venues.baku_niyazi import tree, validate_ground
from venues.baku_niyazi_dataclasses import TreePose


def test_counted_ground_patch_preserves_other_raw_rows(tmp_path: Path) -> None:
    scene = MeshScene()
    scene.triangle("Tile_Ground", "Runoff", (0, 0, 0), (1, 0, 0), (0, 1, 0))
    name, tile = next(iter(scene.tiles.items()))
    original = bytes(tile.triangles)
    tile.triangles.extend(original)
    scene.triangle("Tile_Ground", "Grass", (2, 0, 0), (3, 0, 0), (2, 1, 0))
    untouched = bytes(tile.triangles[-100:])
    payload = original[4:]
    replacement = bytearray(payload)
    struct.pack_into("<f", replacement, 8, 20.0)
    source = GroundPatchSource(
        1,
        {},
        [PackedPatchRow(name, "Runoff", payload, 2)],
        [PackedPatchRow(name, "Concrete", bytes(replacement), 1)],
        "Focused counted-row fixture",
    )
    path = tmp_path / "delta.json.gz"
    path.write_bytes(gzip.compress(TypeAdapter(GroundPatchSource).dump_json(source)))
    finish_terrain(scene, path)
    result = scene.tiles[name]
    assert bytes(result.triangles[:100]) == untouched
    assert len(result.triangles) == 200
    assert bytes(result.triangles[104:]) == replacement
    assert result.maximum[2] == 20.0


def test_missing_expected_row_rejects_patch_without_mutating_any_tile(
    tmp_path: Path,
) -> None:
    scene = MeshScene()
    scene.triangle("Tile_Ground", "Runoff", (0, 0, 0), (1, 0, 0), (0, 1, 0))
    name, tile = next(iter(scene.tiles.items()))
    before = bytes(tile.triangles)
    source = GroundPatchSource(
        1,
        {},
        [PackedPatchRow(name, "Runoff", before[4:], 2)],
        [],
        "Duplicate row guard",
    )
    path = tmp_path / "delta.json.gz"
    path.write_bytes(gzip.compress(TypeAdapter(GroundPatchSource).dump_json(source)))
    with pytest.raises(ValueError, match="expected original Ground rows"):
        finish_terrain(scene, path)
    assert scene.tiles[name] is tile
    assert bytes(tile.triangles) == before


def test_public_height_bounds_rounding_projection_and_rejects_unqualified_ground() -> (
    None
):
    source = ControlFieldSource(
        1,
        [(0, 0, 2), (2, 0, 4), (0, 2, 6)],
        [(0, 1, 2)],
        0.00025,
        "Native boundary rounding fixture",
        "POLYGON EMPTY",
        "POLYGON EMPTY",
        "POLYGON EMPTY",
        (0, 0, 2, 2),
        [],
    )
    height = public_height(source)
    assert height(0, 0) == 2
    assert height(1, 0) == 3
    assert 2 <= height(-0.0001, 0.1) <= 6
    with pytest.raises(ValueError, match="bounded public control field"):
        height(-0.01, 0.1)


def test_native_tree_root_uses_actual_ground_and_rejects_stale_support() -> None:
    scene = MeshScene()
    scene.triangle('Tile_Ground', 'Runoff', (-10, -10, 0), (10, -10, .4), (0, 10, .2))
    name, tile = next(iter(scene.tiles.items()))
    support = PackedPatchRow(name, 'Runoff', bytes(tile.triangles[4:]), 1)
    pose = TreePose(3640, (0, 0, .12), 12, 3100, 0, 2, name, 0)
    validated_embed = validate_ground(scene, [support], [pose], .075)
    model = MeshScene()
    tree(model, pose, .78)
    actual_trunk = []
    for geometry in model.tiles.values():
        for row in struct.iter_unpack('<I24f', geometry.triangles):
            if geometry.materials[row[0]] != 'Trunk':
                continue
            actual_trunk.extend((-row[i + 1] / 100, -row[i] / 100, row[i + 2] / 100) for i in (1, 9, 17))
    lowest = min(point[2] for point in actual_trunk)
    actual_roots = {point for point in actual_trunk if point[2] == lowest}
    actual_embed = min(.2 + .02 * point[0] - point[2] for point in actual_roots)
    assert len(actual_roots) == 4
    assert math.isclose(validated_embed, actual_embed, abs_tol=1e-7)
    struct.pack_into('<f', tile.triangles, 12, 20.)
    with pytest.raises(ValueError, match='supporting Ground changed'):
        validate_ground(scene, [support], [pose], .075)
