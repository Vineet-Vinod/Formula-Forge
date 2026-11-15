"""The finite upper-bank change retains exact outside rows and grounded planting."""

import struct
from collections import Counter
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile, TerrainGrid
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from shapely import from_wkt
from venues.monaco_groves import ground_height, packed_point
from venues.monaco_upper_ground import apply, old_tree, supporting_ground, tree_rows
from venues.monaco_upper_ground_dataclasses import UpperBankSource

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/monaco"


def fixture() -> tuple[MeshScene, TerrainGrid, UpperBankSource]:
    source = TypeAdapter(UpperBankSource).validate_json(
        (SOURCES / "architecture/upper-bank-source.json").read_bytes()
    )
    grid = TypeAdapter(TerrainGrid).validate_json(
        (SOURCES / source.terrain.grid_file).read_bytes()
    )
    scene = old_tree(source)
    for row in source.terrain.original_ground_rows:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        tile.triangles.extend((
            struct.pack("<I", tile.materials.index(row.material))
            + bytes.fromhex(row.attributes_hex)
        ) * row.copies)
        values = struct.unpack("<24f", bytes.fromhex(row.attributes_hex))
        for index in (0, 8, 16):
            for axis in range(3):
                tile.minimum[axis] = min(tile.minimum[axis], values[index + axis])
                tile.maximum[axis] = max(tile.maximum[axis], values[index + axis])
    return scene, grid, source


def test_upper_bank_changes_only_one_tree_and_keeps_its_entire_shape() -> None:
    scene, grid, source = fixture()
    outside = MeshScene()
    outside.broadleaf((-70, 380, 20), 8, 12)
    scene.broadleaf((-70, 380, 20), 8, 12)
    outside_rows = tree_rows(outside)
    old = tree_rows(old_tree(source))
    change, base = apply(scene, grid, source)
    assert change.domain_area_m2 == pytest.approx(368.3183204772705)
    assert change.minimum_normal_alignment >= 0
    assert not change.unresolved_faces
    assert base[:2] == source.old_tree_base[:2]
    assert 0 < base[2] - source.old_tree_base[2] < 5
    new = MeshScene()
    new.broadleaf(base, source.tree_height_m, source.tree_seed)
    new_rows = tree_rows(new)
    actual: Counter[tuple[str, bytes]] = Counter()
    for name, tile in scene.tiles.items():
        if name.startswith("Building_City_"):
            one = MeshScene()
            one.tiles[name] = tile
            actual.update(tree_rows(one))
    assert actual == outside_rows + new_rows
    assert not actual.keys() & old.keys()
    assert sum(new_rows.values()) == 102
    plan = from_wkt(source.terrain.expected_domain_wkt)
    support = supporting_ground(scene, plan)
    for dx in (-0.125, 0.125):
        for dy in (-0.125, 0.125):
            x, y, z = packed_point((base[0] + dx, base[1] + dy, base[2]))
            assert ground_height(support, x, y) - z >= 0.09999


@pytest.mark.parametrize("stale_tree", (False, True))
def test_upper_bank_rejects_stale_owner_rows_before_mutating(stale_tree: bool) -> None:
    scene, grid, source = fixture()
    name = next(iter(old_tree(source).tiles)) if stale_tree else source.terrain.original_ground_rows[0].tile
    scene.tiles[name].triangles[99] ^= 1
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError, match="source rows|original planes changed"):
        apply(scene, grid, source)
    assert before == {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
