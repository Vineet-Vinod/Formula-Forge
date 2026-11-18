"""Inset lobby doors and small service carts visible through the entry glazing."""

from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene

from venues.jeddah_pit_entry_dataclasses import PitEntryDetail


def wheel(scene: MeshScene, center: Point, axis: Point) -> None:
    across = -axis[1], axis[0], 0.0
    rings = []
    for side in (-1, 1):
        ring = []
        for index in range(12):
            angle = math.tau * index / 12
            ring.append((center[0] + axis[0] * side * .045 + across[0] * math.cos(angle) * .075,
                         center[1] + axis[1] * side * .045 + across[1] * math.cos(angle) * .075,
                         center[2] + math.sin(angle) * .075))
        rings.append(ring)
    for index in range(12):
        following = (index + 1) % 12
        scene.quad("Building_JeddahPitEntryCartWheels", "Black",
                   rings[0][following], rings[0][index], rings[1][index], rings[1][following])
        for side, ring in zip((-1, 1), rings, strict=True):
            cap = (center[0] + axis[0] * side * .045,
                   center[1] + axis[1] * side * .045, center[2])
            a, b = (ring[following], ring[index]) if side < 0 else (ring[index], ring[following])
            scene.triangle("Building_JeddahPitEntryCartWheels", "Black", cap, a, b)


def lobby_details(scene: CircuitScene, source: PitEntryDetail) -> None:
    for station in (source.wing_start_m + 13, source.wing_start_m + 36):
        sample = scene.at(station)
        front = -sample.half_width - 13
        heading = math.atan2(sample.ty, sample.tx)
        origin = sample.point(front - 2.5, .4)
        scene.box("Building_JeddahPitEntryServiceCarts", "Steel",
                  (origin[0], origin[1], sample.z + .23), 1.24, .65, .07, heading)
        scene.box("Building_JeddahPitEntryServiceCarts", "White",
                  (origin[0], origin[1], sample.z + .52), 1.12, .55, .46, heading)
        for along in (-.46, .46):
            for lane in (-.23, .23):
                x = origin[0] + sample.tx * along + sample.ty * lane
                y = origin[1] + sample.ty * along - sample.tx * lane
                wheel(scene, (x, y, sample.z + .1), (sample.ty, -sample.tx, 0))
        for lane in (-.26, .26):
            handle_low = sample.point(front - 2.5 + lane, .65)
            handle_high = sample.point(front - 2.5 + lane, 1.05)
            scene.beam("Building_JeddahPitEntryCartHandles", "Steel",
                       (handle_low[0] - sample.tx * .58, handle_low[1] - sample.ty * .58, handle_low[2]),
                       (handle_high[0] - sample.tx * .58, handle_high[1] - sample.ty * .58, handle_high[2]), .035)
        handle_a, handle_b = sample.point(front - 2.76, 1.05), sample.point(front - 2.24, 1.05)
        scene.beam("Building_JeddahPitEntryCartHandles", "Steel",
                   (handle_a[0] - sample.tx * .58, handle_a[1] - sample.ty * .58, handle_a[2]),
                   (handle_b[0] - sample.tx * .58, handle_b[1] - sample.ty * .58, handle_b[2]), .035)
    for station in (source.wing_start_m + 8, source.wing_start_m + 27, source.wing_start_m + 46):
        a, b = scene.at(station - .85), scene.at(station + .85)
        front_a, front_b = -a.half_width - 13, -b.half_width - 13
        low, high = .18, 3.35
        pa, pb = a.point(front_a - 5.6, low), b.point(front_b - 5.6, low)
        pc, pd = b.point(front_b - 5.6, high), a.point(front_a - 5.6, high)
        scene.quad("Building_JeddahPitEntryLobbyDoors", "JeddahEditionRoomGlass", pa, pb, pc, pd)
        for first, last in ((pa, pd), (pb, pc), (pd, pc)):
            scene.beam("Building_JeddahPitEntryLobbyDoorFrames", "Steel", first, last, .065)
        sample = scene.at(station)
        front = -sample.half_width - 13
        scene.beam("Building_JeddahPitEntryLobbyDoorFrames", "Steel",
                   sample.point(front - 5.58, low), sample.point(front - 5.58, high), .045)
        scene.box("Building_JeddahPitEntryServiceCounter", "White",
                  sample.point(front - 6.25, .7), 1.8, .6, 1.1, math.atan2(sample.ty, sample.tx))
