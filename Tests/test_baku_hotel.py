from __future__ import annotations

import gzip
import hashlib
import struct
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.baku_hotel import finish, prepare
from venues.baku_hotel_dataclasses import HotelGroundSource, HotelSource

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/baku"

EXPECTED_CITY = {
    "Building_City_m5_m3": "a4aecea6ac43cbe222f20e8732637d041ff93b039ca418f4360fe83611687ab0"
}


def supported_scene() -> tuple[CircuitScene, HotelGroundSource]:
    scene = CircuitScene("baku")
    guard = TypeAdapter(HotelGroundSource).validate_json(
        gzip.decompress((SOURCES / "hotel-ground-supports.json.gz").read_bytes())
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


def test_hotel_adapter_replays_frozen_geometry_and_preserves_ground() -> None:
    scene, _ = supported_scene()
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    prepare(scene)
    assert scene.modeled_buildings == {152190583}
    assert {name: bytes(tile.triangles) for name, tile in scene.tiles.items()} == before
    assert not scene.terrain_cutouts
    finish(scene)
    assert {name: bytes(scene.tiles[name].triangles) for name in before} == before
    city = {
        name: tile for name, tile in scene.tiles.items() if name.startswith("Building_")
    }
    assert sum(len(tile.triangles) // 100 for tile in city.values()) == 394745
    assert {
        name: hashlib.sha256(tile.triangles).hexdigest() for name, tile in city.items()
    } == EXPECTED_CITY
    assert not scene.terrain_cutouts


def test_hotel_rejects_changed_ground_before_emitting_city() -> None:
    scene, guard = supported_scene()
    prepare(scene)
    scene.tiles[guard.ground_supports[0].tile].triangles[99] ^= 1
    with pytest.raises(ValueError, match="actual supporting Ground changed"):
        finish(scene)
    assert not any(name.startswith("Building_") for name in scene.tiles)


def test_hotel_rejects_shifted_literal_frame(tmp_path: Path) -> None:
    scene, guard = supported_scene()
    source = TypeAdapter(HotelSource).validate_json(
        gzip.decompress((SOURCES / "hotel-recipe.json.gz").read_bytes())
    )
    x, y = source.literal_outer_xy[0]
    source = replace(
        source, literal_outer_xy=((x + 0.2, y), *source.literal_outer_xy[1:])
    )
    recipe = TypeAdapter(HotelSource).dump_json(source)
    (tmp_path / "hotel-recipe.json.gz").write_bytes(gzip.compress(recipe, mtime=0))
    guard = replace(guard, recipe_sha256=hashlib.sha256(recipe).hexdigest())
    (tmp_path / "hotel-ground-supports.json.gz").write_bytes(
        gzip.compress(TypeAdapter(HotelGroundSource).dump_json(guard), mtime=0)
    )
    scene.sources = tmp_path
    with pytest.raises(ValueError, match="literal footprint/source frame changed"):
        prepare(scene)
    assert 152190583 not in scene.modeled_buildings
