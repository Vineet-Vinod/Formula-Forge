"""Atomic finite promenade, office datum and source-fit park planting repair."""

from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter
from copy import copy
from pathlib import Path

from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.baku_foundation import digest, replacement, rows
from venues.baku_ground import finish_terrain
from venues.baku_ground_dataclasses import GroundPatchSource
from venues.baku_park_dataclasses import ParkChange, ParkRecipe
from venues.baku_park_trees import emit as emit_tree
from venues.baku_waterfront import validate_rows
from venues.baku_waterfront_dataclasses import ParkTree
from venues.east_architecture import facade


def emit(
    scene: MeshScene, trees: tuple[ParkTree, ...], foreground: tuple[int, ...] = ()
) -> None:
    selected = set(foreground)
    for pose in trees:
        emit_tree(scene, pose, pose.seed in selected)


def office_family(
    scene: CircuitScene, source: ParkRecipe
) -> tuple[MeshScene, MeshScene]:
    building = scene.footprint(source.office.osm_id)
    if (
        building.tags.get("building:levels") != "2"
        or abs(building.height - source.office.height_m) > 1e-10
        or abs(
            min(scene.ground(x, y) for x, y in building.ring) - source.office.old_base_m
        )
        > 1e-8
    ):
        raise ValueError("Baku park office source envelope or inherited datum changed")
    original = copy(scene)
    original.tiles = {}
    original.landmarks = []
    original.modeled_buildings = set(scene.modeled_buildings)
    original.terrain_cutouts = list(scene.terrain_cutouts)
    facade(original, source.office.osm_id, source.office.height_m, "classical", "Cream")
    original_counter = sum((rows(t) for t in original.tiles.values()), Counter())
    if (
        original_counter.total() != source.office.rows
        or digest(original_counter) != source.office.old_counter_sha256
    ):
        raise ValueError(
            "Baku park office differs from the qualified original owner family"
        )
    translated = MeshScene()
    delta = (source.office.new_base_m - source.office.old_base_m) * 100
    for name, tile in original.tiles.items():
        data = bytearray(tile.triangles)
        for offset in range(0, len(data), 100):
            for vertex in range(3):
                position = offset + 4 + vertex * 32 + 8
                z = struct.unpack_from("<f", data, position)[0]
                struct.pack_into("<f", data, position, z + delta)
        translated.tiles[name] = MeshTile(
            data,
            tile.minimum[:2] + [tile.minimum[2] + delta],
            tile.maximum[:2] + [tile.maximum[2] + delta],
            tile.materials.copy(),
        )
    translated_counter = sum((rows(t) for t in translated.tiles.values()), Counter())
    if (
        translated_counter.total() != source.office.rows
        or digest(translated_counter) != source.office.new_counter_sha256
    ):
        raise ValueError("Baku park office translation differs from reviewed geometry")
    return original, translated


def finish(scene: CircuitScene, source_path: Path | None = None) -> ParkChange:
    path = source_path or scene.sources / "park-context/reconstruction.json.gz"
    source = TypeAdapter(ParkRecipe).validate_json(gzip.decompress(path.read_bytes()))
    provenance = scene.provenance
    if (
        scene.slug != "baku"
        or max(
            abs(provenance.origin.latitude - source.origin_lat_lon[0]),
            abs(provenance.origin.longitude - source.origin_lat_lon[1]),
            abs(provenance.route.uniform_scale - source.uniform_scale),
        )
        > 1e-10
    ):
        raise ValueError("Baku park source frame changed")
    patch_path = path.parent / source.ground_delta_path
    raw = patch_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.ground_delta_sha256:
        raise ValueError("Baku park ground reconstruction differs from reviewed source")
    patch = TypeAdapter(GroundPatchSource).validate_json(gzip.decompress(raw))
    old = MeshScene()
    emit(old, source.original_trees)
    new = MeshScene()
    emit(new, source.trees, source.foreground_seed_ids)
    old_counter = sum((rows(t) for t in old.tiles.values()), Counter())
    new_counter = sum((rows(t) for t in new.tiles.values()), Counter())
    if (
        old_counter.total() != source.original_tree_rows
        or digest(old_counter) != source.original_tree_counter_sha256
    ):
        raise ValueError("Baku original34 park tree family changed")
    if (
        new_counter.total() != source.tree_rows
        or digest(new_counter) != source.tree_counter_sha256
    ):
        raise ValueError("Baku park tree geometry differs from reviewed source")
    old_office, new_office = office_family(scene, source)
    # Every Ground and City replacement is qualified before publishing changes.
    staged = copy(scene)
    staged.tiles = dict(scene.tiles)
    finish_terrain(staged, patch_path)
    supports = validate_rows(staged, source.supporting_ground)
    preserved = 0
    for family, candidate in ((old_office, new_office), (old, new)):
        for parent in family.tiles.keys() | candidate.tiles.keys():
            original = staged.tiles.get(parent, MeshTile())
            result, kept = replacement(
                original,
                rows(family.tiles.get(parent, MeshTile())),
                candidate.tiles.get(parent, MeshTile()),
            )
            staged.tiles[parent] = result
            preserved += kept
    affected = (
        {r.tile for r in patch.removals + patch.additions}
        | old.tiles.keys()
        | new.tiles.keys()
        | old_office.tiles.keys()
    )
    scene.tiles.update({name: staged.tiles[name] for name in affected})
    scene.landmarks.append(
        {
            "name": "Finite seafront promenade and woodland",
            "source": "park-context/reconstruction.json.gz",
            "scope": source.source_note,
            "held": "Absolute ground±2m, exact individual tree inventory/steps/rear grades and native appearance remain estimated or pending; first3999junction is separate.",
        }
    )
    return ParkChange(
        sum(r.copies for r in patch.removals),
        sum(r.copies for r in patch.additions),
        old_counter.total(),
        new_counter.total(),
        source.office.rows,
        supports,
        preserved,
        tuple(sorted(affected)),
    )
