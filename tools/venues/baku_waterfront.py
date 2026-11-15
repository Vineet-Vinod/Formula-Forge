"""Atomic finite waterfront family replacement and original-plane grass segmentation."""

from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter
from copy import copy
from pathlib import Path

from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt

from venues.baku_foundation import Row, digest, replacement, rows
from venues.baku_ground_dataclasses import PackedPatchRow
from venues.baku_khagani_dataclasses import LegacyRow
from venues.baku_waterfront_dataclasses import WaterfrontChange, WaterfrontRecipe
from venues.baku_waterfront_geometry import build
from venues.baku_waterfront_ground import recolor
from venues.east_architecture import facade


def legacy(scene: CircuitScene, source: WaterfrontRecipe) -> dict[str, Counter[Row]]:
    provenance = scene.provenance
    if (
        scene.slug != "baku"
        or abs(provenance.origin.latitude - source.origin_lat_lon[0]) > 1e-10
        or abs(provenance.origin.longitude - source.origin_lat_lon[1]) > 1e-10
        or abs(provenance.route.uniform_scale - source.uniform_scale) > 1e-10
    ):
        raise ValueError("Waterfront source frame changed")
    if hashlib.sha256(scene.road_mask.wkb).hexdigest() != source.road_mask_sha256:
        raise ValueError("Waterfront protected road geometry changed")
    for name, expected_sha in source.protected_inputs_sha256.items():
        if (
            hashlib.sha256((scene.scratch / name).read_bytes()).hexdigest()
            != expected_sha
        ):
            raise ValueError("Waterfront protected road/protection input changed")
    replay = copy(scene)
    replay.tiles = {}
    replay.landmarks = []
    replay.terrain_cutouts = list(scene.terrain_cutouts)
    replay.modeled_buildings = set(scene.modeled_buildings)
    for front in source.geometry.fronts:
        building = scene.footprint(front.osm_id)
        if (
            len(building.ring) != len(front.ring_xy_m)
            or max(
                abs(a - b)
                for p, q in zip(building.ring, front.ring_xy_m)
                for a, b in zip(p, q)
            )
            > 1e-8
            or any(key in building.tags for key in ("height", "building:levels"))
            or abs(
                min(scene.ground(x, y) for x, y in building.ring)
                - front.floor_relative_m
            )
            > 1e-8
        ):
            raise ValueError("Waterfront literal owner or inherited datum changed")
        facade(replay, front.osm_id, 22.0, "classical", "Cream")
    actual = {parent: rows(tile) for parent, tile in replay.tiles.items()}
    expected = {item.parent: item for item in source.legacy_families}
    if set(actual) != set(expected) or any(
        actual[n].total() != expected[n].triangles
        or digest(actual[n]) != expected[n].counter_sha256
        for n in actual
    ):
        raise ValueError("Waterfront old owner families differ from qualified source")
    return actual


def validate_rows(scene: CircuitScene, required: tuple[PackedPatchRow, ...]) -> int:
    grouped: dict[str, Counter[Row]] = {}
    for row in required:
        grouped.setdefault(row.tile, Counter())[row.material, row.payload] += row.copies
    for name, expected in grouped.items():
        if name not in scene.tiles:
            raise ValueError("Waterfront actual supporting Ground tile is missing")
        actual = rows(scene.tiles[name])
        if any(actual[key] != count for key, count in expected.items()):
            raise ValueError("Waterfront actual supporting Ground changed")
    return sum(c.total() for c in grouped.values())


def append(tile: MeshTile, material: str, payload: bytes) -> None:
    if material not in tile.materials:
        tile.materials.append(material)
    tile.triangles.extend(struct.pack("<I", tile.materials.index(material)) + payload)
    for vertex in range(3):
        point = struct.unpack_from("<3f", payload, vertex * 32)
        for axis in range(3):
            tile.minimum[axis] = min(tile.minimum[axis], point[axis])
            tile.maximum[axis] = max(tile.maximum[axis], point[axis])


def finish(scene: CircuitScene, source_path: Path | None = None) -> WaterfrontChange:
    path = source_path or scene.sources / "waterfront/reconstruction.json.gz"
    source = TypeAdapter(WaterfrontRecipe).validate_json(
        gzip.decompress(path.read_bytes())
    )
    original_owners = legacy(scene, source)
    for name, expected in original_owners.items():
        if name not in scene.tiles or expected - rows(scene.tiles[name]):
            raise ValueError(
                "Waterfront requires its exact original prepartitioned owner families"
            )
    supports = validate_rows(scene, source.supporting_ground)
    validate_rows(scene, source.ground_inputs)
    domain = from_wkt(source.ground_domain_wkt)
    ground_old: dict[str, Counter[Row]] = {}
    ground_new: dict[str, MeshTile] = {}
    for row in source.ground_inputs:
        ground_old.setdefault(row.tile, Counter())[row.material, row.payload] += (
            row.copies
        )
        fragments, _ = recolor(
            LegacyRow(row.tile, "Tile_Ground", row.material, row.payload, -1), domain
        )
        target = ground_new.setdefault(row.tile, MeshTile())
        for fragment in fragments:
            for _ in range(row.copies):
                append(target, fragment.material, fragment.payload)
    ground_counter = sum((rows(tile) for tile in ground_new.values()), Counter())
    if (
        ground_counter.total() != source.expected_ground_rows
        or digest(ground_counter) != source.ground_counter_sha256
    ):
        raise ValueError("Waterfront segmented Ground differs from reviewed source")
    candidate = copy(scene)
    candidate.tiles = {}
    candidate.landmarks = []
    candidate.modeled_buildings = set(scene.modeled_buildings)
    candidate.terrain_cutouts = list(scene.terrain_cutouts)
    build(candidate, source.geometry)
    geometry = sum((rows(tile) for tile in candidate.tiles.values()), Counter())
    if (
        geometry.total() != source.expected_geometry_rows
        or digest(geometry) != source.geometry_counter_sha256
    ):
        raise ValueError("Waterfront geometry differs from reviewed source")
    staged: dict[str, MeshTile] = {}
    preserved = 0
    for name in set(original_owners) | set(candidate.tiles):
        original = scene.tiles.get(name, MeshTile())
        result, kept = replacement(
            original,
            original_owners.get(name, Counter()),
            candidate.tiles.get(name, MeshTile()),
        )
        staged[name] = result
        preserved += kept
    for name, expected in ground_old.items():
        result, kept = replacement(scene.tiles[name], expected, ground_new[name])
        staged[name] = result
        preserved += kept
    # Validate the unchanged tree roots on the actual post-segmentation fragments.
    evaluated = copy(scene)
    evaluated.tiles = {**scene.tiles, **staged}
    validate_rows(evaluated, source.post_tree_ground)
    scene.tiles.update(staged)
    scene.modeled_buildings.update(front.osm_id for front in source.geometry.fronts)
    scene.landmarks.append(
        {
            "name": "Neftchilar89/91 and finite seaside park context",
            "source": "waterfront/reconstruction.json.gz",
            "scope": "Three photographed facade bands, distinct arch/hipped-dormer roofs, estimated heights±4m. "
            "Ground changes are original-plane cosmetic grass segmentation only. "
            "34 source-fit tree poses are visual estimates, not individually surveyed; current163/Khagani trees retained. "
            "World-planar masonry UV and new foliage appearance remain native/PBR trials; no acceptance claim.",
            "held": "Absolute datum, thresholds, rear details, LoveFerma/cafe heights and85/87 identities remain held.",
        }
    )
    return WaterfrontChange(
        sum(c.total() for c in original_owners.values()),
        geometry.total(),
        sum(c.total() for c in ground_old.values()),
        ground_counter.total(),
        supports,
        preserved,
        tuple(sorted(staged)),
    )
