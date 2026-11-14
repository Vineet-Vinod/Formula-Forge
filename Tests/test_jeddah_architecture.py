"""The outfield pavilion needs recessed windows and closed roof skins."""

from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from venues.jeddah_facilities import t27_pavilion


class PavilionScene(CircuitScene):
    def __init__(self) -> None:
        super().__init__("jeddah")
        self.faces: list[tuple[str, str, tuple[Point, Point, Point]]] = []
        self.road_surfaces("Runoff")
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
        self.faces.append((kind, material, (a, b, c)))


def test_pavilion_glazing_is_dark_recessed_and_clear_of_the_racing_road() -> None:
    scene = PavilionScene()
    road = list(scene.road)
    t27_pavilion(scene)
    glass = [face for kind, material, face in scene.faces if kind == "Building_T27PavilionGlazing" and material == "Glass"]
    assert glass
    assert all(material != "WarmGlass" for _kind, material, _face in scene.faces)
    for _kind, _material, face in scene.faces:
        assert all(math.isfinite(value) for point in face for value in point)
        projected = Polygon([point[:2] for point in face])
        if projected.area > 1e-8:
            assert projected.intersection(scene.road_mask).area < 1e-7
    assert scene.road == road
    assert len(scene.ground_patches) == 1


def test_pavilion_canopy_has_no_open_edge_or_reversed_shell_seam() -> None:
    scene = PavilionScene()
    t27_pavilion(scene)
    edges: Counter[tuple[Point, Point]] = Counter()
    for kind, _material, face in scene.faces:
        if kind not in ("Building_T27PavilionCanopy", "Building_T27PavilionCanopyEdges"):
            continue
        vertices = [(round(point[0], 8), round(point[1], 8), round(point[2], 8)) for point in face]
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edges[(a, b)] += 1
    assert edges
    for edge, count in edges.items():
        assert count == edges[(edge[1], edge[0])]
