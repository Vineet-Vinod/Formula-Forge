"""Source-fitted Khagani fronts and Sahil planting; existing terrain stays intact."""

from __future__ import annotations

import gzip
import hashlib
import math
import struct
from collections import Counter

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter

from venues.baku_ground import _weights
from venues.baku_khagani_canopy import tree
from venues.baku_khagani_dataclasses import (
    KhaganiGroundSource,
    KhaganiSource,
    StreetTree,
)
from venues.baku_khagani_fronts import composers, house23, writers
from venues.baku_khagani_legacy import append_rows, retained_rows
from venues.baku_khagani_library import library_front

OWNERS = {177428532, 286020256}


def load_source(
    scene: CircuitScene,
) -> tuple[KhaganiSource, tuple[StreetTree, ...], KhaganiGroundSource]:
    folder = scene.sources / "khagani"
    recipe = gzip.decompress((folder / "recipe.json.gz").read_bytes())
    canopy = gzip.decompress((folder / "canopy.json.gz").read_bytes())
    guard = TypeAdapter(KhaganiGroundSource).validate_json(
        gzip.decompress((folder / "ground-supports.json.gz").read_bytes())
    )
    if (
        hashlib.sha256(recipe).hexdigest() != guard.recipe_sha256
        or hashlib.sha256(canopy).hexdigest() != guard.canopy_sha256
    ):
        raise ValueError("Baku Khagani source changed; requalify the frozen model")
    for relative, expected in guard.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Baku Khagani protected source changed: {relative}")
    if (
        hashlib.sha256((scene.scratch / "barriers.csv").read_bytes()).hexdigest()
        != guard.barriers_csv_sha256
    ):
        raise ValueError("Baku Khagani protection changed; requalify the literal trees")
    source = TypeAdapter(KhaganiSource).validate_json(recipe)
    poses = TypeAdapter(tuple[StreetTree, ...]).validate_json(canopy)
    if {family.osm_id for family in guard.legacy_families} != OWNERS:
        raise ValueError("Baku Khagani must retain exactly the two registered owners")
    for family in guard.legacy_families:
        building = scene.footprint(family.osm_id)
        if tuple(building.ring) != family.ring:
            raise ValueError("Baku Khagani literal footprint/source frame changed")
        if min(scene.ground(*point) for point in building.ring) != family.datum_m:
            raise ValueError("Baku Khagani inherited source datum changed")
    return source, poses, guard


def validate_ground(scene: MeshScene, guard: KhaganiGroundSource) -> None:
    expected = Counter(
        {
            (row.tile, row.material, row.payload): row.copies
            for row in guard.ground_supports
        }
    )
    found: Counter[tuple[str, str, bytes]] = Counter()
    for name in {row.tile for row in guard.ground_supports}:
        tile = scene.tiles.get(name)
        if tile is None:
            raise ValueError(f"Baku Khagani supporting Ground tile is missing: {name}")
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            key = name, material, bytes(tile.triangles[offset + 4 : offset + 100])
            if key in expected:
                found[key] += 1
    if found != expected:
        raise ValueError("Baku Khagani actual supporting Ground changed")


def validate_roots(poses: tuple[StreetTree, ...], guard: KhaganiGroundSource) -> None:
    triangles: list[tuple[Point, Point, Point]] = []
    for row in guard.ground_supports:
        values = struct.unpack("<24f", row.payload)
        triangles.append(
            (
                (-values[1] / 100, -values[0] / 100, values[2] / 100),
                (-values[9] / 100, -values[8] / 100, values[10] / 100),
                (-values[17] / 100, -values[16] / 100, values[18] / 100),
            )
        )
    for pose in poses:
        for dx, dy in (
            (-0.125, -0.125),
            (-0.125, 0.125),
            (0.125, -0.125),
            (0.125, 0.125),
        ):
            native_y, native_x, native_z = struct.unpack(
                "<3f",
                struct.pack(
                    "<3f",
                    -(pose.base[1] + dy) * 100,
                    -(pose.base[0] + dx) * 100,
                    pose.base[2] * 100,
                ),
            )
            x, y, z = -native_x / 100, -native_y / 100, native_z / 100
            levels = []
            for points in triangles:
                weights = _weights(points, x, y)
                if min(weights) >= -1e-8 and max(weights) <= 1 + 1e-8:
                    levels.append(sum(w * p[2] for w, p in zip(weights, points)))
            if not levels or max(levels) - z < guard.minimum_native_root_embed_m:
                raise ValueError(
                    "Baku Khagani native tree root lacks its qualified Ground"
                )


def prepare(scene: CircuitScene) -> None:
    load_source(scene)
    if OWNERS & scene.modeled_buildings:
        raise ValueError("Baku Khagani owners were already emitted")
    scene.modeled_buildings.update(OWNERS)


def finish(scene: CircuitScene) -> None:
    source, poses, guard = load_source(scene)
    if not OWNERS <= scene.modeled_buildings:
        raise ValueError(
            "Baku Khagani owners must be reserved before terrain generation"
        )
    validate_ground(scene, guard)
    validate_roots(poses, guard)
    retained = retained_rows(scene, source, guard.legacy_families)
    append_rows(scene, retained)
    library_front(scene, source.library)
    for front in source.historic_fronts:
        if front.address == 27:
            composers(scene, front)
        elif front.address == 25:
            writers(scene, front)
        else:
            house23(scene, front)
    heading = math.atan2(
        source.library.front.face.tangent[1], source.library.front.face.tangent[0]
    )
    for pose in poses:
        tree(scene, pose, heading)
    scene.landmarks.append(
        {
            "name": "Khagani Library and three registered heritage frontages",
            "source": "khagani/reconstruction.json; photographed frontage rhythms, broad height/depth estimates; unregistered Library pavilion, returns and rear faces held",
        }
    )
    scene.vegetation.append(
        {
            "type": "Sahil fringe and Library sidewalk broadleaf",
            "count": len(poses),
            "source_note": "Finite photo-fit estimates in mapped park/sidewalk context; actual Ground witnesses and retained protection; no individual OSM tree claims.",
        }
    )
