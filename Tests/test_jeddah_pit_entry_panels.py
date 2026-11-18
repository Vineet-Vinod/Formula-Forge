"""The Qatar entry facing must stay on its real wall and stop before the walkway."""

from __future__ import annotations

import hashlib
import itertools
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_mesh import MeshScene
from pit_routes import encode_route
from pit_routes_dataclasses import PitRoute
from pydantic import TypeAdapter
from shapely.geometry import LineString, Point
from venues.jeddah_pit_entry_panels import (
    emit_entry_panels,
    load_recipe,
    selected_panels,
)

ROOT = Path(__file__).resolve().parents[1]


def route_source() -> PitRoute:
    return TypeAdapter(PitRoute).validate_json(
        (ROOT / "Attribution/Sources/jeddah/pit-lane-reconstruction.json").read_bytes()
    )


def test_qatar_panels_are_on_exact_retained_faces_and_end_at_walkway() -> None:
    route, recipe = route_source(), load_recipe()
    panels = selected_panels(route, recipe)
    assert len(panels) == 13
    assert [p.source_barrier_index for p in panels] == list(range(18, 31))
    assert recipe.walls[0].route_start_distance_m > 248
    assert recipe.walls[-1].route_end_distance_m == 272
    assert all(w.route_end_distance_m <= 272 for w in recipe.walls)
    for record, panel in zip(recipe.walls, panels):
        wall = record.barrier
        assert wall in route.barriers
        line = LineString([(wall.ax, wall.ay), (wall.bx, wall.by)])
        for point in (panel.first, panel.last):
            assert abs(line.distance(Point(point[:2])) - wall.radius - 0.015) < 1e-8
            assert wall.bottom < point[2] < point[2] + recipe.height_m < wall.top
    assert hashlib.sha256(encode_route(route)).hexdigest() == recipe.source_encoded_pit_lane_sha256


def test_panel_uvs_are_continuous_and_read_correctly_from_the_pit() -> None:
    route, recipe = route_source(), load_recipe()
    panels = selected_panels(route, recipe)
    for previous, current in itertools.pairwise(panels):
        assert abs(previous.u0 - current.u0 - current.repeat) < 1e-12
    scene = MeshScene()
    emit_entry_panels(scene, route)
    assert len(scene.tiles) == 1
    tile = next(iter(scene.tiles.values()))
    assert tile.materials == ["PanelPurple"]
    assert len(tile.triangles) == 13 * 4 * 100
    inward_count = 0
    for index in range(52):
        panel = panels[index // 4]
        vertices = [struct.unpack_from("<8f", tile.triangles, index * 100 + 4 + 32 * i) for i in range(3)]
        normal = (-vertices[0][4], -vertices[0][3], vertices[0][5])
        if sum(a * b for a, b in zip(normal, panel.inward_normal)) < 0.999:
            continue
        inward_count += 1
        points = [(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in vertices]
        du1, dv1 = vertices[1][6] - vertices[0][6], vertices[1][7] - vertices[0][7]
        du2, dv2 = vertices[2][6] - vertices[0][6], vertices[2][7] - vertices[0][7]
        determinant = du1 * dv2 - du2 * dv1
        derivative = [((points[1][i] - points[0][i]) * dv2 -
                       (points[2][i] - points[0][i]) * dv1) / determinant for i in range(2)]
        right = (panel.first[0] - panel.last[0], panel.first[1] - panel.last[1])
        agreement = sum(a * b for a, b in zip(derivative, right)) / (math.hypot(*derivative) * math.hypot(*right))
        assert agreement > 0.9999
    assert inward_count == 26
