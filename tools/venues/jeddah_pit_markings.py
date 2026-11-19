"""Source-visible entry fork, single exit guide and short merge markings."""

from __future__ import annotations

import bisect
import hashlib
import math
from pathlib import Path

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from circuit_portals_dataclasses import Portal
from circuit_scene import CircuitScene
from pit_routes_dataclasses import PitRoute, PitSection
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.jeddah_pit_markings_dataclasses import PaintLine, PitMarkings
from venues.jeddah_pit_protection import sample, sections_hash

SOURCE = Path(__file__).resolve().parents[2] / 'Attribution/Sources/jeddah/pit-markings.json'


def load_recipe(route: PitRoute) -> PitMarkings:
    recipe = TypeAdapter(PitMarkings).validate_json(SOURCE.read_bytes())
    road = SOURCE.parents[3] / 'build/circuits/jeddah/road.csv'
    if sections_hash(route) != recipe.source_sections_sha256 or hashlib.sha256(road.read_bytes()).hexdigest() != recipe.source_road_sha256:
        raise ValueError('Pit paint requires the accepted Jeddah road and pit sections')
    for line in recipe.lines:
        if any(b[0] <= a[0] for a, b in zip(line.controls, line.controls[1:])):
            raise ValueError('Paint stations must increase')
        if bool(line.dash_m) != bool(line.gap_m):
            raise ValueError('Broken paint needs both dash and gap lengths')
        if line.frame == 'entry_fork' and (line.fork_blend_end_m is None or line.handoff_start_m is None):
            raise ValueError('The fork requires its island transition and ordinary-edge handoff')
    return recipe


def offset(line: PaintLine, distance: float) -> float:
    controls = line.controls
    positions = [p[0] for p in controls]
    index = max(0, min(len(controls) - 2, bisect.bisect_right(positions, distance) - 1))
    a, b = controls[index:index + 2]
    t = max(0., min(1., (distance - a[0]) / (b[0] - a[0])))
    t = t * t * (3 - 2 * t)
    return a[1] + (b[1] - a[1]) * t


def paint_point(road: CircuitScene, route: PitRoute, line: PaintLine, distance: float, across: float) -> Point:
    section = sample(route, distance)
    lateral = offset(line, distance) + across
    x, y = section.x + section.normal_x * lateral, section.y + section.normal_y * lateral
    fork_floor: float | None = None
    nearest, _ = road.nearest(x, y)
    lane = (x - nearest.x) * nearest.ty - (y - nearest.y) * nearest.tx
    if line.frame == 'entry_fork':
        assert line.fork_blend_end_m is not None and line.handoff_start_m is not None
        start, end = line.controls[0][0], line.fork_blend_end_m
        blend = max(0., min(1., (distance - start) / (end - start)))
        handoff = max(0., min(1., (distance - line.handoff_start_m) / (line.controls[-1][0] - line.handoff_start_m)))
        handoff = handoff * handoff * (3 - 2 * handoff)
        target = nearest.point(-nearest.half_width - .15 + .21 * handoff + across)
        inner_floor = section.z + section.cross_slope * lateral
        fork_floor = inner_floor + (target[2] - inner_floor) * blend
        x, y = x + (target[0] - x) * blend, y + (target[1] - y) * blend
    elif line.frame in ('exit_outer', 'exit_merge'):
        start = line.curve_start_m if line.curve_start_m is not None else line.controls[0][0]
        if distance >= start:
            x, y = merge_curve(road, route, line, distance, across, start)
    nearest, _ = road.nearest(x, y)
    lane = (x - nearest.x) * nearest.ty - (y - nearest.y) * nearest.tx
    pit_distance = abs(lateral)
    if line.frame == 'exit_merge' or (line.frame == 'exit_outer' and line.curve_start_m is not None and distance >= line.curve_start_m):
        section, pit_distance = closest_pit(route, x, y)
    pit_lane = (x - section.x) * section.normal_x + (y - section.y) * section.normal_y
    floor = section.z + section.cross_slope * pit_lane
    if abs(lane) <= nearest.half_width + .15:
        road_floor = nearest.height(lane) + .006
        floor = max(floor, road_floor) if pit_distance <= section.half_width else road_floor
    if fork_floor is not None:
        floor = fork_floor
    return x, y, floor + .014


def closest_pit(route: PitRoute, x: float, y: float) -> tuple[PitSection, float]:
    best, distance = 0., math.inf
    for a, b in zip(route.sections, route.sections[1:]):
        dx, dy = b.x - a.x, b.y - a.y
        t = max(0., min(1., ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy)))
        gap = (x - a.x - t * dx) ** 2 + (y - a.y - t * dy) ** 2
        if gap < distance:
            distance, best = gap, a.distance + t * (b.distance - a.distance)
    return sample(route, best), math.sqrt(distance)


def merge_curve(road: CircuitScene, route: PitRoute, line: PaintLine, distance: float,
                across: float, start: float) -> tuple[float, float]:
    section = sample(route, start)
    final = route.sections[-1]
    target, _ = road.nearest(final.x, final.y)
    side = -1 if line.frame == 'exit_outer' else 1
    a = section.x + section.normal_x * offset(line, start), section.y + section.normal_y * offset(line, start)
    b = a[0] - section.normal_y * 14., a[1] + section.normal_x * 14.
    d = target.point(side * (target.half_width - .06))[:2]
    c = d[0] - target.tx * 14., d[1] - target.ty * 14.
    t = max(0., min(1., (distance - start) / (line.controls[-1][0] - start)))
    x, y = (sum(weight * p[i] for weight, p in zip(((1 - t) ** 3, 3 * (1 - t) ** 2 * t,
            3 * (1 - t) * t * t, t ** 3), (a, b, c, d))) for i in range(2))
    dx, dy = (3 * (1 - t) ** 2 * (b[i] - a[i]) + 6 * (1 - t) * t * (c[i] - b[i])
              + 3 * t * t * (d[i] - c[i]) for i in range(2))
    length = math.hypot(dx, dy)
    return x + dy / length * across, y - dx / length * across


def strokes(line: PaintLine) -> list[tuple[float, float]]:
    first, last = line.controls[0][0], line.controls[-1][0]
    if not line.dash_m:
        return [(first, last)]
    count = math.ceil((last - first) / (line.dash_m + line.gap_m))
    return [(first + index * (line.dash_m + line.gap_m),
             min(last, first + index * (line.dash_m + line.gap_m) + line.dash_m))
            for index in range(count)]


def emit_markings(scene: MeshScene, route: PitRoute) -> None:
    recipe = load_recipe(route)
    road = CircuitScene('jeddah')
    for line in recipe.lines:
        for start, end in strokes(line):
            count = max(1, math.ceil((end - start) / .5))
            for index in range(count):
                a, b = start + (end - start) * index / count, start + (end - start) * (index + 1) / count
                points = [paint_point(road, route, line, d, side * line.width_m / 2)
                          for d, side in ((a, -1), (b, -1), (b, 1), (a, 1))]
                scene.quad('Tile_JeddahPitPaint', 'White', points[0], points[1], points[2], points[3], up=True)


def road_line_openings(route: PitRoute) -> list[Portal]:
    recipe = load_recipe(route)
    road = CircuitScene('jeddah')
    output = []
    for first, last in recipe.road_edge_replacements_m:
        count = math.ceil((last - first) / 2)
        for index in range(count):
            a, b = road.at(first + (last - first) * index / count), road.at(first + (last - first) * (index + 1) / count)
            points = [p.point(-p.half_width + .06 + side * .24)
                      for p, side in ((a, -1), (b, -1), (b, 1), (a, 1))]
            if not Polygon([p[:2] for p in points]).exterior.is_ccw:
                points.reverse()
            output.append(Portal(f'jeddah-pit-paint-{first:g}-{index:03d}',
                tuple(p[:2] for p in points), min(p[2] for p in points) - .004,
                max(p[2] for p in points) + .05,
                'White paint only at the entry fork or exit merge; retain every other native material and all physical data.'))
    return output
