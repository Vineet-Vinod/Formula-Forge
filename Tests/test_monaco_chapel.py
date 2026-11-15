"""The chapel preserves unrelated City rows and exact source-plane apron boundaries."""
from __future__ import annotations

import struct
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon
from venues import monaco
from venues.monaco_chapel import CITY, STREET, bindings, finish_terrain, replacement
from venues.monaco_chapel_dataclasses import ChapelChange, ChapelSource
from venues.monaco_chapel_roof import absolute_point, emit


def source() -> ChapelSource:
    path = Path(__file__).resolve().parents[1] / 'Attribution/Sources/monaco/architecture/chapel/reconstruction.json'
    return TypeAdapter(ChapelSource).validate_json(path.read_bytes())


def inputs() -> CircuitScene:
    scene = CircuitScene('monaco')
    scene.road_mask = Polygon()
    scene.corridor_mask = Polygon()
    monaco.frontage(scene, scene.footprint(94399398))
    witnesses = source().site.ground.original_ground_rows
    materials = list(dict.fromkeys(row.material for row in witnesses))
    ground = MeshTile(materials=materials)
    for witness in witnesses:
        assert witness.tile == STREET
        ground.triangles.extend(struct.pack('<I', materials.index(witness.material))
                                + bytes.fromhex(witness.attributes_hex))
    values = [struct.unpack_from('<24f', ground.triangles, i + 4)
              for i in range(0, len(ground.triangles), 100)]
    ground.minimum = [min(row[v + axis] for row in values for v in (0, 8, 16)) for axis in range(3)]
    ground.maximum = [max(row[v + axis] for row in values for v in (0, 8, 16)) for axis in range(3)]
    scene.tiles[STREET] = ground
    scene.triangle('Building_UnrelatedChapelFixture', 'Cream',
                   (-120., 80., 12.), (-117., 80., 12.), (-120., 83., 12.),
                   ((.17, .23), (.37, .41), (.59, .67)))
    return scene


@pytest.fixture(scope='module')
def model() -> tuple[CircuitScene, ChapelChange, bytes, list[str]]:
    scene = inputs()
    sentinel = bytes(scene.tiles[CITY].triangles[-100:])
    materials = scene.tiles[CITY].materials.copy()
    grid, road, cutouts = scene.grid, scene.road, list(scene.terrain_cutouts)
    change = finish_terrain(scene)
    assert scene.grid is grid and scene.road is road and scene.terrain_cutouts == cutouts
    return scene, change, sentinel, materials


def test_literal_source_frame_and_unrelated_annex_stay_distinct() -> None:
    scene = CircuitScene('monaco')
    spec = source()
    frame, nave = bindings(scene, spec)
    assert frame.origin[:2] == (-26.711518789726227, 309.8280453778955)
    assert frame.width_m == pytest.approx(14.266654714657511, abs=1e-10)
    assert Polygon(nave.owner_uv_m).area == pytest.approx(394.2441855930813, abs=1e-8)
    assert scene.footprint(103777482).osm_id != spec.osm_id
    with pytest.raises(ValueError, match='source frame'):
        bindings(scene, replace(spec, uniform_scale=spec.uniform_scale + .01))
    with pytest.raises(ValueError, match='literal WGS84 owner'):
        bindings(scene, replace(spec, owner_wgs84_lonlat=spec.owner_wgs84_lonlat[:-1]))


def test_adapter_replaces_only_exact_generic_rows_and_keeps_material_prefix(
    model: tuple[CircuitScene, ChapelChange, bytes, list[str]],
) -> None:
    scene, change, sentinel, materials = model
    assert change.city_tile == CITY and change.removed_generic_rows == 607
    assert change.complete_unselected_city_rows == 1
    assert bytes(scene.tiles[CITY].triangles[:100]) == sentinel
    assert scene.tiles[CITY].materials[:len(materials)] == materials
    assert change.emitted_architecture_rows > 20000
    assert set(scene.tiles) == {CITY, STREET}


def test_front_ground_and_steps_have_actual_support_and_strict_normals(
    model: tuple[CircuitScene, ChapelChange, bytes, list[str]],
) -> None:
    scene, change, _sentinel, _materials = model
    ground = change.ground
    assert ground.tiles == (STREET,) and ground.source_faces == 20
    assert ground.emitted_rows == 24779
    assert ground.domain_area_m2 == pytest.approx(139.21986637639202, abs=1e-8)
    assert ground.minimum_normal_alignment > 0 and not ground.unresolved_faces
    assert ground.maximum_outside_plane_reprojection_m < 8e-6
    assert len(change.stairs) == 5 and sum(s.probes for s in change.stairs) == 75
    assert min(s.minimum_top_clearance_m for s in change.stairs) > .15
    assert min(s.minimum_foot_burial_m for s in change.stairs) == .12
    assert set(scene.tiles[STREET].materials) == {'Runoff', 'MonacoIvyGround'}
    shell = change.stair_shell
    assert shell.original_box_rows == 60 and shell.emitted_rows > 0
    assert shell.original_duplicate_side_area_m2 >= 5.26
    assert shell.minimum_packed_normal_alignment > .999
    assert shell.closed_edge_count * 2 == shell.emitted_rows * 3


def test_missing_old_owner_rejects_before_any_mutation() -> None:
    scene = inputs()
    scene.tiles[CITY].triangles = scene.tiles[CITY].triangles[100:]
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError, match='Exact old chapel rows'):
        finish_terrain(scene)
    assert {name: bytes(tile.triangles) for name, tile in scene.tiles.items()} == before


def test_changed_ground_witness_rejects_without_mutating_city() -> None:
    scene = inputs()
    scene.tiles[STREET].triangles = scene.tiles[STREET].triangles[100:]
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError):
        finish_terrain(scene)
    assert {name: bytes(tile.triangles) for name, tile in scene.tiles.items()} == before


def test_replacement_rejects_unowned_rows() -> None:
    scene = MeshScene()
    scene.triangle('Building_ChapelFixture', 'Cream', (-2., 2., 1.), (-1., 2., 1.), (-2., 3., 1.))
    tile = next(iter(scene.tiles.values()))
    with pytest.raises(ValueError, match='Exact old chapel rows'):
        replacement(tile, Counter({('Cream', b'\0' * 96): 1}), MeshTile())


def test_bell_and_crown_vents_are_true_openings_and_foundation_is_closed() -> None:
    frame, nave = bindings(CircuitScene('monaco'), source())
    scene = MeshScene()
    emit(scene, frame, nave)
    tile = scene.tiles[CITY]
    records = [struct.unpack_from('<24f', tile.triangles, i + 4) for i in range(0, len(tile.triangles), 100)]
    points = np.array([[(-r[v + 1] / 100, -r[v] / 100, r[v + 2] / 100) for v in (0, 8, 16)] for r in records])
    assert len(points) == 6232
    assert points[:, :, 2].min() + frame.datum_m == pytest.approx(6.85, abs=2e-6)
    direction = np.array((*frame.inward, 0.))
    a = points[:, 0]
    e1, e2 = points[:, 1] - a, points[:, 2] - a
    h = np.cross(direction, e2)
    determinant = np.einsum('ij,ij->i', e1, h)
    valid = abs(determinant) > 1e-9
    inv = np.divide(1., determinant, out=np.zeros_like(determinant), where=valid)
    for z, expected in ((20.1, False), (19.7, True), (22.48, False)):
        delta = np.array(absolute_point(frame, 10.7, -3., z)) - a
        u = np.einsum('ij,ij->i', delta, h) * inv
        q = np.cross(delta, e1)
        v = np.einsum('j,ij->i', direction, q) * inv
        distance = np.einsum('ij,ij->i', e2, q) * inv
        hits = valid & (u >= -1e-7) & (v >= -1e-7) & (u + v <= 1 + 1e-7) & (distance > 1e-5)
        assert bool(hits.any()) == expected
