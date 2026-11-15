from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, mul, norm

from venues.baku_khagani_dataclasses import AtlasCrop, CanopyStyle, StreetTree
from venues.baku_sahil_dataclasses import CrownNormalField

# Two-pixel transparent padding around alpha>0 bounds in the accepted atlas.
CROPS = (
    AtlasCrop(2, 0, 30, 26, 227, 230),
    AtlasCrop(5, 0, 26, 37, 230, 219),
    AtlasCrop(2, 1, 52, 49, 204, 207),
    AtlasCrop(5, 1, 15, 16, 241, 241),
    AtlasCrop(5, 2, 57, 43, 199, 213),
)


DEFAULT_STYLE = CanopyStyle()
NORMAL_FIELD = CrownNormalField()


def crown_normal(
    pose: StreetTree,
    heading: float,
    point: Point,
    style: CanopyStyle = DEFAULT_STYLE,
    field: CrownNormalField = NORMAL_FIELD,
) -> Point:
    along = math.cos(heading), math.sin(heading)
    cross = -along[1], along[0]
    width = pose.crown_width_m * (
        style.park_width_multiplier if pose.parcel == "sahil" else 1
    )
    cross_scale = style.sidewalk_cross_scale if pose.parcel == "sidewalk" else 1.0
    x, y = point[0] - pose.base[0], point[1] - pose.base[1]
    u = (x * along[0] + y * along[1]) / (width / 2) ** 2
    v = (x * cross[0] + y * cross[1]) / (width * cross_scale / 2) ** 2
    z = (point[2] - pose.base[2] - pose.height_m * field.origin_height_fraction) / (
        pose.height_m * field.vertical_radius_fraction
    ) ** 2
    return norm((along[0] * u + cross[0] * v, along[1] * u + cross[1] * v, z))


def tree(
    scene: MeshScene,
    pose: StreetTree,
    heading: float,
    style: CanopyStyle = DEFAULT_STYLE,
    field: CrownNormalField = NORMAL_FIELD,
) -> None:
    base, height, seed = pose.base, pose.height_m, pose.seed
    along = math.cos(heading), math.sin(heading)
    normal = -along[1], along[0]
    cross_scale = style.sidewalk_cross_scale if pose.parcel == "sidewalk" else 1.0
    width = pose.crown_width_m * (
        style.park_width_multiplier if pose.parcel == "sahil" else 1
    )

    def offset(x: float, y: float, z: float) -> Point:
        return (
            along[0] * x + normal[0] * y * cross_scale,
            along[1] * x + normal[1] * y * cross_scale,
            z,
        )

    fork = add(base, (0, 0, height * style.trunk_fork_fraction))
    scene.beam("Building_KhaganiTrees", "Trunk", base, fork, 0.25)
    for cluster in range(7):
        azimuth = cluster * math.tau / 6 + seed * 0.13
        if cluster == 0:
            radius, fraction, card_width, card_height = (
                0.0,
                0.70,
                0.80 * width,
                0.60 * height,
            )
        elif cluster <= 4:
            radius, fraction, card_width, card_height = (
                0.22 * width,
                0.64 + 0.02 * (cluster % 2),
                0.62 * width,
                0.54 * height,
            )
        else:
            radius, fraction, card_width, card_height = (
                0.23 * width,
                0.54,
                0.56 * width,
                0.40 * height,
            )
        center = add(
            base,
            offset(
                math.cos(azimuth) * radius,
                math.sin(azimuth) * radius,
                height * fraction,
            ),
        )
        scene.beam("Building_KhaganiTrees", "Trunk", fork, center, 0.09)
        crop = CROPS[(seed + cluster) % len(CROPS)]
        u0, u1 = (
            (crop.column * 256 + crop.left_px) / 1536,
            (crop.column * 256 + crop.right_px) / 1536,
        )
        v0, v1 = (
            (crop.row * 256 + crop.top_px) / 1536,
            (crop.row * 256 + crop.bottom_px) / 1536,
        )
        # Occupied-alpha dimensions, rather than the atlas cell, set each mass.
        card_width *= (crop.right_px - crop.left_px) / (
            crop.right_px - crop.left_px - 5
        )
        card_height *= (crop.bottom_px - crop.top_px) / (
            crop.bottom_px - crop.top_px - 5
        )
        for plane in range(3):
            angle = plane * math.pi / 3 + azimuth
            axis = offset(math.cos(angle), math.sin(angle), 0)
            bottom = add(center, (0, 0, -card_height / 2))
            left, right = (
                add(bottom, mul(axis, -card_width / 2)),
                add(bottom, mul(axis, card_width / 2)),
            )
            upper_left, upper_right = (
                add(left, (0, 0, card_height)),
                add(right, (0, 0, card_height)),
            )
            scene.triangle(
                "Building_KhaganiTrees",
                "BakuSahilCanopy",
                upper_left,
                upper_right,
                right,
                ((u0, v0), (u1, v0), (u1, v1)),
                normals=tuple(
                    crown_normal(pose, heading, p, style, field)
                    for p in (upper_left, upper_right, right)
                ),
            )
            scene.triangle(
                "Building_KhaganiTrees",
                "BakuSahilCanopy",
                upper_left,
                right,
                left,
                ((u0, v0), (u1, v1), (u0, v1)),
                normals=tuple(
                    crown_normal(pose, heading, p, style, field)
                    for p in (upper_left, right, left)
                ),
            )
