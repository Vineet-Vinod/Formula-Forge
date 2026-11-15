from __future__ import annotations

import hashlib
import struct
from collections import Counter
from copy import copy
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_partition_dataclasses import SceneManifest
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from venues.buddh_first_sector import retained_road
from venues.buddh_first_sector_dataclasses import RetainedBaseline
from venues.buddh_terrace import (
    build_palms,
    capture_ground,
    emit,
    finish_terrain,
    load_recipe,
    polygon_at,
)
from venues.buddh_terrace_dataclasses import FrozenTerraceProof, TerraceRecipe
from venues.east_architecture import trees

SOURCE = Path("Attribution/Sources/buddh")


def semantic(scene: MeshScene) -> Counter[bytes]:
    rows: Counter[bytes] = Counter()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            rows[
                material.encode()
                + b"\0"
                + bytes(tile.triangles[offset + 4 : offset + 100])
            ] += 1
    return rows


@pytest.fixture(scope="module")
def source_case() -> tuple[CircuitScene, TerraceRecipe]:
    scene = CircuitScene("buddh")
    recipe = load_recipe(scene)
    domain = polygon_at(recipe.geometry).buffer(1)
    manifest = TypeAdapter(SceneManifest).validate_json(
        (scene.scratch / "manifest.json").read_bytes()
    )
    for source in manifest.tiles:
        b = source.bounds
        bounds = box(-b[4] / 100, -b[3] / 100, -b[1] / 100, -b[0] / 100)
        if not source.name.startswith("Tile_Street") or not bounds.intersects(domain):
            continue
        data = (scene.scratch / source.file).read_bytes()
        scene.tiles[source.name] = MeshTile(
            bytearray(data[12:]), list(b[:3]), list(b[3:]), list(source.materials)
        )
    road = [p for p in scene.road if 1200 <= p.station <= 1700]
    scene.road_mask = unary_union(
        [
            Polygon(
                [
                    a.point(-a.half_width)[:2],
                    b.point(-b.half_width)[:2],
                    b.point(b.half_width)[:2],
                    a.point(a.half_width)[:2],
                ]
            )
            for a, b in pairwise(road)
        ]
    )
    return scene, recipe


def test_actual_emitted_grass_replays_independently_frozen_terrace(
    source_case: tuple[CircuitScene, TerraceRecipe],
) -> None:
    source, recipe = source_case
    ground = capture_ground(source, polygon_at(recipe.geometry).buffer(0.5))
    candidate = MeshScene()
    result = emit(candidate, recipe.geometry, ground)
    expected = TypeAdapter(FrozenTerraceProof).validate_json(
        (SOURCE / "t3-terrace-evidence/private-candidate-proof.json").read_bytes()
    )
    assert {
        name: hashlib.sha256(tile.triangles).hexdigest()
        for name, tile in candidate.tiles.items()
    } == {
        row.name: row.ordered_rows_sha256 for row in expected.candidate_tiles
    }
    assert len(result.feet) == 75
    assert result.minimum_deck_clearance_m == pytest.approx(
        0.16378507021484268, abs=1e-8
    )
    for foot in result.feet:
        assert foot.base_z_m == pytest.approx(foot.minimum_ground_m - 0.1)
        assert foot.plinth_top_z_m == pytest.approx(foot.maximum_ground_m + 0.15)
        assert foot.column_top_z_m > foot.plinth_top_z_m + 0.02
        assert foot.missing_ground_m2 < 1e-7
        assert foot.actual_source_rows


def test_post_terrain_adapter_only_appends_and_keeps_original_row_bytes(
    source_case: tuple[CircuitScene, TerraceRecipe],
) -> None:
    source, recipe = source_case
    scene = copy(source)
    scene.tiles = {
        name: MeshTile(
            bytearray(t.triangles), list(t.minimum), list(t.maximum), list(t.materials)
        )
        for name, t in source.tiles.items()
    }
    scene.landmarks = []
    scene.triangle(
        "Building_Existing", "Steel", (295, 880, 2), (296, 880, 2), (295, 881, 2)
    )
    before = {
        name: (
            bytes(t.triangles),
            tuple(t.materials),
            tuple(t.minimum),
            tuple(t.maximum),
        )
        for name, t in scene.tiles.items()
    }
    result = finish_terrain(scene)
    for name, (rows, materials, minimum, maximum) in before.items():
        tile = scene.tiles[name]
        assert tile.triangles[: len(rows)] == rows
        assert tuple(tile.materials[: len(materials)]) == materials
        if name.startswith("Tile_Street"):
            assert bytes(tile.triangles) == rows
            assert tuple(tile.minimum) == minimum
            assert tuple(tile.maximum) == maximum
    fresh = MeshScene()
    emit(
        fresh,
        recipe.geometry,
        capture_ground(source, polygon_at(recipe.geometry).buffer(0.5)),
    )
    added = MeshScene()
    for name, tile in scene.tiles.items():
        old_length = len(before[name][0]) if name in before else 0
        added.tiles[name] = MeshTile(
            bytearray(tile.triangles[old_length:]), materials=list(tile.materials)
        )
    assert semantic(added) == semantic(fresh)
    assert result.occupied_plan.area == 3984
    assert len(scene.landmarks) == 1


def test_missing_actual_support_and_engineered_overlap_fail_before_mutation(
    source_case: tuple[CircuitScene, TerraceRecipe],
) -> None:
    source, recipe = source_case
    empty = MeshScene()
    with pytest.raises(ValueError, match="support footprint is incomplete"):
        emit(empty, recipe.geometry, ())
    assert not empty.tiles
    invalid = copy(source)
    invalid.tiles = {}
    invalid.road_mask = polygon_at(recipe.geometry)
    with pytest.raises(ValueError, match="overlaps an existing road"):
        finish_terrain(invalid)
    assert not invalid.tiles


def test_exact_two_procedural_exclusions_preserve_all_other_palms() -> None:
    source = CircuitScene("buddh")
    baseline = TypeAdapter(RetainedBaseline).validate_json(
        (SOURCE / "first-sector-baseline.json").read_bytes()
    )
    source.road = list(retained_road(baseline, tuple(source.road)))
    old, new = copy(source), copy(source)
    old.tiles = {}
    new.tiles = {}
    old.vegetation = []
    new.vegetation = []
    trees(old, 1500, 2450, -1, 28, 45, 8, palm=True)
    build_palms(new)
    removed = MeshScene()
    recipe = load_recipe(source)
    for palm in recipe.original_palms:
        if palm.index in recipe.excluded_palm_indices:
            removed.palm(palm.base, palm.height_m)
    old_rows, new_rows, removed_rows = semantic(old), semantic(new), semantic(removed)
    assert old_rows - new_rows == removed_rows
    assert new_rows + removed_rows == old_rows
    assert old.vegetation[0]["count"] == 22
    assert new.vegetation[0]["count"] == 20
    assert sum(removed_rows.values()) == 13456
    assert old.buildings is new.buildings


def test_source_frame_and_palm_pose_drift_are_rejected_before_emission(
    source_case: tuple[CircuitScene, TerraceRecipe],
) -> None:
    source, recipe = source_case
    changed = copy(source)
    changed.tiles = {}
    changed.provenance = replace(
        source.provenance, route=replace(source.provenance.route, uniform_scale=1.001)
    )
    with pytest.raises(ValueError, match="qualified Buddh source frame"):
        load_recipe(changed)
    assert not changed.tiles
    changed = copy(source)
    changed.tiles = {}
    changed.road = [replace(point, x=point.x + 0.1) for point in source.road]
    with pytest.raises(ValueError, match="palm poses"):
        build_palms(changed)
    assert not changed.tiles
    assert recipe.excluded_palm_indices == (0, 1)
