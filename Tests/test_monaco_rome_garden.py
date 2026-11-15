"""A separate formal lawn must preserve old ground, buildings and other mapped trees."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from venues.monaco_hermosa_terrace import CITY, STREET, nearby_ground
from venues.monaco_rome_garden import apply, bindings
from venues.monaco_rome_garden_dataclasses import RomeGardenSource, RomeGardenTree
from venues.monaco_terrace_dataclasses import TerraceSpec

SOURCE = Path('Attribution/Sources/monaco/architecture/rome-garden/reconstruction.json')
OLD = ((-20.0, 367.0, 53.0), (-9.0, 368.0, 53.0))
TREES = (RomeGardenTree(5931906972, (0, 0), OLD[0], 11),
         RomeGardenTree(5931906973, (0, 0), OLD[1], 11))
DOMAIN = Polygon(((-24, 364), (-5, 364), (-5, 382), (-24, 382)))
FRONT = LineString(((-24, 364), (-5, 364)))


def scene_fixture(include_second_tree: bool = True) -> MeshScene:
    scene = MeshScene()
    scene.quad('Tile_Ground', 'Runoff', (-30, 360, 53), (-1, 360, 53),
        (-1, 390, 53), (-30, 390, 53), up=True)
    scene.triangle('Building_House', 'Limestone', (-28, 388, 53), (-27, 388, 53), (-28, 388, 60))
    for tree, base in zip(TREES if include_second_tree else TREES[:1], OLD):
        scene.broadleaf(base, tree.height_m, tree.osm_id % 997)
    return scene


def test_encoded_tree_support_and_complete_old_ground_are_preserved() -> None:
    scene = scene_fixture()
    old_street = bytes(scene.tiles[STREET].triangles)
    old_house = bytes(scene.tiles[CITY].triangles[:100])
    result = apply(scene, DOMAIN, FRONT, nearby_ground(scene, DOMAIN),
        replace(TerraceSpec(), reference_lawn_absolute_m=59.15, lawn_north_grade=0), TREES, OLD)
    assert scene.tiles[STREET].triangles[:len(old_street)] == old_street
    assert scene.tiles[CITY].triangles[:100] == old_house
    assert result.unrelated_city_rows_preserved == 1
    assert result.old_street_rows_preserved == 2
    assert result.minimum_actual_packed_tree_burial_m > .0999
    assert result.minimum_packed_normal_alignment > .9
    assert tuple(p[:2] for p in result.new_tree_bases) == tuple(p[:2] for p in OLD)
    assert result.geometry.maximum_visible_masonry_band_m <= 6


def test_missing_one_exact_mapped_family_rejects_before_mutation() -> None:
    scene = scene_fixture(False)
    old = {n: (bytes(t.triangles), tuple(t.materials)) for n, t in scene.tiles.items()}
    with pytest.raises(ValueError, match='Exact old foreground rows were not found'):
        apply(scene, DOMAIN, FRONT, nearby_ground(scene, DOMAIN),
            replace(TerraceSpec(), reference_lawn_absolute_m=59.15, lawn_north_grade=0), TREES, OLD)
    assert old == {n: (bytes(t.triangles), tuple(t.materials)) for n, t in scene.tiles.items()}


def test_hermosa_grade_is_not_copied_to_rome() -> None:
    scene = scene_fixture()
    old = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    with pytest.raises(ValueError, match='bounded separate source profile'):
        apply(scene, DOMAIN, FRONT, nearby_ground(scene, DOMAIN), TerraceSpec(), TREES, OLD)
    assert old == {n: bytes(t.triangles) for n, t in scene.tiles.items()}


def test_source_frame_change_rejects_before_geometry_access() -> None:
    source = TypeAdapter(RomeGardenSource).validate_json(SOURCE.read_bytes())
    scene = CircuitScene('monaco')
    with pytest.raises(ValueError, match='retained source frame and datum'):
        bindings(scene, replace(source, uniform_scale=1))
    assert not scene.tiles
