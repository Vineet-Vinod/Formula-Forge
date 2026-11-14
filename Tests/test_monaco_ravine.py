from __future__ import annotations

import struct
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile, TerrainGrid
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from shapely import from_wkt
from venues.monaco_groves import ground_height
from venues.monaco_groves_dataclasses import WestBankGroves
from venues.monaco_ravine import replace_ground
from venues.monaco_ravine_dataclasses import RavineSource

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/monaco"


def _fixture() -> tuple[MeshScene, TerrainGrid, RavineSource]:
    source = TypeAdapter(RavineSource).validate_json(
        (SOURCES / "architecture/ravine-source.json").read_bytes()
    )
    grid = TypeAdapter(TerrainGrid).validate_json(
        (SOURCES / source.grid_file).read_bytes()
    )
    scene = MeshScene()
    for row in source.original_ground_rows:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        raw = struct.pack("<I", tile.materials.index(row.material)) + bytes.fromhex(
            row.attributes_hex
        )
        tile.triangles.extend(raw * row.copies)
        values = struct.unpack_from("<24f", raw, 4)
        for index in (0, 8, 16):
            for axis in range(3):
                tile.minimum[axis] = min(tile.minimum[axis], values[index + axis])
                tile.maximum[axis] = max(tile.maximum[axis], values[index + axis])
    return scene, grid, source


def test_ravine_keeps_protected_rows_and_repairs_only_unresolved_normals() -> None:
    scene, grid, source = _fixture()
    name = source.original_ground_rows[0].tile
    tile = scene.tiles[name]
    tile.materials.append("Concrete")
    protected = struct.pack("<I", len(tile.materials) - 1) + bytes(
        tile.triangles[4:100]
    )
    tile.triangles.extend(protected)
    change = replace_ground(scene, grid, from_wkt(source.expected_domain_wkt), source)
    result = scene.tiles[name]
    assert protected in [
        bytes(result.triangles[i : i + 100])
        for i in range(0, len(result.triangles), 100)
    ]
    assert change.tiles == ("Tile_Street_m1_01",)
    assert change.source_faces == 225
    assert change.minimum_normal_alignment >= 0
    assert len(change.unresolved_faces) == 2
    assert all(
        face.minimum_altitude_m <= 2 * face.xy_ulp_bound_m
        for face in change.unresolved_faces
    )
    assert change.maximum_encoding_xy_error_m < 0.00002
    assert change.maximum_encoding_z_error_m < 0.000003


def test_ravine_stale_ground_rejection_leaves_original_scene_intact() -> None:
    scene, grid, source = _fixture()
    first = scene.tiles[source.original_ground_rows[0].tile]
    first.triangles[99] ^= 1
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError, match="original planes changed"):
        replace_ground(scene, grid, from_wkt(source.expected_domain_wkt), source)
    assert {name: bytes(tile.triangles) for name, tile in scene.tiles.items()} == before


def _ground(source: WestBankGroves, x: float, y: float) -> float:
    faces = []
    for row in source.supports:
        values = struct.unpack("<24f", bytes.fromhex(row.attributes_hex))
        points = tuple(
            (-values[k + 1] / 100, -values[k] / 100, values[k + 2] / 100)
            for k in (0, 8, 16)
        )
        faces.append((points[0], points[1], points[2]))
    return ground_height(tuple(faces), x, y)


def _top(base: tuple[float, float, float], height: float, seed: int) -> float:
    scene = MeshScene()
    scene.broadleaf(base, height, seed)
    return max(
        struct.unpack_from("<f", tile.triangles, offset + 4 + k * 32 + 8)[0] / 100
        for tile in scene.tiles.values()
        for offset in range(0, len(tile.triangles), 100)
        for k in range(3)
    )


def test_only_two_canopies_reanchor_and_keep_rendered_height_above_ground() -> None:
    previous = TypeAdapter(WestBankGroves).validate_json(
        (SOURCES / "architecture/ravine-canopy-baseline.json").read_bytes()
    )
    current = TypeAdapter(WestBankGroves).validate_json(
        (SOURCES / "architecture/west-bank-groves.json").read_bytes()
    )
    assert previous.canopies[2:] == current.canopies[2:]
    for old, new in zip(previous.canopies[:2], current.canopies[:2]):
        assert old.base[:2] == new.base[:2]
        assert old.seed == new.seed
        assert old.source_pixel_xy == new.source_pixel_xy
        assert old.crown_diameter_range_m == new.crown_diameter_range_m
        low, high = new.crown_diameter_range_m
        assert low <= 0.82 * new.height_m <= high
        old_height = _top(old.base, old.height_m, old.seed) - _ground(
            previous, *old.base[:2]
        )
        new_height = _top(new.base, new.height_m, new.seed) - _ground(
            current, *new.base[:2]
        )
        assert abs(old_height - new_height) < 0.00001
