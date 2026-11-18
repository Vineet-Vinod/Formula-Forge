"""Fence-mounted distance panels and limiter signs from the supplied Jeddah film."""

from __future__ import annotations

import math

from circuit_scene import CircuitScene
from pit_routes_dataclasses import PitRoute


def distance_boards(scene: CircuitScene, apex: float, side: int) -> None:
    for distance in (150, 100, 50):
        sample = scene.at(apex - distance)
        shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
        lane = side * (sample.half_width + scene.kerb_margin(sample.station) + shoulder - .04)
        scene.banner(sample.point(lane - .20, 1.85), sample.point(lane + .20, 1.85),
                     1.15, "JeddahDistance" + str(distance), "Tile_JeddahDistanceBoards")
        base, top = sample.point(lane, 1.05), sample.point(lane, 3.05)
        behind_base = (base[0] + sample.tx * .06, base[1] + sample.ty * .06, base[2])
        behind_top = (top[0] + sample.tx * .06, top[1] + sample.ty * .06, top[2])
        scene.beam("Tile_JeddahDistancePosts", "Steel", behind_base, behind_top, .045)
    scene.landmarks.append({"name": "Jeddah fence-mounted distance panels", "apex_m": apex,
                            "side": side, "reference": "jeddah.mp4:344,384,548,552s",
                            "dimensions": "Estimated .40 by 1.15m; upright stacked digits, bottom1.85m."})


def limiter_signs(scene: CircuitScene, route: PitRoute) -> None:
    for distance, material in ((route.limit_entry_m, "JeddahPitSpeed80"),
                               (route.limit_exit_m, "JeddahPitLimitEnd")):
        index = min(range(len(route.sections)), key=lambda i: abs(route.sections[i].distance - distance))
        section = route.sections[index]
        # Source-right pit normal: the signs are on the driver's left.
        lane = -section.half_width - .25
        center = (section.x + lane * section.normal_x, section.y + lane * section.normal_y,
                  section.z + lane * section.cross_slope)
        a = (center[0] - section.normal_x * .30, center[1] - section.normal_y * .30, center[2] + .08)
        b = (center[0] + section.normal_x * .30, center[1] + section.normal_y * .30, center[2] + .08)
        scene.banner(a, b, .80, material, "Tile_JeddahLimiterSigns")
        scene.beam("Tile_JeddahLimiterPosts", "Steel", center,
                   (center[0], center[1], center[2] + .08), .055)
    section = min(route.sections, key=lambda row: abs(row.distance - route.limit_exit_m))
    nx, ny = section.normal_x, section.normal_y
    tx, ty = -ny, nx
    lateral = section.half_width + .7
    x, y = section.x + nx * lateral, section.y + ny * lateral
    z = section.z + lateral * section.cross_slope
    scene.beam("Building_JeddahPitExitSignal", "Steel", (x, y, z), (x, y, z + 2.95), .10)
    scene.box("Building_JeddahPitExitSignal", "Black", (x, y, z + 2.96), .34, .30, 1.05,
              math.atan2(ty, tx))
    for index, material in enumerate(("JeddahPitSignalGreen", "JeddahPitSignalOff", "JeddahPitSignalOff")):
        center = (x - tx * .175, y - ty * .175, z + 2.65 + index * .31)
        for segment in range(24):
            first, last = math.tau * segment / 24, math.tau * (segment + 1) / 24
            a = (center[0] + nx * .105 * math.cos(first), center[1] + ny * .105 * math.cos(first),
                 center[2] + .105 * math.sin(first))
            b = (center[0] + nx * .105 * math.cos(last), center[1] + ny * .105 * math.cos(last),
                 center[2] + .105 * math.sin(last))
            scene.triangle("Building_JeddahPitExitSignal", material, center, a, b)
