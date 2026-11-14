"""The actual packed bridge and native walls must leave one clear racing opening."""

from __future__ import annotations

import csv
import struct
import sys
from itertools import pairwise
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from venues.singapore_bridge import anderson_bridge, bridge_frame
from venues.singapore_bridge_dataclasses import AndersonBridge


class BridgeScene(CircuitScene):
    def __init__(self) -> None:
        super().__init__("singapore")
        self.faces: list[tuple[str, tuple[Point, Point, Point]]] = []

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
        tile = self.tile(kind, mul(add(add(a, b), c), 1 / 3))
        size = len(tile.triangles)
        super().triangle(kind, material, a, b, c, uv, normals)
        if len(tile.triangles) == size:
            return
        raw = tile.triangles[-100:]
        points = []
        for vertex in range(3):
            x, y, z = struct.unpack_from("<3f", raw, 4 + vertex * 32)
            points.append((-y / 100, -x / 100, z / 100))
        self.faces.append((kind, (points[0], points[1], points[2])))


@pytest.fixture(scope="module")
def bridge() -> tuple[BridgeScene, AndersonBridge, BaseGeometry, BaseGeometry]:
    scene = BridgeScene()
    config = TypeAdapter(AndersonBridge).validate_json(
        (scene.sources / "anderson-bridge.json").read_bytes()
    )
    anderson_bridge(scene)
    center, axis, right = bridge_frame(scene, config)

    def local(p: Point) -> tuple[float, float]:
        dx, dy = p[0] - center[0], p[1] - center[1]
        return dx * axis[0] + dy * axis[1], dx * right[0] + dy * right[1]

    extent = box(-config.steel_span_m / 2 + 0.5, -config.girder_pitch_m,
                 config.steel_span_m / 2 - 0.5, 0)
    road_faces = []
    for a, b in pairwise(scene.road):
        if not 2790 < a.station < 2920:
            continue
        road_faces.append(Polygon([
            local(a.point(a.half_width)), local(b.point(b.half_width)),
            local(b.point(-b.half_width)), local(a.point(-a.half_width)),
        ]))
    legal = unary_union(road_faces).intersection(extent)
    walls = []
    with (scene.scratch / "barriers.csv").open() as stream:
        for row in csv.DictReader(stream):
            a = local((float(row["ax"]), float(row["ay"]), 0.0))
            b = local((float(row["bx"]), float(row["by"]), 0.0))
            shape = LineString([a, b]).buffer(float(row["radius"]), cap_style="round")
            if shape.intersects(extent):
                walls.append(shape.intersection(extent))
    return scene, config, legal, unary_union(walls)


def test_native_road_and_walls_fit_between_actual_packed_longitudinal_trusses(
    bridge: tuple[BridgeScene, AndersonBridge, BaseGeometry, BaseGeometry],
) -> None:
    scene, config, legal, walls = bridge
    center, axis, right = bridge_frame(scene, config)
    trusses = []
    for kind, face in scene.faces:
        if kind not in {"Building_AndersonLowerChords", "Building_AndersonUpperChords",
                        "Building_AndersonLattice", "Building_AndersonVerticals"}:
            continue
        shape = Polygon([
            ((p[0] - center[0]) * axis[0] + (p[1] - center[1]) * axis[1],
             (p[0] - center[0]) * right[0] + (p[1] - center[1]) * right[1])
            for p in face
        ])
        if shape.area > 1e-10:
            trusses.append(shape)
    assert legal.area > 500
    assert not walls.is_empty
    structure = unary_union(trusses)
    assert legal.distance(walls) > 0.03
    assert walls.distance(structure) > 0.03
    assert legal.distance(structure) > 0.15
    assert legal.bounds[1] < -9.3 and legal.bounds[3] < -0.5


def test_arched_cross_ties_and_event_panels_clear_the_driving_height(
    bridge: tuple[BridgeScene, AndersonBridge, BaseGeometry, BaseGeometry],
) -> None:
    scene, _config, _legal, _walls = bridge
    overhead = [(kind, face) for kind, face in scene.faces
                if "CrossTie" in kind or kind == "Building_AndersonEventPanels"]
    assert overhead and scene.overhead_soffits
    for _kind, face in overhead:
        for point in face:
            road, _distance = scene.nearest(point[0], point[1])
            assert point[2] - road.z > 2.7


def test_bridge_margin_returns_to_the_original_street_allowance() -> None:
    scene = CircuitScene("singapore")
    for station in (0, 1000, 2760, 2950, scene.length):
        assert scene.kerb_margin(station) == pytest.approx(0.95)
    for station in (2820, 2850, 2890):
        assert scene.kerb_margin(station) == pytest.approx(0.15)


def test_entire_braking_marker_stays_outside_the_narrow_bridge_legal_lane() -> None:
    scene = BridgeScene()
    scene.braking_boards(2964.961013, 1, distances=(100,))
    assert scene.faces
    for _kind, face in scene.faces:
        for point in face:
            road, _distance = scene.nearest(point[0], point[1])
            lane = (point[0] - road.x) * road.ty - (point[1] - road.y) * road.tx
            assert lane - road.half_width > 0.14
