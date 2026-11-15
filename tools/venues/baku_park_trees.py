from __future__ import annotations

import struct
from dataclasses import replace

from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene, add

from venues.baku_khagani_canopy import tree as broad_tree
from venues.baku_khagani_dataclasses import StreetTree
from venues.baku_waterfront import append
from venues.baku_waterfront_dataclasses import ParkTree
from venues.baku_waterfront_geometry import evergreen


def emit(scene: MeshScene, pose: ParkTree, foreground: bool = False) -> None:
    if pose.form != "evergreen":
        broad_tree(
            scene,
            StreetTree(
                pose.base,
                pose.height_m,
                pose.crown_width_m,
                pose.seed,
                "sahil",
                "Bounded source-fit seafront tree",
            ),
            0.0,
        )
        return
    if not foreground:
        evergreen(scene, pose)
        return
    # The photographed curb-row conifers have a clear lower trunk over paving.
    crown_height = (pose.height_m - 3.2) / 0.905
    lift = 3.2 - 0.1 * crown_height
    canopy = replace(pose, base=add(pose.base, (0, 0, lift)), height_m=crown_height)
    leaves = MeshScene()
    evergreen(leaves, canopy)
    scene.beam(
        "Building_NeftchilarContext",
        "Trunk",
        pose.base,
        add(pose.base, (0, 0, pose.height_m * 0.82)),
        0.27,
    )
    for parent, tile in leaves.tiles.items():
        target = scene.tiles.setdefault(parent, MeshTile())
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            if material == "BakuSahilCanopy":
                append(
                    target, material, bytes(tile.triangles[offset + 4 : offset + 100])
                )
