"""Replace only the mapped Mirbabayev generic family, retaining current neighbors."""

from __future__ import annotations

import struct
from collections import Counter
from copy import copy
from pathlib import Path

from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.baku_foundation import Row, digest, replacement, rows
from venues.baku_mirbabayev_dataclasses import PalaceChange, PalaceRecipe
from venues.baku_mirbabayev_geometry import build
from venues.east_architecture import facade


def legacy(scene: CircuitScene, source: PalaceRecipe) -> tuple[str, Counter[Row]]:
    building = scene.footprint(source.osm_id)
    provenance = scene.provenance
    if (
        scene.slug != "baku"
        or max(
            abs(provenance.origin.latitude - source.origin_lat_lon[0]),
            abs(provenance.origin.longitude - source.origin_lat_lon[1]),
            abs(provenance.route.uniform_scale - source.uniform_scale),
        )
        > 1e-10
        or len(building.ring) != len(source.geometry.ring_xy_m)
        or max(
            abs(a - b)
            for p, q in zip(building.ring, source.geometry.ring_xy_m)
            for a, b in zip(p, q)
        )
        > 1e-8
        or abs(building.height - source.expected_legacy_height_m) > 1e-8
        or abs(
            min(scene.ground(x, y) for x, y in building.ring)
            - source.geometry.floor_relative_m
        )
        > 1e-8
    ):
        raise ValueError(
            "Mirbabayev mapped owner, inherited datum or source frame changed"
        )
    replay = copy(scene)
    replay.tiles = {}
    replay.landmarks = []
    replay.terrain_cutouts = []
    replay.modeled_buildings = set()
    facade(replay, source.osm_id, source.expected_legacy_height_m, "classical", "Cream")
    if len(replay.tiles) != 1:
        raise ValueError("Mirbabayev generic family escaped its one qualified parent")
    parent, tile = next(iter(replay.tiles.items()))
    expected = rows(tile)
    if (
        expected.total() != source.expected_legacy_rows
        or digest(expected) != source.legacy_counter_sha256
    ):
        raise ValueError("Mirbabayev legacy family differs from its qualified source")
    return parent, expected


def validate_supports(scene: CircuitScene, source: PalaceRecipe) -> int:
    expected: dict[str, Counter[Row]] = {}
    for support in source.ground_supports:
        expected.setdefault(support.tile, Counter())[
            support.material, support.payload
        ] += support.copies
    for name, required in expected.items():
        if name not in scene.tiles:
            raise ValueError(f"Mirbabayev supporting Ground tile is missing: {name}")
        actual = rows(scene.tiles[name])
        if any(actual[key] != copies for key, copies in required.items()):
            raise ValueError(
                "Mirbabayev actual supporting Ground changed; requalify contacts"
            )
    return sum(counter.total() for counter in expected.values())


def project_stone_uvs(tile: MeshTile) -> int:
    changed = 0
    for offset in range(0, len(tile.triangles), 100):
        material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
        if material != "BakuStone":
            continue
        nx, ny, nz = struct.unpack_from("<3f", tile.triangles, offset + 16)
        for vertex in range(3):
            start = offset + 4 + vertex * 32
            wx, wy, wz = struct.unpack_from("<3f", tile.triangles, start)
            x, y, z = -wy / 400, -wx / 400, wz / 400
            u, v = ((x, y) if abs(nz) > .7 else
                    (y if abs(ny) > abs(nx) else x, -z))
            struct.pack_into("<2f", tile.triangles, start + 24, u, v)
        changed += 1
    return changed


def finish(scene: CircuitScene, source_path: Path | None = None) -> PalaceChange:
    path = source_path or scene.sources / "mirbabayev/reconstruction.json"
    source = TypeAdapter(PalaceRecipe).validate_json(path.read_bytes())
    parent, expected = legacy(scene, source)
    if parent not in scene.tiles or expected - rows(scene.tiles[parent]):
        raise ValueError(
            "Mirbabayev requires its exact original prepartitioned City family"
        )
    supports = validate_supports(scene, source)
    candidate = copy(scene)
    candidate.tiles = {}
    candidate.landmarks = []
    candidate.terrain_cutouts = []
    candidate.modeled_buildings = set()
    geometry = build(candidate, source.geometry)
    if set(candidate.tiles) != {parent}:
        raise ValueError("Mirbabayev candidate escaped its qualified City parent")
    emitted = rows(candidate.tiles[parent])
    if (
        emitted.total() != source.expected_candidate_rows
        or digest(emitted) != source.candidate_counter_sha256
        or geometry.rustication_max_curve_change_m > 0.00050001
    ):
        raise ValueError(
            "Mirbabayev geometry differs from its independently reviewed source"
        )
    project_stone_uvs(candidate.tiles[parent])
    result, kept = replacement(scene.tiles[parent], expected, candidate.tiles[parent])
    scene.tiles[parent] = result
    scene.modeled_buildings.add(source.osm_id)
    scene.landmarks.append(
        {
            "osm_id": source.osm_id,
            "name": "Seyid Mirbabayev former tenement / SOCAR Niyazi1",
            "structure": "Three photographed facade bands,17 upper/middle groups, distinct ground openings, slate roof and raised pavilions",
            "source": "mirbabayev/reconstruction.json",
            "cornice_estimate_m": source.geometry.cornice_m,
            "crown_estimate_m": source.geometry.pavilion_top_m,
            "height_uncertainty_m": source.geometry.height_uncertainty_m,
            "scope": "Photo/plan architectural estimates, not measured height or6tagged storeys. "
            "Inherited datum retained; thresholds/steps and rear details held. "
            "Occupied U courtyard open; Ground/Road/protection and all current neighbors retained. "
            "Native/cooked appearance requires independent review.",
        }
    )
    return PalaceChange(expected.total(), emitted.total(), kept, supports, parent)
