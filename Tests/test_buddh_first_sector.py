from __future__ import annotations

import itertools
from copy import copy
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as GeoPoint
from shapely.geometry import Polygon
from shapely.ops import unary_union
from venues.buddh_first_sector import (
    corrected,
    curb_template,
    float32,
    interpolate,
    native_width_controls,
    prepare,
    retained_road,
    scalar_hash,
)
from venues.buddh_first_sector_contact import packed_contact, write_contact
from venues.buddh_first_sector_dataclasses import (
    ContactTriangle,
    FirstSectorProposal,
    FirstSectorResult,
    RetainedBaseline,
)
from venues.buddh_first_sector_rows import face, fragments, lookup
from venues.buddh_first_sector_rows import interpolate as interpolate_vertex

SOURCE = Path("Attribution/Sources/buddh")


def test_two_millimetre_grass_island_gets_height_without_expanding_paving(
    tmp_path: Path,
) -> None:
    points = (
        (264.879, -107.037, 2.327),
        (264.881, -107.037, 2.327),
        (264.880, -107.0353, 2.327),
    )
    support = ((264.0, -108.0, 2.327), (266.0, -108.0, 2.327), (264.0, -106.0, 2.327))
    result = FirstSectorResult(
        (ContactTriangle(points, "grass", support),),
        (),
        0,
        0,
        0,
        0,
        0,
        0.0,
        {},
        Polygon(),
        0.0,
        0.0,
    )
    packed = packed_contact(result)
    height = [p for p in packed if p.height_only]
    assert height
    assert all(p.surface == "grass" for p in packed)
    header = tmp_path / "contact.inc"
    write_contact(result, header)
    text = header.read_text()
    assert "kBuddhFirstSectorGrass" not in text
    assert ", 0> kBuddhFirstSectorPaved" in text
    assert f", {len(height)}> kBuddhFirstSectorHeight" in text
    domain = Polygon([p[:2] for p in points])
    assert any(
        Polygon([p[:2] for p in t.points]).covers(domain.centroid) for t in height
    )
    for triangle in height:
        assert Polygon([p[:2] for p in triangle.points]).area * 2 >= float32(0.00001)
        for x, y, z in triangle.points:
            assert domain.distance(GeoPoint(x, y)) < 0.00104
            assert z == pytest.approx(2.327, abs=1e-6)


@pytest.fixture(scope="module")
def source_case() -> tuple[CircuitScene, FirstSectorProposal, RetainedBaseline]:
    scene = CircuitScene("buddh")
    proposal = TypeAdapter(FirstSectorProposal).validate_json(
        (SOURCE / "first-sector.json").read_bytes()
    )
    baseline = TypeAdapter(RetainedBaseline).validate_json(
        (SOURCE / "first-sector-baseline.json").read_bytes()
    )
    return scene, proposal, baseline


def test_literal_retained_native_controls_replay_complete_source_lattice(
    source_case: tuple[CircuitScene, FirstSectorProposal, RetainedBaseline],
) -> None:
    scene, _proposal, baseline = source_case
    road = retained_road(baseline, tuple(scene.road))
    assert len(road) == 8192
    assert scalar_hash(road) == baseline.scalar_rows_sha256


def test_profile_preserves_outside_rows_and_effective_outer_reach(
    source_case: tuple[CircuitScene, FirstSectorProposal, RetainedBaseline],
) -> None:
    scene, proposal, baseline = source_case
    road = retained_road(baseline, tuple(scene.road))
    candidate = tuple(corrected(proposal, road, p) for p in road)
    for old, new in zip(road, candidate, strict=True):
        assert (old.x, old.y, old.z, old.tx, old.ty, old.bank) == (
            new.x,
            new.y,
            new.z,
            new.tx,
            new.ty,
            new.bank,
        )
        assert old.half_width + old.left_shoulder == pytest.approx(
            new.half_width + new.left_shoulder, abs=1e-11
        )
        assert old.half_width + old.right_shoulder == pytest.approx(
            new.half_width + new.right_shoulder, abs=1e-11
        )
        assert max(new.left_shoulder, new.right_shoulder) < 24
        if old.station <= 304 or old.station >= 2680:
            assert new is old


def test_continuing_flare_has_no_control_shelves_or_overshoot(
    source_case: tuple[CircuitScene, FirstSectorProposal, RetainedBaseline],
) -> None:
    _scene, proposal, _baseline = source_case
    controls = [(p.station_m, p.width_m) for p in proposal.targets]
    for a, b in itertools.pairwise(controls):
        values = [
            interpolate(controls, a[0] + (b[0] - a[0]) * i / 32) for i in range(33)
        ]
        assert min(values) >= min(a[1], b[1]) - 1e-10
        assert max(values) <= max(a[1], b[1]) + 1e-10
    slope = (interpolate(controls, 2580.01) - interpolate(controls, 2579.99)) / 0.02
    assert slope > 0.03


def test_native_width_lattice_keeps_every_literal_outside_control(
    source_case: tuple[CircuitScene, FirstSectorProposal, RetainedBaseline],
) -> None:
    _scene, proposal, baseline = source_case
    rows = dict(native_width_controls(proposal, baseline))
    for station, width in baseline.width_controls:
        if station <= proposal.start_m or station >= proposal.end_m:
            assert rows[station] == width
    assert rows[304.0] == 20.0
    assert rows[2680.0] == 25.0
    native_positions = [float32(s) for s in rows]
    assert all(a < b for a, b in itertools.pairwise(native_positions))


def test_wrong_effective_native_shoulder_is_rejected_before_mutation(
    source_case: tuple[CircuitScene, FirstSectorProposal, RetainedBaseline],
) -> None:
    original, proposal, baseline = source_case
    scene = copy(original)
    road = retained_road(baseline, tuple(scene.road))
    scene.road = [corrected(proposal, road, p) for p in road]
    index = min(range(len(scene.road)), key=lambda i: abs(scene.road[i].station - 1429))
    scene.road[index] = replace(
        scene.road[index], right_shoulder=scene.road[index].right_shoulder - 0.25
    )
    before = scene.road
    with pytest.raises(ValueError, match="compiled right_shoulder"):
        prepare(scene, proposal, baseline)
    assert scene.road is before


def test_complete_corrected_t1_source_curb_is_retained(
    source_case: tuple[CircuitScene, FirstSectorProposal, RetainedBaseline],
) -> None:
    original, proposal, baseline = source_case
    scene = copy(original)
    road = retained_road(baseline, tuple(scene.road))
    scene.road = [corrected(proposal, road, p) for p in road]
    state = prepare(scene, proposal, baseline)
    template, curbs = curb_template(scene, state, False)
    expected = unary_union(template.terrain_cutouts)
    actual = unary_union([source.plan for source in curbs])
    assert expected.area > 50
    assert expected.difference(actual.buffer(0.0003)).area < 0.001
    assert min(v[5] for source in curbs for v in source.vertices) > 0.9


def test_split_preserves_original_planes_normals_and_uvs() -> None:
    scene = MeshScene()
    scene.triangle(
        "Tile_Test",
        "Grass",
        (0.0, 0.0, 1.0),
        (4.0, 0.0, 3.0),
        (0.0, 4.0, 2.0),
        ((0.1, 0.2), (1.1, 0.4), (0.3, 1.2)),
        ((0.0, 0.1, 0.99), (0.1, 0.0, 0.99), (0.05, 0.05, 0.995)),
    )
    name, tile = next(iter(scene.tiles.items()))
    source = face(tile, name, 0)
    clip = source.plan.intersection(
        Polygon([(0.3, 0.5), (3.1, 0.5), (3.1, 2.2), (0.3, 2.2)])
    )
    output = fragments(source, clip)
    assert output
    for triangle in output:
        for vertex in triangle:
            x, y = -vertex[1] / 100, -vertex[0] / 100
            expected = interpolate_vertex(source, x, y)
            assert vertex == pytest.approx(expected, abs=1e-12)
            assert vertex[2] / 100 == pytest.approx(1 + 0.5 * x + 0.25 * y, abs=1e-7)
            assert vertex[6] == pytest.approx(0.1 + 0.25 * x + 0.05 * y, abs=1e-7)
            assert vertex[7] == pytest.approx(0.2 + 0.05 * x + 0.25 * y, abs=1e-7)
            assert vertex[3] == pytest.approx(-0.1 + 0.025 * x + 0.0125 * y, abs=1e-7)
            assert vertex[4] == pytest.approx(-0.025 * x - 0.0125 * y, abs=1e-7)


def test_curb_foot_uses_lower_actual_plane_at_road_grass_step() -> None:
    scene = MeshScene()
    scene.triangle(
        "Tile_Test", "Road", (0.0, 0.0, 0.006), (1.0, 0.0, 0.006), (0.0, 1.0, 0.006)
    )
    scene.triangle(
        "Tile_Test",
        "Grass",
        (0.0, 0.0, -0.015),
        (0.0, 1.0, -0.015),
        (-1.0, 0.0, -0.015),
    )
    emitted = tuple(
        face(tile, name, offset)
        for name, tile in scene.tiles.items()
        for offset in range(0, len(tile.triangles), 100)
    )
    sample = lookup(emitted)
    assert sample(0.0, 0.5) == pytest.approx(-0.015, abs=1e-8)
