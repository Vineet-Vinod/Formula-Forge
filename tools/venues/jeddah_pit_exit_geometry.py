"""Layered occupied service terraces beside Jeddah's open pit exit."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.jeddah_pit_exit_dataclasses import PitExitFrontage
from venues.jeddah_t22_frontage import build as build_t22
from venues.jeddah_t22_frontage import coordinate, faces_t22, front_mask
from venues.jeddah_t22_frontage_dataclasses import T22Frontage


def solid(
    scene: MeshScene, shape: Polygon, bottom: float, top: float, material: str, kind: str,
    t22: T22Frontage | None = None,
) -> None:
    shape = orient(shape)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        ring = list(orient(triangle).exterior.coords)[:3]
        for level, vertices in ((top, ring), (bottom, list(reversed(ring)))):
            points = [(x, y, level) for x, y in vertices]
            scene.triangle(
                kind, material, points[0], points[1], points[2],
                tuple((x / 4, y / 4) for x, y in vertices),
            )
    for a, b in pairwise(shape.exterior.coords):
        side_material = 'JeddahEditionCharcoal' if t22 and faces_t22(a, b, t22) else material
        scene.quad(
            kind, side_material, (a[0], a[1], bottom), (b[0], b[1], bottom),
            (b[0], b[1], top), (a[0], a[1], top),
        )


def build(
    scene: MeshScene, footprint: Polygon, base: float, source: PitExitFrontage,
    t22: T22Frontage | None = None,
) -> None:
    room = footprint.buffer(-source.room_setback_m, join_style="mitre")
    original_room = room
    rear_slab = footprint
    if t22 is not None:
        mask = front_mask(t22)
        room = room.difference(mask)
        rear_slab = footprint.difference(mask)
        if not isinstance(rear_slab, Polygon) or rear_slab.is_empty:
            raise ValueError('T22 stand cut lost the occupied pit-exit slab')
    guard = footprint.buffer(-0.22, join_style="mitre")
    if not isinstance(room, Polygon) or room.is_empty or not isinstance(guard, Polygon):
        raise ValueError("Pit-exit terraces require a connected occupied room body")
    room, original_room, guard = orient(room), orient(original_room), orient(guard)
    levels = (*source.floor_levels_m, source.roof_height_m)
    if levels[0] != 0 or any(b <= a for a, b in pairwise(levels)):
        raise ValueError("Pit-exit floor heights must ascend from the retained base")
    for index, (floor, ceiling) in enumerate(pairwise(levels)):
        solid(
            scene, rear_slab if t22 and index == 2 else footprint,
            base + floor - source.slab_thickness_m, base + floor,
            "JeddahEditionStone", "Building_JeddahExitTerraceSlabs",
        )
        solid(
            scene, room, base + floor, base + ceiling - source.slab_thickness_m,
            "JeddahEditionStone" if index == 0 else "JeddahEditionCharcoal",
            "Building_JeddahExitOccupiedRooms", t22,
        )
        # Keep the old bay phase on retained pit-exit/end faces after the north cut.
        for a, b in pairwise(original_room.exterior.coords):
            if t22 and faces_t22(a, b, t22):
                continue
            span = math.dist(a, b)
            if span < 0.35:
                continue
            tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
            nx, ny = ty, -tx
            count = max(1, round(span / source.bay_pitch_m))
            for bay in range(count):
                u0 = span * bay / count + 0.14
                u1 = span * (bay + 1) / count - 0.14
                low, high = base + floor + 0.55, base + ceiling - 0.85
                offset = source.glazing_setback_m
                left = a[0] + tx * u0 + nx * offset, a[1] + ty * u0 + ny * offset
                right = a[0] + tx * u1 + nx * offset, a[1] + ty * u1 + ny * offset
                if t22:
                    cut = t22.outer_coordinate_m - t22.stand_depth_m
                    va, vb = coordinate(*left, t22) - cut, coordinate(*right, t22) - cut
                    if min(va, vb) >= 0:
                        continue
                    if max(va, vb) > 0:
                        fraction = va / (va - vb)
                        join = (left[0] + fraction * (right[0] - left[0]),
                                left[1] + fraction * (right[1] - left[1]))
                        if va > 0:
                            left = join
                        else:
                            right = join
                scene.quad(
                    "Building_JeddahExitRecessedGlazing", "JeddahEditionRoomGlass",
                    (*left, low), (*right, low), (*right, high), (*left, high),
                )
                scene.beam(
                    "Building_JeddahExitFineMullions", "Steel",
                    (*left, low), (*left, high), 0.055,
                )
        if index == 0:
            continue
        for a, b in pairwise(guard.exterior.coords):
            if t22 and faces_t22(a, b, t22):
                continue
            span = math.dist(a, b)
            if span < 0.35:
                continue
            low = base + floor + 0.12
            high = base + floor + source.guard_height_m
            scene.quad(
                "Building_JeddahExitTerraceGuards", "JeddahEditionGuardGlass",
                (a[0], a[1], low), (b[0], b[1], low),
                (b[0], b[1], high), (a[0], a[1], high),
            )
            scene.beam(
                "Building_JeddahExitGuardRails", "Steel",
                (a[0], a[1], high), (b[0], b[1], high), 0.05,
            )
            count = max(1, math.ceil(span / source.bay_pitch_m))
            for post in range(count):
                t = post / count
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                scene.beam(
                    "Building_JeddahExitGuardPosts", "Steel", (x, y, low), (x, y, high), 0.045,
                )
    solid(
        scene, footprint, base + source.roof_height_m - source.slab_thickness_m,
        base + source.roof_height_m, "JeddahEditionStone", "Building_Roof",
    )
    if t22 is not None:
        build_t22(scene, footprint, base, source.roof_height_m, t22)
