"""Local garden reconstruction must preserve the actual inherited ground and bodies."""
from __future__ import annotations

from dataclasses import replace

import pytest
from circuit_mesh import MeshScene
from shapely.geometry import LineString, Polygon
from venues.monaco_hermosa_terrace import CITY, STREET, apply, nearby_ground
from venues.monaco_terrace import encode_polygon
from venues.monaco_terrace_dataclasses import TerraceSpec

PREVIOUS = (-45.0, 380.0, -0.1)


def garden_scene() -> MeshScene:
    scene = MeshScene()
    scene.quad('Tile_Ground', 'Runoff', (-60, 365, 0), (-30, 365, 0),
        (-30, 395, 0), (-60, 395, 0), up=True)
    scene.triangle('Building_House', 'Limestone', (-55, 390, 8), (-54, 390, 8), (-55, 390, 9))
    scene.broadleaf(PREVIOUS, 11, 239)
    return scene


def recipe() -> TerraceSpec:
    return replace(TerraceSpec(), reference_lawn_absolute_m=6,
        reference_northing_m=375, lawn_north_grade=0)


def test_actual_ground_and_unrelated_city_rows_remain_exact() -> None:
    scene = garden_scene()
    domain = Polygon(((-50, 375), (-40, 375), (-40, 385), (-50, 385)))
    old_street = bytes(scene.tiles[STREET].triangles)
    old_city_sentinel = bytes(scene.tiles[CITY].triangles[:100])
    result = apply(scene, domain, LineString(((-50, 375), (-40, 375))),
        nearby_ground(scene, domain), recipe(), PREVIOUS, 11, 239)
    assert scene.tiles[STREET].triangles[:len(old_street)] == old_street
    assert scene.tiles[CITY].triangles[:100] == old_city_sentinel
    assert result.unrelated_city_rows_preserved == 1
    assert result.old_street_rows_preserved == 2
    assert result.geometry.minimum_foundation_burial_m >= 0.11999
    assert result.geometry.minimum_soil_cover_m >= 0.01999
    assert result.minimum_packed_normal_alignment > 0.9
    assert result.maximum_lawn_missing_area_m2 + result.maximum_lawn_extra_area_m2 < result.geometry.encoding_area_bound_m2
    assert result.new_tree_base[:2] == PREVIOUS[:2]


def test_failed_exact_tree_bind_does_not_mutate_original_tiles() -> None:
    scene = garden_scene()
    original = {name: (bytes(t.triangles), tuple(t.materials)) for name, t in scene.tiles.items()}
    domain = Polygon(((-50, 375), (-40, 375), (-40, 385), (-50, 385)))
    with pytest.raises(ValueError, match='Exact old foreground rows were not found'):
        apply(scene, domain, LineString(((-50, 375), (-40, 375))),
            nearby_ground(scene, domain), recipe(), (-45, 380, 0), 11, 239)
    assert original == {name: (bytes(t.triangles), tuple(t.materials)) for name, t in scene.tiles.items()}


def test_unrepresentable_polygon_ear_is_resolved_before_triangulation() -> None:
    polygon = Polygon(((-45, 375), (-44, 375), (-44, 375.000001)))
    encoded = encode_polygon(polygon)
    assert encoded.area == 0
    assert polygon.symmetric_difference(encoded).area < polygon.length * 0.000022


def test_source_wall_expansion_rejects_before_geometry_mutation() -> None:
    scene = garden_scene()
    original = {name: bytes(t.triangles) for name, t in scene.tiles.items()}
    domain = Polygon(((-50, 375), (-40, 375), (-40, 385), (-50, 385)))
    with pytest.raises(ValueError, match='bounded source recipe'):
        apply(scene, domain, LineString(((-50, 375), (-40, 375))),
            nearby_ground(scene, domain), replace(recipe(), upper_stone_band_height_m=18), PREVIOUS, 11, 239)
    assert original == {name: bytes(t.triangles) for name, t in scene.tiles.items()}
