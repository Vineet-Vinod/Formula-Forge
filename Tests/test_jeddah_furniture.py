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
