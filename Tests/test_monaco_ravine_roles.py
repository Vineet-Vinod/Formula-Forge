"""Material partitioning cannot move old planes or alter protected surfaces."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import numpy as np
import pytest
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from venues.monaco_ravine_roles import partition
from venues.monaco_ravine_roles_dataclasses import GroundRow, RavineRolesSource
from venues.monaco_ravine_roles_ground import native_values, recolor, source_points
from venues.monaco_surfaces import face, interpolate

SOURCE = Path('Attribution/Sources/monaco/architecture/ravine-roles/reconstruction.json')
PARENT = bytes.fromhex('63cb0dc7774926454eef8a451b61233fc18d1b3f130bf23eebd854c0387f3542394211c714c65845dbcfb045de98403f0231923e78f5123f35bc8ac05dee39428b4e0dc7946c5545a46d414504dc373f5860053f4d12ea3e699788c06adf3442')
EAR = bytes.fromhex('cb6b06c7a5d90645ffe30f450c29163f38a8003f162d1f3fb49b2cc0180f2c423ab606c764200545233815458f34193f2e98003f77741c3fe6662ac05e6e2c42177106c7fc660745b19e0f454fb2163fc114003fc80d1f3f9e502dc0e0152c42')
EAR_MASK = 'POLYGON ((-21.57602783203125 344.1179296875, -21.588468903226275 344.12538958525994, -21.576026920470984 344.11793214778714, -21.57602783203125 344.1179296875))'


def test_complete_roles_keep_the_original_native_vertices() -> None:
    row = GroundRow('Runoff', PARENT)
    original = Polygon(source_points(native_values(PARENT))[:, :2])
    outside, unchanged = recolor(row, box(0, 0, 1, 1))
    assert outside == [row] and unchanged is None
    inside, audit = recolor(row, original.buffer(.1))
    assert inside == [GroundRow('MonacoNaturalGround', PARENT)]
    assert audit is not None and audit.outside_area_m2 == 0


def test_split_keeps_plane_normals_uvs_and_complete_coverage() -> None:
    plan = box(-33, 362.3, -27.2, 365.7)
    fragments, audit = recolor(GroundRow('Runoff', PARENT), plan)
    assert audit is not None and audit.normal_min_alignment > 0
    assert {f.material for f in fragments} == {'Runoff', 'MonacoNaturalGround'}
    parent = face(MeshTile(bytearray(struct.pack('<I', 0) + PARENT), materials=['Runoff']), 0)
    pieces = []
    for fragment in fragments:
        values = native_values(fragment.payload)
        points = source_points(values)
        pieces.append(Polygon(points[:, :2]))
        for vertex, point in zip(values, points):
            expected = np.asarray(interpolate(parent, float(point[0]), float(point[1])))
            bounds = np.abs(np.spacing(vertex.astype(np.float32)).astype(float)) * .501
            assert np.all(abs(vertex[2:] - expected[2:]) <= bounds[2:] + 1e-10)
    union = unary_union(pieces)
    assert parent.plan.difference(union.buffer(.00006)).area < 1e-8
    assert union.difference(parent.plan.buffer(.00006)).area < 1e-8
    assert sum(p.area for p in pieces) - union.area < 1e-7


def test_unrepresentable_ear_keeps_the_complete_old_ground_row() -> None:
    row = GroundRow('Runoff', EAR)
    result, audit = recolor(row, from_wkt(EAR_MASK))
    assert result == [row]
    assert audit is not None
    assert audit.held_unrepresentable_natural_area_m2 == pytest.approx(1.8704376900723078e-8)
    assert audit.dropped_f32_area_m2 == 0
    assert audit.maximum_plane_error_m == 0


def test_wrong_ownership_fails_before_any_material_or_geometry_mutation() -> None:
    scene = MeshScene()
    values = native_values(PARENT)[:, :3]
    tile = MeshTile(bytearray(struct.pack('<I', 0) + PARENT),
        values.min(axis=0).tolist(), values.max(axis=0).tolist(), ['Runoff'])
    scene.tiles['Tile_Street_m1_01'] = tile
    original = bytes(tile.triangles), tile.materials.copy()
    with pytest.raises(ValueError, match='parent ownership'):
        partition(scene, box(-33, 362.3, -27.2, 365.7), 2, 100, '0' * 64)
    assert (bytes(tile.triangles), tile.materials) == original


def test_protected_material_and_unrelated_mesh_keep_literal_rows() -> None:
    scene = MeshScene()
    values = native_values(PARENT)[:, :3]
    protected = struct.pack('<I', 1) + PARENT
    name = 'Tile_Street_m1_01'
    scene.tiles[name] = MeshTile(bytearray(struct.pack('<I', 0) + PARENT + protected),
        values.min(axis=0).tolist(), values.max(axis=0).tolist(), ['Runoff', 'MonacoIvyGround'])
    scene.triangle('Building_Detail', 'White', (0, 0, 10), (1, 0, 10), (0, 1, 10))
    untouched = {n: bytes(t.triangles) for n, t in scene.tiles.items() if n != name}
    plan = box(-33, 362.3, -27.2, 365.7)
    area = Polygon(source_points(native_values(PARENT))[:, :2]).intersection(plan).area
    digest = hashlib.sha256(name.encode() + b'\0' + struct.pack('<Q', 0) + PARENT).hexdigest()
    change = partition(scene, plan, 1, area, digest)
    assert change.selected_parent_faces == 1 and change.split_faces == 1
    assert scene.tiles[name].triangles[-100:] == protected
    assert scene.tiles[name].materials[:2] == ['Runoff', 'MonacoIvyGround']
    assert all(bytes(scene.tiles[n].triangles) == raw for n, raw in untouched.items())


def test_typed_source_keeps_the_engineered_junction_held() -> None:
    source = TypeAdapter(RavineRolesSource).validate_json(SOURCE.read_bytes())
    domain = from_wkt(source.expected_domain_wkt)
    assert source.expected_parent_faces == 181
    assert not domain.covers(from_wkt('POINT (-5.199941844901582 362.99942115669387)'))
