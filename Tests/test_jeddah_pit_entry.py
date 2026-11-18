"""The hospitality entry adds occupied glazing outside the unchanged pit route."""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from shapely.geometry import LineString, Polygon
from venues.jeddah_pit_entry import (
    build_entry,
    entry_lights,
    source_record,
    wing_footprint,
)
from venues.jeddah_pits import pit_route_source


def test_lobby_has_no_glass_edge_partitions_and_lights_aim_inside_its_back_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = CircuitScene("jeddah")
    source = source_record()
    sample = scene.at(source.station_m)
    partitions: list[Point] = []

    def capture(
        kind: str, material: str, a: Point, b: Point, c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if kind == "Building_JeddahPitEntryWingRoomPartitions":
            partitions.extend((a, b, c))

    monkeypatch.setattr(scene, "triangle", capture)
    build_entry(scene, sample, -sample.half_width - 13, -sample.half_width - 39)
    assert partitions
    for x, y, z in partitions:
        road, _distance = scene.nearest(x, y)
        lane = (x - road.x) * road.ty - (y - road.y) * road.tx
        depth = -road.half_width - 13 - lane
        assert depth >= 1.54
        assert z > sample.z + source.floor_height_m
    assert 3.5 <= source.lobby_back_depth_m <= 4
    for light in entry_lights(scene):
        assert light.target is not None
        x, y, _z = light.target
        road, _distance = scene.nearest(x, y)
        lane = (x - road.x) * road.ty - (y - road.y) * road.tx
        depth = -road.half_width - 13 - lane
        assert source.glazing_depth_m < depth < source.lobby_back_depth_m


def test_upper_room_back_is_visible_above_the_first_projecting_floor() -> None:
    scene = CircuitScene("jeddah")
    source = source_record()
    sample = scene.at(5963.42724609375)
    camera_lane = -12.784985710592832
    camera_lift = 1.261999877382633
    front = -sample.half_width - 13
    target_lift = source.floor_height_m * 1.5
    crossings = []
    for depth in (source.upper_back_depth_m, source.wing_depth_m - .12):
        target_lane = front - depth
        ratio = (front - camera_lane) / (target_lane - camera_lane)
        crossings.append(camera_lift + ratio * (target_lift - camera_lift))
    assert crossings[0] > source.floor_height_m + .3
    assert crossings[1] < source.floor_height_m


def test_entry_hospitality_has_depth_and_keeps_physical_route_and_workshops_fixed() -> None:
    scene = CircuitScene("jeddah")
    source = source_record()
    sample = scene.at(source.station_m)
    before = list(scene.road), scene.grid, list(scene.buildings)
    front, rear = -sample.half_width - 13, -sample.half_width - 39
    footprint = wing_footprint(scene, source)
    pit = pit_route_source()
    fastlane = LineString([(section.x, section.y) for section in pit.sections]).buffer(2)
    assert footprint.distance(fastlane) > 2
    assert 450 < footprint.area < 490
    build_entry(scene, sample, front, rear)
    assert before == (scene.road, scene.grid, scene.buildings)
    assert scene.terrain_cutouts == [footprint]
    rear_end = Polygon([
        sample.point(lane)[:2] for lane in (rear, front - source.wing_depth_m)
    ] + [
        (sample.point(lane)[0] + sample.tx * source.backing_depth_m,
         sample.point(lane)[1] + sample.ty * source.backing_depth_m)
        for lane in (front - source.wing_depth_m, rear)
    ])
    available = footprint.union(rear_end).buffer(.0002)
    panes = 0
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            values = struct.unpack_from("<I24f", tile.triangles, offset)
            material = tile.materials[values[0]]
            assert material != "Glass"
            points = [(-values[2 + i * 8] / 100, -values[1 + i * 8] / 100,
                       values[3 + i * 8] / 100) for i in range(3)]
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = math.sqrt(sum(value * value for value in normal))
            assert length > 0
            stored = (-values[5], -values[4], values[6])
            assert sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .9999
            projected = Polygon([point[:2] for point in points])
            assert projected.difference(available).area < 1e-8
            assert projected.intersection(fastlane).area < 1e-8
            assert max(point[2] for point in points) <= sample.z + source.height_m + .0002
            if material == "JeddahHospitalityGlass":
                panes += 1
    assert panes > 150
    lights = entry_lights(scene)
    assert len(lights) == source.wing_light_count == 8
    assert all(light.pool_radius_m == 14 and light.power == source.lobby_light_power for light in lights)
    assert all(light.target is not None and light.target[2] < light.position[2] for light in lights)
    assert all(footprint.covers(LineString([light.position[:2], light.target[:2]]))
               for light in lights if light.target is not None)
    assert source.station_m == 6009 and source.height_m == pytest.approx(18.4)
