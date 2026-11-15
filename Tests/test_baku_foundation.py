from __future__ import annotations

import struct
from copy import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.baku import circuit_edges
from venues.baku_foundation import digest, finish, legacy, replacement, rows
from venues.baku_foundation_dataclasses import FoundationRecipe
from venues.baku_foundation_geometry import build, rounded
from venues.east_architecture import facade

RECIPE = Path(__file__).resolve().parents[1] / 'Attribution/Sources/baku/foundation/reconstruction.json'


@pytest.fixture(scope='module')
def baseline() -> CircuitScene:
    scene = CircuitScene('baku')
    scene.road_surfaces('Runoff')
    circuit_edges(scene)
    scene.tiles.clear()
    source = TypeAdapter(FoundationRecipe).validate_json(RECIPE.read_bytes())
    facade(scene, source.osm_id, source.expected_legacy_height_m, 'classical', 'Cream')
    tile = next(iter(scene.tiles.values()))
    tile.materials.append('UnselectedSourceWitness')
    tile.triangles.extend(struct.pack('<I', len(tile.materials) - 1) + tile.triangles[4:100])
    return scene


def independent_scene(source: CircuitScene) -> CircuitScene:
    scene = copy(source)
    scene.tiles = {name: MeshTile(bytearray(tile.triangles), tile.minimum.copy(),
                                  tile.maximum.copy(), tile.materials.copy())
                   for name, tile in source.tiles.items()}
    scene.landmarks = list(source.landmarks)
    return scene


def test_actual_generic_replacement_preserves_unselected_rows_and_ground(baseline: CircuitScene) -> None:
    scene = independent_scene(baseline)
    before = next(iter(scene.tiles.values()))
    original_materials = before.materials.copy()
    witness = bytes(before.triangles[-100:])
    grid, road, mask = scene.grid, scene.road, scene.road_mask
    change = finish(scene)
    tile = scene.tiles[change.parent]
    assert change.removed_generic_rows == 19930
    assert change.emitted_rows == 68722
    assert change.preserved_parent_rows == 1
    assert bytes(tile.triangles[:100]) == witness
    assert tile.materials[:len(original_materials)] == original_materials
    assert scene.grid is grid and scene.road is road and scene.road_mask is mask


def test_packed_architecture_matches_qualified_private_geometry_and_protection(baseline: CircuitScene) -> None:
    source = TypeAdapter(FoundationRecipe).validate_json(RECIPE.read_bytes())
    scene = independent_scene(baseline)
    scene.tiles = {}
    shape = build(scene, source.geometry)
    tile = next(iter(scene.tiles.values()))
    assert digest(rows(tile)) == source.candidate_counter_sha256
    data = np.frombuffer(tile.triangles, dtype=np.dtype([('material', '<u4'), ('vertices', '<f4', (3, 8))]))
    points = data['vertices'][:, :, :3].astype(float)[:, :, [1, 0, 2]] * np.array([-1, -1, 1]) / 100
    normals = data['vertices'][:, :, 3:6].astype(float)[:, :, [1, 0, 2]] * np.array([-1, -1, 1])
    geometric = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    lengths = np.linalg.norm(geometric, axis=1)
    assert float(lengths.min()) > 0
    geometric /= lengths[:, None]
    assert float(np.sum(normals * geometric[:, None], axis=2).min()) > .99
    assert shape.is_valid and shape.distance(scene.corridor_mask) > .25
    assert abs(tile.maximum[2] / 100 - (source.geometry.floor_relative_m + 34.55)) < .00001


def test_photographed_round_corner_stays_inside_literal_owner(baseline: CircuitScene) -> None:
    from shapely.geometry import Polygon

    source = TypeAdapter(FoundationRecipe).validate_json(RECIPE.read_bytes())
    shape, _corner = rounded(source.geometry)
    owner = Polygon(baseline.footprint(source.osm_id).ring)
    assert shape.difference(owner.buffer(.000001)).area < 1e-8
    assert 1 < owner.difference(shape).area < 4


def test_changed_owner_frame_rejects_before_any_city_mutation(baseline: CircuitScene) -> None:
    scene = independent_scene(baseline)
    source = TypeAdapter(FoundationRecipe).validate_json(RECIPE.read_bytes())
    changed = replace(source, origin_lat_lon=(source.origin_lat_lon[0] + .001, source.origin_lat_lon[1]))
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError, match='owner, datum or legacy envelope'):
        legacy(scene, changed)
    assert {name: bytes(tile.triangles) for name, tile in scene.tiles.items()} == before


def test_missing_original_rows_reject_without_mutating_existing_city(baseline: CircuitScene) -> None:
    scene = independent_scene(baseline)
    source = TypeAdapter(FoundationRecipe).validate_json(RECIPE.read_bytes())
    parent, expected = legacy(scene, source)
    tile = scene.tiles[parent]
    del tile.triangles[:100]
    before = bytes(tile.triangles)
    with pytest.raises(ValueError, match='exact subset'):
        replacement(tile, expected, MeshTile())
    assert bytes(tile.triangles) == before
