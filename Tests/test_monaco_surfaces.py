from __future__ import annotations

from collections import Counter

import pytest
from circuit_mesh import MeshScene
from shapely.geometry import Polygon
from venues.monaco_surfaces import face, replace_surfaces
from venues.monaco_surfaces_dataclasses import SurfaceRegion


def test_surface_roles_preserve_planes_outside_attributes_and_untouched_rows() -> None:
    scene = MeshScene()
    coordinates = [(-10.0, -10.0), (10.0, -10.0), (0.0, 10.0)]
    points = [(x, y, 10 + 0.25 * x + 0.5 * y) for x, y in coordinates]
    scene.triangle(
        "Tile_Ground",
        "Runoff",
        points[0],
        points[1],
        points[2],
        tuple((0.05 * x + 1, 0.1 * y + 2) for x, y in coordinates),
    )
    scene.triangle("Tile_Ground", "Runoff", (100, 100, 0), (110, 100, 0), (100, 110, 0))
    before = {(name, bytes(tile.triangles)) for name, tile in scene.tiles.items()}
    region = Polygon([(-2, -2), (2, -2), (2, 2), (-2, 2)])
    report = replace_surfaces(
        scene, [SurfaceRegion("Observed natural strip", region, "rock")]
    )
    assert report.original_faces_split == 1
    assert report.classified_area_m2 == pytest.approx(16)
    assert all(
        bytes(scene.tiles[name].triangles) == payload
        for name, payload in before
        if name not in report.tiles
    )
    area = 0.0
    classified = 0.0
    for name in report.tiles:
        tile = scene.tiles[name]
        for offset in range(0, len(tile.triangles), 100):
            row = face(tile, offset)
            area += row.plan.area
            if row.material == "MonacoRockGround":
                classified += row.plan.area
                assert region.buffer(0.00001).covers(row.plan)
            for (x, y), vertex in zip(row.xy, row.vertices, strict=True):
                assert vertex[2] / 100 == pytest.approx(
                    10 + 0.25 * x + 0.5 * y, abs=2e-6
                )
                if row.material == "Runoff":
                    assert vertex[6] == pytest.approx(0.05 * x + 1, abs=2e-6)
                    assert vertex[7] == pytest.approx(0.1 * y + 2, abs=2e-6)
    assert area == pytest.approx(200)
    assert classified == pytest.approx(16)


def test_overlapping_surface_roles_fail_before_mutating_mesh() -> None:
    scene = MeshScene()
    scene.triangle("Tile_Ground", "Runoff", (0, 0, 0), (10, 0, 0), (0, 10, 0))
    before = Counter(
        (name, bytes(tile.triangles)) for name, tile in scene.tiles.items()
    )
    plan = Polygon([(0, 0), (2, 0), (0, 2)])
    with pytest.raises(ValueError, match="must not overlap"):
        replace_surfaces(
            scene,
            [
                SurfaceRegion("First", plan, "rock"),
                SurfaceRegion("Second", plan, "ivy"),
            ],
        )
    assert (
        Counter((name, bytes(tile.triangles)) for name, tile in scene.tiles.items())
        == before
    )
