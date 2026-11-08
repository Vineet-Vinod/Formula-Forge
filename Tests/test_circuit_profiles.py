"""Retained road evidence must reach the native profiles without roof or layout regressions."""

from __future__ import annotations

import bisect
import itertools
import math
import re
import struct
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from circuit_dataclasses import PitLane
from circuit_profiles import pit_shoulders

SOURCES = ROOT / "Attribution/Sources"
NATIVE = ROOT / "Source/FormulaForge/Native/track_data"
ELEVATION_FILES = tuple(sorted(SOURCES.glob("*/elevation-corrections.json")))
EVIDENCE_FILES = tuple(
    sorted((*SOURCES.glob("*/reference-index.json"), *SOURCES.glob("*/environment-recipe.json")))
)
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


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
Controls = list[tuple[float, float]]


class PublishedSource(BaseModel):
    published_relief_m: float


class Digitisation(BaseModel):
    coarse_registered_controls: Controls = Field(default_factory=list)


class Profile(BaseModel):
    controls: Controls
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
        profile.source_controls_m
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
    assert [turn.number for turn in review.turns] == list(range(1, 15))
    assert sum(turn.direction == "Right" for turn in review.turns) == 9
    text = (NATIVE / "australia_survey.inc").read_text()
    block = re.search(r"kAustraliaTurns\[\] = \{(.*?)\n\};", text, re.DOTALL)
    assert block is not None
    turns = re.findall(rf'\{{"([^"]+)",\s*({NUMBER})f,\s*TrackTurnDirection::(Left|Right)\}}', block[1])
    assert len(turns) == 14
    for native, source in zip(turns, review.turns, strict=True):
        name, fraction, direction = native
        assert (name, direction) == (source.name, source.direction)
        assert float(fraction) * review.published_length_m == pytest.approx(source.station_m, abs=0.05)
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
