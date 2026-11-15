from __future__ import annotations

import gzip
import struct
from pathlib import Path

import numpy as np
import pytest
from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.baku_ground_dataclasses import GroundPatchSource
from venues.baku_junction import finish
from venues.baku_junction_dataclasses import JunctionRecipe
from venues.baku_khagani_legacy import native_values, source_points

SOURCE = Path(__file__).resolve().parents[1] / "Attribution/Sources/baku/junction/reconstruction.json"


@pytest.fixture(scope="module")
def source() -> JunctionRecipe:
    return TypeAdapter(JunctionRecipe).validate_json(SOURCE.read_bytes())


@pytest.fixture(scope="module")
def patch(source: JunctionRecipe) -> GroundPatchSource:
    return TypeAdapter(GroundPatchSource).validate_json(
        gzip.decompress(SOURCE.with_name(source.ground_delta_file).read_bytes())
    )


def scene_with_parents(patch: GroundPatchSource) -> tuple[CircuitScene, bytes]:
    scene = CircuitScene("baku")
    for row in patch.removals:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        raw = struct.pack("<I", tile.materials.index(row.material)) + row.payload
        tile.triangles.extend(raw * row.copies)
    tile = scene.tiles[patch.removals[0].tile]
    witness = bytearray(patch.removals[0].payload)
    for vertex in range(3):
        struct.pack_into("<3f", witness, vertex*32+12, 0.31, -0.41, 0.857788)
    tile.materials.append("TreeCanopy")
    raw_witness = struct.pack("<I", len(tile.materials)-1) + witness
    tile.triangles.extend(raw_witness)
    return scene, bytes(raw_witness)


def test_junction_preserves_unselected_bytes_and_rejects_stale_parents(
    source: JunctionRecipe, patch: GroundPatchSource
) -> None:
    scene, witness = scene_with_parents(patch)
    prefix = list(scene.tiles[patch.removals[0].tile].materials)
    change = finish(scene, SOURCE)
    tile = scene.tiles[patch.removals[0].tile]
    assert bytes(tile.triangles[:100]) == witness
    assert tile.materials[:len(prefix)] == prefix
    assert (change.removed_rows, change.new_rows, change.curb_faces) == (674, 18507, 484)
    stale, _ = scene_with_parents(patch)
    del stale.tiles[patch.removals[0].tile].triangles[:100]
    before = {name: bytes(tile.triangles) for name, tile in stale.tiles.items()}
    with pytest.raises(ValueError, match="expected original Ground rows are missing"):
        finish(stale, SOURCE)
    assert {name: bytes(tile.triangles) for name, tile in stale.tiles.items()} == before
    assert sum(row.copies for row in patch.additions) == source.new_rows


def test_literal_island_and_low_curb_are_ground_geometry(
    source: JunctionRecipe, patch: GroundPatchSource
) -> None:
    assert source.island_osm_id == 270087949
    assert source.estimated_curb_rise_m == 0.15
    assert source.estimated_outward_crossfall == 0.02
    assert 572.17 < source.island_area_m2 < 572.18
    curb_faces = 0
    grass_faces = 0
    for row in patch.additions:
        points = source_points(native_values(row.payload))
        cross = np.cross(points[1]-points[0], points[2]-points[0])
        if row.material == "Concrete":
            curb_faces += row.copies
            assert abs(float(cross[2])) < 1e-12
            pairs = [
                (i, j)
                for i in range(3)
                for j in range(i+1, 3)
                if np.linalg.norm(points[i, :2]-points[j, :2]) < 1e-10
            ]
            assert len(pairs) == 1
            a, b = pairs[0]
            assert abs(abs(float(points[a, 2]-points[b, 2]))-0.15) < 2e-6
        else:
            assert float(cross[2]) > 0
            grass_faces += row.copies if row.material == "Grass" else 0
    assert curb_faces == source.curb_faces
    assert grass_faces == 1772
