"""The bridge deck must not exclude woodland on lower, retained ground."""
from __future__ import annotations

import struct
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import box
from venues.monaco_underarch import actual_faces, apply, source_window
from venues.monaco_underarch_dataclasses import UnderarchSource

SOURCE = Path('Attribution/Sources/monaco/architecture/underarch/reconstruction.json')


def source() -> UnderarchSource:
    return TypeAdapter(UnderarchSource).validate_json(SOURCE.read_bytes())


def bridge_scene(ceiling: float = 10) -> MeshScene:
    scene = MeshScene()
    scene.quad('Tile_Ground', 'Runoff', (0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0), up=True)
    scene.quad('Building_Bridge', 'Concrete', (0, 0, ceiling), (20, 0, ceiling), (20, 20, ceiling), (0, 20, ceiling), up=False)
    scene.quad('Building_Bridge', 'Runoff', (0, 0, ceiling + 1), (20, 0, ceiling + 1), (20, 20, ceiling + 1), (0, 20, ceiling + 1), up=True)
    scene.triangle('Tile_Ground', 'MonacoRockGround', (30, 30, 0), (31, 30, 0), (30, 31, 0))
    return scene


def test_lower_woodland_and_shrubs_preserve_actual_overhead_deck() -> None:
    scene = bridge_scene()
    window = box(0, 0, 20, 20)
    floors, ceilings = actual_faces(scene, window)
    assert len(floors) == len(ceilings) == 2
    old_city = bytes(scene.tiles['Building_City_00_00'].triangles)
    old_rock = bytes(scene.tiles['Tile_Street_00_00'].triangles[-100:])
    result = apply(scene, box(2, 2, 18, 18), floors, ceilings, source())
    assert result.original_faces_split == 2
    assert result.classified_area_m2 == pytest.approx(256)
    assert result.foliage.plants
    assert result.foliage.minimum_clearance_m >= 1
    city = scene.tiles['Building_City_00_00']
    assert city.triangles[:len(old_city)] == old_city
    street = scene.tiles['Tile_Street_00_00']
    assert street.triangles[-100:] == old_rock
    assert 'MonacoIvyGround' in street.materials
    assert all(p.actual_ground_relative_m == pytest.approx(0) for p in result.foliage.plants)


def test_insufficient_actual_soffit_clearance_rejects_before_mutation() -> None:
    scene = bridge_scene(1)
    original = {name: (bytes(tile.triangles), tuple(tile.materials)) for name, tile in scene.tiles.items()}
    floors, ceilings = actual_faces(scene, box(0, 0, 20, 20))
    with pytest.raises(ValueError, match='no clearance-safe shrubs'):
        apply(scene, box(2, 2, 18, 18), floors, ceilings, source())
    assert original == {name: (bytes(tile.triangles), tuple(tile.materials)) for name, tile in scene.tiles.items()}


def test_only_literal_lower_runoff_is_reclassified() -> None:
    scene = bridge_scene()
    street = scene.tiles['Tile_Street_00_00']
    original = bytes(street.triangles)
    original_materials = street.materials.copy()
    floors, ceilings = actual_faces(scene, box(0, 0, 20, 20))
    apply(scene, box(2, 2, 18, 18), floors, ceilings, source())
    current = scene.tiles['Tile_Street_00_00']
    assert current.materials[:len(original_materials)] == original_materials
    rock = original[-100:]
    assert current.triangles.count(rock) == 1
    for offset in range(0, len(current.triangles), 100):
        material = current.materials[struct.unpack_from('<I', current.triangles, offset)[0]]
        if material == 'MonacoRockGround':
            assert current.triangles[offset:offset + 100] == rock


def test_changed_source_frame_rejects_before_source_or_geometry_access() -> None:
    scene = CircuitScene('monaco')
    with pytest.raises(ValueError, match='registration differs'):
        source_window(scene, replace(source(), uniform_scale=1))
    assert not scene.tiles
