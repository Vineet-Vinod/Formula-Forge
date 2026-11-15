"""Material ownership cannot alter packed terrain, structures, or plants."""
from __future__ import annotations

import struct
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import box
from venues.monaco_cliff_cover import domain, reclassify
from venues.monaco_cliff_cover_dataclasses import CliffCoverSource

SOURCE = Path('Attribution/Sources/monaco/architecture/cliff-cover/reconstruction.json')


def test_whole_natural_ground_changes_only_material_indices() -> None:
    scene = MeshScene()
    scene.quad('Tile_Ground', 'Grass', (0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), up=True)
    scene.triangle('Tile_Ground', 'MonacoRockGround', (4, 4, 0), (5, 4, 0), (4, 5, 0))
    scene.quad('Building_Deck', 'Grass', (0, 0, 10), (2, 0, 10), (2, 2, 10), (0, 2, 10), up=True)
    scene.broadleaf((1, 1, 0), 5, 123)
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    materials = {n: t.materials.copy() for n, t in scene.tiles.items()}
    bounds = {n: (t.minimum.copy(), t.maximum.copy()) for n, t in scene.tiles.items()}
    result = reclassify(scene, box(-.1, -.1, 2.1, 2.1), 2, 4)
    assert result.changed_faces == 2
    for name, tile in scene.tiles.items():
        assert tile.materials[:len(materials[name])] == materials[name]
        assert (tile.minimum, tile.maximum) == bounds[name]
        if not name.startswith('Tile_Street_'):
            assert tile.triangles == before[name]
            continue
        for offset in range(0, len(tile.triangles), 100):
            assert tile.triangles[offset + 4:offset + 100] == before[name][offset + 4:offset + 100]
            if offset >= 200:
                assert tile.triangles[offset:offset + 100] == before[name][offset:offset + 100]
            else:
                index = struct.unpack_from('<I', tile.triangles, offset)[0]
                assert tile.materials[index] == 'MonacoNaturalGround'


def test_crossing_face_and_separate_rock_role_are_retained() -> None:
    scene = MeshScene()
    scene.triangle('Tile_Ground', 'Grass', (0, 0, 0), (1, 0, 0), (0, 1, 0))
    scene.triangle('Tile_Ground', 'Grass', (1.8, 1.8, 0), (3, 1.8, 0), (1.8, 3, 0))
    scene.triangle('Tile_Ground', 'MonacoRockGround', (1, 0, 0), (2, 0, 0), (1, 1, 0))
    tile = scene.tiles['Tile_Street_00_00']
    outside = bytes(tile.triangles[100:])
    result = reclassify(scene, box(-.1, -.1, 2, 2), 1, .5)
    assert result.held_crossing_faces == 1
    assert tile.triangles[100:] == outside


def test_changed_actual_ownership_rejects_before_mutation() -> None:
    scene = MeshScene()
    scene.triangle('Tile_Ground', 'Grass', (0, 0, 0), (1, 0, 0), (0, 1, 0))
    tile = scene.tiles['Tile_Street_00_00']
    old = bytes(tile.triangles), tile.materials.copy()
    with pytest.raises(ValueError, match='Actual old Grass ownership'):
        reclassify(scene, box(-1, -1, 2, 2), 2, 1)
    assert (bytes(tile.triangles), tile.materials) == old


def test_source_frame_change_rejects_before_domain_access() -> None:
    source = TypeAdapter(CliffCoverSource).validate_json(SOURCE.read_bytes())
    scene = CircuitScene('monaco')
    with pytest.raises(ValueError, match='retained Monaco source frame'):
        domain(scene, replace(source, uniform_scale=1))
    assert not scene.tiles
