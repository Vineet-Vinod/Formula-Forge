"""Pit architecture must retain its parcel and stay outside the driving road."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.australia_pits import PIT_END, PIT_START, pit_building


class PitScene(CircuitScene):
    def __init__(self) -> None:
        super().__init__("australia")
        self.faces: list[tuple[str, tuple[Point, Point, Point]]] = []
        self.road_surfaces("Grass")
        self.faces.clear()

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
        self.faces.append((kind, (a, b, c)))


def test_pit_replacement_preserves_the_original_horizontal_parcel_and_road() -> None:
    scene = PitScene()
    original_road = list(scene.road)
    scene.pit_building(PIT_START, PIT_END, side=1, depth=21, height=13, levels=3)
    old_footprint = unary_union(scene.terrain_cutouts)
    scene.terrain_cutouts.clear()
    scene.faces.clear()
    pit_building(scene)
    replacement = unary_union(scene.terrain_cutouts)
    assert old_footprint.symmetric_difference(replacement).area < 1e-7
    assert scene.road == original_road
    for _kind, face in scene.faces:
        assert all(math.isfinite(value) for p in face for value in p)
        projected = Polygon([p[:2] for p in face])
        if projected.area > 1e-8:
            assert projected.intersection(scene.road_mask).area < 1e-7


def test_roof_flags_have_matching_front_and_back_faces() -> None:
    scene = PitScene()
    pit_building(scene)
    flags = [face for kind, face in scene.faces if kind == "Building_AlbertParkFlags"]
    assert flags
    faces = {frozenset(face) for face in flags}
    assert len(faces) * 2 == len(flags)
    for face in flags:
        matches = [other for other in flags if frozenset(other) == frozenset(face)]
        assert len(matches) == 2
        a, b, c = face
        x, y, z = matches[0] if matches[1] == face else matches[1]
        normal = (b[0] - a[0]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[0] - a[0])
        opposite = (y[0] - x[0]) * (z[2] - x[2]) - (y[2] - x[2]) * (z[0] - x[0])
        assert normal * opposite < 0
