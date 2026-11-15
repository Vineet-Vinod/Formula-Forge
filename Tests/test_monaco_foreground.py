"""The two photographed frontages replace only their own old bodies and empty estate void."""

from __future__ import annotations

import struct
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from venues import monaco
from venues.monaco_bruyeres import core_plan
from venues.monaco_foreground import (
    TILE,
    bindings,
    finish_terrain,
    replacement,
    surface,
)
from venues.monaco_foreground_dataclasses import (
    ForegroundChange,
    ForegroundFloor,
    ForegroundSource,
)
from venues.monaco_montjoie import facade_shape, front_frame, openings, pavilion_plan


class FlatScene(CircuitScene):
    def ground(self, x: float, y: float) -> float:
        return 5.5


@pytest.fixture(scope='module')
def model() -> tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]]:
    scene = FlatScene('monaco')
    source = TypeAdapter(ForegroundSource).validate_json(
        (scene.sources / 'architecture/foreground-properties.json').read_bytes())
    scene.road_mask = Polygon()
    scene.corridor_mask = Polygon()
    for osm_id in (94400108, 94399506):
        monaco.frontage(scene, scene.footprint(osm_id))
    owner = Polygon(source.bruyeres.owner_xy_m)
    outside = box(*owner.buffer(2).bounds).difference(owner)
    for triangle in constrained_delaunay_triangles(outside).geoms:
        points = list(orient(triangle, 1).exterior.coords)[:3]
        scene.triangle('Tile_ForegroundFixture', 'Runoff',
                       (points[0][0], points[0][1], 5.5),
                       (points[1][0], points[1][1], 5.5),
                       (points[2][0], points[2][1], 5.5))
    scene.triangle('Building_UnrelatedForegroundFixture', 'Cream',
                   (140., 200., 12.), (143., 200., 12.), (140., 203., 12.),
                   ((.17, .23), (.37, .41), (.59, .67)))
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    materials = scene.tiles[TILE].materials.copy()
    grid, road, cutouts = scene.grid, scene.road, list(scene.terrain_cutouts)
    change = finish_terrain(scene)
    assert scene.grid is grid and scene.road is road and scene.terrain_cutouts == cutouts
    return scene, source, change, before, materials


def test_primary_roof_core_replaces_the_tall_lower_estate_prism(
    model: tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]],
) -> None:
    scene, source, change, _before, _materials = model
    bruyeres, _montjoie = bindings(scene, source)
    core = core_plan(bruyeres)
    assert core.area == pytest.approx(164.58052911875, abs=1e-7)
    assert Polygon(bruyeres.owner_xy_m).area - core.area > 110
    assert change.bruyeres.floor_count == 4 and change.bruyeres.openings == 12
    assert change.bruyeres.main_roof_absolute_m == pytest.approx(27.41529931364375)
    tile = scene.tiles[TILE]
    paint = tile.materials.index('MonacoBruyeresRed')
    north = []
    for offset in range(0, len(tile.triangles), 100):
        if struct.unpack_from('<I', tile.triangles, offset)[0] == paint:
            row = struct.unpack_from('<24f', tile.triangles, offset + 4)
            north.extend(-row[i] / 100 for i in (0, 8, 16))
    assert min(north) > min(p[1] for p in bruyeres.owner_xy_m) + 8
    record = next(item for item in scene.landmarks if item.get('osm_id') == bruyeres.osm_id)
    assert record['retained_osm_levels'] == 6 and record['front_bands'] == 4
    assert 'levels' not in record and 'height_m' not in record


def test_montjoie_has_separate_true_apertures_and_a_bounded_small_roof_pavilion(
    model: tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]],
) -> None:
    _scene, source, change, _before, _materials = model
    spec = source.montjoie
    frame = front_frame(spec)
    apertures = openings(spec)
    wall = facade_shape(spec, frame, apertures)
    assert len(apertures) == 10
    assert sum(len(p.contour_uz_m) > 4 for p in apertures) == 2
    triangles = tuple(constrained_delaunay_triangles(wall).geoms)
    for opening in apertures:
        shape = Polygon(opening.contour_uz_m)
        assert all(triangle.intersection(shape).area < 1e-9 for triangle in triangles)
    assert Polygon(spec.owner_xy_m).contains(Polygon([p[:2] for p in pavilion_plan(spec, frame)]))
    assert change.montjoie.projecting_balcony_count == 4
    assert change.montjoie.juliet_rail_count == 5
    assert spec.recess_m == .16


def test_adapter_preserves_street_bytes_unrelated_city_row_and_material_prefix(
    model: tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]],
) -> None:
    scene, _source, change, before, materials = model
    assert change.changed_tiles == (TILE,)
    assert change.old_rows_removed > 0 and change.new_rows_appended > change.old_rows_removed
    for name, payload in before.items():
        if name != TILE:
            assert bytes(scene.tiles[name].triangles) == payload
    sentinel = before[TILE][-100:]
    assert bytes(scene.tiles[TILE].triangles).count(sentinel) == 1
    assert scene.tiles[TILE].materials[:len(materials)] == materials
    assert change.preserved_old_rows == 1


def test_missing_exact_old_owner_row_rejects_before_mutation() -> None:
    scene = MeshScene()
    scene.triangle('Building_ForegroundTest', 'Cream', (1., 1., 1.), (2., 1., 1.), (1., 2., 1.))
    tile = next(iter(scene.tiles.values()))
    before, materials = bytes(tile.triangles), tile.materials.copy()
    with pytest.raises(ValueError, match='Exact old foreground rows'):
        replacement(tile, Counter({('Cream', bytes(96)): 1}), tile)
    assert bytes(tile.triangles) == before and tile.materials == materials


def test_registration_drift_rejects_before_authoring(
    model: tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]],
) -> None:
    scene, source, _change, _before, _materials = model
    before = bytes(scene.tiles[TILE].triangles)
    with pytest.raises(ValueError, match='registration'):
        bindings(scene, replace(source, scene_scale=source.scene_scale + .0001))
    assert bytes(scene.tiles[TILE].triangles) == before


def test_shared_wall_precision_is_bounded_and_open_frontage_is_not_a_garden(
    model: tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]],
) -> None:
    _scene, source, change, _before, _materials = model
    assert change.garden.shared_body_edges
    for edge in change.garden.shared_body_edges:
        assert edge.maximum_body_distance_m <= 2 * edge.xy_ulp_bound_m
    for face in change.garden.precision_faces:
        assert face.source_minimum_altitude_m <= 2 * face.xy_ulp_bound_m
        assert face.maximum_xy_error_m <= .501 * face.xy_ulp_bound_m
        if face.action == 'collapsed':
            assert face.packed_three_dimensional_area_m2 == 0
    planted = Polygon(source.bruyeres.owner_xy_m).difference(core_plan(source.bruyeres))
    assert planted.intersection(box(*source.estimated_open_frontage_bounds_xy_m)).area == 0


def test_competing_actual_floor_levels_are_not_replaced_by_a_grid_guess() -> None:
    lower = ForegroundFloor('Tile_Street_00_00', 0, 'Runoff',
                            ((0., 0., 3.), (5., 0., 3.), (0., 5., 3.)))
    upper = ForegroundFloor('Tile_Street_00_00', 100, 'Concrete',
                            ((0., 0., 7.), (5., 0., 7.), (0., 5., 7.)))
    with pytest.raises(ValueError, match='competing planes'):
        surface((lower, upper), 1., 1.)


def test_new_garden_uses_continuous_registered_ground_texture_coordinates(
    model: tuple[FlatScene, ForegroundSource, ForegroundChange, dict[str, bytes], list[str]],
) -> None:
    scene, _source, _change, _before, _materials = model
    tile = scene.tiles[TILE]
    index = tile.materials.index('MonacoIvyGround')
    checked = 0
    for offset in range(0, len(tile.triangles), 100):
        if struct.unpack_from('<I', tile.triangles, offset)[0] != index:
            continue
        row = struct.unpack_from('<24f', tile.triangles, offset + 4)
        for start in (0, 8, 16):
            expected = struct.unpack('<2f', struct.pack('<2f', (-row[start + 1] / 100) / 8,
                                                       (-row[start] / 100) / 8))
            assert row[start + 6:start + 8] == expected
        checked += 1
    assert checked > 0
