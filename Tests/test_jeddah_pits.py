"""The working apron must join the route plane and keep cars clear of equipment."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point, TerrainGrid
from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from venues.jeddah_facilities import pit_compound
from venues.jeddah_pits import (
    apron_floor_point,
    apron_point,
    pit_route_source,
    route_section,
    working_apron,
    working_lane_source,
)


class PitScene(CircuitScene):
    def __init__(self) -> None:
        super().__init__("jeddah")
        self.faces: list[tuple[str, str, tuple[Point, Point, Point]]] = []

    def triangle(self, kind: str, material: str, a: Point, b: Point, c: Point,
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                 normals: tuple[Point, ...] | None = None) -> None:
        self.faces.append((kind, material, (a, b, c)))


@pytest.fixture(scope="module")
def pits() -> PitScene:
    scene = PitScene()
    road, grid = list(scene.road), scene.grid
    pit_compound(scene)
    assert scene.road == road and scene.grid == grid
    return scene


def test_apron_has_exact_route_edge_and_uses_route_plane(pits: PitScene) -> None:
    route, source = pit_route_source(), working_lane_source()
    for station in range(6010, 6288, 7):
        sample = pits.at(station)
        section = route_section(route, station, sample.point(-sample.half_width - source.garage_front_offset_m))
        front = apron_point(sample, section, source, 0)
        edge = apron_point(sample, section, source, 1)
        assert edge == pytest.approx((section.x - section.normal_x * section.half_width,
                                     section.y - section.normal_y * section.half_width,
                                     section.z - section.cross_slope * section.half_width), abs=1e-12)
        lateral = (front[0] - section.x) * section.normal_x + (front[1] - section.y) * section.normal_y
        assert lateral < -7
        assert front[2] == pytest.approx(section.z + section.cross_slope * lateral, abs=1e-12)
        assert 5 < math.dist(front[:2], edge[:2]) < 8
    assert any(kind == "Tile_JeddahWorkingStrip" for kind, _, _ in pits.faces)
    assert sum(kind == "Tile_JeddahStopGuides" for kind, _, _ in pits.faces) == 40
    assert not any(kind == "Building_JeddahPitGarages" for kind, _, _ in pits.faces)


def test_parallel_stop_car_clears_garages_and_equipment(pits: PitScene) -> None:
    route, source = pit_route_source(), working_lane_source()
    obstacles = [(kind, face) for kind, _, face in pits.faces if kind.startswith("Building_")]
    for garage in source.stop_garage_centres:
        index = garage - 1
        station = source.start_m + 1.25 + index * source.bay_spacing_m + (source.service_gap_m if index >= 21 else 0)
        sample = pits.at(station)
        center = apron_floor_point(pits, route, source, station, source.stop_center_from_garage_m)
        body = Polygon([(center[0] + sample.tx * along + sample.ty * across,
                         center[1] + sample.ty * along - sample.tx * across)
                        for along, across in ((-2.46, -1.12), (2.46, -1.12), (2.46, 1.12), (-2.46, 1.12))])
        hits: list[str] = []
        for kind, face in obstacles:
            if max(p[2] for p in face) < center[2] + .08 or min(p[2] for p in face) > center[2] + 1.2:
                continue
            footprint = Polygon([p[:2] for p in face])
            shape = footprint if footprint.area > 1e-10 else LineString([p[:2] for p in face])
            if shape.intersects(body):
                hits.append(kind)
        assert not hits, (station, hits)
        assert body.area == pytest.approx(4.92 * 2.24)


def test_exit_variant_closes_retained_body_and_leaves_whole_fastlane_open() -> None:
    from venues.jeddah_pit_exit import exit_tip_mask, pit_exit_building, source_record

    scene = PitScene()
    scene.road_mask = Polygon()
    buildings, road = list(scene.buildings), list(scene.road)
    source = source_record()
    original = Polygon(scene.footprint(source.osm_id).ring)
    retained = original.difference(exit_tip_mask(source))
    assert isinstance(retained, Polygon)
    assert .75 < retained.area / original.area < .99
    pit_exit_building(scene)
    assert scene.buildings == buildings and scene.road == road
    route = pit_route_source()
    selected = [section for section in route.sections if 649 < section.distance < 716]
    corridor = Polygon([(section.x + section.normal_x * side * 2.2,
                         section.y + section.normal_y * side * 2.2)
                        for side, samples in ((-1, selected), (1, list(reversed(selected))))
                        for section in samples])
    roofs = []
    for kind, material, face in scene.faces:
        footprint = Polygon([point[:2] for point in face])
        shape = footprint if footprint.area > 1e-10 else LineString([point[:2] for point in face])
        assert not shape.intersects(corridor), (kind, material)
        if kind == "Building_Roof":
            roofs.append(footprint)
    assert roofs
    assert unary_union(roofs).area == pytest.approx(retained.area, abs=1e-6)


def test_working_floor_excludes_actual_terrain_and_keeps_paint_visible() -> None:
    scene = PitScene()
    working_apron(scene)
    floor = unary_union([Polygon([point[:2] for point in face])
                         for kind, _, face in scene.faces if kind == "Tile_JeddahWorkingApron"])
    exclusions = unary_union(scene.terrain_cutouts)
    assert floor.area > 1500
    assert floor.difference(exclusions).area < 1e-7
    paint = unary_union([Polygon([point[:2] for point in face]) for kind, _, face in scene.faces
                         if kind in ("Tile_JeddahWorkingStrip", "Tile_JeddahStopGuides", "Tile_JeddahStopMark")])
    assert paint.area > 200
    assert paint.difference(exclusions).area < 1e-7
    route, source = pit_route_source(), working_lane_source()
    center = apron_floor_point(scene, route, source, 6150, source.stop_center_from_garage_m)
    scene.grid = TerrainGrid(center[0] - 12, center[1] - 12, 6, 5, 5, (40.0,) * 25)
    scene.corridor_mask = Polygon()
    scene.faces.clear()
    scene.terrain("Grass")
    terrain = [Polygon([point[:2] for point in face]) for kind, _, face in scene.faces if kind == "Tile_Ground"]
    assert terrain
    assert sum(face.intersection(floor).area for face in terrain) < 1e-6


def test_garage_reveals_are_dark_and_ceiling_faces_down(pits: PitScene) -> None:
    reveals = [(material, face) for kind, material, face in pits.faces
               if kind == "Building_JeddahPitGarageReturns"]
    ceilings = [face for kind, _, face in pits.faces if kind == "Building_JeddahPitGarageCeilings"]
    assert reveals and ceilings
    assert all(material == "Black" for material, _ in reveals)
    assert all(cross(sub(face[1], face[0]), sub(face[2], face[0]))[2] < 0 for face in ceilings)


def test_upper_frontage_depth_stays_local_across_start_finish() -> None:
    from venues.jeddah_pit_details import detail_source, upper_bay

    scene = PitScene()
    a, b = scene.at(scene.length - 3), scene.at(3)
    detail = detail_source()
    upper_bay(scene, a, b, -a.half_width - 13, -b.half_width - 13, 4.6, detail)
    assert scene.faces
    assert all(math.hypot(point[0] - a.x, point[1] - a.y) < 30
               for _, _, face in scene.faces for point in face)
    assert any(kind == "Building_JeddahPitUpperReturns" for kind, _, _ in scene.faces)
    assert any(kind == "Building_JeddahPitBalconyRailPosts" for kind, _, _ in scene.faces)


def test_pit_frontage_and_workstations_preserve_main_racing_clearance(pits: PitScene) -> None:
    upper = [face for kind, _, face in pits.faces if kind in (
        "Building_JeddahPitLounges", "Building_JeddahPitUpperReturns", "Building_JeddahPitUpperMullions",
        "Building_JeddahPitBalconySlabs", "Building_JeddahPitBalconyFascias", "Building_JeddahPitBalconyRailPosts")]
    site = pits.ground_patches[0][0].buffer(3)
    assert upper
    for face in upper:
        assert Polygon([point[:2] for point in face]).difference(site).area < 1e-7
        assert all(site.covers(ShapePoint(point[:2])) for point in face)
    consoles = [face for kind, _, face in pits.faces if kind.startswith("Building_JeddahPitWall")]
    assert consoles
    for face in consoles:
        for point in face:
            sample, distance = pits.nearest(point[0], point[1])
            assert distance > sample.half_width + .85 + .18


def test_separate_interior_fixture_csv_has_all_bays_and_valid_aim(pits: PitScene, tmp_path: Path) -> None:
    import csv
    import hashlib

    from venues.jeddah_pit_details import (
        detail_source,
        write_entry_lights,
        write_interior_lights,
    )
    from venues.jeddah_pit_entry import source_record

    target = tmp_path / "pit_interior_lights.csv"
    write_interior_lights(pits, target)
    with target.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 45
    detail = detail_source()
    assert detail.interior_light_power == 1.0
    coordinates = '\n'.join(','.join(row[key] for key in
                            ('x', 'y', 'z', 'target_x', 'target_y', 'target_z')) for row in rows)
    assert hashlib.sha256(coordinates.encode()).hexdigest() == '81b8b72047994aa0a6e4aae9ab254e18de6b9ae44f720865bc40196a2cee8c21'
    for row in rows:
        values = [float(value) for value in row.values()]
        assert len(values) == 7 and all(math.isfinite(value) for value in values)
        assert values[2] > values[5] + 200
        assert values[6] == detail.interior_light_power
    entry_target = tmp_path / "pit_entry_lights.csv"
    write_entry_lights(pits, entry_target)
    with entry_target.open() as stream:
        entry_rows = list(csv.DictReader(stream))
    assert len(entry_rows) == source_record().wing_light_count == 8
    assert source_record().lobby_light_power == 3.0
    assert hashlib.sha256(entry_target.read_bytes()).hexdigest() == '7c52d9b63a527eed11e885459060673765023f3ebc1479cfff497f8672edc3f3'
    assert all(float(row["power"]) == source_record().lobby_light_power for row in entry_rows)
    assert all(float(row["z"]) > float(row["target_z"]) + 200 for row in entry_rows)


def test_service_cylinder_is_closed_round_outward_and_bounded() -> None:
    import struct
    from collections import Counter

    from circuit_mesh import MeshScene
    from venues.jeddah_pit_details import service_cylinder

    scene = MeshScene()
    service_cylinder(scene, (0.0, 0.0, 0.0), (.25, 0.0, 1.5))
    edges: Counter[tuple[Point, Point]] = Counter()
    volume = 0.0
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            material = struct.unpack_from('<I', tile.triangles, offset)[0]
            if tile.materials[material] != 'Black':
                continue
            points = []
            normals = []
            for corner in range(3):
                x, y, z, nx, ny, nz, _u, _v = struct.unpack_from('<8f', tile.triangles, offset + 4 + corner * 32)
                points.append((-y / 100, -x / 100, z / 100))
                normals.append((-ny, -nx, nz))
            a, b, c = points
            geometric = cross(sub(b, a), sub(c, a))
            assert sum(geometric[axis] * normals[0][axis] for axis in range(3)) > 0
            volume += sum(a[axis] * cross(b, c)[axis] for axis in range(3)) / 6
            for point in points:
                assert -.15 < point[0] < .4 and -.15 < point[1] < .15 and -.05 < point[2] < 1.55
            rounded = [tuple(round(value, 6) for value in point) for point in points]
            for first, last in ((rounded[0], rounded[1]), (rounded[1], rounded[2]), (rounded[2], rounded[0])):
                edges[(first, last)] += 1
    assert .05 < volume < .09
    assert edges
    assert all(count == edges[(last, first)] for (first, last), count in edges.items())


def test_presentation_casings_stay_inside_existing_console_footprints(pits: PitScene) -> None:
    desks = unary_union([Polygon([point[:2] for point in face]) for kind, _, face in pits.faces
                         if kind == 'Building_JeddahPitWallConsoleDesk']).buffer(.02)
    cases = [face for kind, _, face in pits.faces if kind in
             ('Building_JeddahPitConsoleHousing', 'Building_JeddahPitConsoleCheeks',
              'Building_JeddahPitConsoleHood', 'Building_JeddahPitConsoleEquipmentCase')]
    assert cases
    assert all(desks.covers(ShapePoint(point[:2])) for face in cases for point in face)
    fascia = [face for kind, material, face in pits.faces
              if kind.endswith('Fascias') and material == 'PanelDHL']
    assert fascia
    assert min(point[2] for face in fascia for point in face) > pits.at(0).z + 3.8
