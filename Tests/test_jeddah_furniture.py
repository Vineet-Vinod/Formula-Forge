"""Catch fixture feet on another track arm and on the separate pit fast lane."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_scene import CircuitScene
from venues.jeddah_furniture import fixture_site, place_foot, start_gantry
from venues.jeddah_pits import pit_route_source
from venues.night_lighting import pole_base


@pytest.fixture(scope="module")
def scene() -> CircuitScene:
    result = CircuitScene("jeddah")
    result.road_surfaces("Runoff")
    result.tiles.clear()
    return result


def test_real_infield_mast_and_pit_approach_pole_leave_all_paving(scene: CircuitScene) -> None:
    site = fixture_site(scene)
    for station, side, setback in ((650., -1, 38.), (5792., -1, .8)):
        sample = scene.at(station)
        original = pole_base(scene, sample, side, setback)
        assert site.paving.covers(ShapePoint(original[:2]))
        placed = place_foot(scene, site, sample, side, original)
        assert math.dist(original[:2], placed[:2]) > .5
        assert site.paving.intersection(ShapePoint(placed[:2]).buffer(.4)).is_empty


def test_gantry_columns_clear_both_race_road_and_pit_fast_lane(scene: CircuitScene) -> None:
    scene.tiles.clear()
    start_gantry(scene, scene.at(10))
    import struct

    route = pit_route_source()
    strips = []
    for a, b in zip(route.sections, route.sections[1:]):
        strips.append(Polygon([(s.x + side * s.normal_x * s.half_width,
                                s.y + side * s.normal_y * s.half_width)
                               for s, side in ((a, -1), (b, -1), (b, 1), (a, 1))]))
    driving = unary_union([scene.road_mask, *strips])
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            points = [struct.unpack_from("<8f", tile.triangles, offset + 4 + i * 32)[:3] for i in range(3)]
            if min(p[2] for p in points) > 400:
                continue
            shape = Polygon([(-p[1] / 100, -p[0] / 100) for p in points])
            assert shape.intersection(driving).area < 1e-8


def test_entry_wedge_excludes_previously_exposed_lamp_feet(scene: CircuitScene) -> None:
    from venues.jeddah_early_pit import load_recipe

    site = fixture_site(scene)
    paint = unary_union([Polygon([face.a[:2], face.b[:2], face.c[:2]])
                         for face in load_recipe(pit_route_source()).separator_paint])
    for station, old in ((5824., (99.89478070373538, -334.53184546994487)),
                         (5856., (92.5645701350911, -303.59779096400547))):
        assert paint.buffer(.4).covers(ShapePoint(old))
        sample = scene.at(station)
        preferred = pole_base(scene, sample, -1, .8)
        placed = place_foot(scene, site, sample, -1, preferred)
        assert paint.distance(ShapePoint(placed[:2])) >= .6


def test_pit_service_width_and_fixed_personnel_edge() -> None:
    route = pit_route_source()
    for section in route.sections:
        expected = 2.5 if 272 <= section.distance <= 581 else 2.
        if 247 < section.distance < 272 or 581 < section.distance < 601:
            assert 2 < section.half_width < 2.5
        else:
            assert section.half_width == expected
        assert section.positive_extent == section.half_width
        assert section.negative_extent >= section.half_width


def test_early_pit_wall_and_footings_preserve_every_racing_arm(scene: CircuitScene) -> None:
    from shapely.geometry import LineString
    from venues.jeddah_early_pit import load_recipe
    from venues.jeddah_pit_approach import approach_walls
    from venues.jeddah_pit_approach import load_recipe as approach_recipe

    early = load_recipe(pit_route_source())
    for record in early.walls:
        wall = record.barrier
        body = LineString([(wall.ax, wall.ay), (wall.bx, wall.by)]).buffer(wall.radius)
        assert body.distance(scene.road_mask) >= .49
    for face in early.floors:
        assert Polygon([p[:2] for p in (face.a, face.b, face.c)]).intersection(scene.road_mask).area < 1e-8
    for face in early.separator_paint:
        assert Polygon([p[:2] for p in (face.a, face.b, face.c)]).intersection(scene.road_mask).area < 1e-6
    following = next(w for w in approach_walls(pit_route_source(), approach_recipe()) if w.side < 0).barrier
    last = early.walls[-1].barrier
    assert (last.bx, last.by) == pytest.approx((following.ax, following.ay), abs=1e-9)
    for foot in (early.bridge.left, early.bridge.right):
        assert ShapePoint(foot[:2]).buffer(.16).intersection(scene.road_mask).is_empty


def test_early_pit_wall_follows_grade_without_steps() -> None:
    import struct

    from circuit_mesh import MeshScene
    from venues.jeddah_early_pit import emit_details, load_recipe

    recipe = load_recipe(pit_route_source())
    for first, last in zip(recipe.walls, recipe.walls[1:]):
        assert first.last_floor_m == last.first_floor_m
    geometry = MeshScene()
    emit_details(geometry, recipe)
    cap_points = set()
    for tile in geometry.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            material = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[material] != "Concrete":
                continue
            for vertex in range(3):
                x, y, z = struct.unpack_from("<8f", tile.triangles, offset + 4 + vertex * 32)[:3]
                cap_points.add((-y / 100, -x / 100, z / 100))
    assert any(abs(w.first_floor_m - w.last_floor_m) > .005 for w in recipe.walls)
    for record in recipe.walls:
        wall = record.barrier
        dx, dy = wall.bx - wall.ax, wall.by - wall.ay
        length = math.hypot(dx, dy)
        for x, y, floor in ((wall.ax, wall.ay, record.first_floor_m),
                            (wall.bx, wall.by, record.last_floor_m)):
            expected = (x + dy / length * wall.radius, y - dx / length * wall.radius, floor + .95)
            assert min(math.dist(expected, point) for point in cap_points) < .0001
        assert abs(record.first_floor_m + .95 - wall.top) < .03
        assert abs(record.last_floor_m + .95 - wall.top) < .03


def test_pit_entry_separator_is_open_before_qatar_nose(scene: CircuitScene) -> None:
    import csv

    from circuit_portals_dataclasses import Barrier
    from circuit_route_assets import clip_foreign_protection
    from pydantic import TypeAdapter
    from shapely.geometry import LineString
    from venues.jeddah_early_pit import load_recipe
    from venues.jeddah_pit_protection import sample

    route = pit_route_source()
    early = load_recipe(route)
    with (scene.scratch / "barriers.csv").open() as handle:
        walls = TypeAdapter(list[Barrier]).validate_python(list(csv.DictReader(handle)))
    walls = clip_foreign_protection([*walls, *route.barriers],
                                    [*route.portals, *early.separator_portals, *early.base_separator_portals])
    for distance, inner, outer in ((100., 2., 8.), (110., 2., 8.), (124., 2., 8.),
                                    (145., 5., 14.), (160., 5., 14.)):
        section = sample(route, distance)
        crossing = LineString([(section.x + section.normal_x * lane,
                                section.y + section.normal_y * lane) for lane in (inner, outer)])
        assert all(not crossing.intersects(LineString([(w.ax, w.ay), (w.bx, w.by)]).buffer(w.radius))
                   for w in walls)
