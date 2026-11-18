"""Jeddah close walls must clear real kerbs without retaining detached spurs."""

from __future__ import annotations

import bisect
import itertools
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import ShoulderBaseline
from pydantic import TypeAdapter
from shapely.geometry import LinearRing
from venues.jeddah_boundary import load_recipe, usable_ring

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Attribution/Sources/jeddah"


def test_close_wall_profile_clears_kerbs_and_preserves_pit_divider() -> None:
    recipe = load_recipe()
    profile = TypeAdapter(ShoulderBaseline).validate_json(
        (SOURCE / "shoulder-baseline.json").read_bytes()
    )
    rows = profile.controls
    positions = [row[0] for row in rows]

    def gap(station: float, side: int) -> float:
        index = max(0, min(len(rows) - 2, bisect.bisect_right(positions, station) - 1))
        a, b = rows[index], rows[index + 1]
        column = 1 if side > 0 else 2
        t = (station - a[0]) / (b[0] - a[0])
        return a[column] + t * (b[column] - a[column]) + 0.15

    assert profile.includes_pit_registration
    assert rows[0][0] == 0 and rows[-1][0] == recipe.length_m
    assert rows[0][1:] == rows[-1][1:]
    assert all(b[0] > a[0] for a, b in itertools.pairwise(rows))
    for start, end, side in recipe.kerbs:
        for i in range(int(end - start) + 1):
            clearance = gap(start + i, side) - recipe.kerb_inner_offset_m - recipe.kerb_width_m
            assert clearance >= 0.30
    for station in (0, 50, 100, 6020, 6100, 6174):
        assert abs(gap(station, -1) - 1.05) < 1e-6
    for station in (700, 1100, 1900, 3200, 4500, 5800):
        assert 0.64 <= gap(station, 1) <= 1.41
        assert 0.64 <= gap(station, -1) <= 1.41
    margin = json.loads((SOURCE / "kerb-margins.json").read_text())
    assert margin["controls_m"] == [[0, 0.15], [recipe.length_m, 0.15]]


def test_retraced_wall_chain_is_rejected_but_real_narrow_island_remains() -> None:
    assert not usable_ring(LinearRing([(0, 0), (1, 0), (2, 0), (3, 0), (2, 0), (1, 0), (0, 0)]))
    assert usable_ring(LinearRing([(0, 0), (5, 0), (5, 0.1), (0, 0.1)]))


def test_native_profile_matches_literal_source_and_green_ribbons_are_removed() -> None:
    text = (ROOT / "Source/FormulaForge/Native/track_data/jeddah_survey.inc").read_text()
    match = re.search(r"constexpr TrackShoulderPoint kJeddahShoulder\[\] = \{(.*?)\n\};", text, re.DOTALL)
    assert match
    actual = [[float(value) for value in row] for row in re.findall(
        r"\{([\d.]+)f, ([\d.]+)f, ([\d.]+)f\}", match[1]
    )]
    expected = json.loads((SOURCE / "shoulder-baseline.json").read_text())["controls"]
    assert len(actual) == len(expected)
    assert max(abs(a - b) for ra, rb in zip(actual, expected) for a, b in zip(ra, rb)) <= 0.000501
    assert all(a.material == "Runoff" for a in load_recipe().apron_ranges)
    assert "RunoffGreen" not in (ROOT / "tools/venues/jeddah.py").read_text()
