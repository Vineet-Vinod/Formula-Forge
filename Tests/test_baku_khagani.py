from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.baku_khagani import finish, prepare
from venues.baku_khagani_dataclasses import KhaganiGroundSource

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/baku"
EXPECTED_CITY = "1d4410abaaeddffd43f1fbe2c3d03b09984b625d283a02af682f5fcee7dc83f5"


def supported_scene() -> tuple[CircuitScene, KhaganiGroundSource]:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    guard = TypeAdapter(KhaganiGroundSource).validate_json(
        gzip.decompress((SOURCES / "khagani/ground-supports.json.gz").read_bytes())
    )
    for row in guard.ground_supports:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        tile.triangles.extend(
            (struct.pack("<I", tile.materials.index(row.material)) + row.payload)
            * row.copies
        )
    return scene, guard


def city_digest(scene: CircuitScene) -> tuple[int, str]:
    rows: Counter[tuple[str, bytes]] = Counter()
    for name, tile in scene.tiles.items():
        if not name.startswith("Building_"):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            rows[material, bytes(tile.triangles[offset + 4 : offset + 100])] += 1
    digest = hashlib.sha256()
    for (material, payload), copies in sorted(rows.items()):
        digest.update(material.encode() + b"\0" + payload + struct.pack("<Q", copies))
    return rows.total(), digest.hexdigest()


def test_khagani_replays_frozen_geometry_without_terrain_or_road_change() -> None:
    scene, _ = supported_scene()
    before = {
        name: (list(tile.materials), bytes(tile.triangles))
        for name, tile in scene.tiles.items()
    }
    prepare(scene)
    assert scene.modeled_buildings == {177428532, 286020256}
    assert not scene.terrain_cutouts
    assert {
        name: (tile.materials, bytes(tile.triangles))
        for name, tile in scene.tiles.items()
    } == before
    finish(scene)
    assert {
        name: (scene.tiles[name].materials, bytes(scene.tiles[name].triangles))
        for name in before
    } == before
    assert city_digest(scene) == (166942, EXPECTED_CITY)
    assert not scene.terrain_cutouts
    assert scene.vegetation[-1]["count"] == 31


def test_khagani_rejects_changed_actual_ground_before_city_emission() -> None:
    scene, guard = supported_scene()
    prepare(scene)
    row = guard.ground_supports[0]
    tile = scene.tiles[row.tile]
    offset = next(
        i
        for i in range(0, len(tile.triangles), 100)
        if bytes(tile.triangles[i + 4 : i + 100]) == row.payload
    )
    tile.triangles[offset + 99] ^= 1
    with pytest.raises(ValueError, match="actual supporting Ground changed"):
        finish(scene)
    assert not any(name.startswith("Building_") for name in scene.tiles)


def test_khagani_rejects_stale_legacy_replay_atomically(tmp_path: Path) -> None:
    scene, guard = supported_scene()
    folder = tmp_path / "khagani"
    folder.mkdir()
    for name in ("recipe.json.gz", "canopy.json.gz"):
        (folder / name).write_bytes((SOURCES / "khagani" / name).read_bytes())
    family = replace(guard.legacy_families[0], emission_sha256="0" * 64)
    guard = replace(guard, legacy_families=(family, *guard.legacy_families[1:]))
    (folder / "ground-supports.json.gz").write_bytes(
        gzip.compress(TypeAdapter(KhaganiGroundSource).dump_json(guard), mtime=0)
    )
    scene.sources = tmp_path
    prepare(scene)
    with pytest.raises(ValueError, match="legacy body changed"):
        finish(scene)
    assert not any(name.startswith("Building_") for name in scene.tiles)
