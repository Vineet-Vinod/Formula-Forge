from __future__ import annotations

import struct
from copy import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.baku import circuit_edges
from venues.baku_foundation import digest, rows
from venues.baku_mirbabayev import finish, legacy, project_stone_uvs
from venues.baku_mirbabayev_dataclasses import PalaceRecipe
from venues.baku_mirbabayev_geometry import build
from venues.east_architecture import facade

RECIPE = (
    Path(__file__).resolve().parents[1]
    / "Attribution/Sources/baku/mirbabayev/reconstruction.json"
)


@pytest.fixture(scope="module")
def source() -> PalaceRecipe:
    return TypeAdapter(PalaceRecipe).validate_json(RECIPE.read_bytes())


@pytest.fixture(scope="module")
def baseline(source: PalaceRecipe) -> CircuitScene:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    circuit_edges(scene)
    scene.tiles.clear()
    facade(scene, source.osm_id, source.expected_legacy_height_m, "classical", "Cream")
    city = next(iter(scene.tiles.values()))
    payload = bytearray(city.triangles[4:100])
    for offset in (12, 44, 76):
        struct.pack_into("<3f", payload, offset, 0.31, -0.41, 0.857788)
    city.materials.append("BakuSahilCanopy")
    city.triangles.extend(struct.pack("<I", len(city.materials) - 1) + payload)
    for support in source.ground_supports:
        tile = scene.tiles.setdefault(support.tile, MeshTile())
        if support.material not in tile.materials:
            tile.materials.append(support.material)
        tile.triangles.extend(
            (
                struct.pack("<I", tile.materials.index(support.material))
                + support.payload
            )
            * support.copies
        )
    return scene


def independent_scene(baseline: CircuitScene) -> CircuitScene:
    scene = copy(baseline)
    scene.tiles = {
        name: MeshTile(
            bytearray(tile.triangles),
            tile.minimum.copy(),
            tile.maximum.copy(),
            tile.materials.copy(),
        )
        for name, tile in baseline.tiles.items()
    }
    scene.landmarks = list(baseline.landmarks)
    scene.modeled_buildings = set(baseline.modeled_buildings)
    scene.terrain_cutouts = list(baseline.terrain_cutouts)
    return scene


def test_only_old_owner_is_replaced_preserving_unselected_normal_payload(
    baseline: CircuitScene,
) -> None:
    scene = independent_scene(baseline)
    parent = next(name for name in scene.tiles if name.startswith("Building_City"))
    original = scene.tiles[parent]
    materials, witness = original.materials.copy(), bytes(original.triangles[-100:])
    ground = {
        n: bytes(t.triangles)
        for n, t in scene.tiles.items()
        if n.startswith("Tile_Street")
    }
    grid, road, mask = scene.grid, scene.road, scene.road_mask
    change = finish(scene, RECIPE)
    tile = scene.tiles[change.parent]
    assert (
        change.removed_generic_rows,
        change.emitted_rows,
        change.preserved_parent_rows,
    ) == (41104, 122684, 1)
    assert change.supporting_ground_rows == 95
    assert bytes(tile.triangles[:100]) == witness
    assert tile.materials[: len(materials)] == materials
    assert ground == {n: bytes(scene.tiles[n].triangles) for n in ground}
    assert scene.grid is grid and scene.road is road and scene.road_mask is mask


def test_actual_packed_taller_geometry_matches_review_and_leaves_courtyard_open(
    baseline: CircuitScene, source: PalaceRecipe
) -> None:
    scene = independent_scene(baseline)
    scene.tiles = {}
    geometry = build(scene, source.geometry)
    tile = next(iter(scene.tiles.values()))
    assert digest(rows(tile)) == source.candidate_counter_sha256
    assert len(tile.triangles) // 100 == 122684
    data = np.frombuffer(
        tile.triangles, dtype=np.dtype([("material", "<u4"), ("v", "<f4", (3, 8))])
    )
    vertices = data["v"].astype(float)
    points = vertices[:, :, [1, 0, 2]] * np.array([-1, -1, 1]) / 100
    normals = vertices[:, :, [4, 3, 5]] * np.array([-1, -1, 1])
    crosses = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    lengths = np.linalg.norm(crosses, axis=1)
    assert float(lengths.min()) > 0
    crosses /= lengths[:, None]
    assert float(np.sum(normals * crosses[:, None], axis=2).min()) > 0.99
    roof_index = tile.materials.index("Roof")
    roof = unary_union(
        [
            Polygon(p[:, :2])
            for p in points[data["material"] == roof_index]
            if Polygon(p[:, :2]).area > 1e-12
        ]
    )
    owner = Polygon(source.geometry.ring_xy_m)
    assert owner.convex_hull.difference(owner).area > 100
    assert roof.difference(owner.buffer(0.0001)).area < 1e-8
    assert owner.difference(roof.buffer(0.000175)).area < 1e-10
    assert (
        abs(float(points[:, :, 2].max()) - source.geometry.floor_relative_m - 26.38)
        < 0.00001
    )
    assert geometry.rustication_max_curve_change_m <= 0.0005


def test_stale_actual_ground_fails_before_city_or_landmark_mutation(
    baseline: CircuitScene, source: PalaceRecipe
) -> None:
    scene = independent_scene(baseline)
    tile = scene.tiles[source.ground_supports[0].tile]
    tile.triangles[8] ^= 1
    before = {name: bytes(t.triangles) for name, t in scene.tiles.items()}
    landmarks, modeled = list(scene.landmarks), set(scene.modeled_buildings)
    with pytest.raises(ValueError, match="supporting Ground changed"):
        finish(scene, RECIPE)
    assert before == {name: bytes(t.triangles) for name, t in scene.tiles.items()}
    assert scene.landmarks == landmarks and scene.modeled_buildings == modeled


def test_missing_legacy_row_fails_before_any_source_mutation(
    baseline: CircuitScene,
) -> None:
    scene = independent_scene(baseline)
    city = next(t for n, t in scene.tiles.items() if n.startswith("Building_City"))
    del city.triangles[:100]
    before = {name: bytes(t.triangles) for name, t in scene.tiles.items()}
    with pytest.raises(ValueError, match="exact original prepartitioned"):
        finish(scene, RECIPE)
    assert before == {name: bytes(t.triangles) for name, t in scene.tiles.items()}


def test_changed_owner_frame_rejects_without_mutating_modeled_set(
    baseline: CircuitScene, source: PalaceRecipe
) -> None:
    scene = independent_scene(baseline)
    changed = replace(
        source,
        origin_lat_lon=(source.origin_lat_lon[0] + 0.001, source.origin_lat_lon[1]),
    )
    before = {name: bytes(t.triangles) for name, t in scene.tiles.items()}
    modeled = set(scene.modeled_buildings)
    with pytest.raises(ValueError, match="source frame changed"):
        legacy(scene, changed)
    assert before == {name: bytes(t.triangles) for name, t in scene.tiles.items()}
    assert scene.modeled_buildings == modeled


def test_stone_mapping_is_continuous_across_different_wall_triangulations() -> None:
    scene = MeshScene()
    a, b, c, d = (0., 0., 0.), (12., 0., 0.), (12., 0., 8.), (0., 0., 8.)
    scene.triangle('Building_Stone', 'BakuStone', a, b, c)
    scene.triangle('Building_Stone', 'BakuStone', a, c, d)
    scene.triangle('Building_Trim', 'Cream', a, b, d)
    tile = next(iter(scene.tiles.values()))
    before = bytes(tile.triangles)
    assert project_stone_uvs(tile) == 2
    assert tile.triangles[200:] == before[200:]
    shared: dict[tuple[float, float, float], tuple[float, float]] = {}
    for offset in (0, 100):
        assert tile.triangles[offset:offset + 4] == before[offset:offset + 4]
        for vertex in range(3):
            start = offset + 4 + vertex * 32
            assert tile.triangles[start:start + 24] == before[start:start + 24]
            point = struct.unpack_from('<3f', tile.triangles, start)
            uv = struct.unpack_from('<2f', tile.triangles, start + 24)
            assert point not in shared or shared[point] == uv
            shared[point] = uv
    assert len(set(shared.values())) == 4
