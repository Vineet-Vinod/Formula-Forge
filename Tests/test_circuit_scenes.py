"""Coverage and source-registration invariants for circuit scenery authoring."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import circuit_scene
from circuit_scene import CircuitScene


@pytest.fixture
def scene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CircuitScene:
    monkeypatch.setattr(circuit_scene, "ROOT", tmp_path)
    scratch = tmp_path / "build/circuits/fixture"
    source = tmp_path / "Attribution/Sources/fixture"
    data = tmp_path / "Content/Generated/Fixture/Data"
    for directory in (scratch, source, data):
        directory.mkdir(parents=True)
    length = math.tau * 40
    (scratch / "catalogue.json").write_text(
        json.dumps(
            {
                "slug": "fixture",
                "content_dir": "Fixture/Data",
                "length_m": length,
                "start_station_m": 0,
                "deck_separation": False,
            }
        )
    )
    (source / "provenance.json").write_text(
        json.dumps(
            {"origin": {"latitude": 0, "longitude": 0}, "route": {"uniform_scale": 1}}
        )
    )
    with (scratch / "road.csv").open("w") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "station",
                "x",
                "y",
                "z",
                "tx",
                "ty",
                "half_width",
                "bank",
                "left_shoulder",
                "right_shoulder",
            )
        )
        for i in range(128):
            angle = i * math.tau / 128
            writer.writerow(
                (
                    i * length / 128,
                    40 * math.cos(angle),
                    40 * math.sin(angle),
                    3.0,
                    -math.sin(angle),
                    math.cos(angle),
                    5.0,
                    0.0,
                    4.0,
                    4.0,
                )
            )
    (data / "terrain.bin").write_bytes(
        b"FFTRN1\0\0"
        + struct.pack("<ddfII", -80.0, -80.0, 8.0, 21, 21)
        + struct.pack("<441f", *([3.0] * 441))
    )
    return CircuitScene("fixture")


def surfaces(scene: CircuitScene, materials: set[str]) -> list[Polygon]:
    result = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] not in materials:
                continue
            vertices = [
                struct.unpack_from("<8f", tile.triangles, offset + 4 + corner * 32)
                for corner in range(3)
            ]
            result.append(Polygon([(-v[1] / 100, -v[0] / 100) for v in vertices]))
    return result


def test_terrain_and_verges_cover_cut_cells_without_holes(scene: CircuitScene) -> None:
    scene.road_surfaces()
    scene.terrain()
    coverage = unary_union(surfaces(scene, {"Road", "Grass"}))
    assert box(-80, -80, 80, 80).difference(coverage).area < 0.0005
    assert (
        scene.road_mask.difference(unary_union(surfaces(scene, {"Road"}))).area < 0.0005
    )


def test_runoff_does_not_cover_another_road_arm(scene: CircuitScene) -> None:
    scene.road_surfaces()
    scene.runoff(20, 70, 1, 30, "Gravel")
    gravel = unary_union(surfaces(scene, {"Gravel"}))
    assert gravel.intersection(scene.road_mask.buffer(-0.001)).area < 0.0001


def test_bounded_ground_patch_replaces_dsm_and_grounds_details(scene: CircuitScene) -> None:
    parcel = box(55, -10, 75, 10)
    scene.ground_patches.append((parcel, 4.0, 'Runoff'))
    assert scene.raw_ground(65, 0) == 4.0
    assert scene.raw_ground(76, 0) == 3.0
    scene.road_surfaces()
    scene.terrain()
    paving = unary_union(surfaces(scene, {'Runoff'}))
    grass = unary_union(surfaces(scene, {'Grass'}))
    assert paving.intersection(grass).area < 0.000001
    assert parcel.difference(paving).area < 0.000001
    assert paving.intersection(scene.road_mask).area < 0.000001


def test_ground_parcels_keep_priority_and_follow_authoring_edits(scene: CircuitScene) -> None:
    scene.ground_patches.extend([
        (box(50, -10, 70, 10), 4.0, 'Concrete'),
        (box(60, -10, 80, 10), 6.0, 'Concrete'),
    ])
    assert scene.raw_ground(65, 0) == 4.0
    assert scene.raw_ground(70, 0) == 4.0
    assert scene.raw_ground(75, 0) == 6.0
    scene.ground_patches[0] = (box(40, -10, 55, 10), 8.0, 'Concrete')
    assert scene.raw_ground(65, 0) == 6.0
    assert scene.raw_ground(45, 0) == 8.0
    scene.ground_patches.append((box(81, -10, 90, 10), 9.0, 'Concrete'))
    assert scene.raw_ground(85, 0) == 9.0
    scene.ground_patches.clear()
    assert scene.raw_ground(65, 0) == 3.0


def test_escape_surface_follows_road_instead_of_climbing_the_bank(
    scene: CircuitScene,
) -> None:
    scene.grid = replace(scene.grid, heights=tuple(30.0 for _ in scene.grid.heights))
    scene.road_surfaces()
    scene.runoff(5, 35, 1, 24, "Gravel")
    heights: list[float] = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] == "Gravel":
                heights.extend(
                    struct.unpack_from("<8f", tile.triangles, offset + 4 + vertex * 32)[
                        2
                    ]
                    / 100
                    for vertex in range(3)
                )
    assert heights
    assert min(heights) == pytest.approx(3.001, abs=0.0001)
    assert max(heights) == pytest.approx(3.001, abs=0.0001)


def test_grass_cannot_cover_registered_escape_paving(scene: CircuitScene) -> None:
    scene.road_surfaces()
    scene.runoff(5, 35, 1, 24, "Runoff")
    scene.terrain()
    grass = unary_union(surfaces(scene, {"Grass"}))
    paving = unary_union(surfaces(scene, {"Runoff"}))
    assert grass.intersection(paving.buffer(-0.00001)).area < 0.0001


def test_paint_sits_on_the_actual_sloped_apron(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(scene, "ground", lambda x, y: 3 + x * .1 + y * .2)
    scene.polygon_surface(box(0, 0, 4, 4), "Runoff", paved=True)
    scene.paint_surface(box(-1, 1, 3, 5), "White")
    painted = unary_union(surfaces(scene, {"White"}))
    assert painted.area == pytest.approx(9)
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "White":
                continue
            for vertex in range(3):
                wx, wy, wz = struct.unpack_from("<8f", tile.triangles, offset + 4 + vertex * 32)[:3]
                x, y, z = -wy / 100, -wx / 100, wz / 100
                assert z == pytest.approx(3 + x * .1 + y * .2 + .005, abs=.00001)


def test_positive_lane_is_right_of_source_tangent(scene: CircuitScene) -> None:
    sample = scene.at(0)
    x, y, _ = sample.point(3.0)
    assert sample.tx * (y - sample.y) - sample.ty * (x - sample.x) == pytest.approx(
        -3.0
    )


def test_periodic_sampling_handles_sub_ulp_negative_stations(scene: CircuitScene) -> None:
    first = scene.at(0)
    for station in (-math.ulp(0.0), -1e-20, 0.0, scene.length,
                    math.nextafter(scene.length, 0.0)):
        sample = scene.at(station)
        assert 0 <= sample.station < scene.length
        assert sample.point(0) == pytest.approx(first.point(0), abs=1e-8)


def test_barrier_lettering_reads_left_to_right_from_the_road(
    scene: CircuitScene,
) -> None:
    with (scene.scratch / "barriers.csv").open("w") as handle:
        writer = csv.writer(handle)
        writer.writerow(("ax", "ay", "bx", "by", "bottom", "top", "radius"))
        writer.writerows(((50, 0, 50, 1, 3, 4, 0.2), (30, 0, 30, 1, 3, 4, 0.2)))
    for side in (-1, 1):
        scene.branding(0, scene.length - 0.001, side, "PanelGreen")
    scene.barriers()
    panels = set()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "PanelGreen":
                continue
            points = [
                struct.unpack_from("<8f", tile.triangles, offset + 4 + vertex * 32)
                for vertex in range(3)
            ]
            a, b = points[:2]
            if b[6] <= a[6]:
                continue
            ax, ay, bx, by = -a[1] / 100, -a[0] / 100, -b[1] / 100, -b[0] / 100
            sample, _ = scene.nearest((ax + bx) / 2, (ay + by) / 2)
            outward_x, outward_y = (ax + bx) / 2 - sample.x, (ay + by) / 2 - sample.y
            assert (bx - ax) * outward_y - (by - ay) * outward_x > 0
            panels.add((ax, ay))
    assert len(panels) == 2


@pytest.mark.parametrize("interleaved", [False, True])
def test_barrier_lettering_remains_continuous_across_native_sample_jumps(
    scene: CircuitScene, interleaved: bool,
) -> None:
    with (scene.scratch / "barriers.csv").open("w") as handle:
        writer = csv.writer(handle)
        writer.writerow(("ax", "ay", "bx", "by", "bottom", "top", "radius"))
        rows = (
            (50, 0, 50, 1, 3, 4, 0.2), (50, 1, 50, 2, 3, 4, 0.2),
            (30, 0, 30, 1, 3, 4, 0.2), (30, 1, 30, 2, 3, 4, 0.2),
        )
        writer.writerows([rows[i] for i in (0, 2, 1, 3)] if interleaved else rows)
    for side in (-1, 1):
        scene.branding(0, scene.length - 0.001, side, "PanelGreen")
    scene.barriers()
    seams: dict[int, list[float]] = {}
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "PanelGreen":
                continue
            for corner in range(3):
                vertex = struct.unpack_from("<8f", tile.triangles, offset + 4 + corner * 32)
                if round(-vertex[0] / 100) == 1:
                    seams.setdefault(round(-vertex[1] / 1000), []).append(vertex[6])
    assert len(seams) == 2
    for coordinates in seams.values():
        assert len(coordinates) >= 4
        assert max(coordinates) - min(coordinates) < 0.000001


@pytest.mark.parametrize(
    ("classification", "expected"),
    (
        ({"building": "hotel"}, "hotel"),
        ({"building": "yes", "leisure": "bleachers"}, "grandstand"),
        ({"building": "yes", "grandstand": "yes"}, "grandstand"),
    ),
)
def test_multipolygon_buildings_keep_semantic_type(
    scene: CircuitScene, classification: dict[str, str], expected: str
) -> None:
    from circuit_dataclasses import OsmData
    from pydantic import TypeAdapter

    payload = {
        "elements": [
            {
                "type": "relation",
                "id": 7,
                "tags": {"type": "multipolygon", "height": "34 m", **classification},
                "members": [
                    {
                        "type": "way",
                        "ref": 9,
                        "role": "outer",
                        "geometry": [
                            {"lat": 0, "lon": 0},
                            {"lat": 0, "lon": 0.001},
                            {"lat": 0.001, "lon": 0.001},
                            {"lat": 0.001, "lon": 0},
                            {"lat": 0, "lon": 0},
                        ],
                    }
                ],
            }
        ]
    }
    scene.osm = [TypeAdapter(OsmData).validate_json(json.dumps(payload))]
    scene.buildings = scene._load_buildings()
    building = scene.footprint(7)
    assert building.use == expected
    assert building.height == 34
    assert Polygon(building.ring).area > 12000


@pytest.mark.parametrize("tree_form", ["broadleaf", "conifer"])
def test_leaf_geometry_samples_individual_atlas_cells(
    scene: CircuitScene, tree_form: str
) -> None:
    from venues.west_architecture import conifer

    if tree_form == "conifer":
        conifer(scene, (0.0, 0.0, 0.0), 10.0, 4)
    else:
        scene.broadleaf((0.0, 0.0, 0.0), 10.0, 4)
    leaves = 0
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "TreeCanopy":
                continue
            leaves += 1
            uv = [
                struct.unpack_from("<8f", tile.triangles, offset + 4 + i * 32)[6:]
                for i in range(3)
            ]
            assert max(p[0] for p in uv) - min(p[0] for p in uv) < 1 / 6
            assert max(p[1] for p in uv) - min(p[1] for p in uv) < 1 / 6
            assert {int(p[0] * 6) for p in uv} <= {2, 5}
            assert {int(p[1] * 6) for p in uv} <= {0, 1, 2}
    assert leaves > 0


def test_stand_roof_faces_up_on_either_side(scene: CircuitScene) -> None:
    for side in (-1, 1):
        scene.stand(10.0, 40.0, side, rows=6, roofed=True)
    roofs = 0
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "Roof":
                continue
            roofs += 1
            for corner in range(3):
                vertex = struct.unpack_from(
                    "<8f", tile.triangles, offset + 4 + corner * 32
                )
                assert vertex[5] > 0
    assert roofs > 0


def test_mapped_hooked_stand_preserves_its_grass_opening(scene: CircuitScene) -> None:
    from circuit_dataclasses import Building
    from venues.east_architecture import footprint_stand

    ring = [
        (50.0, -25.0),
        (80.0, -25.0),
        (80.0, -15.0),
        (60.0, -15.0),
        (60.0, 15.0),
        (80.0, 15.0),
        (80.0, 25.0),
        (50.0, 25.0),
    ]
    scene.buildings = [Building(1, "Hooked terrace", "grandstand", 7.0, ring, {})]
    scene.road_surfaces()
    footprint_stand(scene, 1, rows=10)
    concrete = unary_union([p for p in surfaces(scene, {"Concrete"}) if p.area > 1e-8])
    assert concrete.area > 300
    assert concrete.difference(Polygon(ring)).area < 0.0001
    assert concrete.intersection(box(61, -14, 79, 14)).area < 0.0001


def test_mapped_stand_front_follows_sloping_ground(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    from circuit_dataclasses import Building
    from venues.east_architecture import footprint_stand

    ring = [(50.0, -30.0), (70.0, -30.0), (70.0, 30.0), (50.0, 30.0)]
    scene.buildings = [Building(1, "Sloping terrace", "grandstand", 7.0, ring, {})]
    monkeypatch.setattr(scene, "ground", lambda x, y: 3.0 + y * 0.2)
    footprint_stand(scene, 1, rows=10)
    front_heights = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "Concrete":
                continue
            for corner in range(3):
                vertex = struct.unpack_from(
                    "<8f", tile.triangles, offset + 4 + corner * 32
                )
                x, y, z = -vertex[1] / 100, -vertex[0] / 100, vertex[2] / 100
                if abs(x - 50) < 0.001:
                    front_heights.append(z - scene.ground(x, y))
    assert front_heights
    assert max(front_heights) < 0.81


def test_mapped_stand_treads_clear_a_steep_rear_bank(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    from circuit_dataclasses import Building, Point
    from venues.east_architecture import footprint_stand

    ring = [(50.0, -30.0), (70.0, -30.0), (70.0, 30.0), (50.0, 30.0)]
    scene.buildings = [Building(1, "Bank terrace", "grandstand", 7.0, ring, {})]
    monkeypatch.setattr(scene, "ground", lambda x, y: 3.0 + (x - 50) * 0.9)
    original = scene.triangle
    treads: list[Point] = []

    def triangle(
        kind: str,
        material: str,
        a: Point,
        b: Point,
        c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if kind == "Building_StandTread":
            treads.extend((a, b, c))
        original(kind, material, a, b, c, uv, normals)

    monkeypatch.setattr(scene, "triangle", triangle)
    footprint_stand(scene, 1, rows=10)
    assert treads
    assert min(z - scene.ground(x, y) for x, y, z in treads) >= 0.1799


def test_bahrain_sail_fabric_has_opposite_top_and_underside_normals(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    from circuit_dataclasses import Building, Point
    from circuit_mesh import cross, sub
    from venues.east_architecture import footprint_stand

    scene.slug = "bahrain"
    ring = [(50.0, -30.0), (66.0, -30.0), (66.0, 30.0), (50.0, 30.0)]
    scene.buildings = [Building(1, "Tensile stand", "grandstand", 7.0, ring, {})]
    original = scene.triangle
    roof_faces: list[tuple[str, str, float]] = []

    def triangle(
        kind: str,
        material: str,
        a: Point,
        b: Point,
        c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if kind in ("Building_TensileRoof", "Building_TensileSoffit"):
            roof_faces.append((kind, material, cross(sub(b, a), sub(c, a))[2]))
        original(kind, material, a, b, c, uv, normals)

    monkeypatch.setattr(scene, "triangle", triangle)
    footprint_stand(scene, 1, rows=10, roof="sail")
    assert roof_faces
    for kind, material, normal_z in roof_faces:
        if kind == "Building_TensileRoof":
            assert material == "CanopyFabric" and normal_z > 0
        else:
            assert material == "CanopyFabric" and normal_z < 0


def test_smooth_terrain_shares_hillside_normals_without_moving_vertices(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    def hillside(x: float, y: float) -> float:
        return 0.2 * x * x + 0.3 * y * y + 0.1 * x * y

    def exported_vertices() -> list[tuple[float, ...]]:
        return [
            struct.unpack_from("<8f", tile.triangles, offset + 4 + corner * 32)
            for tile in scene.tiles.values()
            for offset in range(0, len(tile.triangles), 100)
            for corner in range(3)
        ]

    monkeypatch.setattr(scene, "ground", hillside)
    scene.grid = replace(
        scene.grid, x=0.0, y=0.0, step=1.0, columns=3, rows=2, heights=(0.0,) * 6
    )
    scene.corridor_mask = Polygon()
    patches = (box(0, 0, 1, 1), box(1, 0, 2, 1))
    for patch in patches:
        scene.polygon_surface(patch.difference(Polygon()), "Grass")
    faceted = exported_vertices()
    scene.tiles.clear()
    scene.terrain()
    smoothed = exported_vertices()
    assert [vertex[:3] for vertex in smoothed] == [vertex[:3] for vertex in faceted]
    normals: dict[tuple[float, float], list[tuple[float, ...]]] = {}
    for vertex in smoothed:
        x, y = -vertex[1] / 100, -vertex[0] / 100
        nx, ny, nz = -vertex[4], -vertex[3], vertex[5]
        normals.setdefault((x, y), []).append((nx, ny, nz))
        # A smooth normal must be perpendicular to both analytic hill tangents.
        assert nx + nz * (0.4 * x + 0.1 * y) == pytest.approx(0, abs=1e-6)
        assert ny + nz * (0.6 * y + 0.1 * x) == pytest.approx(0, abs=1e-6)
        assert nx * nx + ny * ny + nz * nz == pytest.approx(1, abs=1e-6)
        assert nz > 0
    for shared in ((1.0, 0.0), (1.0, 1.0)):
        assert len(normals[shared]) >= 2
        assert all(normal == normals[shared][0] for normal in normals[shared])
    assert any(a[3:6] != b[3:6] for a, b in zip(faceted, smoothed))


def test_dense_tiles_split_without_losing_vertex_or_material_data(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(circuit_scene, "MAX_TILE_TRIANGLES", 2)
    for index in range(5):
        scene.triangle(
            "Building_Dense",
            "White" if index % 2 else "Concrete",
            (index, 0, 0),
            (index + 0.5, 0, 1),
            (index, 0.5, 0),
            ((0.2, 0.3), (0.6, 0.7), (0.8, 0.9)),
            ((0, 0, 1), (0.6, 0, 0.8), (0, 0.6, 0.8)),
        )
    tile = next(iter(scene.tiles.values()))
    original = bytes(tile.triangles)
    original_bounds = tile.minimum + tile.maximum
    scene.save()
    records = json.loads((scene.scratch / "manifest.json").read_text())["tiles"]
    assert [record["triangles"] for record in records] == [2, 2, 1]
    bodies = []
    for record in records:
        payload = (scene.scratch / record["file"]).read_bytes()
        assert payload[:8] == b"FFLVM1\0\0"
        assert struct.unpack_from("<I", payload, 8)[0] == record["triangles"]
        assert record["materials"] == tile.materials
        body = payload[12:]
        bodies.append(body)
        for offset in range(4, len(body), 100):
            for vertex in range(3):
                point = struct.unpack_from("<3f", body, offset + vertex * 32)
                for axis in range(3):
                    assert record["bounds"][axis] <= point[axis] <= record["bounds"][axis + 3]
    assert b"".join(bodies) == original
    assert tile.minimum + tile.maximum == original_bounds


def test_t10_advertisement_follows_its_paving_without_expanding_physical_corridor(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    from circuit_dataclasses import RoadStation
    from venues.zandvoort import t10_infield_paint

    def hillside(x: float, y: float) -> float:
        return 3 + x * 0.1 + y * 0.2

    def straight(station: float) -> RoadStation:
        x = station - 2480
        return RoadStation(station, x, 0, hillside(x, 0), 1, 0, 6, 0, 7, 7)

    monkeypatch.setattr(scene, "at", straight)
    monkeypatch.setattr(scene, "ground", hillside)
    scene.road_mask = box(-10, -6.15, 120, 6.15)
    scene.corridor_mask = box(-10, -14, 120, 14)
    original_corridor = scene.corridor_mask.wkb
    t10_infield_paint(scene)
    assert scene.corridor_mask.wkb == original_corridor
    assert not scene.extra_corridors
    assert not scene.surface_ranges
    paving = unary_union(surfaces(scene, {"RunoffNavy"}))
    lettering = unary_union(surfaces(scene, {"GroundMSC"}))
    assert not lettering.is_empty
    assert lettering.difference(paving.buffer(0.00001)).area < 0.00001
    assert paving.intersection(scene.road_mask).area == 0
    assert paving.bounds[1] >= 8.0499
    scene.grid = replace(
        scene.grid, x=-10.0, y=-20.0, step=5.0, columns=27, rows=11,
        heights=(0.0,) * 297,
    )
    scene.verge_patches.append((scene.corridor_mask.difference(scene.road_mask), "Grass", straight(2500)))
    scene.terrain()
    grass = unary_union(surfaces(scene, {"Grass"}))
    assert grass.intersection(paving.buffer(-0.00001)).area < 0.00001
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "GroundMSC":
                continue
            for corner in range(3):
                wx, wy, wz, _, _, _, u, v = struct.unpack_from(
                    "<8f", tile.triangles, offset + 4 + corner * 32
                )
                x, y, z = -wy / 100, -wx / 100, wz / 100
                assert z == pytest.approx(hillside(x, y) + 0.006, abs=0.00001)
                assert -0.00001 <= u <= 1.00001
                assert -0.00001 <= v <= 1.00001


def test_opted_in_tight_inside_edges_have_one_grass_skin_and_unfolded_bands(
    scene: CircuitScene,
) -> None:
    from circuit_dataclasses import EdgeCorrection, RoadStation
    from shapely.geometry import LineString
    from shapely.strtree import STRtree

    points = [(float(x), 0.0) for x in range(41)]
    points.extend(
        (40 + 4 * math.cos(angle), -4 + 4 * math.sin(angle))
        for angle in (math.pi / 2 * (1 - i / 32) for i in range(1, 33))
    )
    points.extend([(44, -44), (-20, -44), (-20, 0), (0, 0)])
    path = LineString(points)
    scene.length = path.length
    road = []
    for index in range(512):
        station = index * scene.length / 512
        point = path.interpolate(station)
        before = path.interpolate((station - 0.01) % scene.length)
        after = path.interpolate((station + 0.01) % scene.length)
        dx, dy = after.x - before.x, after.y - before.y
        length = math.hypot(dx, dy)
        road.append(RoadStation(station, point.x, point.y, 3, dx / length, dy / length, 6, 0, 5, 5))
    scene.road = road
    scene.segments = STRtree([
        LineString([(a.x, a.y), (road[(i + 1) % len(road)].x, road[(i + 1) % len(road)].y)])
        for i, a in enumerate(road)
    ])
    scene.edge_corrections = [EdgeCorrection(30, 65, 1, "Four-metre radius inside a six-metre half-width")]
    original = tuple((p.x, p.y, p.z, p.bank, p.half_width) for p in road)
    scene.road_surfaces()
    scene.kerb(34, 60, 1, material="SeatYellow", alternate_material="Green")
    scene.terrain()
    assert tuple((p.x, p.y, p.z, p.bank, p.half_width) for p in road) == original
    kerbs = surfaces(scene, {"SeatYellow", "Green"})
    assert kerbs
    assert sum(shape.area for shape in kerbs) == pytest.approx(unary_union(kerbs).area, abs=0.00001)
    assert unary_union(kerbs).intersection(scene.road_mask.buffer(-0.02)).area < 0.00001
    white = unary_union(surfaces(scene, {"White"})).intersection(scene._edge_mask)
    assert not white.is_empty
    assert white.intersection(scene.road_mask.buffer(-0.3)).area < 0.00001
    grass = [shape.intersection(scene._edge_mask) for shape in surfaces(scene, {"Grass"})]
    assert sum(shape.area for shape in grass) == pytest.approx(unary_union(grass).area, abs=0.00001)
    assert unary_union(grass).intersection(scene.road_mask).area < 0.00001


def test_default_surface_packed_output_remains_stable(scene: CircuitScene) -> None:
    scene.road_surfaces()
    scene.kerb(10, 40, 1)
    scene.kerb(80, 120, -1)
    scene.polygon_surface(box(0, 0, 4, 4), "Runoff", paved=True)
    scene.paint_surface(box(1, 1, 3, 3), "White")
    digest = hashlib.sha256()
    for name, tile in sorted(scene.tiles.items()):
        digest.update(name.encode())
        digest.update(json.dumps(tile.materials).encode())
        digest.update(tile.triangles)
    assert digest.hexdigest() == "5e18626fb1f3353f76c20096b5e27d6c45b7743c01de1764709be3a7c0900257"


def test_skypark_closes_actual_concave_footprint(scene: CircuitScene, monkeypatch: pytest.MonkeyPatch) -> None:
    import gzip
    from collections import Counter

    from circuit_dataclasses import Building, OsmData, Point
    from circuit_mesh import cross, sub
    from pydantic import TypeAdapter
    from venues.singapore_waterfront import skypark

    source = Path(__file__).resolve().parents[1] / 'Attribution/Sources/singapore/environment.osm.json.gz'
    dataset = TypeAdapter(OsmData).validate_json(gzip.decompress(source.read_bytes()))
    mapped = next(e for e in dataset.elements if e.id == 116800998)
    latitude = sum(p.lat for p in mapped.geometry)/len(mapped.geometry)
    longitude = sum(p.lon for p in mapped.geometry)/len(mapped.geometry)
    ring = [(math.radians(p.lon-longitude)*6378137*math.cos(math.radians(latitude)),
             math.radians(p.lat-latitude)*6378137) for p in mapped.geometry]
    shape = Polygon(ring)
    assert shape.convex_hull.area > shape.area*1.01
    building = Building(mapped.id, 'SkyPark', 'commercial', 207, ring, mapped.tags)
    faces: list[tuple[str, Point, Point, Point]] = []

    def triangle(kind: str, material: str, a: Point, b: Point, c: Point,
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                 normals: tuple[Point, ...] | None = None) -> None:
        if kind in ('Building_SandsSkyparkDeck', 'Building_SandsSkyparkSoffit') or (
            kind == 'Building_SandsSkypark' and material == 'Cream'
        ):
            faces.append((kind, a, b, c))

    monkeypatch.setattr(scene, 'triangle', triangle)
    skypark(scene, building)
    edge_counts: Counter[tuple[Point, Point]] = Counter()
    for kind, a, b, c in faces:
        assert Polygon([a[:2], b[:2], c[:2]]).difference(shape).area < 1e-7
        if kind == 'Building_SandsSkyparkSoffit':
            assert cross(sub(b, a), sub(c, a))[2] < 0
        for start, end in ((a, b), (b, c), (c, a)):
            first = round(start[0], 7), round(start[1], 7), round(start[2], 7)
            last = round(end[0], 7), round(end[1], 7), round(end[2], 7)
            edge_counts[(first, last)] += 1
    assert edge_counts
    assert all(count == 1 and edge_counts[(end, start)] == 1
               for (start, end), count in edge_counts.items())


@pytest.mark.parametrize(
    ('arc_gap', 'center_chord', 'owner_z', 'nearest_z', 'expected_z'),
    [(31.612, 24.434, 62.09, 59.12, 59.12), (2373.0, 1.0, 6.2, 0.0, 6.2)],
    ids=['austria-local-uphill-bend', 'japan-separated-crossing'],
)
def test_surface_projection_distinguishes_local_bend_from_separate_branch(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
    arc_gap: float, center_chord: float, owner_z: float,
    nearest_z: float, expected_z: float,
) -> None:
    from circuit_dataclasses import RoadStation

    scene.length = 7004
    owner = RoadStation(4645, 0, 0, owner_z, 1, 0, 6, 0)
    nearest = RoadStation(owner.station - arc_gap, center_chord, 0, nearest_z, 1, 0, 6, 0)
    monkeypatch.setattr(scene, 'nearest', lambda x, y: (nearest, center_chord))
    monkeypatch.setattr(scene, 'at', lambda station: replace(owner, station=station))
    scene.polygon_surface(box(0, 0, .5, .5), 'Runoff', sample=owner)
    elevations = [
        struct.unpack_from('<8f', tile.triangles, offset + 4 + corner * 32)[2] / 100
        for tile in scene.tiles.values()
        for offset in range(0, len(tile.triangles), 100)
        for corner in range(3)
    ]
    assert elevations
    assert elevations == pytest.approx([expected_z] * len(elevations), abs=1e-5)


@pytest.mark.parametrize(
    ('upper_deck', 'separate_branch'),
    [(False, False), (False, True), (True, True)],
    ids=['joined-ground-verge', 'separate-lower-branch-verge', 'upper-japan-deck'],
)
def test_terrain_verges_keep_ground_join_and_upper_deck_heights(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch, upper_deck: bool, separate_branch: bool,
) -> None:
    from circuit_dataclasses import RoadStation

    scene.length = 5807
    scene.catalogue = replace(scene.catalogue, deck_separation=upper_deck)
    owner = RoadStation(4645, 0, 0, 6.2, 1, 0, 6, 0)
    lower = RoadStation(2272 if separate_branch else 4613.388, 1 if separate_branch else 24.434, 0, 0, 1, 0, 6, 0)
    scene.verge_patches = [(box(0, 0, .5, .5), 'Concrete' if upper_deck else 'Grass', owner)]
    scene.corridor_mask = box(-100, -100, 100, 100)
    scene.ground_corridor_mask = scene.corridor_mask
    monkeypatch.setattr(scene, 'ground', lambda x, y: 0.0)
    monkeypatch.setattr(scene, 'nearest', lambda x, y: (lower, 1.0))
    monkeypatch.setattr(scene, 'at', lambda station: replace(owner, station=station))
    scene.terrain()
    elevations = [
        struct.unpack_from('<8f', tile.triangles, offset + 4 + corner * 32)[2] / 100
        for tile in scene.tiles.values()
        for offset in range(0, len(tile.triangles), 100)
        for corner in range(3)
    ]
    expected = 6.2 - .015 if upper_deck or separate_branch else 0.0
    assert elevations
    assert elevations == pytest.approx([expected] * len(elevations), abs=1e-5)


def test_hockenheim_nord_rows_and_roof_ignore_exterior_dsm(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch
) -> None:
    from circuit_dataclasses import Building
    from venues.hockenheim_nord import nord_stand

    ring = [
        (radius * math.cos(angle), radius * math.sin(angle))
        for radius, angles in (
            (50., [-1.2 + 2.4 * index / 24 for index in range(25)]),
            (75., [1.2 - 2.4 * index / 24 for index in range(25)]),
        )
        for angle in angles
    ]
    scene.buildings.append(Building(232009789, "Nord fixture", "grandstand", 15, ring, {}))
    scene.road_surfaces()
    footprint = Polygon(ring)
    digest = hashlib.sha256()
    row_heights: set[float] = set()
    roof_heights: set[float] = set()

    def capture(
        kind: str, material: str,
        a: tuple[float, float, float], b: tuple[float, float, float],
        c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        digest.update(kind.encode() + material.encode() + struct.pack("<9d", *a, *b, *c))
        if kind == "Building_NordTreads":
            assert max(a[2], b[2], c[2]) == pytest.approx(min(a[2], b[2], c[2]))
            row_heights.add(round(a[2], 7))
        if kind == "Building_NordCanopyRoof":
            roof_heights.update(round(p[2], 7) for p in (a, b, c))
        assert footprint.buffer(1e-6).covers(Polygon([a[:2], b[:2], c[:2]]))

    monkeypatch.setattr(scene, "triangle", capture)
    monkeypatch.setattr(scene, "spectators", lambda *args: None)
    monkeypatch.setattr(scene, "ground", lambda x, y: 3.)
    nord_stand(scene)
    expected = digest.hexdigest()
    assert len(row_heights) == 24
    assert len(roof_heights) == 1
    assert max(abs(b - a - .46) for a, b in zip(sorted(row_heights), sorted(row_heights)[1:])) < 1e-6
    digest = hashlib.sha256()
    monkeypatch.setattr(scene, "ground", lambda x, y: 40 * math.sin(x) + 90)
    nord_stand(scene)
    assert digest.hexdigest() == expected


def test_monaco_quai_roof_preserves_component_hole_and_storey_step(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import asdict

    from circuit_dataclasses import Provenance, RetainedTerrainSource
    from pydantic import TypeAdapter
    from venues.monaco_dataclasses import PropertyEnvelope
    from venues.monaco_properties import property_envelopes

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/monaco'
    records = TypeAdapter(list[PropertyEnvelope]).validate_json(
        (retained / 'architecture/property-envelopes.json').read_bytes()
    )
    record = next(record for record in records if record.style == 'ruscino')
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    architecture = scene.sources / 'architecture'
    architecture.mkdir()
    (architecture / 'property-envelopes.json').write_text(json.dumps([asdict(record)]))
    (scene.sources / 'scenery-ground.json').write_bytes((retained / 'scenery-ground.json').read_bytes())
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    footprint = Polygon([scene.geo(lat, lon) for lon, lat in record.outer],
                        [[scene.geo(lat, lon) for lon, lat in ring] for ring in record.holes])
    roof_faces: list[tuple[tuple[float, float, float], ...]] = []

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        if kind == 'Building_QuaiAntoineResidential' and material == 'Roof':
            roof_faces.append((a, b, c))

    monkeypatch.setattr(scene, 'triangle', capture)
    monkeypatch.setattr(scene, 'ground', lambda x, y: 0.)
    property_envelopes(scene)
    expected = tuple(roof_faces)
    assert expected
    roofs = unary_union([Polygon([p[:2] for p in face]) for face in roof_faces])
    assert roofs.symmetric_difference(footprint).area < 1e-7
    assert len(footprint.interiors) == 1
    assert roofs.intersection(Polygon(footprint.interiors[0])).area < 1e-7
    vertices = {(round(x, 6), round(y, 6), round(z, 6)) for face in roof_faces for x, y, z in face}
    for ring, heights_m in [(record.outer, record.roof_outline_m),
                           *zip(record.holes, record.holes_roof_m, strict=True)]:
        for (lon, lat), z in zip(ring, heights_m, strict=True):
            x, y = scene.geo(lat, lon)
            assert (round(x, 6), round(y, 6), round(z - datum, 6)) in vertices
    assert max(p[2] for face in roof_faces for p in face) == pytest.approx(
        max([*record.roof_outline_m, *[z for ring in record.holes_roof_m for z in ring]]) - datum
    )
    heights: dict[tuple[float, float], set[float]] = {}
    for face in roof_faces:
        for x, y, z in face:
            heights.setdefault((round(x, 6), round(y, 6)), set()).add(z)
    assert any(max(values) - min(values) > 6.5 for values in heights.values())
    roof_faces.clear()
    monkeypatch.setattr(scene, 'ground', lambda x, y: 200. + 30 * math.sin(x))
    property_envelopes(scene)
    assert tuple(roof_faces) == expected


def test_monaco_ermanno_uses_primary_roof_envelope_over_stale_osm_storeys(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import asdict

    from circuit_dataclasses import Building, Provenance, RetainedTerrainSource
    from pydantic import TypeAdapter
    from venues.monaco_dataclasses import PropertyEnvelope
    from venues.monaco_properties import property_envelopes

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/monaco'
    record = next(record for record in TypeAdapter(list[PropertyEnvelope]).validate_json(
        (retained / 'architecture/property-envelopes.json').read_bytes()
    ) if record.style == 'ermanno')
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    architecture = scene.sources / 'architecture'
    architecture.mkdir()
    (architecture / 'property-envelopes.json').write_text(json.dumps([asdict(record)]))
    (scene.sources / 'scenery-ground.json').write_bytes((retained / 'scenery-ground.json').read_bytes())
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    measured = Polygon([scene.geo(lat, lon) for lon, lat in record.outer])
    detailed = measured.buffer(-.6, join_style='mitre')
    ring = list(detailed.exterior.coords)
    scene.buildings.append(Building(record.osm_id, record.name, 'apartments', 61, ring,
                                    {'building:levels': '18'}))
    maximum_z = -math.inf
    floor_levels: set[float] = set()

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        nonlocal maximum_z
        maximum_z = max(maximum_z, a[2], b[2], c[2])
        upward = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if kind == 'Building_ErmannoPalace' and material == 'Cream' and a[2] == b[2] == c[2] and upward > 1e-6:
            floor_levels.add(round(a[2], 7))

    monkeypatch.setattr(scene, 'triangle', capture)
    monkeypatch.setattr(scene, 'ground', lambda x, y: 200.)
    property_envelopes(scene)
    assert record.roof_peak_m - datum <= maximum_z <= record.roof_peak_m - datum + .2
    assert len(floor_levels) == 13
    assert unary_union(scene.terrain_cutouts).symmetric_difference(detailed).area < 1e-7


def test_monaco_rascasse_keeps_ground_open_below_the_measured_overhang(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gzip
    from dataclasses import asdict

    from circuit_dataclasses import Building, OsmData, Provenance, RetainedTerrainSource
    from pydantic import TypeAdapter
    from shapely.geometry import Point as ShapePoint
    from venues.monaco_dataclasses import PropertyEnvelope
    from venues.monaco_properties import property_envelopes, roof_height

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/monaco'
    record = next(record for record in TypeAdapter(list[PropertyEnvelope]).validate_json(
        (retained / 'architecture/property-envelopes.json').read_bytes()
    ) if record.style == 'rascasse')
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    architecture = scene.sources / 'architecture'
    architecture.mkdir()
    (architecture / 'property-envelopes.json').write_text(json.dumps([asdict(record)]))
    (scene.sources / 'scenery-ground.json').write_bytes((retained / 'scenery-ground.json').read_bytes())
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    dataset = TypeAdapter(OsmData).validate_json(gzip.decompress((retained / 'buildings.osm.json.gz').read_bytes()))
    mapped = next(element for element in dataset.elements if element.id == record.osm_id)
    ground = Polygon([scene.geo(p.lat, p.lon) for p in mapped.geometry])
    roof = Polygon([(*scene.geo(lat, lon), z - datum)
                    for (lon, lat), z in zip(record.outer, record.roof_outline_m, strict=True)])
    body = ground.intersection(roof)
    assert roof.difference(ground).area > 60
    scene.buildings.append(Building(record.osm_id, record.name, 'yes', 6.8,
                                    list(ground.exterior.coords), mapped.tags))
    top_faces: list[Polygon] = []
    soffit_faces: list[Polygon] = []

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        if kind != 'Building_LaRascasse':
            return
        shape = Polygon([a[:2], b[:2], c[:2]])
        normal_z = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if material == 'Roof':
            assert normal_z > 0
            top_faces.append(shape)
        elif material == 'Cream':
            assert normal_z < 0
            soffit_faces.append(shape)
        for x, y, z in (a, b, c):
            if roof.covers(ShapePoint(x, y)) and z < roof_height(roof, x, y) - .3:
                assert body.distance(ShapePoint(x, y)) < .1

    monkeypatch.setattr(scene, 'triangle', capture)
    monkeypatch.setattr(scene, 'ground', lambda x, y: 0.)
    property_envelopes(scene)
    assert unary_union(top_faces).symmetric_difference(roof).area < 1e-7
    assert unary_union(soffit_faces).symmetric_difference(roof).area < 1e-7
    assert unary_union(scene.terrain_cutouts).symmetric_difference(body).area < 1e-7
    witness_a = (137.655594, -237.110794, 1.78009999)
    witness_b = (138.006302, -238.584396, 1.78009999)
    ceiling = scene.fence_ceiling(witness_a, witness_b)
    assert ceiling == pytest.approx(5.8 - datum - .18 - .12)
    assert witness_a[2] + .95 < ceiling < witness_a[2] + 3.15


def test_overhead_fence_cap_preserves_default_mesh_and_concrete_wall(scene: CircuitScene) -> None:
    (scene.scratch / 'barriers.csv').write_text(
        'ax,ay,bx,by,bottom,top,radius\n'
        '48,-6,48,-2,3,3.95,0.15\n'
        '48,-2,48,2,3,3.95,0.15\n'
        '48,2,48,6,3,3.95,0.15\n'
        '48,6,47.5,10,3,3.95,0.15\n'
    )
    assert scene.overhead_soffits == []
    scene.barriers(street=True)
    digest = hashlib.sha256()
    original_concrete = bytearray()
    for name, tile in sorted(scene.tiles.items()):
        digest.update(name.encode())
        digest.update(bytes(tile.triangles))
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from('<I', tile.triangles, offset)[0]
            if tile.materials[slot] == 'Concrete':
                original_concrete.extend(tile.triangles[offset:offset + 100])
    # Same fixture emitted by the pre-hook6a970d40 barrier producer.
    assert digest.hexdigest() == '2054eb8c57c64a2dbbe380cab4461063f7c9aed783ee30cbd74d011495514b9a'
    scene.tiles.clear()
    scene.overhead_soffits.extend([
        ((47, -3, 5.9), (49, 7, 5.9), (49, -3, 5.9)),
        ((47, -3, 5.9), (47, 7, 5.9), (49, 7, 5.9)),
    ])
    scene.barriers(street=True)
    capped_concrete = bytearray()
    capped_vertices: list[float] = []
    for _name, tile in sorted(scene.tiles.items()):
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from('<I', tile.triangles, offset)[0]
            material = tile.materials[slot]
            if material == 'Concrete':
                capped_concrete.extend(tile.triangles[offset:offset + 100])
            elif material in ('Fence', 'Steel'):
                for corner in range(3):
                    vertex = struct.unpack_from('<8f', tile.triangles, offset + 4 + corner * 32)
                    x, y, z = -vertex[1] / 100, -vertex[0] / 100, vertex[2] / 100
                    if 47 <= x <= 49 and -3 <= y <= 7:
                        capped_vertices.append(z)
    assert capped_concrete == original_concrete
    assert capped_vertices
    assert max(capped_vertices) < 5.9 - .08


def test_monaco_property_roofs_never_add_z_to_terrain_masks(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gzip

    from circuit_dataclasses import Building, OsmData, Provenance
    from pydantic import TypeAdapter
    from venues.monaco_dataclasses import PropertyEnvelope
    from venues.monaco_properties import property_envelopes

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/monaco'
    records = TypeAdapter(list[PropertyEnvelope]).validate_json(
        (retained / 'architecture/property-envelopes.json').read_bytes()
    )
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    architecture = scene.sources / 'architecture'
    architecture.mkdir()
    (architecture / 'property-envelopes.json').write_bytes(
        (retained / 'architecture/property-envelopes.json').read_bytes()
    )
    (scene.sources / 'scenery-ground.json').write_bytes((retained / 'scenery-ground.json').read_bytes())
    identifiers = {record.osm_id for record in records}
    dataset = TypeAdapter(OsmData).validate_json(gzip.decompress((retained / 'buildings.osm.json.gz').read_bytes()))
    for element in dataset.elements:
        if element.type == 'way' and element.id in identifiers:
            scene.buildings.append(Building(element.id, '', 'yes', 6.8,
                                            [scene.geo(p.lat, p.lon) for p in element.geometry], element.tags))

    def discard(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        pass

    monkeypatch.setattr(scene, 'triangle', discard)
    monkeypatch.setattr(scene, 'ground', lambda x, y: 0.)
    property_envelopes(scene)
    assert scene.terrain_cutouts
    assert all(not mask.has_z for mask in scene.terrain_cutouts)
    assert any(mask.interiors for mask in scene.terrain_cutouts)
    owned = unary_union(scene.terrain_cutouts)
    clipped_ground = box(*owned.buffer(1).bounds).difference(owned)
    assert not clipped_ground.has_z
    scene.polygon_surface(clipped_ground, 'Grass')


def test_progressive_bank_road_and_contact_heights_follow_the_same_bowl(scene: CircuitScene) -> None:
    scene.road = [replace(sample, bank=.16, bank_quadratic=.01) for sample in scene.road]
    scene.road_surfaces()
    maximum_error = 0.0
    road_triangles = 0
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from('<I', tile.triangles, offset)[0]
            if tile.materials[slot] != 'Road':
                continue
            road_triangles += 1
            for corner in range(3):
                vertex = struct.unpack_from('<8f', tile.triangles, offset + 4 + corner * 32)
                x, y, z = -vertex[1] / 100, -vertex[0] / 100, vertex[2] / 100
                sample, _distance = scene.nearest(x, y)
                lane = (x - sample.x) * sample.ty - (y - sample.y) * sample.tx
                maximum_error = max(maximum_error, abs(z - sample.height(lane) - .006))
    assert road_triangles == len(scene.road) * 16
    assert maximum_error < .003
    sample = scene.at(40)
    assert sample.height(0) == sample.z
    assert sample.height(-5) == pytest.approx(sample.z - .55)
    assert sample.height(5) == pytest.approx(sample.z + 1.05)
    assert sample.slope(-5) == pytest.approx(.06)
    assert sample.slope(5) == pytest.approx(.26)


def test_zero_quadratic_keeps_the_existing_road_mesh(scene: CircuitScene) -> None:
    scene.road_surfaces()
    digest = hashlib.sha256()
    for name, tile in sorted(scene.tiles.items()):
        digest.update(name.encode())
        digest.update(bytes(tile.triangles))
    # Same unbanked fixture after the independently verified road-line winding fix.
    assert digest.hexdigest() == 'fa0fee113f911ca320e909f747faaa848d9d2aa8eea6c07db6629f1224fcf6a1'


def test_sachs_stand_keeps_mapped_rear_canopy_and_measured_foundations(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gzip
    from collections import Counter

    from circuit_dataclasses import Building, OsmData, Provenance
    from pydantic import TypeAdapter
    from shapely.geometry import LineString
    from venues.hockenheim_dataclasses import SachsStandSource
    from venues.hockenheim_sachs import SachsFoundation, build_sachs_stand

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/hockenheim'
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    (scene.sources / 'sachs-stand-correction.json').write_bytes((retained / 'sachs-stand-correction.json').read_bytes())
    (scene.sources / 'scenery-ground.json').write_text(json.dumps({
        'grid_file': 'unused', 'grid_sha256': '0' * 64, 'relative_datum_m': 100.0,
    }))
    osm = TypeAdapter(OsmData).validate_json(gzip.decompress((retained / 'buildings.osm.json.gz').read_bytes()))
    for element in osm.elements:
        if element.id in (232009782, 34400102):
            ring = [scene.geo(point.lat, point.lon) for point in element.geometry[:-1]]
            scene.buildings.append(Building(element.id, 'Sachs source fixture', 'grandstand', 15., ring, element.tags))
    stand = Polygon(scene.footprint(232009782).ring)
    roof = Polygon(scene.footprint(34400102).ring)
    source = TypeAdapter(SachsStandSource).validate_json((scene.sources / 'sachs-stand-correction.json').read_bytes())
    front = LineString(scene.footprint(232009782).ring[3:18])
    foundation = SachsFoundation(scene, source, front)
    digest = hashlib.sha256()
    roof_edges: Counter[tuple[tuple[float, ...], tuple[float, ...]]] = Counter()
    roof_faces: list[Polygon] = []
    rows: set[int] = set()

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        digest.update(kind.encode() + material.encode() + struct.pack('<9d', *a, *b, *c))
        triangle = Polygon([p[:2] for p in (a, b, c)])
        if material != 'Crowd':
            assert triangle.difference(stand.buffer(1e-6)).area < 1e-8
        if kind == 'Building_SachsTreadRoof':
            for x, y, z in (a, b, c):
                row = (z - foundation.front_height(x, y) - source.first_floor_m) / source.row_rise_m
                assert row == pytest.approx(round(row), abs=1e-8)
                rows.add(round(row))
        if kind.startswith('Building_SachsCanopy'):
            assert triangle.difference(roof.buffer(1e-6)).area < 1e-8
            vertices = [tuple(round(value, 6) for value in point) for point in (a, b, c)]
            for p, q in zip(vertices, vertices[1:] + vertices[:1]):
                roof_edges[tuple(sorted((p, q)))] += 1
        if kind == 'Building_SachsCanopyRoof':
            roof_faces.append(triangle)

    monkeypatch.setattr(scene, 'triangle', capture)
    monkeypatch.setattr(scene, 'raw_ground', lambda x, y: 999 + math.sin(x))
    monkeypatch.setattr(scene, 'ground', lambda x, y: 999 + math.cos(y))
    build_sachs_stand(scene)
    expected = digest.hexdigest()
    assert rows == set(range(source.row_count))
    assert roof.area / stand.area == pytest.approx(.3277287208964271)
    assert unary_union(roof_faces).symmetric_difference(roof).area < 1e-7
    assert set(roof_edges.values()) == {2}
    assert all(not shape.has_z for shape in scene.terrain_cutouts)
    for anchor in source.ground_anchors:
        x, y = scene.geo(anchor.latitude, anchor.longitude)
        assert foundation.ground(x, y) == pytest.approx(anchor.height_nhn_m - 100., abs=1e-7)
    digest = hashlib.sha256()
    monkeypatch.setattr(scene, 'raw_ground', lambda x, y: -999.)
    monkeypatch.setattr(scene, 'ground', lambda x, y: -999.)
    build_sachs_stand(scene)
    assert digest.hexdigest() == expected


def test_measured_bank_edge_surface_is_tessellated_across_the_narrow_fade(scene: CircuitScene) -> None:
    from circuit_dataclasses import RoadStation

    road = RoadStation(0, 0, 0, 3, 1, 0, 4.5, .11,
                       bank_fade=.25, bank_outer_positive=.015, bank_outer_negative=.03)

    def vertex(x: float, y: float) -> tuple[float, float, float]:
        return x, y, road.height(y)

    triangles = scene._bank_surface_triangles((vertex(0, 4.5), vertex(1, 24), vertex(0, 24)), vertex)
    assert len(triangles) > 2
    maximum_error = 0.
    for a, b, c in triangles:
        for weights in ((.25, .25, .5), (.5, .25, .25), (.25, .5, .25), (1 / 3, 1 / 3, 1 / 3)):
            point = tuple(sum(w * p[i] for w, p in zip(weights, (a, b, c), strict=True)) for i in range(3))
            maximum_error = max(maximum_error, abs(point[2] - road.height(point[1])))
    assert maximum_error < .003
    linear = RoadStation(0, 0, 0, 3, 1, 0, 4.5, .11)
    assert len(scene._bank_surface_triangles(
        ((0, 4.5, linear.height(4.5)), (1, 24, linear.height(24)), (0, 24, linear.height(24))),
        lambda x, y: (x, y, linear.height(y)),
    )) == 1


def test_rascasse_corner_occupies_ground_body_and_keeps_road_clear(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gzip
    from collections import Counter

    from circuit_dataclasses import Building, OsmData, Provenance
    from pydantic import TypeAdapter
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    from venues.monaco_dataclasses import PropertyEnvelope
    from venues.monaco_rascasse_frontage import rascasse_frontage

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/monaco'
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    architecture = scene.sources / 'architecture'
    architecture.mkdir()
    for filename in ('rascasse-frontage-correction.json', 'rascasse-frontage-ground-grid.json',
                     'property-envelopes.json'):
        (architecture / filename).write_bytes((retained / 'architecture' / filename).read_bytes())
    (scene.sources / 'scenery-ground.json').write_bytes((retained / 'scenery-ground.json').read_bytes())
    osm = TypeAdapter(OsmData).validate_json(gzip.decompress((retained / 'buildings.osm.json.gz').read_bytes()))
    element = next(element for element in osm.elements if element.id == 161885377)
    body_ring = [scene.geo(point.lat, point.lon) for point in element.geometry[:-1]]
    scene.buildings.append(Building(element.id, 'Actual quay ground body', 'yes', 25., body_ring, element.tags))
    scene.road = [replace(point, x=point.x + 180, y=point.y - 200, z=.3) for point in scene.road]
    scene.segments = STRtree([LineString([(a.x, a.y), (b.x, b.y)])
                             for a, b in zip(scene.road, scene.road[1:] + scene.road[:1])])
    scene.road_surfaces()
    records = TypeAdapter(list[PropertyEnvelope]).validate_json((architecture / 'property-envelopes.json').read_bytes())
    record = next(record for record in records if record.style == 'ruscino')
    roof = Polygon([scene.geo(lat, lon) for lon, lat in record.outer])
    body = Polygon(body_ring)
    digest = hashlib.sha256()
    top_faces: list[Polygon] = []
    edges: Counter[tuple[tuple[float, ...], tuple[float, ...]]] = Counter()

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        if not kind.startswith('Building_QuaiCorner'):
            return
        digest.update(kind.encode() + material.encode() + struct.pack('<9d', *a, *b, *c))
        triangle = Polygon([p[:2] for p in (a, b, c)])
        assert triangle.difference(body.buffer(.11)).area < 1e-8
        assert triangle.intersection(scene.road_mask).area < 1e-8
        if kind.startswith('Building_QuaiCornerPodium'):
            vertices = [tuple(round(value, 6) for value in point) for point in (a, b, c)]
            for p, q in zip(vertices, vertices[1:] + vertices[:1]):
                edges[tuple(sorted((p, q)))] += 1
        if kind == 'Building_QuaiCornerPodiumRoof':
            top_faces.append(triangle)

    monkeypatch.setattr(scene, 'triangle', capture)
    rascasse_frontage(scene)
    expected = digest.hexdigest()
    podium = unary_union(top_faces)
    assert podium.area == pytest.approx(12.79677009146649, abs=1e-6)
    assert podium.intersection(roof).area < 1e-7
    assert set(edges.values()) == {2}
    assert all(not patch.has_z for patch in scene.terrain_cutouts)
    assert all(patch.intersection(scene.road_mask).area < 1e-8 for patch in scene.terrain_cutouts)
    digest = hashlib.sha256()
    monkeypatch.setattr(scene, 'ground', lambda x, y: 40.)
    rascasse_frontage(scene)
    assert digest.hexdigest() == expected


def test_flame_towers_keep_actual_bases_primary_heights_and_closed_crowns(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gzip
    from collections import Counter

    from circuit_dataclasses import Building, OsmData, Provenance
    from pydantic import TypeAdapter
    from shapely.geometry import Point as ShapePoint
    from venues.baku_flames import flame_towers
    from venues.baku_skyline_dataclasses import FlameTowerRecipe

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/baku'
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    for filename in ('flame-towers.json', 'flame-towers.osm.json.gz'):
        (scene.sources / filename).write_bytes((retained / filename).read_bytes())
    recipe = TypeAdapter(FlameTowerRecipe).validate_json((scene.sources / 'flame-towers.json').read_bytes())
    osm = TypeAdapter(OsmData).validate_json(gzip.decompress((scene.sources / recipe.source_file).read_bytes()))
    plans = {element.id: Polygon([scene.geo(p.lat, p.lon) for p in element.geometry])
             for element in osm.elements}
    primary_heights = {253081850: 181.8, 253082095: 164.6, 253081914: 160.8}
    records = {record.osm_id: record for record in recipe.towers}
    shells: dict[int, Counter[tuple[tuple[float, ...], tuple[float, ...]]]] = {osm_id: Counter() for osm_id in records}
    z_bounds = {osm_id: [math.inf, -math.inf] for osm_id in records}
    bases: dict[int, list[Polygon]] = {osm_id: [] for osm_id in records}
    source_building = Building(1, 'Preserved source property', 'yes', 4., [(0, 0), (1, 0), (1, 1), (0, 1)], {})
    scene.buildings.append(source_building)
    scene.road_surfaces()

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        osm_id = next(osm_id for osm_id in records if kind.startswith(f'Building_FlameTower{osm_id}'))
        if kind != f'Building_FlameTower{osm_id}':
            return
        vertices = [tuple(round(value, 6) for value in point) for point in (a, b, c)]
        for p, q in zip(vertices, vertices[1:] + vertices[:1]):
            shells[osm_id][tuple(sorted((p, q)))] += 1
        for x, y, z in (a, b, c):
            assert plans[osm_id].buffer(.25).covers(ShapePoint(x, y))
            z_bounds[osm_id][0] = min(z_bounds[osm_id][0], z)
            z_bounds[osm_id][1] = max(z_bounds[osm_id][1], z)
        if material == 'Concrete':
            bases[osm_id].append(Polygon([point[:2] for point in (a, b, c)]))
        if normals is not None:
            assert all(sum(value * value for value in normal) == pytest.approx(1., abs=1e-10) for normal in normals)

    monkeypatch.setattr(scene, 'triangle', capture)
    monkeypatch.setattr(scene, 'ground', lambda x, y: 999.)
    monkeypatch.setattr(scene, 'raw_ground', lambda x, y: 999.)
    flame_towers(scene)
    assert scene.buildings[0] is source_building
    assert len(scene.buildings) == 4
    assert all(not polygon.has_z for polygon in scene.terrain_cutouts)
    for osm_id, record in records.items():
        assert z_bounds[osm_id][0] == pytest.approx(record.base_relative_m)
        assert z_bounds[osm_id][1] - z_bounds[osm_id][0] == pytest.approx(primary_heights[osm_id])
        assert set(shells[osm_id].values()) == {2}
        assert unary_union(bases[osm_id]).symmetric_difference(plans[osm_id]).area < 1e-7


def test_jeddah_named_residency_keeps_geometry_and_other_tiles(
    scene: CircuitScene,
) -> None:
    import gzip

    from circuit_dataclasses import Building, OsmData, Provenance
    from pydantic import TypeAdapter
    from venues.jeddah_skyline import skyline_residency

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/jeddah'
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    (scene.sources / 'skyline-residency.json').write_bytes((retained / 'skyline-residency.json').read_bytes())
    osm = TypeAdapter(OsmData).validate_json(gzip.decompress((retained / 'buildings.osm.json.gz').read_bytes()))
    element = next(element for element in osm.elements if element.id == 1244131504)
    ring = [scene.geo(point.lat, point.lon) for point in element.geometry[:-1]]
    scene.buildings.append(Building(element.id, 'Actual Diamond site', 'yes', 300., ring, element.tags))
    center = Polygon(ring).centroid
    scene.box('Building_DiamondConstructionCore', 'Concrete', (center.x, center.y, 100.), 13., 12., 200.)
    scene.box('Building_Unrelated', 'White', (1000., 1000., 10.), 10., 10., 20.)
    source_bounds = json.loads((scene.sources / 'skyline-residency.json').read_text())['actual_baseline_bounds_ue_cm']
    scene.tiles['Building_City_m1_04'].minimum = source_bounds[:3]
    scene.tiles['Building_City_m1_04'].maximum = source_bounds[3:]
    before = {name: (bytes(tile.triangles), tuple(tile.materials), tuple(tile.minimum + tile.maximum))
              for name, tile in scene.tiles.items()}
    skyline_residency(scene)
    changed = 'Building_City_m1_04'
    for name, tile in scene.tiles.items():
        triangles, materials, bounds = before[name]
        assert bytes(tile.triangles) == triangles
        assert tuple(tile.materials) == materials
        after = tile.minimum + tile.maximum
        expected = list(bounds)
        if name == changed:
            expected[3] += 60000.
        assert after == expected
    actor = (64900., -17600., 0.)

    def distance(bounds: tuple[float, ...] | list[float]) -> float:
        return math.sqrt(sum(max(lo - p, 0., p - hi) ** 2
                             for p, lo, hi in zip(actor, bounds[:3], bounds[3:]))) / 100

    assert distance(before[changed][2]) > 2050.
    tile = scene.tiles[changed]
    assert distance(tile.minimum + tile.maximum) < 1800.
    first_bounds = tile.minimum + tile.maximum
    skyline_residency(scene)
    assert tile.minimum + tile.maximum == first_bounds


def test_sachs_visible_foundation_joins_original_planes_without_dsm_replacement(
    scene: CircuitScene, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from circuit_dataclasses import Building, Provenance
    from pydantic import TypeAdapter
    from shapely.geometry import LineString
    from shapely.geometry import Point as ShapePoint
    from venues.hockenheim_dataclasses import SachsForecourtSource, SachsStandSource
    from venues.hockenheim_forecourt import build_sachs_forecourt, plane
    from venues.hockenheim_sachs import SachsFoundation

    retained = Path(__file__).resolve().parents[1] / 'Attribution/Sources/hockenheim'
    scene.provenance = TypeAdapter(Provenance).validate_json((retained / 'provenance.json').read_bytes())
    for name in ('sachs-forecourt-correction.json', 'sachs-stand-correction.json', 'scenery-ground.json'):
        (scene.sources / name).write_bytes((retained / name).read_bytes())
    source = TypeAdapter(SachsForecourtSource).validate_json((scene.sources / 'sachs-forecourt-correction.json').read_bytes())
    section = TypeAdapter(SachsStandSource).validate_json((scene.sources / 'sachs-stand-correction.json').read_bytes())
    ring = [scene.geo(anchor.latitude, anchor.longitude) for anchor in section.ground_anchors]
    scene.buildings.append(Building(232009782, 'Innentribuene', 'grandstand', 6.8, ring, {}))
    front = LineString(ring[3:18])
    foundation = SachsFoundation(scene, section, front)
    scene.road_surfaces()
    generated: list[tuple[str, tuple[tuple[float, float, float], ...]]] = []

    def capture(
        kind: str, material: str, a: tuple[float, float, float],
        b: tuple[float, float, float], c: tuple[float, float, float],
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[tuple[float, float, float], ...] | None = None,
    ) -> None:
        generated.append((kind, (a, b, c)))

    monkeypatch.setattr(scene, 'triangle', capture)
    monkeypatch.setattr(scene, 'ground', lambda x, y: 999.)
    monkeypatch.setattr(scene, 'raw_ground', lambda x, y: 999.)
    build_sachs_forecourt(scene)
    graded = [(Polygon([p[:2] for p in points]), points) for kind, points in generated
              if kind == 'Tile_SachsForecourt']
    paving = unary_union([shape for shape, _points in graded])
    assert paving.area == pytest.approx(291.249, abs=.001)
    assert paving.intersection(Polygon(ring)).area < 1e-6
    assert paving.intersection(scene.road_mask).area < 1e-8
    assert all(not polygon.has_z for polygon in scene.terrain_cutouts)
    for offset in (0., 1.5, 3., 6., 9.):
        point = front.interpolate(offset)
        candidates = [points for shape, points in graded if shape.distance(point) < .0001]
        assert candidates
        assert min(abs(plane((points[0], points[1], points[2]), point.x, point.y)
                       - foundation.ground(point.x, point.y)) for points in candidates) < .0005
    original = [(Polygon([p[:2] for p in triangle.points]), triangle.points)
                for triangle in source.triangles]
    for kind, points in generated:
        if kind != 'Tile_SachsExterior':
            continue
        for x, y, z in points:
            candidates = [vertices for shape, vertices in original if shape.distance(ShapePoint(x, y)) < .0001]
            assert candidates
            assert min(abs(z - plane(vertices, x, y)) for vertices in candidates) < 1e-8


def test_spa_refined_bank_tracks_the_existing_field_and_preserves_outer_planes() -> None:
    from shapely.geometry import Point as GeoPoint
    from shapely.geometry import Polygon
    from venues.spa_bank import BankSurface
    from venues.spa_bank_dataclasses import BankRefinement

    scene = CircuitScene("spa")
    scene.corridor_mask = Polygon()
    x, y = -451.3883804434962, -942.9109581362972
    step = scene.grid.step
    left = scene.grid.x + math.floor((x - scene.grid.x) / step) * step
    bottom = scene.grid.y + math.floor((y - scene.grid.y) / step) * step
    source = BankRefinement((left, bottom, left + step, bottom + step))
    surface = BankSurface(scene, source)
    road = list(scene.road)
    heights = tuple(scene.grid.heights)
    fine = step / source.subdivisions
    for column in range(source.subdivisions):
        for row in range(source.subdivisions):
            corners = [(left + column * fine, bottom + row * fine),
                       (left + (column + 1) * fine, bottom + row * fine),
                       (left + (column + 1) * fine, bottom + (row + 1) * fine),
                       (left + column * fine, bottom + (row + 1) * fine)]
            for indices in ((0, 1, 2), (0, 2, 3)):
                points = [surface.vertex(*corners[index])[0] for index in indices]
                cx, cy, cz = (sum(point[i] for point in points) / 3 for i in range(3))
                assert abs(cz - scene.ground(cx, cy)) < .03
    bounds = surface.region.bounds
    edge_x = bounds[0]
    edge_y = (bounds[1] + bounds[3]) / 2
    point, _normal = surface.vertex(edge_x, edge_y)
    indices = surface.index.query(GeoPoint(edge_x, edge_y).buffer(.000001), predicate="intersects")
    assert len(indices)
    a, b, c = surface.old_triangles[int(indices[0])]
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    u = ((b[1] - c[1]) * (edge_x - c[0]) + (c[0] - b[0]) * (edge_y - c[1])) / denominator
    v = ((c[1] - a[1]) * (edge_x - c[0]) + (a[0] - c[0]) * (edge_y - c[1])) / denominator
    old_z = u * a[2] + v * b[2] + (1 - u - v) * c[2]
    assert abs(point[2] - old_z) < 1e-9
    assert scene.road == road
    assert scene.grid.heights == heights


def test_dense_runoff_index_preserves_ground_and_refreshes_after_append(scene: CircuitScene) -> None:
    scene.road_surfaces('Grass')
    for index in range(80):
        start = index * 3.9 % scene.length
        scene.surface_ranges.append({'type': 'runoff', 'start_m': start,
                                     'end_m': (start + 21) % scene.length,
                                     'side': 1 if index % 2 else -1,
                                     'requested_width_m': 8 + index % 11, 'material': 'Gravel'})
    probes = [scene.at(index * 1.73).point((-1 if index % 2 else 1) * 26)[:2] for index in range(200)]
    expected = [scene.ground(*point) for point in probes]
    scene.slug = 'malaysia'
    assert [scene.ground(*point) for point in probes] == expected
    scene.surface_ranges.append({'type': 'runoff', 'start_m': 230., 'end_m': 20.,
                                 'side': -1, 'requested_width_m': 35., 'material': 'Gravel'})
    indexed = [scene.ground(*point) for point in probes]
    scene.slug = 'fixture'
    assert indexed == [scene.ground(*point) for point in probes]


@pytest.mark.parametrize(('kind', 'material'), [('Tile_Road', 'White'), ('Tile_Kerb', 'Red'), ('Tile_Kerb', 'White')])
@pytest.mark.parametrize('width', [.12, 1.0])
def test_road_and_kerb_tops_face_up_at_every_triangle_size(kind: str, material: str, width: float) -> None:
    from circuit_mesh import MeshScene, world

    mesh = MeshScene()
    points = ((17.1, -48.3, 4.4), (17.1, -47.5, 4.42), (17.1 + width, -47.5, 4.42))
    texture = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))
    mesh.triangle(kind, material, *points, texture)
    tile = next(iter(mesh.tiles.values()))
    values = struct.unpack_from('<24f', tile.triangles, 4)
    a, b, c = [values[i:i + 8] for i in (0, 8, 16)]
    assert (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0
    assert min(a[5], b[5], c[5]) > .99
    expected = {struct.pack('<3f', *world(point)): uv for point, uv in zip(points, texture, strict=True)}
    assert {struct.pack('<3f', *p[:3]): p[6:8] for p in (a, b, c)} == expected


def test_small_other_surface_and_building_underside_keep_their_winding() -> None:
    from circuit_mesh import MeshScene

    for kind in ('Tile_Field', 'Building_Roof'):
        mesh = MeshScene()
        mesh.triangle(kind, 'Concrete', (0, 0, 0), (0, .8, .02), (.12, .8, .02))
        tile = next(iter(mesh.tiles.values()))
        assert struct.unpack_from('<f', tile.triangles, 4 + 5 * 4)[0] < 0
