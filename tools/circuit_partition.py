"""Partition city meshes without changing triangles or their residency bounds."""

from __future__ import annotations

import hashlib
import math
import struct
from collections import Counter
from dataclasses import replace
from pathlib import Path

from circuit_partition_dataclasses import (
    CityPartitionProof,
    CityPartitionRecipe,
    PartitionParent,
    SceneManifest,
    SceneTile,
)
from pydantic import TypeAdapter

MAGIC = b"FFLVM1\0\0"
HEADER_SIZE = 12
TRIANGLE_SIZE = 100


def mesh_rows(path: Path, expected: SceneTile) -> bytes:
    payload = path.read_bytes()
    if payload[:8] != MAGIC or len(payload) < HEADER_SIZE:
        raise ValueError(f"Invalid native city mesh: {path.name}")
    count = struct.unpack_from("<I", payload, 8)[0]
    if count != expected.triangles or len(payload) != HEADER_SIZE + count * TRIANGLE_SIZE:
        raise ValueError(f"City mesh triangle count differs: {path.name}")
    if hashlib.sha256(payload).hexdigest() != expected.sha256:
        raise ValueError(f"City mesh source hash differs: {path.name}")
    return payload[HEADER_SIZE:]


def partition_parent(directory: Path, parent: SceneTile, cell_m: float) -> tuple[list[SceneTile], PartitionParent]:
    rows = mesh_rows(directory / parent.file, parent)
    cells: dict[tuple[int, int], bytearray] = {}
    cell_cm = cell_m * 100
    for offset in range(0, len(rows), TRIANGLE_SIZE):
        a = struct.unpack_from("<2f", rows, offset + 4)
        b = struct.unpack_from("<2f", rows, offset + 36)
        c = struct.unpack_from("<2f", rows, offset + 68)
        key = (math.floor((a[0] + b[0] + c[0]) / (3 * cell_cm)),
               math.floor((a[1] + b[1] + c[1]) / (3 * cell_cm)))
        cells.setdefault(key, bytearray()).extend(rows[offset:offset + TRIANGLE_SIZE])
    if len(cells) == 1:
        return [parent], PartitionParent(parent.name, parent.sha256, parent.triangles, [parent.name], True)

    children = []
    remaining = Counter(rows[i:i + TRIANGLE_SIZE] for i in range(0, len(rows), TRIANGLE_SIZE))
    for (x, y), triangles in sorted(cells.items()):
        suffix = f"{x}_{y}".replace("-", "m")
        name = parent.name + "_Cell_" + suffix
        count = len(triangles) // TRIANGLE_SIZE
        payload = MAGIC + struct.pack("<I", count) + triangles
        path = directory / (name + ".mesh")
        path.write_bytes(payload)
        child = replace(parent, name=name, file=path.name, triangles=count,
                        sha256=hashlib.sha256(payload).hexdigest(), source_parent=parent.name)
        # Independently reopen output, including duplicates and encoded material indices.
        written = mesh_rows(path, child)
        for i in range(0, len(written), TRIANGLE_SIZE):
            row = written[i:i + TRIANGLE_SIZE]
            if remaining[row] <= 0:
                raise ValueError(f"City partition introduced a triangle: {name}")
            remaining[row] -= 1
            if remaining[row] == 0:
                del remaining[row]
        children.append(child)
    if remaining or sum(child.triangles for child in children) != parent.triangles:
        raise ValueError(f"City partition lost triangles: {parent.name}")
    return children, PartitionParent(parent.name, parent.sha256, parent.triangles,
                                     [child.name for child in children], True)


def partition_city(directory: Path, recipe: CityPartitionRecipe) -> int:
    path = directory / "manifest.json"
    original = path.read_bytes()
    adapter = TypeAdapter(SceneManifest)
    manifest = adapter.validate_json(original)
    if manifest.city_partition is not None:
        raise ValueError("Regenerate the original scene before partitioning city tiles")
    tiles = []
    parents = []
    superseded = []
    for tile in manifest.tiles:
        if not tile.name.startswith("Building_City_"):
            tiles.append(tile)
            continue
        children, proof = partition_parent(directory, tile, recipe.cell_m)
        tiles.extend(children)
        parents.append(proof)
        if len(children) > 1:
            superseded.append(tile.name)
    partition_proof = CityPartitionProof(recipe.cell_m, hashlib.sha256(original).hexdigest(), parents, superseded)
    updated = replace(manifest, tiles=tiles, city_partition=partition_proof)
    temporary = path.with_suffix(".json.partitioning")
    temporary.write_bytes(adapter.dump_json(updated, indent=2, exclude_none=True) + b"\n")
    temporary.replace(path)
    return len(tiles)
