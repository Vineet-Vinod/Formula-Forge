"""The eastern skyline must use its real sites and retain the hotel's open arch."""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from circuit_dataclasses import Building, Point
from circuit_mesh import add, cross, mul, sub
from circuit_scene import CircuitScene
from shapely import prepare
from shapely.geometry import Polygon
from venues.baku_philharmonic import philharmonic_hall
from venues.baku_skyline import crescent_hotel, waterfront_skyline
from venues.east_architecture import frame


def ray_hits(origin: Point, direction: Point, a: Point, b: Point, c: Point) -> bool:
    e1, e2 = sub(b, a), sub(c, a)
    h = cross(direction, e2)
    det = sum(x * y for x, y in zip(e1, h))
    if abs(det) < 1e-9:
        return False
    offset = sub(origin, a)
    u = sum(x * y for x, y in zip(offset, h)) / det
    q = cross(offset, e1)
    v = sum(x * y for x, y in zip(direction, q)) / det
    distance = sum(x * y for x, y in zip(e2, q)) / det
    return 0 <= u <= 1 and 0 <= v and u + v <= 1 and distance > .001


def test_new_skyline_preserves_existing_sites_and_uses_the_published_city_height() -> None:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    before = list(scene.buildings)
    original_road = list(scene.road)
    waterfront_skyline(scene)
    assert scene.buildings[:len(before)] == before
    assert scene.road == original_road
    assert len({building.osm_id for building in scene.buildings}) == len(scene.buildings)
    city = scene.footprint(1067699501)
    assert city.name == "Crescent City"
    assert city.height == 210
    near, distance = scene.nearest(*frame(city)[0][:2])
    assert 180 < near.station < 550
    assert distance > 100
    for tile in scene.tiles.values():
        assert len(tile.triangles) % 100 == 0
        for row in struct.iter_unpack("<I24f", tile.triangles):
            assert all(math.isfinite(value) for value in row[1:])


def test_crescent_hotel_keeps_a_real_open_void_below_its_glazed_crown() -> None:
    scene = CircuitScene("baku")
    # A rotated site catches an accidental world-axis hole or solid-box fallback.
    angle = .6
    ring = [(u * math.cos(angle) - v * math.sin(angle),
             u * math.sin(angle) + v * math.cos(angle))
            for u, v in ((-90, -18), (90, -18), (90, 18), (-90, 18))]
    hotel = Building(901738189, "Crescent Hotel", "hotel", 166, ring, {})
    center, _, side, _, _ = frame(hotel)
    base = min(scene.ground(x, y) for x, y in ring)
    crescent_hotel(scene, hotel)
    triangles = []
    for tile in scene.tiles.values():
        for row in struct.iter_unpack("<I24f", tile.triangles):
            triangles.append(tuple((-row[i + 1] / 100, -row[i] / 100, row[i + 2] / 100)
                                   for i in (1, 9, 17)))
    for z, expected in ((50, False), (150, True)):
        origin = add((center[0], center[1], base + z), mul(side, -100))
        assert any(ray_hits(origin, side, *triangle) for triangle in triangles) is expected
    assert base + 166 <= max(point[2] for triangle in triangles for point in triangle) < base + 166.2


def test_philharmonic_roofs_and_arcades_leave_the_racing_surface_clear() -> None:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    scene.tiles.clear()
    road = list(scene.road)
    philharmonic_hall(scene)
    prepare(scene.road_mask)
    overlap = 0.0
    for tile in scene.tiles.values():
        for row in struct.iter_unpack("<I24f", tile.triangles):
            projected = Polygon([(-row[i + 1] / 100, -row[i] / 100) for i in (1, 9, 17)])
            if projected.area > 1e-9 and scene.road_mask.intersects(projected):
                overlap += scene.road_mask.intersection(projected).area
    assert overlap < 0.001
    assert scene.road == road
