"""The EDITION must have occupied terraces and outward, closed structural members."""

from __future__ import annotations

import math
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, sub
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.jeddah_edition import edition_hotel


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
