"""The EDITION must have occupied terraces and outward, closed structural members."""

from __future__ import annotations

import csv
import math
import struct
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, sub
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.jeddah_edition import edition_hotel
from venues.jeddah_edition_lighting import fixtures, write_fixtures


class EditionScene(CircuitScene):
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


def test_edition_wash_uses_emitted_foundation_and_separate_native_csv(
    tmp_path: Path,
) -> None:
    scene = CircuitScene("jeddah")
    scene.data = tmp_path
    with pytest.raises(ValueError, match="emitted foundation"):
        fixtures(scene)
    base = 7.25
    scene.landmarks.append({"osm_id": 1258744123, "foundation_top_m": base})
    before = list(scene.road), scene.grid
    road_lights = tmp_path / "night_lights.csv"
    road_lights.write_text("existing independent road-light pool\n")
    lights = fixtures(scene)
    assert len(lights) == 4
    property_shape = Polygon(scene.footprint(1258744123).ring)
    for light in lights:
        assert light.position[2] == base + 4.5
        assert light.target[2] == base + 13.5
        assert property_shape.distance(ShapePoint(*light.position[:2])) > 5.9
        assert property_shape.contains(ShapePoint(*light.target[:2]))
        assert math.dist(light.position[:2], light.target[:2]) == pytest.approx(11)
        assert scene.nearest(*light.position[:2])[1] > 50
        assert light.power == 3.2
    write_fixtures(scene)
    with (tmp_path / "edition_lights.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    for row, light in zip(rows, lights, strict=True):
        assert float(row["x"]) == pytest.approx(-light.position[1] * 100)
        assert float(row["y"]) == pytest.approx(-light.position[0] * 100)
        assert float(row["z"]) == pytest.approx(light.position[2] * 100)
        assert float(row["target_x"]) == pytest.approx(-light.target[1] * 100)
        assert float(row["target_y"]) == pytest.approx(-light.target[0] * 100)
        assert float(row["target_z"]) == pytest.approx(light.target[2] * 100)
    assert road_lights.read_text() == "existing independent road-light pool\n"
    assert (scene.road, scene.grid) == before
    assert not scene.tiles
    assert not scene.terrain_cutouts


def test_edition_members_are_closed_and_face_outward_after_native_packing() -> None:
    scene = MeshScene()
    center = (123.5, -77.25, 13.7)
    scene.beam(
        "Building_EditionTest",
        "White",
        (120.5, -79.25, 7.7),
        (126.5, -75.25, 19.7),
        0.7,
        0.58,
    )
    edges: Counter[tuple[Point, Point]] = Counter()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            values = struct.unpack_from("<I24f", tile.triangles, offset)
            points = [
                (
                    -values[2 + i * 8] / 100,
                    -values[1 + i * 8] / 100,
                    values[3 + i * 8] / 100,
                )
                for i in range(3)
            ]
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            radial = tuple(
                sum(p[axis] for p in points) / 3 - center[axis] for axis in range(3)
            )
            assert sum(n * r for n, r in zip(normal, radial, strict=True)) > 0
            for a, b in zip(points, points[1:] + points[:1]):
                edges[(a, b)] += 1
    assert edges
    assert all(count == edges[(b, a)] for (a, b), count in edges.items())


def test_edition_stays_on_its_property_and_preserves_driving_and_ground_inputs() -> (
    None
):
    scene = EditionScene()
    before = list(scene.road), scene.grid, scene.road_mask.wkb
    owned = Polygon(scene.footprint(1258744123).ring)
    edition_hotel(scene)
    assert (scene.road, scene.grid, scene.road_mask.wkb) == before
    assert len(scene.terrain_cutouts) == 1
    assert scene.terrain_cutouts[0].symmetric_difference(owned).area < 1e-8
    assert scene.modeled_buildings == {1258744123}
    assert scene.faces
    for _kind, _material, points in scene.faces:
        assert all(math.isfinite(value) for point in points for value in point)
        projected = Polygon([p[:2] for p in points])
        if projected.area > 1e-9:
            assert projected.difference(owned).area < 1e-7
            assert projected.intersection(scene.road_mask).area < 1e-8
    assert any(
        kind == "Building_EditionRoomPiers" for kind, _material, _points in scene.faces
    )
    assert any(
        kind == "Building_EditionGlassBalustrades"
        for kind, _material, _points in scene.faces
    )
    assert all(
        material not in ("Glass", "WarmGlass")
        for _kind, material, _points in scene.faces
    )
    panes = [
        points
        for kind, _material, points in scene.faces
        if kind == "Building_EditionInsetRoomGlazing"
    ]
    backs = [
        points
        for kind, _material, points in scene.faces
        if kind == "Building_EditionSolidRoomBacks"
    ]
    assert panes and len(backs) == len(panes)
    for pane, back in zip(panes, backs, strict=True):
        normal = cross(sub(pane[1], pane[0]), sub(pane[2], pane[0]))
        magnitude = math.sqrt(sum(n * n for n in normal))
        assert all(
            sum((b - a) * n for a, b, n in zip(front, rear, normal, strict=True))
            / magnitude
            < -0.5
            for front, rear in zip(pane, back, strict=True)
        )


def test_edition_projecting_slabs_have_closed_fascias_and_opposing_edge_directions() -> (
    None
):
    scene = EditionScene()
    edition_hotel(scene)
    edges: Counter[tuple[Point, Point]] = Counter()
    for kind, _material, points in scene.faces:
        if not kind.startswith(
            (
                "Building_EditionOccupiedDeck",
                "Building_EditionProjectingCanopy",
                "Building_EditionRaisedWingFin",
            )
        ):
            continue
        vertices = [tuple(round(v, 7) for v in p) for p in points]
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edges[(a, b)] += 1
    assert edges
    assert all(count == edges[(b, a)] for (a, b), count in edges.items())

    fin = [
        points
        for kind, _material, points in scene.faces
        if kind == "Building_EditionRaisedWingFin"
    ]
    foot_z = min(p[2] for face in fin for p in face)
    deck = unary_union(
        [
            Polygon([p[:2] for p in points])
            for kind, _material, points in scene.faces
            if kind == "Building_EditionOccupiedDeckTop"
            and abs(points[0][2] - foot_z) < 1e-8
        ]
    )
    assert not deck.is_empty
    assert all(
        deck.buffer(1e-8).covers(ShapePoint(p[:2]))
        for face in fin
        for p in face
        if abs(p[2] - foot_z) < 1e-8
    )
