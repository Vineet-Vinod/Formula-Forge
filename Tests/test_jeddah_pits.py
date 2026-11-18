"""The working apron must join the route plane and keep cars clear of equipment."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from venues.jeddah_facilities import pit_compound
from venues.jeddah_pits import (
    apron_floor_point,
    apron_point,
    pit_route_source,
    route_section,
    working_lane_source,
)


class PitScene(CircuitScene):
    def __init__(self) -> None:
        super().__init__("jeddah")
        self.faces: list[tuple[str, str, tuple[Point, Point, Point]]] = []

    def triangle(self, kind: str, material: str, a: Point, b: Point, c: Point,
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                 normals: tuple[Point, ...] | None = None) -> None:
        self.faces.append((kind, material, (a, b, c)))


@pytest.fixture(scope="module")
def pits() -> PitScene:
    scene = PitScene()
    road, grid = list(scene.road), scene.grid
    pit_compound(scene)
    assert scene.road == road and scene.grid == grid
    return scene


def test_apron_has_exact_route_edge_and_uses_route_plane(pits: PitScene) -> None:
    route, source = pit_route_source(), working_lane_source()
    for station in range(6010, 6288, 7):
        sample = pits.at(station)
        section = route_section(route, station, sample.point(-sample.half_width - source.garage_front_offset_m))
        front = apron_point(sample, section, source, 0)
        edge = apron_point(sample, section, source, 1)
        assert edge == pytest.approx((section.x - section.normal_x * section.half_width,
                                     section.y - section.normal_y * section.half_width,
                                     section.z - section.cross_slope * section.half_width), abs=1e-12)
        lateral = (front[0] - section.x) * section.normal_x + (front[1] - section.y) * section.normal_y
        assert lateral < -7
        assert front[2] == pytest.approx(section.z + section.cross_slope * lateral, abs=1e-12)
        assert 5 < math.dist(front[:2], edge[:2]) < 8
    assert any(kind == "Tile_JeddahWorkingStrip" for kind, _, _ in pits.faces)
    assert sum(kind == "Tile_JeddahStopGuides" for kind, _, _ in pits.faces) == 40
    assert not any(kind == "Building_JeddahPitGarages" for kind, _, _ in pits.faces)


def test_parallel_stop_car_clears_garages_and_equipment(pits: PitScene) -> None:
    route, source = pit_route_source(), working_lane_source()
    obstacles = [(kind, face) for kind, _, face in pits.faces if kind.startswith("Building_")]
    for garage in source.stop_garage_centres:
        index = garage - 1
        station = source.start_m + 1.25 + index * source.bay_spacing_m + (source.service_gap_m if index >= 21 else 0)
        sample = pits.at(station)
        center = apron_floor_point(pits, route, source, station, source.stop_center_from_garage_m)
        body = Polygon([(center[0] + sample.tx * along + sample.ty * across,
                         center[1] + sample.ty * along - sample.tx * across)
                        for along, across in ((-2.46, -1.12), (2.46, -1.12), (2.46, 1.12), (-2.46, 1.12))])
        hits: list[str] = []
        for kind, face in obstacles:
            if max(p[2] for p in face) < center[2] + .08 or min(p[2] for p in face) > center[2] + 1.2:
                continue
            footprint = Polygon([p[:2] for p in face])
            shape = footprint if footprint.area > 1e-10 else LineString([p[:2] for p in face])
            if shape.intersects(body):
                hits.append(kind)
        assert not hits, (station, hits)
        assert body.area == pytest.approx(4.92 * 2.24)


def test_exit_variant_closes_retained_body_and_leaves_whole_fastlane_open() -> None:
    from venues.jeddah_pit_exit import exit_tip_mask, pit_exit_building, source_record

    scene = PitScene()
    scene.road_mask = Polygon()
    buildings, road = list(scene.buildings), list(scene.road)
    source = source_record()
    original = Polygon(scene.footprint(source.osm_id).ring)
    retained = original.difference(exit_tip_mask(source))
    assert isinstance(retained, Polygon)
    assert .75 < retained.area / original.area < .99
    pit_exit_building(scene)
    assert scene.buildings == buildings and scene.road == road
    route = pit_route_source()
    selected = [section for section in route.sections if 649 < section.distance < 716]
    corridor = Polygon([(section.x + section.normal_x * side * 2.2,
                         section.y + section.normal_y * side * 2.2)
                        for side, samples in ((-1, selected), (1, list(reversed(selected))))
                        for section in samples])
    roofs = []
    for kind, material, face in scene.faces:
        footprint = Polygon([point[:2] for point in face])
        shape = footprint if footprint.area > 1e-10 else LineString([point[:2] for point in face])
        assert not shape.intersects(corridor), (kind, material)
        if kind == "Building_Roof":
            roofs.append(footprint)
    assert roofs
    assert unary_union(roofs).area == pytest.approx(retained.area, abs=1e-6)
