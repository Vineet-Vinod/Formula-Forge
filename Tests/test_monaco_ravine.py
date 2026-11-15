from __future__ import annotations

import struct
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile, Point, TerrainGrid
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from shapely import from_wkt
from venues.monaco_groves import ground_height
from venues.monaco_groves_dataclasses import WestBankGroves
from venues.monaco_ravine import (
    _normal_check,
    _points,
    _precision,
    _project_outside,
    replace_ground,
)
from venues.monaco_ravine_dataclasses import RavineSource
from venues.monaco_surfaces_dataclasses import NativeVertex

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/monaco"


def test_quantized_outside_fragment_stays_on_its_original_sloping_plane() -> None:
    from circuit_mesh import cross, norm, sub

    normal = (-.2377839161160891, -.5800818071771148, .7790788831810481)
    anchor = (-16.088902587890626, 321.9223828125, 10.6381005859375)
    x = (-16.080142822265625 - 16.08014404296875) / 2
    y = (321.88623046875 + 321.88625) / 2
    points: tuple[Point, ...] = (
        anchor, (x + .00000005, y - .0000002, 0), (x - .00000005, y + .0000002, 0)
    )
    vertices: list[NativeVertex] = []
    for x, y, _z in points:
        z = anchor[2] - (normal[0] * (x - anchor[0]) + normal[1] * (y - anchor[1])) / normal[2]
        vertices.append((-y * 100, -x * 100, z * 100,
                         -normal[1], -normal[0], normal[2], x / 8, y / 8))
    original = _precision(0, tuple(vertices), normal, False)
    raw = bytearray(struct.pack('<I24f', 0, *(value for vertex in original.packed_vertices for value in vertex)))
    with pytest.raises(ValueError, match='inward stored normal'):
        _normal_check('outside', raw, [original])

    projected, shift = _project_outside(original)
    assert 0 < shift < .00001
    assert projected.packed_vertices[0] == original.packed_vertices[0]
    for old, new in zip(original.packed_vertices, projected.packed_vertices):
        assert new[:2] == old[:2]
        assert new[3:] == old[3:]
    points = _points(projected.packed_vertices)
    geometric = norm(cross(sub(points[1], points[0]), sub(points[2], points[0])))
    assert sum(a * b for a, b in zip(geometric, normal)) > .99
    for x, y, z in points:
        expected = anchor[2] - (normal[0] * (x - anchor[0]) + normal[1] * (y - anchor[1])) / normal[2]
        assert abs(z - expected) < .0000007
    raw = bytearray(struct.pack('<I24f', 0, *(value for vertex in projected.packed_vertices for value in vertex)))
    minimum, resolved, repairs = _normal_check('outside', raw, [projected])
    assert minimum > .99 and resolved > .99
    assert not repairs


def _fixture() -> tuple[MeshScene, TerrainGrid, RavineSource]:
    source = TypeAdapter(RavineSource).validate_json(
        (SOURCES / "architecture/ravine-source.json").read_bytes()
    )
    grid = TypeAdapter(TerrainGrid).validate_json(
        (SOURCES / source.grid_file).read_bytes()
    )
    scene = MeshScene()
    for row in source.original_ground_rows:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        raw = struct.pack("<I", tile.materials.index(row.material)) + bytes.fromhex(
            row.attributes_hex
        )
        tile.triangles.extend(raw * row.copies)
        values = struct.unpack_from("<24f", raw, 4)
        for index in (0, 8, 16):
            for axis in range(3):
                tile.minimum[axis] = min(tile.minimum[axis], values[index + axis])
                tile.maximum[axis] = max(tile.maximum[axis], values[index + axis])
    return scene, grid, source


def test_ravine_keeps_protected_rows_and_repairs_only_unresolved_normals() -> None:
    scene, grid, source = _fixture()
    name = source.original_ground_rows[0].tile
    tile = scene.tiles[name]
    tile.materials.append("Concrete")
    protected = struct.pack("<I", len(tile.materials) - 1) + bytes(
        tile.triangles[4:100]
    )
    tile.triangles.extend(protected)
    change = replace_ground(scene, grid, from_wkt(source.expected_domain_wkt), source)
    result = scene.tiles[name]
    assert protected in [
        bytes(result.triangles[i : i + 100])
        for i in range(0, len(result.triangles), 100)
    ]
    assert change.tiles == ("Tile_Street_m1_01",)
    assert change.source_faces == 225
    assert change.minimum_normal_alignment >= 0
    assert len(change.unresolved_faces) == 2
    assert all(
        face.minimum_altitude_m <= 2 * face.xy_ulp_bound_m
        for face in change.unresolved_faces
    )
    assert change.maximum_encoding_xy_error_m < 0.00002
    assert change.maximum_encoding_z_error_m < 0.000003


def test_ravine_stale_ground_rejection_leaves_original_scene_intact() -> None:
    scene, grid, source = _fixture()
    first = scene.tiles[source.original_ground_rows[0].tile]
    first.triangles[99] ^= 1
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError, match="original planes changed"):
        replace_ground(scene, grid, from_wkt(source.expected_domain_wkt), source)
    assert {name: bytes(tile.triangles) for name, tile in scene.tiles.items()} == before


def _ground(source: WestBankGroves, x: float, y: float) -> float:
    faces = []
    for row in source.supports:
        values = struct.unpack("<24f", bytes.fromhex(row.attributes_hex))
        points = tuple(
            (-values[k + 1] / 100, -values[k] / 100, values[k + 2] / 100)
            for k in (0, 8, 16)
        )
        faces.append((points[0], points[1], points[2]))
    return ground_height(tuple(faces), x, y)


def _top(base: tuple[float, float, float], height: float, seed: int) -> float:
    scene = MeshScene()
    scene.broadleaf(base, height, seed)
    return max(
        struct.unpack_from("<f", tile.triangles, offset + 4 + k * 32 + 8)[0] / 100
        for tile in scene.tiles.values()
        for offset in range(0, len(tile.triangles), 100)
        for k in range(3)
    )


def test_only_two_canopies_reanchor_and_keep_rendered_height_above_ground() -> None:
    previous = TypeAdapter(WestBankGroves).validate_json(
        (SOURCES / "architecture/ravine-canopy-baseline.json").read_bytes()
    )
    current = TypeAdapter(WestBankGroves).validate_json(
        (SOURCES / "architecture/west-bank-groves.json").read_bytes()
    )
    assert previous.canopies[2:] == current.canopies[2:]
    for old, new in zip(previous.canopies[:2], current.canopies[:2]):
        assert old.base[:2] == new.base[:2]
        assert old.seed == new.seed
        assert old.source_pixel_xy == new.source_pixel_xy
        assert old.crown_diameter_range_m == new.crown_diameter_range_m
        low, high = new.crown_diameter_range_m
        assert low <= 0.82 * new.height_m <= high
        old_height = _top(old.base, old.height_m, old.seed) - _ground(
            previous, *old.base[:2]
        )
        new_height = _top(new.base, new.height_m, new.seed) - _ground(
            current, *new.base[:2]
        )
        assert abs(old_height - new_height) < 0.00001
