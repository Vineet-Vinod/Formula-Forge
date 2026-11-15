"""The reviewed Rome mesh replaces one generic family without replaying its parent."""
from __future__ import annotations

from collections import Counter
from copy import copy, deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.monaco import frontage
from venues.monaco_rome import CITY, Row, apply, bindings, legacy_rows
from venues.monaco_rome_dataclasses import RomeSource
from venues.monaco_rome_geometry import source_object_point

SOURCE = Path(__file__).parents[1]/'Attribution/Sources/monaco/architecture/villa-de-rome/reconstruction.json'


@pytest.fixture(scope='module')
def source() -> RomeSource:
    return TypeAdapter(RomeSource).validate_json(SOURCE.read_bytes())


@pytest.fixture(scope='module')
def generic() -> CircuitScene:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    scene.tiles.clear()
    frontage(scene, scene.footprint(94400097))
    return scene


@pytest.fixture
def scene(generic: CircuitScene) -> CircuitScene:
    result = copy(generic)
    result.tiles = deepcopy(generic.tiles)
    result.landmarks = deepcopy(generic.landmarks)
    return result


def test_exact_v3_preserves_future_garden_and_mapped_tree_rows(scene: CircuitScene, source: RomeSource) -> None:
    wanted = legacy_rows(scene)
    old_size = len(scene.tiles[CITY].triangles)
    scene.triangle('Building_FutureHermosa', 'MonacoTerraceStoneLight',
                   (-45, 390, 60), (-44, 390, 60), (-45, 390, 61))
    scene.broadleaf((-45, 379, 58.48), 11, 239)
    future_rows = bytes(scene.tiles[CITY].triangles[old_size:])
    original_materials = scene.tiles[CITY].materials.copy()
    change = apply(scene, source, wanted)
    assert change.old_rows_removed == 1822
    assert change.new_triangles == 70612
    assert change.unrelated_city_rows_preserved == 103
    assert scene.tiles[CITY].triangles[:len(future_rows)] == future_rows
    assert scene.tiles[CITY].materials[:len(original_materials)] == original_materials
    assert change.new_geometry_sha256 == '14bb1943aece4a841a286f84088b39072e612983fa653ac38b453d6d6670b832'
    assert change.body_south_prefix_sha256 == source.body_south_prefix_sha256
    assert change.closed_roof_triangles == 40
    assert change.closed_soffit_triangles == 12
    assert change.main_roof_top_triangles == 14
    assert change.roof_coverage_error_m2 < .002
    assert change.roof_overlap_area_m2 < 1e-8
    assert change.minimum_packed_normal_alignment > .99999
    assert change.maximum_object_center_offset_m < 1e-7
    for obj in source.spec.source_objects:
        assert source_object_point(source.spec, obj, .5, .5, 0)[:2] == pytest.approx(obj.nominal_xy_m, abs=1e-7)


def test_incomplete_generic_bind_is_atomic(scene: CircuitScene, source: RomeSource) -> None:
    wanted: Counter[Row] = legacy_rows(scene)
    scene.tiles[CITY].triangles[4] ^= 1
    original = bytes(scene.tiles[CITY].triangles), scene.tiles[CITY].materials.copy()
    with pytest.raises(ValueError, match='Exact old foreground rows were not found'):
        apply(scene, source, wanted)
    assert (bytes(scene.tiles[CITY].triangles), scene.tiles[CITY].materials) == original


@pytest.mark.parametrize('control', ('frame', 'ign'))
def test_source_registration_change_rejects_before_mutation(scene: CircuitScene, source: RomeSource, control: str) -> None:
    original = bytes(scene.tiles[CITY].triangles)
    if control == 'frame':
        changed = replace(source, origin_lat_lon=(source.origin_lat_lon[0]+.001, source.origin_lat_lon[1]))
        message = 'source frame and datum'
    else:
        roof = source.spec.roof_xy_absolute_z_m
        changed = replace(source, spec=replace(source.spec, roof_xy_absolute_z_m=((roof[0][0], roof[0][1], roof[0][2]+1), *roof[1:])))
        message = 'IGN XYZ observations changed'
    with pytest.raises(ValueError, match=message):
        bindings(scene, changed)
    assert bytes(scene.tiles[CITY].triangles) == original
