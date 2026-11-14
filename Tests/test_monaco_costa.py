"""Measured stepped roofs and actual open Casa Mia galleries."""

from __future__ import annotations

import math
import sys
from itertools import pairwise
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.monaco_costa import costa_properties, open_porch, plan, roof_parts
from venues.monaco_dataclasses import CostaArchitecture


def test_costa_roofs_preserve_primary_3d_edges_without_using_a_global_ground_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    config = TypeAdapter(CostaArchitecture).validate_json(
        (scene.sources / 'architecture/costa-properties.json').read_bytes()
    )
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    before_road, before_grid = list(scene.road), scene.grid
    roofs: dict[str, list[tuple[Point, Point, Point]]] = {}

    def capture(
        kind: str, material: str, a: Point, b: Point, c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if (kind.startswith('Building_CostaRoof_') or kind == 'Building_CostaPorchRoof') and material in ('Terracotta', 'Steel'):
            assert cross(sub(b, a), sub(c, a))[2] > 0
            roofs.setdefault(kind, []).append((a, b, c))

    monkeypatch.setattr(scene, 'triangle', capture)
    costa_properties(scene)
    assert scene.road == before_road and scene.grid == before_grid
    assert {94399990, 94401978} <= scene.modeled_buildings
    for record in config.components:
        faces = list(roofs['Building_CostaRoof_' + record.style])
        if record.style == 'casa_core':
            faces.extend(roofs['Building_CostaPorchRoof'])
        expected = Polygon([scene.geo(lat, lon) for lon, lat in record.outer])
        emitted = unary_union([Polygon([p[:2] for p in face]) for face in faces])
        assert emitted.symmetric_difference(expected).area < 1e-7
        vertices = {(round(x, 6), round(y, 6), round(z, 6)) for face in faces for x, y, z in face}
        for (lon, lat), height in zip(record.outer, record.roof_outline_m, strict=True):
            x, y = scene.geo(lat, lon)
            assert (round(x, 6), round(y, 6), round(height - datum, 6)) in vertices
        assert max(p[2] for face in faces for p in face) == pytest.approx(record.roof_peak_m - datum)
    original = {name: tuple(faces) for name, faces in roofs.items()}
    roofs.clear()
    monkeypatch.setattr(scene, 'ground', lambda x, y: -100. + 15 * math.sin(x))
    costa_properties(scene)
    assert {name: tuple(faces) for name, faces in roofs.items()} == original


def ray_distance(origin: Point, direction: Point, triangle: tuple[Point, Point, Point]) -> float | None:
    a, b, c = triangle
    edge_a, edge_b = sub(b, a), sub(c, a)
    h = cross(direction, edge_b)
    determinant = sum(p * q for p, q in zip(edge_a, h, strict=True))
    if abs(determinant) < 1e-10:
        return None
    offset = sub(origin, a)
    u = sum(p * q for p, q in zip(offset, h, strict=True)) / determinant
    q = cross(offset, edge_a)
    v = sum(p * r for p, r in zip(direction, q, strict=True)) / determinant
    distance = sum(p * r for p, r in zip(edge_b, q, strict=True)) / determinant
    return distance if 0 <= u <= 1 and 0 <= v and u + v <= 1 and distance > 0 else None


def test_casa_mia_keeps_three_open_galleries_with_supported_columns_and_separate_roof_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    config = TypeAdapter(CostaArchitecture).validate_json(
        (scene.sources / 'architecture/costa-properties.json').read_bytes()
    )
    record = next(r for r in config.components if r.style == 'casa_core')
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    source = Polygon([(*scene.geo(lat, lon), z - datum)
                      for (lon, lat), z in zip(record.outer, record.roof_outline_m, strict=True)])
    main, porch = roof_parts(source, record, datum)
    assert porch is not None
    assert main.intersection(porch).area < 1e-7
    assert main.union(porch).symmetric_difference(source).area < 1e-7
    assert record.roof_step is not None
    assert min(record.roof_step.upper_endpoint_m) - max(record.roof_step.lower_endpoint_m) > 3
    owner = Polygon(scene.footprint(record.osm_id).ring)
    deck = record.upper_floor_base_m - datum
    faces: list[tuple[Point, Point, Point]] = []
    shaft_points: set[Point] = set()

    def capture(
        kind: str, material: str, a: Point, b: Point, c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        faces.append((a, b, c))
        for point in [a, b, c]:
            assert owner.buffer(1e-6).covers(ShapePoint(point[:2]))
            assert plan(porch).buffer(1e-6).covers(ShapePoint(point[:2]))
            if kind == 'Building_CostaPorchColumns' and abs(point[2] - deck - .1) < 1e-7:
                shaft_points.add(point)

    monkeypatch.setattr(scene, 'triangle', capture)
    open_porch(scene, porch, owner, deck, scene.ground)
    front_a, front_b = list(porch.exterior.coords)[:2]
    length = math.dist(front_a[:2], front_b[:2])
    tx, ty = (front_b[0] - front_a[0]) / length, (front_b[1] - front_a[1]) / length
    ordered = sorted(shaft_points, key=lambda p: p[0] * tx + p[1] * ty)
    groups: list[list[Point]] = []
    for point in ordered:
        if not groups or (point[0] - groups[-1][-1][0]) * tx + (point[1] - groups[-1][-1][1]) * ty > 1:
            groups.append([])
        groups[-1].append(point)
    assert len(groups) == 4
    centers = [(sum(p[0] for p in group) / len(group), sum(p[1] for p in group) / len(group))
               for group in groups]
    direction: Point = -ty, tx, 0
    middle_x, middle_y = ((centers[0][i] + centers[-1][i]) / 2 for i in range(2))
    if not plan(porch).covers(ShapePoint(middle_x + direction[0], middle_y + direction[1])):
        direction = ty, -tx, 0
    for level in [deck + 1.8, deck - 2.2]:
        for first, last in pairwise(centers):
            middle = ((first[0] + last[0]) / 2, (first[1] + last[1]) / 2)
            origin = (middle[0] - direction[0] * 5, middle[1] - direction[1] * 5, level)
            hits = [distance for face in faces if (distance := ray_distance(origin, direction, face)) is not None]
            assert not hits or min(hits) > 6, 'A solid facade must not replace a photographed gallery opening'
        origin = (centers[1][0] - direction[0] * 5, centers[1][1] - direction[1] * 5, level)
        hits = [distance for face in faces if (distance := ray_distance(origin, direction, face)) is not None]
        assert hits and min(hits) < 5.5, 'Open galleries must retain real supporting piers/columns'
