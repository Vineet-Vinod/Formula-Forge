from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, mul

from venues.baku_khagani_dataclasses import StreetTree


def tree(scene: MeshScene, pose: StreetTree, heading: float) -> None:
    base, height, seed = pose.base, pose.height_m, pose.seed
    along = math.cos(heading), math.sin(heading)
    normal = -along[1], along[0]
    width_scale = pose.crown_width_m / (height * 0.82)
    cross_scale = 0.62 if pose.parcel == "sidewalk" else 1.0

    def offset(x: float, y: float, z: float) -> Point:
        return (
            along[0] * x + normal[0] * y * cross_scale,
            along[1] * x + normal[1] * y * cross_scale,
            z,
        )

    fork = add(base, (0, 0, height * 0.52))
    scene.beam("Building_KhaganiTrees", "Trunk", base, fork, 0.25)
    for cluster in range(5):
        azimuth = cluster * math.tau / 5 + seed * 0.13
        centre = add(
            base,
            offset(
                math.cos(azimuth) * height * 0.16 * width_scale,
                math.sin(azimuth) * height * 0.16 * width_scale,
                height * (0.68 + 0.04 * (cluster % 3)),
            ),
        )
        scene.beam("Building_KhaganiTrees", "Trunk", fork, centre, 0.10)
        column, row = (2, 5)[(seed + cluster) % 2], (seed + cluster) % 3
        u0, u1 = (column + 0.012) / 6, (column + 0.988) / 6
        v0, v1 = (row + 0.012) / 6, (row + 0.988) / 6
        for plane in range(3):
            angle = plane * math.pi / 3 + azimuth
            axis = offset(math.cos(angle), math.sin(angle), 0)
            bottom = add(centre, (0, 0, -height * 0.23))
            left, right = (
                add(bottom, mul(axis, -height * 0.25 * width_scale)),
                add(bottom, mul(axis, height * 0.25 * width_scale)),
            )
            upper_left, upper_right = (
                add(left, (0, 0, height * 0.5)),
                add(right, (0, 0, height * 0.5)),
            )
            scene.triangle(
                "Building_KhaganiTrees",
                "TreeCanopy",
                upper_left,
                upper_right,
                right,
                ((u0, v0), (u1, v0), (u1, v1)),
            )
            scene.triangle(
                "Building_KhaganiTrees",
                "TreeCanopy",
                upper_left,
                right,
                left,
                ((u0, v0), (u1, v1), (u0, v1)),
            )
