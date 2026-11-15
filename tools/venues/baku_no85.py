"""Replace the exact No5/old85 family, retaining current waterfront and park fields."""

from __future__ import annotations

import hashlib
from collections import Counter
from copy import copy
from pathlib import Path

from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.baku_foundation import Row, digest, replacement, rows
from venues.baku_no85_dataclasses import No85Change, No85Recipe
from venues.baku_no85_geometry import build
from venues.east_architecture import facade


def legacy(scene: CircuitScene, source: No85Recipe) -> tuple[str, Counter[Row]]:
    origin = scene.provenance.origin
    building = scene.footprint(source.osm_id)
    if (
        scene.slug != "baku"
        or abs(origin.latitude - source.origin_lat_lon[0]) > 1e-10
        or abs(origin.longitude - source.origin_lat_lon[1]) > 1e-10
        or abs(scene.provenance.route.uniform_scale - source.uniform_scale) > 1e-10
        or len(building.ring) != len(source.geometry.ring_xy_m)
        or max(
            abs(a - b)
            for p, q in zip(building.ring, source.geometry.ring_xy_m)
            for a, b in zip(p, q)
        )
        > 1e-8
        or any(k in building.tags for k in ("height", "building:levels"))
        or abs(building.height - source.expected_tag_height_m) > 1e-8
        or abs(
            min(scene.ground(x, y) for x, y in building.ring)
            - source.geometry.floor_relative_m
        )
        > 1e-8
    ):
        raise ValueError("No85 literal owner, inherited datum or source frame changed")
    if hashlib.sha256(scene.road_mask.wkb).hexdigest() != source.road_mask_sha256:
        raise ValueError("No85 protected road geometry changed")
    for name, expected in source.protected_inputs_sha256.items():
        if hashlib.sha256((scene.scratch / name).read_bytes()).hexdigest() != expected:
            raise ValueError("No85 protected road/protection input changed")
    candidate = copy(scene)
    candidate.tiles = {}
    candidate.landmarks = []
    candidate.modeled_buildings = set(scene.modeled_buildings)
    candidate.terrain_cutouts = list(scene.terrain_cutouts)
    facade(
        candidate, source.osm_id, source.expected_legacy_height_m, "classical", "Cream"
    )
    if len(candidate.tiles) != 1:
        raise ValueError("No85 old family escaped its qualified parent")
    parent, tile = next(iter(candidate.tiles.items()))
    counter = rows(tile)
    if (
        counter.total() != source.expected_legacy_rows
        or digest(counter) != source.legacy_counter_sha256
    ):
        raise ValueError("No85 old generic family differs from qualified source")
    return parent, counter


def validate_supports(scene: CircuitScene, source: No85Recipe) -> int:
    required: dict[str, Counter[Row]] = {}
    for support in source.ground_supports:
        required.setdefault(support.tile, Counter())[
            support.material, support.payload
        ] += support.copies
    for name, counter in required.items():
        if name not in scene.tiles:
            raise ValueError("No85 actual supporting Ground tile is missing")
        actual = rows(scene.tiles[name])
        if any(actual[key] != count for key, count in counter.items()):
            raise ValueError(
                "No85 actual supporting Ground changed; requalify contacts"
            )
    return sum(c.total() for c in required.values())


def finish(scene: CircuitScene, source_path: Path | None = None) -> No85Change:
    path = source_path or scene.sources / "no85/reconstruction.json"
    source = TypeAdapter(No85Recipe).validate_json(path.read_bytes())
    parent, old = legacy(scene, source)
    if parent not in scene.tiles or old - rows(scene.tiles[parent]):
        raise ValueError("No85 requires its exact original prepartitioned owner family")
    supporting = validate_supports(scene, source)
    candidate = copy(scene)
    candidate.tiles = {}
    candidate.landmarks = []
    candidate.modeled_buildings = set(scene.modeled_buildings)
    candidate.terrain_cutouts = list(scene.terrain_cutouts)
    build(candidate, source.geometry)
    if set(candidate.tiles) != {parent}:
        raise ValueError("No85 new family escaped its qualified parent")
    emitted = rows(candidate.tiles[parent])
    if (
        emitted.total() != source.expected_candidate_rows
        or digest(emitted) != source.candidate_counter_sha256
    ):
        raise ValueError("No85 geometry differs from independently reviewed source")
    result, kept = replacement(scene.tiles[parent], old, candidate.tiles[parent])
    scene.tiles[parent] = result
    scene.modeled_buildings.add(source.osm_id)
    scene.landmarks.append(
        {
            "osm_id": source.osm_id,
            "name": "Neftchilar old85/current5",
            "source": "no85/reconstruction.json",
            "structure": "Raised3bay double-heightcolonnade, lower3arched balconygroup, flanking loggias, projectingglazed oriels andsteppedwings",
            "cornice_estimate_m": source.geometry.cornice_m,
            "height_uncertainty_m": source.geometry.height_uncertainty_m,
            "scope": "Photographic architectural reconstruction;28m central/24m wing/20.4&16.5m return are estimates, notsurvey. "
            "Internalfloor pitches, groundshops, inheritedbase andunphotographedrears remainestimated. "
            "Literal concaveowner/courtyardretained; Ground/Road/protection/currentwaterfront andallneighbors unchanged. "
            "Native/PBRappearance acceptance pending.",
        }
    )
    return No85Change(old.total(), emitted.total(), kept, supporting, parent)
