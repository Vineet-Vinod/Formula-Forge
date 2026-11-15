from __future__ import annotations

import gzip
import struct
from collections import Counter
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.baku import circuit_edges
from venues.baku_foundation import digest, rows
from venues.baku_ground_dataclasses import GroundPatchSource
from venues.baku_park import emit, finish, office_family
from venues.baku_park_dataclasses import ParkRecipe
from venues.baku_waterfront import append

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "Attribution/Sources/baku/park-context/reconstruction.json.gz"
)


def recipe() -> tuple[ParkRecipe, GroundPatchSource]:
    source = TypeAdapter(ParkRecipe).validate_json(gzip.decompress(SOURCE.read_bytes()))
    patch = TypeAdapter(GroundPatchSource).validate_json(
        gzip.decompress((SOURCE.parent / source.ground_delta_path).read_bytes())
    )
    return source, patch


def initial_scene(source: ParkRecipe, patch: GroundPatchSource) -> CircuitScene:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    circuit_edges(scene)
    scene.tiles = {}
    original, _ = office_family(scene, source)
    scene.tiles.update(original.tiles)
    emit(scene, source.original_trees)
    counts = Counter(
        (r.tile, r.material, r.payload) for r in patch.removals for _ in range(r.copies)
    )
    additions = Counter(
        (r.tile, r.material, r.payload)
        for r in patch.additions
        for _ in range(r.copies)
    )
    for r in source.supporting_ground:
        key = r.tile, r.material, r.payload
        counts[key] = max(counts[key], r.copies - additions[key])
    for (tile, material, payload), copies in counts.items():
        target = scene.tiles.setdefault(tile, MeshTile())
        for _ in range(copies):
            append(target, material, payload)
    return scene


def test_park_geometry_matches_reviewed_families() -> None:
    source, _ = recipe()
    old = MeshScene()
    new = MeshScene()
    emit(old, source.original_trees)
    emit(new, source.trees, source.foreground_seed_ids)
    assert (
        digest(sum((rows(t) for t in old.tiles.values()), Counter()))
        == source.original_tree_counter_sha256
    )
    assert (
        digest(sum((rows(t) for t in new.tiles.values()), Counter()))
        == source.tree_counter_sha256
    )
    assert len(source.trees) == 98 and len(source.foreground_seed_ids) == 5
    assert [p.base[:2] for p in source.trees[:34]] == [
        p.base[:2] for p in source.original_trees
    ]


def test_office_translation_preserves_source_dimensions_and_attributes() -> None:
    source, patch = recipe()
    scene = initial_scene(source, patch)
    old, new = office_family(scene, source)
    assert sum(len(t.triangles) // 100 for t in new.tiles.values()) == 6492
    assert (
        digest(sum((rows(t) for t in new.tiles.values()), Counter()))
        == source.office.new_counter_sha256
    )
    delta = (source.office.new_base_m - source.office.old_base_m) * 100
    for name, tile in old.tiles.items():
        changed = new.tiles[name].triangles
        for offset in range(0, len(tile.triangles), 100):
            expected = bytearray(tile.triangles[offset : offset + 100])
            for vertex in range(3):
                position = 4 + vertex * 32 + 8
                z = struct.unpack_from("<f", expected, position)[0]
                struct.pack_into("<f", expected, position, z + delta)
            assert changed[offset : offset + 100] == expected
    assert source.office.new_base_m < source.office.old_base_m


def test_stale_ground_rejects_without_partial_changes() -> None:
    source, patch = recipe()
    scene = initial_scene(source, patch)
    missing = patch.removals[0]
    scene.tiles[missing.tile] = MeshTile()
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    with pytest.raises(ValueError, match="expected original Ground rows"):
        finish(scene, SOURCE)
    assert before == {n: bytes(t.triangles) for n, t in scene.tiles.items()}


def test_complete_patch_keeps_native_providers_and_supports() -> None:
    source, patch = recipe()
    scene = initial_scene(source, patch)
    grid, road, mask = scene.grid, scene.road, scene.road_mask
    result = finish(scene, SOURCE)
    assert result.translated_office_rows == 6492 and result.new_tree_rows == 11364
    assert result.supporting_ground_rows == sum(
        r.copies for r in source.supporting_ground
    )
    assert scene.grid is grid and scene.road is road and scene.road_mask is mask
