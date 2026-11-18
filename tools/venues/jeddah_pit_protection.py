"""Continuous source-reconstructed pit-exit walls, separate from racing protection."""

from __future__ import annotations

import bisect
import hashlib
import itertools
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

from circuit_mesh import MeshScene
from circuit_portals_dataclasses import Barrier, Portal
from pit_routes_dataclasses import PitRoute, PitSection
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from venues.jeddah_pit_protection_dataclasses import (
    ExitProtection,
    ExitProtectionRecipe,
    ExitWall,
)

ROOT = Path(__file__).resolve().parents[2]


def sections_hash(route: PitRoute) -> str:
    payload = json.dumps([asdict(s) for s in route.sections], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def load_recipe() -> ExitProtectionRecipe:
    return TypeAdapter(ExitProtectionRecipe).validate_json(
        (ROOT / "Attribution/Sources/jeddah/pit-exit-protection.json").read_bytes()
    )


def sample(route: PitRoute, distance: float) -> PitSection:
    positions = [s.distance for s in route.sections]
    i = max(0, min(len(positions) - 2, bisect.bisect_right(positions, distance) - 1))
    a, b = route.sections[i:i + 2]
    t = (distance - a.distance) / (b.distance - a.distance)
    nx = a.normal_x + t * (b.normal_x - a.normal_x)
    ny = a.normal_y + t * (b.normal_y - a.normal_y)
    length = math.hypot(nx, ny)
    if length < 0.99:
        raise ValueError("Pit-exit source normals cannot define a continuous divider")
    return replace(a, x=a.x + t * (b.x - a.x), y=a.y + t * (b.y - a.y),
                   z=a.z + t * (b.z - a.z), distance=distance,
                   half_width=a.half_width + t * (b.half_width - a.half_width),
                   normal_x=nx / length, normal_y=ny / length,
                   cross_slope=a.cross_slope + t * (b.cross_slope - a.cross_slope))


def new_walls(route: PitRoute, recipe: ExitProtectionRecipe) -> list[ExitWall]:
    if route.slug != "jeddah" or sections_hash(route) != recipe.source_sections_sha256:
        raise ValueError("Jeddah pit-exit source must match all 433 literal route sections")
    output = []
    for join in recipe.joins:
        start = recipe.cancellation_distance_m
        if join.side < 0:
            start += recipe.left_start_after_cancellation_m
        knots = sorted({start, join.distance_m, start + recipe.leading_transition_m,
                        *(s.distance for s in route.sections if start < s.distance < join.distance_m)})
        points = []
        initial = sample(route, recipe.cancellation_distance_m)
        right_delta = (recipe.right_start_xy_m[0] - initial.x - initial.normal_x * recipe.wall_axis_offset_m,
                       recipe.right_start_xy_m[1] - initial.y - initial.normal_y * recipe.wall_axis_offset_m)
        for distance in knots:
            s = sample(route, distance)
            lateral = join.side * recipe.wall_axis_offset_m
            x, y = s.x + s.normal_x * lateral, s.y + s.normal_y * lateral
            if join.side > 0:
                t = max(0.0, min(1.0, (distance - start) / recipe.leading_transition_m))
                blend = 1 - t * t * (3 - 2 * t)
                x, y = x + right_delta[0] * blend, y + right_delta[1] * blend
            if distance == join.distance_m:
                x, y = join.point_xy_m
            points.append((x, y, s.z + s.cross_slope * lateral))
        for index, (a, b) in enumerate(itertools.pairwise(points)):
            z = (a[2] + b[2]) / 2
            output.append(ExitWall(join.side, knots[index], knots[index + 1],
                Barrier(a[0], a[1], b[0], b[1], z - recipe.foundation_embed_m,
                        z + recipe.height_above_lane_m, recipe.wall_radius_m)))
    return output


def replacement(route: PitRoute, recipe: ExitProtectionRecipe) -> ExitProtection:
    walls = new_walls(route, recipe)
    points = [sample(route, recipe.cancellation_distance_m),
              *(s for s in route.sections if s.distance > recipe.cancellation_distance_m)]
    pieces = []
    for a, b in itertools.pairwise(points):
        shape = Polygon([(a.x - 6 * a.normal_x, a.y - 6 * a.normal_y),
                         (b.x - 6 * b.normal_x, b.y - 6 * b.normal_y),
                         (b.x + 6 * b.normal_x, b.y + 6 * b.normal_y),
                         (a.x + 6 * a.normal_x, a.y + 6 * a.normal_y)])
        if not shape.is_valid:
            raise ValueError("The finite pit-exit replacement strip must be valid")
        pieces.append(shape)
    domain = unary_union(pieces)
    retained = []
    replaced_count = 0
    for wall in route.barriers:
        line = LineString([(wall.ax, wall.ay), (wall.bx, wall.by)])
        if not line.intersects(domain):
            retained.append(wall)
            continue
        replaced_count += 1
        remainder = line.difference(domain)
        parts = [remainder] if isinstance(remainder, LineString) else list(remainder.geoms)
        for part in parts:
            if isinstance(part, LineString) and part.length > 1e-6:
                a, b = part.coords[0], part.coords[-1]
                retained.append(replace(wall, ax=a[0], ay=a[1], bx=b[0], by=b[1]))
    return ExitProtection(walls, retained, replaced_count)


def emit_panels(scene: MeshScene, route: PitRoute) -> None:
    recipe = load_recipe()
    expected = new_walls(route, recipe)
    actual = set(route.barriers)
    if any(record.barrier not in actual for record in expected):
        raise ValueError("The source-qualified pit-exit walls are missing from the route")
    phases = {-1: 0.0, 1: 0.0}
    for record in expected:
        wall = record.barrier
        length = math.hypot(wall.bx - wall.ax, wall.by - wall.ay)
        s = sample(route, (record.start_distance_m + record.end_distance_m) / 2)
        inward = -record.side * (wall.radius + 0.015)
        a = (wall.ax + s.normal_x * inward, wall.ay + s.normal_y * inward, wall.bottom + 0.08)
        b = (wall.bx + s.normal_x * inward, wall.by + s.normal_y * inward, wall.bottom + 0.08)
        phase = phases[record.side] / recipe.panel_repeat_m
        if record.side > 0:
            a, b = b, a
            phase = -(phases[record.side] + length) / recipe.panel_repeat_m
        scene.banner(a, b, recipe.panel_height_m, recipe.panel_material,
                     "Tile_Route", phase, length / recipe.panel_repeat_m)
        phases[record.side] += length


def support_quads(route: PitRoute) -> list[tuple[tuple[float, float, float], ...]]:
    recipe = load_recipe()
    output = []
    for record in new_walls(route, recipe):
        a, b = sample(route, record.start_distance_m), sample(route, record.end_distance_m)
        wall = record.barrier
        points = []
        for section, x, y in ((a, a.x + record.side * a.half_width * a.normal_x,
                              a.y + record.side * a.half_width * a.normal_y),
                             (b, b.x + record.side * b.half_width * b.normal_x,
                              b.y + record.side * b.half_width * b.normal_y),
                             (b, wall.bx + record.side * wall.radius * b.normal_x,
                              wall.by + record.side * wall.radius * b.normal_y),
                             (a, wall.ax + record.side * wall.radius * a.normal_x,
                              wall.ay + record.side * wall.radius * a.normal_y)):
            lateral = (x - section.x) * section.normal_x + (y - section.y) * section.normal_y
            points.append((x, y, section.z + section.cross_slope * lateral))
        polygon = Polygon([p[:2] for p in points])
        if not polygon.is_valid or polygon.area < 1e-5:
            raise ValueError("The narrow pit-exit footing support must be a valid surface")
        output.append(tuple(points))
    return output


def emit_exit_paving(scene: MeshScene, route: PitRoute) -> None:
    for points in support_quads(route):
        for indices in ((0, 1, 2), (0, 2, 3)):
            a, b, c = (points[i] for i in indices)
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
                b, c = c, b
            scene.triangle("Tile_Route", "Runoff", a, b, c,
                           uv=tuple((p[0] / 4, p[1] / 4) for p in (a, b, c)))


def exit_floor_portals(route: PitRoute) -> list[Portal]:
    output = []
    for index, points in enumerate(support_quads(route)):
        ring = tuple(p[:2] for p in points)
        if not Polygon(ring).exterior.is_ccw:
            ring = ring[::-1]
        output.append(Portal(f"jeddah-exit-footing-{index:03d}", ring,
            min(p[2] for p in points) - 2, max(p[2] for p in points) + 1,
            "Visual-only cosmetic Ground/Runoff clearance below the source-estimated narrow pit-exit footing. Preserve all barrier, fence, racing Road/kerb and native physical records."))
    return output
