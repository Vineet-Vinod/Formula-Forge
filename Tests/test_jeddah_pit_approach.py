"""The missing entry corridor must fit the full car and preserve its runtime axis."""

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
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from venues.jeddah_pit_approach import (
    approach_floor_portals,
    approach_walls,
    emit_approach_gantry,
    emit_approach_panels,
    entry_extra_barriers,
    load_recipe,
)
from venues.jeddah_pit_protection import sample

ROOT = Path(__file__).resolve().parents[1]


def route_source() -> PitRoute:
    return TypeAdapter(PitRoute).validate_json(
        (ROOT / "Attribution/Sources/jeddah/pit-lane-reconstruction.json").read_bytes()
    )


def test_corridor_has_exact_joins_dense_walls_and_unchanged_runtime_route() -> None:
    route, recipe = route_source(), load_recipe()
    walls = approach_walls(route, recipe)
    assert len(walls) == 289
    assert len(entry_extra_barriers(route)) == 289
    assert hashlib.sha256(encode_route(route)).hexdigest() == recipe.source_encoded_pit_lane_sha256
    assert len(route.sections) == 433 and len(route.portals) == 30
    assert not set(entry_extra_barriers(route)).intersection(route.barriers)
    for side in (-1, 1):
        chain = [w for w in walls if w.side == side]
        for a, b in itertools.pairwise(chain):
            assert (a.barrier.bx, a.barrier.by) == (b.barrier.ax, b.barrier.ay)
        assert LineString([(w.barrier.ax, w.barrier.ay) for w in chain] +
                          [(chain[-1].barrier.bx, chain[-1].barrier.by)]).is_simple
        assert all(math.hypot(w.barrier.bx - w.barrier.ax, w.barrier.by - w.barrier.ay) <= 0.8 for w in chain)
    right = [w for w in walls if w.side > 0]
    assert (right[0].barrier.ax, right[0].barrier.ay) == (route.barriers[17].bx, route.barriers[17].by)
    assert (right[-1].barrier.bx, right[-1].barrier.by) == (route.barriers[18].ax, route.barriers[18].ay)
    assert right[0].barrier.top == route.barriers[17].top
    assert right[-1].barrier.top == route.barriers[18].top
    portals = approach_floor_portals(route)
    assert len(portals) == 97 and len(portals) <= 200
    for portal in portals:
        polygon = Polygon(portal.polygon_xy_m)
        assert polygon.is_valid and abs(polygon.convex_hull.area - polygon.area) < 1e-8


def test_full_car_envelope_clears_the_source_entry_chicane() -> None:
    route = route_source()
    footprint = unary_union([LineString([(w.ax, w.ay), (w.bx, w.by)]).buffer(w.radius)
                             for w in entry_extra_barriers(route)])
    for distance in (137, 150, 180, 184, 200, 220, 228.249, 240, 245, 248.887):
        s = sample(route, distance)
        tx, ty = -s.normal_y, s.normal_x
        car = Polygon([(s.x + along * tx + lane * s.normal_x,
                        s.y + along * ty + lane * s.normal_y)
                       for along, lane in ((-2.625, -1.25), (2.625, -1.25),
                                           (2.625, 1.25), (-2.625, 1.25))])
        assert car.distance(footprint) > 0.5


def test_right_qatar_phase_meets_retained_facing_and_gantry_is_above_the_lane() -> None:
    route, recipe = route_source(), load_recipe()

    class FacingScene(MeshScene):
        def __init__(self) -> None:
            super().__init__()
            self.phase: list[tuple[float, float]] = []

        def banner(self, a: tuple[float, float, float], b: tuple[float, float, float],
                   height: float, material: str, kind: str = "Tile_Detail",
                   u0: float = 0, repeat: float = 1) -> None:
            self.phase.append((u0, repeat))
            super().banner(a, b, height, material, kind, u0, repeat)

    scene = FacingScene()
    walls = approach_walls(route, recipe)
    emit_approach_panels(scene, route)
    right_count = sum(w.side > 0 for w in walls)
    right = scene.phase[:right_count]
    assert abs(right[-1][0]) < 1e-10
    for a, b in itertools.pairwise(right):
        assert abs(a[0] - b[0] - b[1]) < 1e-10
    assert all(set(tile.materials) == {"PanelPurple"} for tile in scene.tiles.values())
    assert all(struct.unpack_from("<f", tile.triangles, offset + 4 + 20)[0] == 0
               for tile in scene.tiles.values() for offset in range(0, len(tile.triangles), 100))
    gantry = MeshScene()
    emit_approach_gantry(gantry, route)
    assert recipe.gantry.clearance_m >= 4.8
    assert all(set(tile.materials) <= {"Steel", "PanelJeddahEntrySalesforce"} for tile in gantry.tiles.values())
