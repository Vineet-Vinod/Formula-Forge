from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path
from typing import cast

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, mul, sub
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter

from venues.baku_ground import _weights
from venues.baku_ground_dataclasses import PackedPatchRow
from venues.baku_niyazi_dataclasses import TreePlantingSource, TreePose


def tree(scene: MeshScene, pose: TreePose, width_scale: float) -> None:
    base, height, seed = pose.base, pose.height_m, pose.seed
    fork = add(base, (0, 0, height * 0.52))
    scene.beam("Building_NiyaziTrees", "Trunk", base, fork, 0.25)
    for cluster in range(5):
        azimuth = cluster * math.tau / 5 + seed * 0.13
        center = add(
            base,
            (
                math.cos(azimuth) * height * 0.16 * width_scale,
                math.sin(azimuth) * height * 0.16 * width_scale,
                height * (0.68 + 0.04 * (cluster % 3)),
            ),
        )
        scene.beam("Building_NiyaziTrees", "Trunk", fork, center, 0.10)
        column, row = (2, 5)[(seed + cluster) % 2], (seed + cluster) % 3
        u0, u1 = (column + 0.012) / 6, (column + 0.988) / 6
        v0, v1 = (row + 0.012) / 6, (row + 0.988) / 6
        for plane in range(3):
            angle = plane * math.pi / 3 + azimuth
            axis = math.cos(angle), math.sin(angle), 0.0
            bottom = add(center, (0, 0, -height * 0.23))
            a, b = (
                sub(bottom, mul(axis, height * 0.25 * width_scale)),
                add(bottom, mul(axis, height * 0.25 * width_scale)),
            )
            ta, tb = add(a, (0, 0, height * 0.5)), add(b, (0, 0, height * 0.5))
            scene.triangle(
                "Building_NiyaziTrees",
                "TreeCanopy",
                ta,
                tb,
                b,
                ((u0, v0), (u1, v0), (u1, v1)),
            )
            scene.triangle(
                "Building_NiyaziTrees",
                "TreeCanopy",
                ta,
                b,
                a,
                ((u0, v0), (u1, v1), (u0, v1)),
            )


def _packed_point(point: Point) -> Point:
    y, x, z = struct.unpack(
        "<3f", struct.pack("<3f", -point[1] * 100, -point[0] * 100, point[2] * 100)
    )
    return -x / 100, -y / 100, z / 100


def validate_ground(
    scene: MeshScene,
    supports: list[PackedPatchRow],
    poses: list[TreePose],
    minimum_embed_m: float,
) -> float:
    expected = {(row.tile, row.material, row.payload) for row in supports}
    found = set()
    for name in {row.tile for row in supports}:
        tile = scene.tiles.get(name)
        if tile is None:
            raise ValueError(f"Baku tree supporting Ground tile is missing: {name}")
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            key = name, material, bytes(tile.triangles[offset + 4 : offset + 100])
            if key in expected:
                found.add(key)
    if found != expected:
        raise ValueError(
            "Baku tree supporting Ground changed; requalify the literal roots"
        )
    triangles = []
    for row in supports:
        raw = struct.unpack("<24f", row.payload)
        triangles.append(
            cast(
                tuple[Point, Point, Point],
                tuple(
                    (-raw[k + 1] / 100, -raw[k] / 100, raw[k + 2] / 100)
                    for k in (0, 8, 16)
                ),
            )
        )
    minimum = math.inf
    for pose in poses:
        for dx, dy in (
            (-0.125, -0.125),
            (-0.125, 0.125),
            (0.125, -0.125),
            (0.125, 0.125),
        ):
            x, y, z = _packed_point(
                (pose.base[0] + dx, pose.base[1] + dy, pose.base[2])
            )
            levels = []
            for points in triangles:
                weights = _weights(points, x, y)
                if min(weights) >= -1e-8 and max(weights) <= 1 + 1e-8:
                    levels.append(
                        sum(weight * p[2] for weight, p in zip(weights, points))
                    )
            if not levels:
                raise ValueError(
                    "Baku tree native root has no actual supporting Ground"
                )
            embed = max(levels) - z
            if embed < minimum_embed_m:
                raise ValueError(
                    "Baku tree native root no longer embeds into actual Ground"
                )
            minimum = min(minimum, embed)
    return minimum


def planting(scene: CircuitScene, source_path: Path) -> None:
    source = TypeAdapter(TreePlantingSource).validate_json(source_path.read_bytes())
    for path, expected in source.protected_source_sha256.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Baku tree protected source changed: {path}")
    validate_ground(
        scene, source.ground_supports, source.poses, source.minimum_native_root_embed_m
    )
    for pose in source.poses:
        tree(scene, pose, source.source.crown_width_scale)
    scene.vegetation.append(
        {
            "type": "Niyazi right-side broadleaf row",
            "count": len(source.poses),
            "start_m": source.source.start_m,
            "end_m": source.source.end_m,
            "source_note": source.source.source_note,
        }
    )
