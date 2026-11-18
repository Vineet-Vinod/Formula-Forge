"""Close exit protection must preserve the route and print readable continuous panels."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from circuit_portals_dataclasses import Barrier
from circuit_route_assets import clip_foreign_protection
from pit_routes import encode_route
from pit_routes_dataclasses import PitRoute
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.strtree import STRtree
from venues.jeddah_pit_protection import (
    emit_exit_paving,
    emit_panels,
    exit_floor_portals,
    load_recipe,
    new_walls,
    sample,
)

ROOT = Path(__file__).resolve().parents[1]


def route_source() -> PitRoute:
    return TypeAdapter(PitRoute).validate_json(
        (ROOT / "Attribution/Sources/jeddah/pit-lane-reconstruction.json").read_bytes()
    )


def test_exit_route_and_physical_lane_remain_exact() -> None:
    route, recipe = route_source(), load_recipe()
    raw = json.loads((ROOT / "Attribution/Sources/jeddah/pit-exit-protection.json").read_text())
    assert len(route.sections) == 433
    assert len(route.portals) == 30
    assert hashlib.sha256(encode_route(route)).hexdigest() == raw["source_encoded_pit_lane_sha256"]
    walls = new_walls(route, recipe)
    assert all(w.barrier in route.barriers for w in walls)
    for side in (-1, 1):
        chain = [w for w in walls if w.side == side]
        for a, b in itertools.pairwise(chain):
            assert (a.barrier.bx, a.barrier.by) == (b.barrier.ax, b.barrier.ay)
        assert chain[-1].end_distance_m == next(j.distance_m for j in recipe.joins if j.side == side)
    assert min(w.start_distance_m for w in walls if w.side < 0) >= route.limit_exit_m + 1.5
    with (ROOT / "build/circuits/jeddah/barriers.csv").open() as handle:
        base = TypeAdapter(list[Barrier]).validate_python(list(csv.DictReader(handle)))
    for join in recipe.joins:
        survivors = clip_foreign_protection([base[join.source_wall_index]], route.portals)
        point = ShapePoint(join.point_xy_m)
        assert survivors
        assert min(LineString([(w.ax, w.ay), (w.bx, w.by)]).distance(point) for w in survivors) < 1e-7



class PanelScene(MeshScene):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[Point, Point, float, float]] = []

    def banner(self, a: Point, b: Point, height: float, material: str,
               kind: str = "Tile_Detail", u0: float = 0, repeat: float = 1) -> None:
        self.calls.append((a, b, u0, repeat))
        super().banner(a, b, height, material, kind, u0, repeat)


def test_packed_inward_panels_have_readable_uvs_and_continuous_phase() -> None:
    route, recipe = route_source(), load_recipe()
    records = new_walls(route, recipe)
    lines = [LineString([(w.barrier.ax, w.barrier.ay), (w.barrier.bx, w.barrier.by)]) for w in records]
    index = STRtree(lines)
    scene = PanelScene()
    emit_panels(scene, route)
    assert len(scene.calls) == len(records)
    previous: dict[int, tuple[Point, Point, float, float]] = {}
    for record, call in zip(records, scene.calls):
        if record.side in previous:
            before = previous[record.side]
            difference = before[2] - call[2] - call[3] if record.side > 0 else before[2] + before[3] - call[2]
            assert abs(difference) < 1e-10
        previous[record.side] = call
    inward_faces = 0
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            vertices = [struct.unpack_from("<8f", tile.triangles, offset + 4 + 32 * i) for i in range(3)]
            points = [(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in vertices]
            center = Polygon([p[:2] for p in points]).centroid
            record = records[int(index.nearest(center))]
            section = sample(route, (record.start_distance_m + record.end_distance_m) / 2)
            normal = (-vertices[0][4], -vertices[0][3], vertices[0][5])
            inward = -record.side * section.normal_x, -record.side * section.normal_y
            if normal[0] * inward[0] + normal[1] * inward[1] < 0.95:
                continue
            inward_faces += 1
            du1, dv1 = vertices[1][6] - vertices[0][6], vertices[1][7] - vertices[0][7]
            du2, dv2 = vertices[2][6] - vertices[0][6], vertices[2][7] - vertices[0][7]
            determinant = du1 * dv2 - du2 * dv1
            derivative = [((points[1][i] - points[0][i]) * dv2 -
                           (points[2][i] - points[0][i]) * dv1) / determinant for i in range(2)]
            wall = record.barrier
            dx, dy = wall.bx - wall.ax, wall.by - wall.ay
            agreement = -record.side * (derivative[0] * dx + derivative[1] * dy)
            assert agreement / (math.hypot(*derivative) * math.hypot(dx, dy)) > 0.9999
    assert inward_faces == len(records) * 2


def test_visual_footing_paving_is_finite_convex_and_has_no_white_repaint() -> None:
    route = route_source()
    portals = exit_floor_portals(route)
    assert len(portals) == len(new_walls(route, load_recipe()))
    for portal in portals:
        polygon = Polygon(portal.polygon_xy_m)
        assert polygon.is_valid and polygon.exterior.is_ccw
        assert abs(polygon.convex_hull.area - polygon.area) < 1e-8
    scene = MeshScene()
    emit_exit_paving(scene, route)
    assert all(tile.materials == ["Runoff"] for tile in scene.tiles.values())
    assert all(math.isfinite(v) for tile in scene.tiles.values() for v in (*tile.minimum, *tile.maximum))


def test_prepared_physical_portals_exclude_visual_footing_clips(tmp_path: Path) -> None:
    from circuit_route_assets import prepare

    path = ROOT / "Attribution/Sources/jeddah/pit-lane-reconstruction.json"
    assets = prepare("jeddah", tmp_path, path, None)
    magic, walls, portals = struct.unpack_from("<8sII", (tmp_path / "pit_barriers.bin").read_bytes())
    assert magic == b"FFBAR2\0\0"
    assert len(route_source().barriers) == 272
    assert walls == 644 and portals == 30
    assert all(tile.name.startswith("Tile_Route_") for tile in assets.tiles)
    assert len(assets.portals) == 30
    assert len(assets.cosmetic_portals) == 409
    assert len(json.loads((tmp_path / "portals.json").read_text())["portals"]) == 30
    assert hashlib.sha256((tmp_path / "pit_lane.bin").read_bytes()).hexdigest() == "78b99f8f4b6817776b2161e675561c33ba8d99bc6755eb88b211c78db57a78a4"
