"""Coverage and source-registration invariants for circuit scenery authoring."""

from __future__ import annotations

import csv
import json
import math
import struct
import sys
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


def test_positive_lane_is_right_of_source_tangent(scene: CircuitScene) -> None:
    sample = scene.at(0)
    x, y, _ = sample.point(3.0)
    assert sample.tx * (y - sample.y) - sample.ty * (x - sample.x) == pytest.approx(
        -3.0
    )


def test_barrier_lettering_reads_left_to_right_from_the_road(scene: CircuitScene) -> None:
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


def test_leaf_geometry_samples_individual_atlas_cells(scene: CircuitScene) -> None:
    scene.broadleaf((0.0, 0.0, 0.0), 10.0, 4)
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            slot = struct.unpack_from("<I", tile.triangles, offset)[0]
            if tile.materials[slot] != "TreeCanopy":
                continue
            uv = [
                struct.unpack_from("<8f", tile.triangles, offset + 4 + i * 32)[6:]
                for i in range(3)
            ]
            assert max(p[0] for p in uv) - min(p[0] for p in uv) < 1 / 6
            assert max(p[1] for p in uv) - min(p[1] for p in uv) < 1 / 6


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
