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
from venues.baku_streetscape import finish, prepare
from venues.baku_streetscape_dataclasses import (
    StreetscapeGroundSource,
    StreetscapeSource,
)

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/baku"
EXPECTED_CITY: dict[str, tuple[list[str], str]] = {
    "Building_City_m6_m3": (
        [
            "BakuPhilharmonicOchre",
            "Glass",
            "Cream",
            "White",
            "Black",
            "Trunk",
            "Roof",
            "Yellow",
        ],
        "2d04f08aab1f65b05064aeffddcdf1e36bac3a78399b7365b339489cfae5c48a",
    ),
    "Building_City_m5_m3": (
        ["BakuPhilharmonicOchre", "Cream", "White", "Black"],
        "d53eab054a1124257fef8b8417102eb838414c4f2c31c64e9f8625ad398dbccb",
    ),
}


def supported_scene() -> tuple[CircuitScene, StreetscapeGroundSource]:
    scene = CircuitScene("baku")
    scene.road_surfaces()
    scene.sources = SOURCES
    guard = TypeAdapter(StreetscapeGroundSource).validate_json(
        gzip.decompress((SOURCES / "streetscape/ground-supports.json.gz").read_bytes())
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


def test_streetscape_replays_frozen_geometry_and_preserves_road_ground_cutout() -> None:
    scene, _ = supported_scene()
    before = {
        name: (list(tile.materials), bytes(tile.triangles))
        for name, tile in scene.tiles.items()
    }
    prepare(scene)
    assert scene.modeled_buildings == {152190848, 196291852}
    assert len(scene.terrain_cutouts) == 1
    cutout = scene.terrain_cutouts[0].wkb
    assert {
        name: (tile.materials, bytes(tile.triangles))
        for name, tile in scene.tiles.items()
    } == before
    finish(scene)
    assert {
        name: (scene.tiles[name].materials, bytes(scene.tiles[name].triangles))
        for name in before
    } == before
    assert len(scene.terrain_cutouts) == 1 and scene.terrain_cutouts[0].wkb == cutout
    city = {
        name: tile for name, tile in scene.tiles.items() if name.startswith("Building_")
    }
    assert sum(len(tile.triangles) // 100 for tile in city.values()) == 106085
    assert {
        name: (tile.materials, hashlib.sha256(tile.triangles).hexdigest())
        for name, tile in city.items()
    } == EXPECTED_CITY


def test_streetscape_rejects_changed_ground_before_emitting_city() -> None:
    scene, guard = supported_scene()
    prepare(scene)
    row = guard.ground_supports[0]
    tile = scene.tiles[row.tile]
    offset = next(
        offset
        for offset in range(0, len(tile.triangles), 100)
        if bytes(tile.triangles[offset + 4 : offset + 100]) == row.payload
    )
    tile.triangles[offset + 99] ^= 1
    with pytest.raises(ValueError, match="actual supporting Ground changed"):
        finish(scene)
    assert not any(name.startswith("Building_") for name in scene.tiles)


def test_streetscape_rejects_shifted_literal_frame(tmp_path: Path) -> None:
    scene, guard = supported_scene()
    source = TypeAdapter(StreetscapeSource).validate_json(
        gzip.decompress((SOURCES / "streetscape/recipe.json.gz").read_bytes())
    )
    x, y = source.hall_literal_xy[0]
    source = replace(
        source, hall_literal_xy=((x + 0.2, y), *source.hall_literal_xy[1:])
    )
    recipe = TypeAdapter(StreetscapeSource).dump_json(source)
    folder = tmp_path / "streetscape"
    folder.mkdir()
    (folder / "recipe.json.gz").write_bytes(gzip.compress(recipe, mtime=0))
    guard = replace(guard, recipe_sha256=hashlib.sha256(recipe).hexdigest())
    (folder / "ground-supports.json.gz").write_bytes(
        gzip.compress(TypeAdapter(StreetscapeGroundSource).dump_json(guard), mtime=0)
    )
    scene.sources = tmp_path
    with pytest.raises(ValueError, match="literal footprint/source frame changed"):
        prepare(scene)
    assert not scene.modeled_buildings and not scene.terrain_cutouts


def test_streetscape_rejects_changed_road_clearance_before_reserving() -> None:
    scene, _ = supported_scene()
    scene.road_mask = scene.road_mask.buffer(0.1)
    with pytest.raises(ValueError, match="road clearance/cutout changed"):
        prepare(scene)
    assert not scene.modeled_buildings and not scene.terrain_cutouts
