"""Retained road evidence must reach the native profiles without roof or layout regressions."""

from __future__ import annotations

import bisect
import itertools
import json
import math
import re
import struct
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field, TypeAdapter
from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from circuit_dataclasses import AlignmentControls, PitLane, TurnRegistrations
from circuit_profiles import (
    native_profile,
    pit_shoulders,
    replace_profile,
    section_shoulders,
)

SOURCES = ROOT / "Attribution/Sources"
NATIVE = ROOT / "Source/FormulaForge/Native/track_data"
ELEVATION_FILES = tuple(sorted(SOURCES.glob("*/elevation-corrections.json")))
ALIGNMENT_FILES = tuple(sorted({
    path.parent / "alignment-refinement.json"
    if (path.parent / "alignment-refinement.json").exists() else path
    for pattern in ("*/alignment-corrections.json", "*/alignment-refinement.json")
    for path in SOURCES.glob(pattern)
}))
EVIDENCE_FILES = tuple(
    sorted((*SOURCES.glob("*/reference-index.json"), *SOURCES.glob("*/environment-recipe.json")))
)
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


@pytest.mark.parametrize("path", ALIGNMENT_FILES, ids=lambda path: path.parent.name)
def test_native_alignment_retains_the_registered_corner_reconstruction(path: Path) -> None:
    source = TypeAdapter(AlignmentControls).validate_json(path.read_bytes())
    text = (NATIVE / f"{path.parent.name}_survey.inc").read_text()
    block = re.search(r"constexpr TrackControlPoint \w+\[\] = \{(.*?)\n\};", text, re.DOTALL)
    assert block is not None
    controls = re.findall(rf"\{{\s*({NUMBER})f,\s*({NUMBER})f\s*\}}", block[1])
    assert len(controls) == len(source.controls_xy_m)
    for (x, y), expected in zip(controls, source.controls_xy_m, strict=True):
        assert (float(x), float(y)) == pytest.approx(expected, abs=0.000001)


@pytest.mark.parametrize("path", tuple(sorted(SOURCES.glob("*/alignment-refinement.json"))),
                         ids=lambda path: path.parent.name)
def test_refined_periodic_alignment_has_no_duplicate_closing_control(path: Path) -> None:
    source = TypeAdapter(AlignmentControls).validate_json(path.read_bytes())
    length = float(json.loads((path.parent / "reconstruction.json").read_text())["target_m"])
    assert len(source.controls_xy_m) == math.ceil(length)
    assert 0.5 < math.dist(source.controls_xy_m[-1], source.controls_xy_m[0]) < 1.5


def test_registered_racing_replacement_preserves_alignment_and_bank() -> None:
    original = (NATIVE / "portimao_survey.inc").read_text()
    elevation = native_profile(original, "Elevation")
    replacement = [(station, height + 1.25) for station, height in elevation]
    updated = replace_profile(original, "Elevation", replacement, elevation[-1][0])
    for actual, expected in zip(native_profile(updated, "Elevation"), replacement, strict=True):
        assert actual == pytest.approx(expected)
    assert native_profile(updated, "Width") == native_profile(original, "Width")
    strip = r"constexpr TrackElevationPoint \w+\[\] = \{.*?\n\};"
    assert re.sub(strip, "", updated, flags=re.DOTALL) == re.sub(strip, "", original, flags=re.DOTALL)
    assert replace_profile(updated, "Elevation", replacement, elevation[-1][0]) == updated


def test_portimao_keeps_the_fia_galp_and_direct_first_corner_configuration() -> None:
    source = SOURCES / "portimao"
    evidence = json.loads((source / "galp-plan-source.json").read_text())
    provenance = json.loads((source / "provenance.json").read_text())
    scale = provenance["route"]["uniform_scale"] / evidence["raw_controls_old_uniform_scale"]
    alignment = TypeAdapter(AlignmentControls).validate_json((source / "alignment-corrections.json").read_bytes())
    route = LineString([*alignment.controls_xy_m, alignment.controls_xy_m[0]])
    for x, y in evidence["raw_controls_xy_m"] + evidence["first_corner_raw_controls_xy_m"]:
        assert route.distance(Point(x * scale, y * scale)) < 1.5


@pytest.mark.parametrize(("slug", "rise", "fall", "tolerance"), [
    ("bahrain", 3.6, 5.6, 0.02),
    ("china", 3.0, 8.0, 0.02),
    ("turkey", 8.145, 8.145, 0.01),
    ("austria", 12.0, 9.3, 0.3),
])
def test_racing_grades_respect_retained_operator_constraints(
    slug: str, rise: float, fall: float, tolerance: float,
) -> None:
    controls = native_controls(slug, "Elevation")
    grades = [(b[1] - a[1]) * 100 / (b[0] - a[0]) for a, b in itertools.pairwise(controls)]
    assert max(grades) <= rise + tolerance
    assert min(grades) >= -fall - tolerance


@pytest.mark.parametrize("controls", [
    [(0.0, 14.0), (20.0, 18.0), (15.0, 16.0), (100.0, 14.0)],
    [(0.0, 14.0), (90.0, 14.0)],
    [(0.0, 14.0), (100.0, 18.0)],
    [(0.0, 14.0), (50.0, -1.0), (100.0, 14.0)],
])
def test_invalid_registered_width_never_replaces_native_text(controls: Controls) -> None:
    original = "constexpr TrackWidthPoint kFixtureWidth[] = {\n    {0.0f, 14.0f},\n    {100.0f, 14.0f}\n};"
    with pytest.raises(ValueError):
        replace_profile(original, "Width", controls, 100.0)


def test_pit_wall_profile_wraps_smoothly_without_repeated_application_drift() -> None:
    rows = [(float(station), 6.0, 7.0) for station in range(0, 201, 5)]
    profile = PitLane(180, 20, 1, 13, "Registered test pit", transition_m=10)
    result = pit_shoulders(rows, 200, profile)
    assert pit_shoulders(result, 200, profile) == result
    samples = {station: (left, right) for station, left, right in result}
    assert samples[0] == pytest.approx((0.1, 7))
    assert samples[200] == samples[0]
    assert samples[175] == pytest.approx((3.05, 7))
    assert samples[25] == pytest.approx((3.05, 7))
    assert samples[50] == pytest.approx((6, 7))


def test_local_bank_shoulder_preserves_opposite_side_and_upper_bridge(tmp_path: Path) -> None:
    rows = [
        (float(station), 0.4 if 4637 <= station <= 4667 else 6.0, 7.0)
        for station in range(0, 5001, 5)
    ]
    (tmp_path / "shoulder-corrections.json").write_text(json.dumps({
        "back_straight_bridge": {"start_m": 4637, "end_m": 4667, "shoulder_m": 0.4},
        "sections": [{
            "start_m": 2300, "end_m": 2417, "side": 1,
            "shoulder_m": 1.25, "transition_m": 25,
            "source_note": "Registered G2 bank",
        }],
    }))
    result = section_shoulders(rows, 5000, tmp_path)
    assert section_shoulders(result, 5000, tmp_path) == result
    samples = {station: (left, right) for station, left, right in result}
    assert samples[2300] == pytest.approx((1.25, 7.0))
    assert samples[2417] == pytest.approx((1.25, 7.0))
    assert samples[2275] == pytest.approx((6.0, 7.0))
    assert samples[2442] == pytest.approx((6.0, 7.0))
    for station, left, right in rows:
        assert samples[station][1] == right
        if station < 2275 or station > 2442:
            assert samples[station][0] == left


Controls = list[tuple[float, float]]


class PublishedSource(BaseModel):
    published_relief_m: float


class Digitisation(BaseModel):
    coarse_registered_controls: Controls = Field(default_factory=list)


class Profile(BaseModel):
    controls: Controls
    registered_controls_m: Controls = Field(default_factory=list)
    source_controls_m: Controls = Field(default_factory=list)
    coarse_registered_controls: Controls = Field(default_factory=list)
    digitisation: Digitisation = Field(default_factory=Digitisation)
    source: PublishedSource | None = None
    relief_m: float | None = None


class EvidenceDocument(BaseModel):
    schema_version: int
    circuit: str


class RegisteredTurn(BaseModel):
    number: int
    name: str
    station_m: float
    direction: str


class LayoutReview(BaseModel):
    published_length_m: float
    turns: list[RegisteredTurn]


def native_controls(slug: str, kind: str) -> Controls:
    text = (NATIVE / f"{slug}_survey.inc").read_text()
    block = re.search(
        rf"constexpr Track{kind}Point \w+{kind}\[\] = \{{(.*?)\n\}};", text, re.DOTALL
    )
    assert block is not None, f"{slug}: missing native {kind} profile"
    rows = re.findall(rf"\{{\s*({NUMBER})f,\s*({NUMBER})f\s*\}}", block[1])
    assert rows, f"{slug}: empty native {kind} profile"
    return [(float(station), float(value)) for station, value in rows]


def value_at(controls: Controls, station: float) -> float:
    index = min(
        len(controls) - 2,
        max(0, bisect.bisect_right([point[0] for point in controls], station) - 1),
    )
    a, b = controls[index : index + 2]
    fraction = (station - a[0]) / (b[0] - a[0])
    return a[1] * (1 - fraction) + b[1] * fraction


@pytest.mark.parametrize("path", EVIDENCE_FILES, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_reference_and_environment_documents_are_readable(path: Path) -> None:
    evidence = EvidenceDocument.model_validate_json(path.read_bytes())
    assert evidence.schema_version >= 1
    assert evidence.circuit == path.parent.name


@pytest.mark.parametrize("path", ELEVATION_FILES, ids=lambda path: path.parent.name)
def test_elevation_controls_are_finite_ordered_and_close_the_lap(path: Path) -> None:
    controls = Profile.model_validate_json(path.read_bytes()).controls
    assert len(controls) > 2
    assert all(math.isfinite(value) for control in controls for value in control)
    stations = [struct.unpack("<f", struct.pack("<f", control[0]))[0] for control in controls]
    assert all(b > a for a, b in itertools.pairwise(stations))
    assert controls[0][0] == 0
    assert controls[0][1] == pytest.approx(controls[-1][1], abs=0.0001)
    native = native_controls(path.parent.name, "Elevation")
    assert controls[-1][0] == pytest.approx(native[-1][0], abs=0.001)


@pytest.mark.parametrize("path", ELEVATION_FILES, ids=lambda path: path.parent.name)
def test_native_elevation_preserves_registered_source_anchors_and_extrema(path: Path) -> None:
    profile = Profile.model_validate_json(path.read_bytes())
    native = native_controls(path.parent.name, "Elevation")
    anchors = (
        profile.registered_controls_m
        or profile.source_controls_m
        or profile.coarse_registered_controls
        or profile.digitisation.coarse_registered_controls
    )
    extrema = [min(profile.controls, key=lambda p: p[1]), max(profile.controls, key=lambda p: p[1])]
    # Six centimetres allows dense-profile resampling and C++ decimal storage, not survey uncertainty.
    for station, elevation in [*anchors, *extrema, profile.controls[0], profile.controls[-1]]:
        assert value_at(native, station) == pytest.approx(elevation, abs=0.06), (
            f"{path.parent.name}: native road diverges from retained source at {station} m"
        )
    published_relief = profile.source.published_relief_m if profile.source else profile.relief_m
    assert published_relief is not None
    assert max(z for _, z in native) - min(z for _, z in native) == pytest.approx(
        published_relief, abs=0.06
    )


def test_monaco_tunnel_follows_the_road_below_fairmont() -> None:
    native = native_controls("monaco", "Elevation")
    assert value_at(native, 946) == pytest.approx(42, abs=0.1)
    tunnel = [value_at(native, station) for station in (1520, 1650, 1750, 1900, 2010)]
    assert max(tunnel) < 6.3
    assert max(tunnel) - min(tunnel) < 0.5
    assert value_at(native, 2130) < 1.5


def test_cota_first_corner_retains_the_published_hill() -> None:
    native = native_controls("cota", "Elevation")
    station, elevation = max(native, key=lambda point: point[1])
    assert 500 < station < 550
    assert elevation == pytest.approx(30.9, abs=0.06)
    assert value_at(native, 517) > 30.5


def test_zandvoort_banking_is_registered_and_raises_the_outside() -> None:
    source = Profile.model_validate_json(
        (SOURCES / "zandvoort/banking-corrections.json").read_bytes()
    ).controls
    native = native_controls("zandvoort", "Bank")
    assert source[0] == (0, 0)
    assert source[-1] == (4259, 0)
    assert all(b[0] > a[0] for a, b in itertools.pairwise(source))
    for station in (720, 780, 873, 980, 3600, 3786.67, 4000):
        assert value_at(native, station) == pytest.approx(value_at(source, station), abs=0.001)
    assert value_at(native, 720) == 0  # The previous recipe banked Gerlach instead of Hugenholtz.
    assert 11.8 < value_at(native, 873) < 11.9
    assert value_at(native, 3786.67) == pytest.approx(-18, abs=0.001)


def test_australia_has_the_current_fourteen_registered_turns() -> None:
    review = LayoutReview.model_validate_json((SOURCES / "australia/layout-review.json").read_bytes())
    registered = TypeAdapter(TurnRegistrations).validate_json(
        (SOURCES / "australia/turn-registration.json").read_bytes()
    ).turns
    assert [turn.number for turn in review.turns] == list(range(1, 15))
    assert sum(turn.direction == "Right" for turn in review.turns) == 9
    text = (NATIVE / "australia_survey.inc").read_text()
    block = re.search(r"kAustraliaTurns\[\] = \{(.*?)\n\};", text, re.DOTALL)
    assert block is not None
    turns = re.findall(rf'\{{"([^"]+)",\s*({NUMBER})f,\s*TrackTurnDirection::(Left|Right)\}}', block[1])
    assert len(turns) == 14
    for native, source, current in zip(turns, review.turns, registered, strict=True):
        name, fraction, direction = native
        assert (name, direction) == (source.name, source.direction)
        assert (current.official_turn, current.direction.title()) == (source.number, source.direction)
        assert float(fraction) * review.published_length_m == pytest.approx(current.native_station_m, abs=0.05)
    assert review.turns[8].station_m == 3234
    assert review.turns[9].station_m == 3361


def test_australia_removed_clark_chicane_is_a_continuous_sweep() -> None:
    text = (NATIVE / "australia_survey.inc").read_text()
    block = re.search(r"kAustraliaCenterline\[\] = \{(.*?)\n\};", text, re.DOTALL)
    assert block is not None
    rows = re.findall(rf"\{{\s*({NUMBER})f,\s*({NUMBER})f\s*\}}", block[1])
    points = [(float(x), float(y)) for x, y in rows]

    def point_at(station: float) -> tuple[float, float]:
        return points[round(station / 5278 * len(points)) % len(points)]

    deflections = []
    for station in range(2650, 3101, 25):
        a, b, c = point_at(station - 30), point_at(station), point_at(station + 30)
        first, second = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
        deflections.append(
            math.atan2(first[0] * second[1] - first[1] * second[0],
                       first[0] * second[0] + first[1] * second[1])
        )
    # The current map curves left here; the surviving T9/T10 chicane is farther down the lap.
    assert min(deflections) > math.radians(-2)
    assert max(deflections) < math.radians(15)
