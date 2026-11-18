"""Close Qatar pit-entry chicane, with source-qualified joins and a high gantry."""

from __future__ import annotations

import itertools
import math
from pathlib import Path

from circuit_mesh import MeshScene
from circuit_portals_dataclasses import Barrier, Portal
from pit_routes_dataclasses import PitRoute
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.jeddah_pit_approach_dataclasses import (
    ApproachChain,
    ApproachPoint,
    ApproachRecipe,
    ApproachWall,
)
from venues.jeddah_pit_protection import sample, sections_hash

SOURCE = Path(__file__).resolve().parents[2] / "Attribution/Sources/jeddah/pit-approach-corridor.json"


def load_recipe() -> ApproachRecipe:
    return TypeAdapter(ApproachRecipe).validate_json(SOURCE.read_bytes())


def smooth(value: float) -> float:
    t = max(0.0, min(1.0, value))
    return t * t * (3 - 2 * t)


def chain_point(route: PitRoute, recipe: ApproachRecipe, chain: ApproachChain, distance: float) -> ApproachPoint:
    section = sample(route, distance)
    lane = chain.side * recipe.axis_offset_m
    x, y = section.x + section.normal_x * lane, section.y + section.normal_y * lane
    for anchor, anchor_distance, blend in (
        (chain.start_xy_m, chain.start_m, 1 - smooth((distance - chain.start_m) / chain.start_transition_m)),
        (chain.end_xy_m, chain.end_m, smooth((distance - chain.end_m + chain.end_transition_m) / chain.end_transition_m)),
    ):
        if anchor is None:
            continue
        at = sample(route, anchor_distance)
        x += (anchor[0] - at.x - at.normal_x * lane) * blend
        y += (anchor[1] - at.y - at.normal_y * lane) * blend
    if distance == chain.start_m and chain.start_xy_m is not None:
        x, y = chain.start_xy_m
    if distance == chain.end_m and chain.end_xy_m is not None:
        x, y = chain.end_xy_m
    lateral = (x - section.x) * section.normal_x + (y - section.y) * section.normal_y
    return ApproachPoint(distance, (x, y, section.z + section.cross_slope * lateral))


def chain_knots(route: PitRoute, recipe: ApproachRecipe, chain: ApproachChain, dense: bool) -> list[float]:
    knots = {chain.start_m, chain.end_m}
    if not dense:
        knots.update(s.distance for s in route.sections if chain.start_m < s.distance < chain.end_m)
        knots.update((chain.start_m - 0.15, chain.end_m + 0.15))
    if chain.start_xy_m is not None:
        knots.add(chain.start_m + chain.start_transition_m)
    if chain.end_xy_m is not None:
        knots.add(chain.end_m - chain.end_transition_m)
    if dense:
        count = math.ceil((chain.end_m - chain.start_m) / recipe.segment_m)
        knots.update(chain.start_m + (chain.end_m - chain.start_m) * i / count for i in range(1, count))
    return sorted(knots)


def approach_walls(route: PitRoute, recipe: ApproachRecipe) -> list[ApproachWall]:
    if route.slug != "jeddah" or sections_hash(route) != recipe.source_sections_sha256:
        raise ValueError("Approach protection requires the unchanged 433-section Jeddah route")
    if any(w not in route.barriers for w in recipe.joins):
        raise ValueError("The retained approach wall joins changed")
    walls = []
    for chain in recipe.chains:
        knots = chain_knots(route, recipe, chain, True)
        refined = set(knots)
        for first, last in itertools.pairwise(knots):
            first_point = chain_point(route, recipe, chain, first).point
            last_point = chain_point(route, recipe, chain, last).point
            count = math.ceil(math.hypot(last_point[0] - first_point[0],
                                         last_point[1] - first_point[1]) / recipe.segment_m)
            refined.update(first + (last - first) * i / count for i in range(1, count))
        points = [chain_point(route, recipe, chain, d) for d in sorted(refined)]
        tops = []
        for point in points:
            top = point.point[2] + recipe.wall_height_m
            if chain.side > 0:
                start_floor = chain_point(route, recipe, chain, chain.start_m).point[2]
                end_floor = chain_point(route, recipe, chain, chain.end_m).point[2]
                top += (recipe.joins[0].top - start_floor - recipe.wall_height_m) * (
                    1 - smooth((point.distance_m - chain.start_m) / chain.start_transition_m))
                top += (recipe.joins[1].top - end_floor - recipe.wall_height_m) * smooth(
                    (point.distance_m - chain.end_m + chain.end_transition_m) / chain.end_transition_m)
            tops.append(top)
        for index, (a, b) in enumerate(itertools.pairwise(points)):
            z = (a.point[2] + b.point[2]) / 2
            top = (tops[index] + tops[index + 1]) / 2
            if chain.side > 0 and index == 0:
                top = recipe.joins[0].top
            if chain.side > 0 and index == len(points) - 2:
                top = recipe.joins[1].top
            walls.append(ApproachWall(chain.side, a.distance_m, b.distance_m,
                Barrier(a.point[0], a.point[1], b.point[0], b.point[1],
                        z - recipe.footing_embed_m, top, recipe.radius_m),
                a.point[2], b.point[2]))
    return walls


def entry_extra_barriers(route: PitRoute) -> list[Barrier]:
    return [w.barrier for w in approach_walls(route, load_recipe())]


def emit_approach_panels(scene: MeshScene, route: PitRoute) -> None:
    recipe = load_recipe()
    walls = approach_walls(route, recipe)
    total = sum(math.hypot(w.barrier.bx - w.barrier.ax, w.barrier.by - w.barrier.ay)
                for w in walls if w.side > 0)
    phase = {-1: 0.0, 1: 0.0}
    for record in walls:
        wall = record.barrier
        dx, dy = wall.bx - wall.ax, wall.by - wall.ay
        length = math.hypot(dx, dy)
        nx, ny = dy / length, -dx / length
        inward = -record.side * (wall.radius + 0.015)
        a = (wall.ax + nx * inward, wall.ay + ny * inward, wall.bottom + 0.08)
        b = (wall.bx + nx * inward, wall.by + ny * inward, wall.bottom + 0.08)
        u0 = phase[record.side] / recipe.panel_repeat_m
        if record.side > 0:
            a, b = b, a
            u0 = (total - phase[1] - length) / recipe.panel_repeat_m
        scene.banner(a, b, recipe.panel_height_m, recipe.panel_material, "Tile_Route",
                     u0, length / recipe.panel_repeat_m)
        phase[record.side] += length


def emit_approach_gantry(scene: MeshScene, route: PitRoute) -> None:
    recipe = load_recipe()
    gantry = recipe.gantry
    section = sample(route, gantry.distance_m)
    for side in (-1, 1):
        x = section.x + side * section.normal_x * gantry.post_offset_m
        y = section.y + side * section.normal_y * gantry.post_offset_m
        scene.beam("Tile_Route", "Steel", (x, y, section.z - recipe.footing_embed_m),
                   (x, y, section.z + gantry.clearance_m + gantry.height_m), 0.16)
    left = (section.x - section.normal_x * gantry.width_m / 2,
            section.y - section.normal_y * gantry.width_m / 2,
            section.z + gantry.clearance_m)
    right = (section.x + section.normal_x * gantry.width_m / 2,
             section.y + section.normal_y * gantry.width_m / 2,
             section.z + gantry.clearance_m)
    scene.banner(left, right, gantry.height_m, gantry.material, "Tile_Route")


def support_quads(route: PitRoute, recipe: ApproachRecipe) -> list[tuple[tuple[float, float, float], ...]]:
    output = []
    for chain in recipe.chains:
        points = [chain_point(route, recipe, chain, d) for d in chain_knots(route, recipe, chain, False)]
        for a, b in itertools.pairwise(points):
            vertices = []
            for node, outside in ((a, False), (b, False), (b, True), (a, True)):
                s = sample(route, node.distance_m)
                if outside:
                    x = node.point[0] + chain.side * s.normal_x * (recipe.radius_m + 0.10)
                    y = node.point[1] + chain.side * s.normal_y * (recipe.radius_m + 0.10)
                else:
                    x = s.x + chain.side * s.half_width * s.normal_x
                    y = s.y + chain.side * s.half_width * s.normal_y
                lateral = (x - s.x) * s.normal_x + (y - s.y) * s.normal_y
                vertices.append((x, y, s.z + s.cross_slope * lateral))
            shape = Polygon([p[:2] for p in vertices])
            if not shape.is_valid or shape.area < 1e-5:
                raise ValueError("The entry wall footing support must have a finite valid plan")
            output.append(tuple(vertices))
    return output


def emit_approach_paving(scene: MeshScene, route: PitRoute) -> None:
    recipe = load_recipe()
    for points in support_quads(route, recipe):
        for indices in ((0, 1, 2), (0, 2, 3)):
            a, b, c = (points[i] for i in indices)
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
                b, c = c, b
            scene.triangle("Tile_Route", "Runoff", a, b, c,
                           uv=tuple((p[0] / 4, p[1] / 4) for p in (a, b, c)))


def approach_floor_portals(route: PitRoute) -> list[Portal]:
    recipe = load_recipe()
    output = []
    for index, points in enumerate(support_quads(route, recipe)):
        ring = tuple(p[:2] for p in points)
        if not Polygon(ring).exterior.is_ccw:
            ring = ring[::-1]
        output.append(Portal(f"jeddah-approach-footing-{index:03d}", ring,
            min(p[2] for p in points) - 2, max(p[2] for p in points) + 2,
            "Visual-only cosmetic Ground clearance below the reconstructed entry approach. Preserve Road, kerb, barriers, glass and native physical support."))
    return output
