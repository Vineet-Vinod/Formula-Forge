"""The eastern skyline must use its real sites and retain the hotel's open arch."""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path
from typing import Literal

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from circuit_dataclasses import Building, Point
from circuit_mesh import add, cross, mul, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import prepare
from shapely.geometry import LineString, Polygon
from venues.baku_civic import _face, _north_front, _panel, _retained_north_face
from venues.baku_civic_dataclasses import (
    CourtFace,
    CourtFrontageSource,
    NorthFrontageSource,
    StreetGrade,
)
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


class CivicPanelScene(CircuitScene):
    def triangle(
        self,
        kind: str,
        material: str,
        a: Point,
        b: Point,
        c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if kind in {
            "Building_CourtMasonry",
            "Building_NorthFrontMasonry",
            "Building_NorthRetainedMasonry",
        }:
            super().triangle(kind, material, a, b, c, uv, normals)


@pytest.mark.parametrize("emitter", ("panel", "court", "north", "retained"))
def test_triangulated_civic_facades_face_outward_in_source_coordinates(
    emitter: Literal["panel", "court", "north", "retained"],
) -> None:
    scene = CivicPanelScene("baku")
    scene.road_mask = Polygon()
    face = CourtFace((-1450, -400, 7.15), (0.6, 0.8, 0), (0.8, -0.6, 0), 33, 33)
    if emitter == "panel":
        _panel(
            scene,
            face,
            Polygon(
                [(0, 0), (8, 0), (8, 6), (0, 6)], [[(2, 2), (4, 2), (4, 4), (2, 4)]]
            ),
            0,
            "Cream",
        )
    elif emitter == "court":
        source = TypeAdapter(CourtFrontageSource).validate_json(
            (scene.sources / "court-frontage.json").read_bytes()
        )
        _face(scene, face, source, source.entrance_edge, -0.03)
    elif emitter == "north":
        north = TypeAdapter(NorthFrontageSource).validate_json(
            (scene.sources / "north-frontage.json").read_bytes()
        )
        street = StreetGrade(LineString([(0, 0), (100, 0)]), 7.15, 7.15)
        _north_front(scene, face, street, north, 31.15, lambda x, y: 7.15)
    else:
        _retained_north_face(scene, face, 12, 31.15, 7.15, 7.15, lambda x, y: 7.15)
    assert scene.tiles
    for tile in scene.tiles.values():
        for row in struct.iter_unpack("<I24f", tile.triangles):
            normal = -row[5], -row[4], row[6]
            assert sum(a * b for a, b in zip(normal, face.outward)) > 0.999
            a = row[1], row[2], row[3]
            b = row[9], row[10], row[11]
            c = row[17], row[18], row[19]
            native_cross = cross(sub(b, a), sub(c, a))
            assert sum(a * b for a, b in zip(native_cross, row[4:7])) < 0
