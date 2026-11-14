"""as-built Sail candidate with separate recessed tower and low podium."""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.jeddah_context_dataclasses import LocalFrame, SailArchitecture
from venues.jeddah_context_shapes import (
    facade_bays,
    local,
    rectangle,
    skin,
    slab,
    walls,
)

XY = tuple[float, float]


def site_frame(config: SailArchitecture, geo: Callable[[float, float], XY]) -> tuple[LocalFrame, Polygon]:
    ring = [geo(lat, lon) for lon, lat in config.site.outer_wgs84]
    a, b = [ring[i] for i in config.axis_source_vertices]
    length = math.dist(a, b)
    axis = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    center = geo(config.center_wgs84[1], config.center_wgs84[0])
    return LocalFrame(center, axis, (-axis[1], axis[0])), Polygon(ring)


def fin(scene: MeshScene, a: Point, b: Point, height: float, tangent: XY) -> None:
    dx, dy = tangent[0] * .065, tangent[1] * .065
    left_a, left_b = (a[0] - dx, a[1] - dy, a[2]), (b[0] - dx, b[1] - dy, b[2])
    right_a, right_b = (a[0] + dx, a[1] + dy, a[2]), (b[0] + dx, b[1] + dy, b[2])
    def top(p: Point) -> Point:
        return p[0], p[1], p[2] + height
    scene.quad('Building_SailFins', 'White', left_a, left_b, top(left_b), top(left_a))
    scene.quad('Building_SailFins', 'White', right_b, right_a, top(right_a), top(right_b))
    scene.quad('Building_SailFins', 'White', right_a, left_a, top(left_a), top(right_a))
    scene.quad('Building_SailFins', 'White', left_b, right_b, top(right_b), top(left_b))
    scene.quad('Building_SailFins', 'White', top(left_a), top(left_b), top(right_b), top(right_a))
    scene.quad('Building_SailFins', 'White', right_a, right_b, left_b, left_a)
    depth = math.dist(a[:2], b[:2])
    x = a[0] + (a[0] - b[0]) / depth * .004
    y = a[1] + (a[1] - b[1]) / depth * .004
    dx, dy = tangent[0] * .0175, tangent[1] * .0175
    scene.quad('Building_SailFinLightStrips', 'WarmGlass', (x - dx, y - dy, a[2]),
               (x + dx, y + dy, a[2]), (x + dx, y + dy, a[2] + height),
               (x - dx, y - dy, a[2] + height))


def tower(scene: MeshScene, config: SailArchitecture, frame: LocalFrame) -> Polygon:
    shape = rectangle(frame, 0, 0, config.length_m, config.width_m)
    outer = list(orient(shape, sign=1.).exterior.coords)[:-1]
    pitch = (config.height_m - config.crown_height_m) / config.floors
    for floor in range(config.floors + 1):
        slab(scene, shape, config.base_relative_m + floor * pitch,
             config.floor_slab_thickness_m, 'Building_SailFloorSlabs')
    for floor in range(config.floors):
        low = config.base_relative_m + floor * pitch + .08
        high = config.base_relative_m + (floor + 1) * pitch - config.floor_slab_thickness_m
        fraction = floor / (config.floors - 1)
        depth = config.balcony_depth_m[0] + fraction * (config.balcony_depth_m[1] - config.balcony_depth_m[0])
        for face, (a, b) in enumerate(pairwise([*outer, outer[0]])):
            span = math.dist(a, b)
            tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
            nx, ny = ty, -tx
            count = max(2, round(span / config.bay_width_m))
            ia = a[0] - nx * depth + tx * depth, a[1] - ny * depth + ty * depth
            ib = b[0] - nx * depth - tx * depth, b[1] - ny * depth - ty * depth
            for bay in range(count):
                first, last = bay / count, (bay + 1) / count
                first_xy = ia[0] + (ib[0] - ia[0]) * first, ia[1] + (ib[1] - ia[1]) * first
                last_xy = ia[0] + (ib[0] - ia[0]) * last, ia[1] + (ib[1] - ia[1]) * last
                material = 'WarmGlass' if (floor * 17 + bay * 7 + face * 11) % 41 == 0 else 'Glass'
                scene.quad('Building_SailRecessedRooms', material, (*first_xy, low), (*last_xy, low),
                           (*last_xy, high), (*first_xy, high))
                width = .075
                scene.banner((*last_xy, low),
                             (last_xy[0] - tx * width, last_xy[1] - ty * width, low),
                             high - low, 'Steel', 'Building_SailWindowMullions')
                if bay % 2 == floor % 2:
                    shift = .18 * math.sin(floor * .17 + bay * .33)
                    along = min(span - .25, max(.25, (bay + .5 + shift) * span / count))
                    front = a[0] + tx * along, a[1] + ty * along, low
                    back = front[0] - nx * depth, front[1] - ny * depth, low
                    fin(scene, front, back, high - low, (tx, ty))
            rail_a = a[0] - nx * .025, a[1] - ny * .025, low + 1.05
            rail_b = b[0] - nx * .025, b[1] - ny * .025, low + 1.05
            scene.quad('Building_SailBalconyRails', 'Glass', (rail_a[0], rail_a[1], low + .1),
                       (rail_b[0], rail_b[1], low + .1), rail_b, rail_a)
            scene.beam('Building_SailRailCaps', 'Steel', rail_a, rail_b, .035, .035)
    for x, y in outer:
        scene.beam('Building_SailCornerFins', 'White', (x, y, config.foundation_bottom_relative_m),
                   (x, y, config.base_relative_m + config.height_m - config.crown_height_m), .16)
    crown = []
    for index, (x, y) in enumerate(outer):
        z = config.base_relative_m + config.height_m - (.7 if index in (0, 3) else 0)
        crown.append((x, y, z))
    roof = config.base_relative_m + config.height_m - config.crown_height_m
    for a, b in pairwise([*crown, crown[0]]):
        scene.quad('Building_SailModestCrown', 'Glass', (a[0], a[1], roof), (b[0], b[1], roof), b, a)
    scene.quad('Building_SailModestCrown', 'Steel', crown[0], crown[1], crown[2], crown[3], up=True)
    return shape


def podium_plans(config: SailArchitecture, frame: LocalFrame,
                  site: Polygon, tower_plan: Polygon) -> tuple[Polygon, Polygon]:
    north = rectangle(frame, 0, config.podium_north_offset_m + 100, 400, 200)
    main = site.intersection(north)
    if not isinstance(main, Polygon):
        raise TypeError('The mapped Sail podium must retain one northern body')
    main = main.buffer(-2.5, join_style='round').buffer(2.5, quad_segs=8)
    if not isinstance(main, Polygon):
        raise TypeError('Rounded podium corners must stay inside the original site')
    side = rectangle(frame, 70, config.podium_north_offset_m / 2, 100, config.podium_north_offset_m)
    ballroom = site.intersection(side).difference(tower_plan.buffer(.3))
    if not isinstance(ballroom, Polygon):
        raise TypeError('The separate ballroom must remain one bounded low wing')
    return main, ballroom


def low_podium(scene: MeshScene, config: SailArchitecture, frame: LocalFrame,
               site: Polygon, tower_plan: Polygon) -> tuple[Polygon, Polygon]:
    main, ballroom = podium_plans(config, frame, site, tower_plan)
    base = config.base_relative_m
    podium_top = base + config.podium_floors * config.podium_floor_pitch_m
    ballroom_top = base + config.ballroom_floors * config.ballroom_floor_pitch_m
    walls(scene, main, base, podium_top, 'Building_SailSevenStoreyPodium', 'Glass')
    walls(scene, main, config.foundation_bottom_relative_m, base + .08,
          'Building_SailPodiumFoundation', 'Concrete')
    facade_bays(scene, main, base, podium_top, config.podium_floor_pitch_m, 5.5, 'Building_SailPodiumSlabs')
    skin(scene, main, podium_top, 'Building_SailPodiumTerrace', 'Concrete')
    for a, b in pairwise(orient(main, sign=1.).exterior.coords):
        mid = (a[0] + b[0]) / 2 - frame.center[0], (a[1] + b[1]) / 2 - frame.center[1]
        if mid[0] * frame.normal[0] + mid[1] * frame.normal[1] > config.podium_north_offset_m + .1:
            continue
        span = math.dist(a, b)
        if span < 4:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        count = max(1, int(span / 5.5))
        for index in range(count):
            if index % 3:
                continue
            distance = span * (index + .5) / count
            x, y = a[0] + tx * distance + nx * .015, a[1] + ty * distance + ny * .015
            scene.banner((x - tx * 1.2, y - ty * 1.2, base + .3),
                         (x + tx * 1.2, y + ty * 1.2, base + .3), 2.8,
                         'WarmGlass', 'Building_SailLobbyGlazing')
    walls(scene, ballroom, base, ballroom_top, 'Building_SailThreeStoreyBallroom', 'Glass')
    walls(scene, ballroom, config.foundation_bottom_relative_m, base + .08,
          'Building_SailPodiumFoundation', 'Concrete')
    facade_bays(scene, ballroom, base, ballroom_top, config.ballroom_floor_pitch_m, 5.2, 'Building_SailBallroomFrames')
    skin(scene, ballroom, ballroom_top, 'Building_SailBallroomRoof', 'White')
    for a, b in pairwise(orient(ballroom, sign=1.).exterior.coords):
        span = math.dist(a, b)
        if span < 1:
            continue
        count = max(1, round(span / 1.1))
        for index in range(count):
            t = (index + .5) / count
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            scene.beam('Building_SailBallroomVerticalScreens', 'Trunk', (x, y, base + 1.2),
                       (x, y, ballroom_top - .45), .09, .18)
        if span > 10:
            scene.beam('Building_SailBallroomDiagonalFrame', 'Cream', (*a[:2], base + .4),
                       (*b[:2], ballroom_top - .4), .18, .18)
    pool = rectangle(frame, -12, 55, 23, 8).intersection(main.buffer(-2))
    if isinstance(pool, Polygon) and pool.area > 120:
        skin(scene, pool, podium_top + .05, 'Building_SailRoofPool', 'Water')
        for u in (-25., -17., -9., -1.):
            for v in (49., 61.):
                a = local(frame, u, v, podium_top)
                b = local(frame, u, v, podium_top + 3.2)
                scene.beam('Building_SailRoofTerraceFrame', 'Cream', a, b, .22, .22)
        for v in (49., 61.):
            scene.beam('Building_SailRoofTerraceFrame', 'Cream', local(frame, -25, v, podium_top + 3.2),
                       local(frame, -1, v, podium_top + 3.2), .22, .24)
    # The source entrance canopy occupies the courtyard gap between the low wings and tower.
    canopy = rectangle(frame, 0, config.width_m / 2 + 3, 15, 6)
    skin(scene, canopy, base + 6.4, 'Building_SailEntranceCanopy', 'Trunk')
    walls(scene, canopy, base + 6.0, base + 6.4, 'Building_SailEntranceCanopy', 'Black')
    return main, ballroom


def sail_complex(scene: MeshScene, config: SailArchitecture,
                 geo: Callable[[float, float], XY]) -> dict[str, float]:
    frame, site = site_frame(config, geo)
    tower_plan = rectangle(frame, 0, 0, config.length_m, config.width_m)
    if not site.buffer(config.podium_projection_limit_m).covers(tower_plan):
        raise ValueError('The estimated tower projection exceeds its declared podium-plan uncertainty')
    if abs(config.length_m * config.width_m - 79264 / 65) > 50:
        raise ValueError('The tower floorplate must remain consistent with the qualified tower GFA')
    walls(scene, tower_plan, config.foundation_bottom_relative_m,
          config.base_relative_m + .08, 'Building_SailTowerFoundation', 'Concrete')
    tower(scene, config, frame)
    main, ballroom = low_podium(scene, config, frame, site, tower_plan)
    return {'tower_height_m': config.height_m, 'tower_floors': float(config.floors),
            'tower_floorplate_m2': tower_plan.area, 'podium_site_m2': site.area,
            'seven_storey_podium_m2': main.area, 'three_storey_ballroom_m2': ballroom.area,
            'tower_outside_podium_m2': tower_plan.difference(site).area,
            'tower_axis_deg': math.degrees(math.atan2(frame.axis[1], frame.axis[0]))}
