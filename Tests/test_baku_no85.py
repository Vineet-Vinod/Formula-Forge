from __future__ import annotations

import struct
from copy import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.baku import circuit_edges
from venues.baku_foundation import digest, rows
from venues.baku_no85 import finish, legacy
from venues.baku_no85_dataclasses import No85Recipe
from venues.baku_no85_geometry import build
from venues.east_architecture import facade

RECIPE = (
    Path(__file__).resolve().parents[1]
    / "Attribution/Sources/baku/no85/reconstruction.json"
)


@pytest.fixture(scope="module")
def source() -> No85Recipe:
    return TypeAdapter(No85Recipe).validate_json(RECIPE.read_bytes())


@pytest.fixture(scope="module")
def baseline(source: No85Recipe) -> CircuitScene:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    circuit_edges(scene)
    scene.tiles.clear()
    facade(scene, source.osm_id, source.expected_legacy_height_m, "classical", "Cream")
    tile = next(iter(scene.tiles.values()))
    payload = bytearray(tile.triangles[4:100])
    for vertex in range(3):
        struct.pack_into("<3f", payload, vertex * 32 + 12, 0.31, -0.41, 0.857788)
    tile.materials.append("BakuSahilCanopy")
    tile.triangles.extend(struct.pack("<I", len(tile.materials) - 1) + payload)
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


def independent(original: CircuitScene) -> CircuitScene:
    scene = copy(original)
    scene.tiles = {
        n: MeshTile(
            bytearray(t.triangles),
            t.minimum.copy(),
            t.maximum.copy(),
            t.materials.copy(),
        )
        for n, t in original.tiles.items()
    }
    scene.landmarks = list(original.landmarks)
    scene.modeled_buildings = set(original.modeled_buildings)
    scene.terrain_cutouts = list(original.terrain_cutouts)
    return scene


def test_only_no85_family_changes_preserving_other_lighting_and_ground(
    baseline: CircuitScene, source: No85Recipe
) -> None:
    scene = independent(baseline)
    parent = next(n for n in scene.tiles if n.startswith("Building_City"))
    tile = scene.tiles[parent]
    witness = bytes(tile.triangles[-100:])
    materials = tile.materials.copy()
    ground = {
        n: bytes(t.triangles)
        for n, t in scene.tiles.items()
        if n.startswith("Tile_Street")
    }
    grid, road, mask = scene.grid, scene.road, scene.road_mask
    change = finish(scene, RECIPE)
    assert (change.removed_rows, change.emitted_rows, change.preserved_rows) == (
        23724,
        72336,
        1,
    )
    assert change.supporting_ground_rows == 63
    assert scene.tiles[parent].triangles[:100] == witness
    assert scene.tiles[parent].materials[: len(materials)] == materials
    assert ground == {n: bytes(scene.tiles[n].triangles) for n in ground}
    assert scene.grid is grid and scene.road is road and scene.road_mask is mask
    assert scene.terrain_cutouts == baseline.terrain_cutouts


def test_reviewed_loggia_oriel_model_has_outward_packed_faces_and_open_courtyard(
    source: No85Recipe,
) -> None:
    scene = CircuitScene("baku")
    build(scene, source.geometry)
    tile = next(iter(scene.tiles.values()))
    assert (
        len(tile.triangles) // 100 == 72336
        and digest(rows(tile)) == source.candidate_counter_sha256
    )
    data = np.frombuffer(
        tile.triangles, dtype=np.dtype([("material", "<u4"), ("v", "<f4", (3, 8))])
    )
    v = data["v"].astype(float)
    p = v[:, :, [1, 0, 2]] * np.array([-1, -1, 1]) / 100
    n = v[:, :, [4, 3, 5]] * np.array([-1, -1, 1])
    crosses = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    lengths = np.linalg.norm(crosses, axis=1)
    assert float(lengths.min()) > 0
    assert float(np.sum(n * (crosses / lengths[:, None])[:, None], axis=2).min()) > 0.99
    roof_index = tile.materials.index("Roof")
    roof = unary_union(
        [
            Polygon(q[:, :2])
            for q in p[data["material"] == roof_index]
            if Polygon(q[:, :2]).area > 1e-12
        ]
    )
    owner = Polygon(source.geometry.ring_xy_m)
    assert owner.convex_hull.difference(owner).area > 200
    assert (
        roof.difference(owner.buffer(0.00035)).area < 1e-8
        and owner.difference(roof.buffer(0.00035)).area < 1e-8
    )
    assert (
        abs(
            float(p[:, :, 2].max())
            - source.geometry.floor_relative_m
            - (source.geometry.cornice_m + 1.03)
        )
        < 0.0001
    )


def test_stale_actual_ground_fails_before_any_scene_mutation(
    baseline: CircuitScene, source: No85Recipe
) -> None:
    scene = independent(baseline)
    scene.tiles[source.ground_supports[0].tile].triangles[8] ^= 1
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    landmarks = list(scene.landmarks)
    modeled = set(scene.modeled_buildings)
    with pytest.raises(ValueError, match="supporting Ground changed"):
        finish(scene, RECIPE)
    assert before == {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    assert scene.landmarks == landmarks and scene.modeled_buildings == modeled


def test_missing_owner_fails_before_any_ground_or_neighbor_changes(
    baseline: CircuitScene,
) -> None:
    scene = independent(baseline)
    tile = next(t for n, t in scene.tiles.items() if n.startswith("Building_City"))
    del tile.triangles[:100]
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    with pytest.raises(ValueError, match="exact original prepartitioned"):
        finish(scene, RECIPE)
    assert before == {n: bytes(t.triangles) for n, t in scene.tiles.items()}


def test_stale_source_frame_rejects_before_modeled_set_changes(
    baseline: CircuitScene, source: No85Recipe
) -> None:
    scene = independent(baseline)
    changed = replace(
        source,
        origin_lat_lon=(source.origin_lat_lon[0] + 0.001, source.origin_lat_lon[1]),
    )
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    modeled = set(scene.modeled_buildings)
    with pytest.raises(ValueError, match="source frame changed"):
        legacy(scene, changed)
    assert (
        before == {n: bytes(t.triangles) for n, t in scene.tiles.items()}
        and scene.modeled_buildings == modeled
    )
