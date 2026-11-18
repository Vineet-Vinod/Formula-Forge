"""Keep Jeddah fixture feet behind protection on every road and pit arm."""

from __future__ import annotations

import json
import math
from dataclasses import asdict

from circuit_dataclasses import Point, RoadStation
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

from venues.jeddah_furniture_dataclasses import FixtureFoot, FixtureSite
from venues.jeddah_pits import pit_route_source


def fixture_site(scene: CircuitScene) -> FixtureSite:
    from venues.jeddah_early_pit import load_recipe as entry_recipe

    route = pit_route_source()
    strips = []
    for a, b in zip(route.sections, route.sections[1:]):
        points = []
        for section, side in ((a, -1), (b, -1), (b, 1), (a, 1)):
            extent = ((section.positive_extent or section.half_width) if side > 0
                      else (section.negative_extent or section.half_width))
            points.append((section.x + side * section.normal_x * extent,
                           section.y + side * section.normal_y * extent))
        strips.append(Polygon(points))
    # The escape is paved but is not part of the main-road mask.
    escape = scene.sources / "escape-reconstruction.json"
    from circuit_escapes import build_overlay, load_recipe

    overlay = build_overlay(load_recipe(escape), scene.road, [],
                            scene.provenance.route.uniform_scale, occupied=[])
    strips.extend(Polygon([face.a[:2], face.b[:2], face.c[:2]]) for face in overlay.paving)
    entry = entry_recipe(route)
    strips.extend(Polygon([face.a[:2], face.b[:2], face.c[:2]]) for face in entry.separator_paint)
    paving = unary_union([scene.corridor_mask, scene.road_mask.buffer(.96),
                          unary_union(strips).buffer(.5)])
    forbidden = unary_union([
        paving.buffer(.6),
        *(Polygon(building.ring).buffer(.6) for building in scene.buildings),
        *(water.buffer(.6) for water in scene.water_shapes),
    ])
    return FixtureSite(paving, prep(forbidden))


def place_foot(scene: CircuitScene, site: FixtureSite, sample: RoadStation,
               side: int, preferred: Point) -> Point:
    candidates = []
    for outward in range(121):
        across = outward * .25
        for along in (0., -2., 2., -4., 4., -8., 8., -12., 12.):
            candidates.append((across * across + along * along, across, along))
    for _, across, along in sorted(candidates):
        x = preferred[0] + side * sample.ty * across + sample.tx * along
        y = preferred[1] - side * sample.tx * across + sample.ty * along
        point = ShapePoint(x, y)
        if site.forbidden.covers(point):
            continue
        placed = x, y, scene.ground(x, y)
        clearance = site.paving.distance(point)
        site.feet.append(FixtureFoot(sample.station, side, preferred, placed,
                                     math.dist(preferred[:2], placed[:2]), clearance))
        return placed
    raise ValueError(f"No protected Jeddah fixture foot near {sample.station:.2f}m")


def write_clearance(scene: CircuitScene, site: FixtureSite) -> None:
    (scene.scratch / "furniture-clearance.json").write_text(
        json.dumps({"foot_radius_m": .4, "required_paving_clearance_m": .6,
                    "coverage": "All race-road arms plus kerbs, full pit support, open entry wedge, escape, buildings and water.",
                    "feet": [asdict(foot) for foot in site.feet]}, indent=2) + "\n"
    )


def lamp_shaft(scene: CircuitScene, sample: RoadStation, side: int, base: Point) -> Point:
    for level in range(4):
        z0, z1 = level * 4., (level + 1) * 4.
        r0, r1 = .115 - level * .014, .115 - (level + 1) * .014
        for index in range(12):
            a, b = math.tau * index / 12, math.tau * (index + 1) / 12
            na, nb = (math.cos(a), math.sin(a), 0.), (math.cos(b), math.sin(b), 0.)
            pa, pb = add(add(base, (0., 0., z0)), mul(na, r0)), add(add(base, (0., 0., z0)), mul(nb, r0))
            qa, qb = add(add(base, (0., 0., z1)), mul(na, r1)), add(add(base, (0., 0., z1)), mul(nb, r1))
            scene.triangle("Building_JeddahLampShaft", "White", pa, pb, qb, normals=(na, nb, nb))
            scene.triangle("Building_JeddahLampShaft", "White", pa, qb, qa, normals=(na, nb, na))
    scene.box("Building_JeddahLampFoot", "Concrete", add(base, (0., 0., .10)), .56, .56, .20)
    scene.box("Building_JeddahLampFlange", "Steel", add(base, (0., 0., .22)), .38, .38, .035)
    for x in (-.145, .145):
        for y in (-.145, .145):
            scene.box("Building_JeddahLampBolts", "Steel", add(base, (x, y, .25)), .045, .045, .05)
    top = add(base, (0., 0., 16.))
    head = add(top, (-sample.ty * side * .7, sample.tx * side * .7, 0.))
    scene.beam("Building_JeddahLampNeck", "White", top, head, .10)
    arm_a = add(head, (-sample.tx * .67, -sample.ty * .67, 0.))
    arm_b = add(head, (sample.tx * .67, sample.ty * .67, 0.))
    scene.beam("Building_JeddahLampCrossarm", "Steel", arm_a, arm_b, .08)
    return head


def start_gantry(scene: CircuitScene, sample: RoadStation) -> None:
    from venues.jeddah_boundary import load_recipe

    # Mount the columns on the main-track divider, before the separate pit lane.
    gaps = ((-1, 1.05), (1, load_recipe().ordinary_wall_gap_m))
    feet = [sample.point(side * (sample.half_width + gap), .95) for side, gap in gaps]
    tops = [add(foot, (0, 0, 5.55)) for foot in feet]
    for foot, top in zip(feet, tops):
        scene.beam("Building_JeddahStartGantry", "Steel", foot, top, .22)
        scene.box("Building_JeddahGantryBasePlate", "Steel", foot, .28, .28, .04)
    scene.beam("Building_JeddahStartGantry", "Steel", tops[0], tops[1], .25)
    scene.banner(add(tops[0], (0, 0, -1.2)), add(tops[1], (0, 0, -1.2)),
                 1.2, "VenueSign", "Building_JeddahStartGantry")
