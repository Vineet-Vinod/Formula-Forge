"""Fit the personnel strip outside the variable-width pit fast lane."""
from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, cross, mul, norm, sub
from circuit_portals_dataclasses import Barrier, Portal
from pit_routes_dataclasses import PitRoute, PitSection
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from venues.jeddah_pit_walkway_dataclasses import (
    WalkwayProof,
    WalkwayRecipe,
    WalkwayResult,
    WalkwayStation,
)
from venues.jeddah_pits import route_section

SOURCE = Path(__file__).resolve().parents[2] / 'Attribution/Sources/jeddah/pit-personnel-walkway.json'


def walkway_recipe() -> WalkwayRecipe:
    recipe = TypeAdapter(WalkwayRecipe).validate_json(SOURCE.read_bytes())
    if recipe.start_distance_m >= recipe.end_distance_m or recipe.rail_edge_gap_m <= recipe.lane_edge_gap_m:
        raise ValueError('Invalid Jeddah personnel walkway interval/rail position')
    return recipe


def section_at_distance(route: PitRoute, distance: float) -> PitSection:
    distances = [section.distance for section in route.sections]
    index = max(0, min(len(distances) - 2, bisect.bisect_right(distances, distance) - 1))
    a, b = route.sections[index:index + 2]
    t = (distance - a.distance) / (b.distance - a.distance)
    return route_section(route, a.track_station * (1 - t) + b.track_station * t)


def point(section: PitSection, lateral: float, lift: float) -> Point:
    return (section.x + section.normal_x * lateral, section.y + section.normal_y * lateral,
            section.z + section.cross_slope * lateral + lift)


def station(route: PitRoute, walls: Sequence[Barrier], recipe: WalkwayRecipe, distance: float) -> WalkwayStation:
    section = section_at_distance(route, distance)
    tx, ty = -section.normal_y, section.normal_x
    selected: tuple[float, Barrier] | None = None
    for wall in walls:
        dx, dy = wall.bx - wall.ax, wall.by - wall.ay
        size = math.hypot(dx, dy)
        if size < .01 or abs((dx * tx + dy * ty) / size) < .8:
            continue
        if not .6 <= wall.top - wall.bottom <= 1.5 or abs(wall.bottom - section.z) > .3:
            continue
        t = max(0.0, min(1.0, ((section.x - wall.ax) * dx + (section.y - wall.ay) * dy) / (size * size)))
        qx, qy = wall.ax + t * dx - section.x, wall.ay + t * dy - section.y
        lateral = qx * section.normal_x + qy * section.normal_y
        along = qx * tx + qy * ty
        if abs(along) > 3.2 or not 2.6 < lateral < 7:
            continue
        face = lateral - wall.radius
        if selected is None or face < selected[0]:
            selected = face, wall
    if selected is None:
        raise ValueError(f'No qualified existing pit divider at distance{distance:.3f}m')
    face, wall = selected
    outer = face - recipe.wall_gap_m
    inner = section.half_width + recipe.lane_edge_gap_m
    rail = section.half_width + recipe.rail_edge_gap_m
    if outer - inner < recipe.minimum_width_m:
        raise ValueError(f'Existing divider leaves insufficient personnel width at{distance:.3f}m')
    blend = max(0.0, min(1.0, (distance - recipe.start_distance_m) / recipe.end_ramp_m,
                         (recipe.end_distance_m - distance) / recipe.end_ramp_m))
    return WalkwayStation(section, face, wall.bottom, wall.top, outer,
                          recipe.platform_height_m * blend, inner, rail)


def tube(scene: MeshScene, a: Point, b: Point, radius: float) -> None:
    tangent = norm(sub(b, a))
    side = norm(cross(tangent, (0.0, 0.0, 1.0) if abs(tangent[2]) < .95 else (0.0, 1.0, 0.0)))
    up = cross(tangent, side)
    for index in range(8):
        first, last = math.tau * index / 8, math.tau * ((index + 1) % 8) / 8
        na = add(mul(side, math.cos(first)), mul(up, math.sin(first)))
        nb = add(mul(side, math.cos(last)), mul(up, math.sin(last)))
        pa, pb, qa, qb = add(a, mul(na, radius)), add(a, mul(nb, radius)), add(b, mul(na, radius)), add(b, mul(nb, radius))
        scene.triangle('Building_JeddahPersonnelRails', 'Steel', pa, pb, qb, normals=(na, nb, nb))
        scene.triangle('Building_JeddahPersonnelRails', 'Steel', pa, qb, qa, normals=(na, nb, na))
        scene.triangle('Building_JeddahPersonnelRails', 'Steel', a, pb, pa)
        scene.triangle('Building_JeddahPersonnelRails', 'Steel', b, qa, qb)


def platform(scene: MeshScene, first: WalkwayStation, last: WalkwayStation, recipe: WalkwayRecipe) -> Polygon:
    top = (point(first.section, first.inner_edge_m, first.lift_m),
           point(last.section, last.inner_edge_m, last.lift_m),
           point(last.section, last.outer_edge_m, last.lift_m),
           point(first.section, first.outer_edge_m, first.lift_m))
    bottom = (point(first.section, first.inner_edge_m, -.02),
              point(last.section, last.inner_edge_m, -.02),
              point(last.section, last.outer_edge_m, -.02),
              point(first.section, first.outer_edge_m, -.02))
    if cross(sub(top[1], top[0]), sub(top[2], top[0]))[2] < 0:
        top = top[3], top[2], top[1], top[0]
        bottom = bottom[3], bottom[2], bottom[1], bottom[0]
    scene.quad('Building_JeddahPersonnelPlatform', 'Concrete', *top, up=True)
    scene.quad('Building_JeddahPersonnelPlatform', 'Concrete', *bottom, up=False)
    for index in range(4):
        following = (index + 1) % 4
        scene.quad('Building_JeddahPersonnelPlatform', 'Concrete',
                   bottom[index], bottom[following], top[following], top[index])
    return Polygon([p[:2] for p in top])


def armco(scene: MeshScene, first: WalkwayStation, last: WalkwayStation) -> None:
    for height in (.25, .52, .79):
        # A shallow W-section retains the existing solid divider behind it.
        profile = ((-.115, -.015), (-.065, -.055), (0.0, -.025), (.065, -.055), (.115, -.015))
        for (z0, across0), (z1, across1) in pairwise(profile):
            a = point(first.section, first.wall_face_m + across0, first.wall_bottom_m + height + z0 - first.section.z)
            b = point(last.section, last.wall_face_m + across0, last.wall_bottom_m + height + z0 - last.section.z)
            c = point(last.section, last.wall_face_m + across1, last.wall_bottom_m + height + z1 - last.section.z)
            d = point(first.section, first.wall_face_m + across1, first.wall_bottom_m + height + z1 - first.section.z)
            scene.quad('Building_JeddahPersonnelArmco', 'Steel', a, b, c, d)
            scene.quad('Building_JeddahPersonnelArmco', 'Steel', b, a, d, c)


def build_walkway(scene: MeshScene, route: PitRoute, reference_walls: Sequence[Barrier],
                  recipe: WalkwayRecipe) -> WalkwayResult:
    if route.slug != 'jeddah' or recipe.end_distance_m >= route.sections[-1].distance:
        raise ValueError('Personnel walkway belongs only to the registered Jeddah pit')
    count = math.ceil((recipe.end_distance_m - recipe.start_distance_m) / recipe.segment_m)
    samples = [station(route, reference_walls, recipe, recipe.start_distance_m +
                       (recipe.end_distance_m - recipe.start_distance_m) * index / count)
               for index in range(count + 1)]
    lane = Polygon([point(sample.section, side * sample.section.half_width, 0)[:2]
                    for side, controls in ((1, samples), (-1, list(reversed(samples)))) for sample in controls])
    floors: list[Polygon] = []
    portals: list[Portal] = []
    barriers: list[Barrier] = []
    for index, (first, last) in enumerate(pairwise(samples)):
        footprint = platform(scene, first, last, recipe)
        if not footprint.is_valid:
            raise ValueError('Personnel floor became invalid')
        floors.append(footprint)
        corners = tuple((float(x), float(y)) for x, y in list(footprint.exterior.coords)[:-1])
        floor_values = [point(first.section, lateral, 0)[2] for lateral in (first.inner_edge_m, first.outer_edge_m)]
        floor_values.extend(point(last.section, lateral, 0)[2] for lateral in (last.inner_edge_m, last.outer_edge_m))
        portals.append(Portal(f'jeddah-personnel-floor-{index:03d}', corners, min(floor_values) - .5,
                              max(floor_values) + recipe.platform_height_m + .02,
                              'Cosmetic ground only below raised personnel strip; preserve Road, old divider and all nonfloor structures.'))
        for lift in (recipe.lower_rail_m, recipe.upper_rail_m):
            tube(scene, point(first.section, first.rail_center_m, first.lift_m + lift),
                 point(last.section, last.rail_center_m, last.lift_m + lift), recipe.rail_radius_m)
        a, b = point(first.section, first.rail_center_m, first.lift_m), point(last.section, last.rail_center_m, last.lift_m)
        barriers.append(Barrier(a[0], a[1], b[0], b[1], min(a[2], b[2]) - recipe.platform_height_m - .02,
                                max(a[2], b[2]) + recipe.upper_rail_m, recipe.rail_radius_m))
        armco(scene, first, last)
    posts = math.ceil((recipe.end_distance_m - recipe.start_distance_m) / recipe.post_spacing_m)
    for index in range(posts + 1):
        distance = recipe.start_distance_m + (recipe.end_distance_m - recipe.start_distance_m) * index / posts
        control = station(route, reference_walls, recipe, distance)
        a = point(control.section, control.rail_center_m, control.lift_m)
        tube(scene, a, point(control.section, control.rail_center_m, control.lift_m + recipe.upper_rail_m), recipe.rail_radius_m)
    floor_union = unary_union(floors)
    overlap = floor_union.intersection(lane).area
    # Only low, locally parallel divider rows belong to this strip's wall proof.
    relevant_walls = []
    for wall in reference_walls:
        line = LineString(((wall.ax, wall.ay), (wall.bx, wall.by)))
        if line.distance(floor_union) < .5 and .6 <= wall.top - wall.bottom <= 1.5:
            relevant_walls.append(line.buffer(wall.radius))
    wall_overlap = floor_union.intersection(unary_union(relevant_walls)).area if relevant_walls else 0.0
    if overlap > 1e-6 or wall_overlap > 1e-6:
        raise ValueError(f'Personnel strip overlaps protected lane/wall: {overlap:.9f}/{wall_overlap:.9f}m2')
    proof = WalkwayProof(recipe.start_distance_m, recipe.end_distance_m, floor_union.area,
                         min(sample.outer_edge_m - sample.inner_edge_m for sample in samples),
                         max(sample.outer_edge_m - sample.inner_edge_m for sample in samples), overlap,
                         wall_overlap, min(s.rail_center_m - recipe.rail_radius_m for s in samples),
                         len(reference_walls), len(barriers), len(portals), recipe.source_note)
    return WalkwayResult(tuple(barriers), tuple(portals), proof)
