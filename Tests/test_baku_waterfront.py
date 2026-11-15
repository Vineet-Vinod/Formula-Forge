from __future__ import annotations

import gzip
import struct
from collections import Counter
from copy import copy
from pathlib import Path

import numpy as np
import pytest
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from venues.baku import circuit_edges
from venues.baku_foundation import Row, digest, rows
from venues.baku_khagani_dataclasses import LegacyRow
from venues.baku_khagani_legacy import native_values, source_points
from venues.baku_waterfront import finish
from venues.baku_waterfront_dataclasses import WaterfrontRecipe
from venues.baku_waterfront_geometry import build
from venues.baku_waterfront_ground import recolor
from venues.east_architecture import facade

RECIPE = (
    Path(__file__).resolve().parents[1]
    / "Attribution/Sources/baku/waterfront/reconstruction.json.gz"
)


@pytest.fixture(scope="module")
def source() -> WaterfrontRecipe:
    return TypeAdapter(WaterfrontRecipe).validate_json(
        gzip.decompress(RECIPE.read_bytes())
    )


@pytest.fixture(scope="module")
def baseline(source: WaterfrontRecipe) -> CircuitScene:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    circuit_edges(scene)
    scene.tiles.clear()
    for front in source.geometry.fronts:
        facade(scene, front.osm_id, 22.0, "classical", "Cream")
    # An unrelated already-lit leaf witness must survive every position/UV/normal byte.
    city = next(iter(scene.tiles.values()))
    payload = bytearray(city.triangles[4:100])
    for vertex in range(3):
        struct.pack_into("<3f", payload, vertex * 32 + 12, 0.31, -0.41, 0.857788)
    city.materials.append("BakuSahilCanopy")
    city.triangles.extend(struct.pack("<I", len(city.materials) - 1) + payload)
    required: dict[str, Counter[Row]] = {}
    for row in (*source.ground_inputs, *source.supporting_ground):
        target = required.setdefault(row.tile, Counter())
        target[row.material, row.payload] = max(
            target[row.material, row.payload], row.copies
        )
    for name, counter in required.items():
        tile = scene.tiles.setdefault(name, MeshTile())
        for (material, raw), copies in counter.items():
            if material not in tile.materials:
                tile.materials.append(material)
            tile.triangles.extend(
                (struct.pack("<I", tile.materials.index(material)) + raw) * copies
            )
    return scene


def independent(original: CircuitScene) -> CircuitScene:
    scene = copy(original)
    scene.tiles = {
        name: MeshTile(
            bytearray(tile.triangles),
            tile.minimum.copy(),
            tile.maximum.copy(),
            tile.materials.copy(),
        )
        for name, tile in original.tiles.items()
    }
    scene.landmarks = list(original.landmarks)
    scene.modeled_buildings = set(original.modeled_buildings)
    scene.terrain_cutouts = list(original.terrain_cutouts)
    return scene


def test_atomic_owner_and_ground_replacement_retains_other_lighting_and_field(
    baseline: CircuitScene,
    source: WaterfrontRecipe,
) -> None:
    scene = independent(baseline)
    parent = next(name for name in scene.tiles if name.startswith("Building_City"))
    witness = bytes(scene.tiles[parent].triangles[-100:])
    materials = scene.tiles[parent].materials.copy()
    before_grid, before_road, before_mask = scene.grid, scene.road, scene.road_mask
    result = finish(scene, RECIPE)
    assert result.removed_owner_rows == sum(f.triangles for f in source.legacy_families)
    assert result.new_geometry_rows == source.expected_geometry_rows
    assert result.segmented_ground_rows == source.expected_ground_rows
    assert scene.tiles[parent].triangles[:100] == witness
    assert scene.tiles[parent].materials[: len(materials)] == materials
    assert (
        scene.grid is before_grid
        and scene.road is before_road
        and scene.road_mask is before_mask
    )
    assert scene.terrain_cutouts == baseline.terrain_cutouts


def test_new_geometry_matches_frozen_source_and_foliage_field(
    source: WaterfrontRecipe,
) -> None:
    scene = CircuitScene("baku")
    build(scene, source.geometry)
    counter = sum((rows(tile) for tile in scene.tiles.values()), Counter())
    assert (
        counter.total() == source.expected_geometry_rows
        and digest(counter) == source.geometry_counter_sha256
    )
    assert len(source.geometry.trees) == 34
    assert {f.osm_id for f in source.geometry.fronts} == {465003806, 152191301}
    for tile in scene.tiles.values():
        data = np.frombuffer(
            tile.triangles,
            dtype=np.dtype([("material", "<u4"), ("vertices", "<f4", (3, 8))]),
        )
        values = data["vertices"].astype(float)
        points = values[:, :, [1, 0, 2]] * np.array([-1, -1, 1]) / 100
        normals = values[:, :, [4, 3, 5]] * np.array([-1, -1, 1])
        crosses = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        lengths = np.linalg.norm(crosses, axis=1)
        assert float(lengths.min()) > 0
        leaf_index = (
            tile.materials.index("BakuSahilCanopy")
            if "BakuSahilCanopy" in tile.materials
            else -1
        )
        leaves = data["material"] == leaf_index
        assert np.all(normals[leaves, :, 2] > 0)
        assert (
            float(abs(np.linalg.norm(normals[leaves], axis=2) - 1).max(initial=0.0))
            < 1e-5
        )
        hard = ~leaves
        assert (
            float(
                np.sum(
                    normals[hard] * (crosses[hard] / lengths[hard, None])[:, None],
                    axis=2,
                ).min(initial=1.0)
            )
            > 0.98
        )


def test_stale_ground_rejects_before_any_geometry_or_metadata_mutation(
    baseline: CircuitScene,
    source: WaterfrontRecipe,
) -> None:
    scene = independent(baseline)
    tile = scene.tiles[source.supporting_ground[0].tile]
    tile.triangles[8] ^= 1
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    landmarks = list(scene.landmarks)
    modeled = set(scene.modeled_buildings)
    with pytest.raises(ValueError, match="supporting Ground changed"):
        finish(scene, RECIPE)
    assert before == {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    assert scene.landmarks == landmarks and scene.modeled_buildings == modeled


def test_missing_owner_rejects_before_ground_recolor(baseline: CircuitScene) -> None:
    scene = independent(baseline)
    tile = next(t for n, t in scene.tiles.items() if n.startswith("Building_City"))
    del tile.triangles[:100]
    before = {n: bytes(t.triangles) for n, t in scene.tiles.items()}
    with pytest.raises(ValueError, match="exact original prepartitioned"):
        finish(scene, RECIPE)
    assert before == {n: bytes(t.triangles) for n, t in scene.tiles.items()}


def test_plane_segmentation_preserves_full_rows_and_barycentric_fields() -> None:
    scene = MeshScene()
    scene.triangle(
        "Tile_Ground",
        "Runoff",
        (-1432.0, -950.0, 1.0),
        (-1417.0, -949.0, 1.2),
        (-1427.0, -930.0, 1.5),
    )
    name, tile = next(iter(scene.tiles.items()))
    row = LegacyRow(name, "Tile_Ground", "Runoff", bytes(tile.triangles[4:100]), -1)
    unchanged, audit = recolor(row, box(0, 0, 2, 2))
    assert unchanged == [row] and audit is None
    whole, _ = recolor(row, box(-1450, -960, -1400, -920))
    assert whole[0].payload == row.payload and whole[0].material == "Grass"
    clipped, audit = recolor(row, box(-1430, -960, -1422, -925))
    assert audit is not None
    assert {r.material for r in clipped} == {"Runoff", "Grass"}
    original = Polygon(source_points(native_values(row.payload))[:, :2])
    actual = unary_union(
        [Polygon(source_points(native_values(r.payload))[:, :2]) for r in clipped]
    )
    assert original.difference(actual.buffer(0.00035)).area < 1e-8
    assert audit.maximum_plane_error_m <= audit.maximum_plane_error_bound_m * 1.01
    assert audit.overlap_area_m2 < 1e-7 and audit.dropped_f32_area_m2 == 0
    assert (
        audit.maximum_normal_interpolation_error < 1e-6
        and audit.maximum_uv_interpolation_error < 1e-6
    )
