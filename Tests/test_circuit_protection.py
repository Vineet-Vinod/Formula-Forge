"""Source openings remove only the registered local physical/visible wall pieces."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from circuit_dataclasses import BarrierSegment, ProtectionOpening, RoadStation
from circuit_protection import filter_barriers, load_openings


def nearest_straight(x: float, y: float) -> tuple[RoadStation, float]:
    return RoadStation(x, x, 0, 0, 1, 0, 6, 0), abs(y)


def test_source_opening_splits_only_the_local_inside_wall() -> None:
    opening = ProtectionOpening(12, 18, 1, 12, (10, -20, 30, -6), 'Open grass island')
    inside: BarrierSegment = (0, -8, 40, -8, 1, 1.95, .15)
    opposite: BarrierSegment = (0, 8, 40, 8, 1, 1.95, .15)
    distant: BarrierSegment = (0, -25, 40, -25, 1, 1.95, .15)
    other_area: BarrierSegment = (100, -8, 140, -8, 1, 1.95, .15)
    result = filter_barriers([inside, opposite, distant, other_area], [opening], nearest_straight)
    assert result[0] == pytest.approx((0, -8, 12, -8, 1, 1.95, .15), abs=1e-7)
    assert result[1] == pytest.approx((18, -8, 40, -8, 1, 1.95, .15), abs=1e-7)
    assert result[2:] == [opposite, distant, other_area]


def test_another_road_branch_within_the_xy_box_is_preserved() -> None:
    opening = ProtectionOpening(12, 18, 1, 12, (10, -20, 30, -6), 'Open grass island')
    wall: BarrierSegment = (12, -8, 18, -8, 1, 1.95, .15)

    def another_branch(x: float, y: float) -> tuple[RoadStation, float]:
        return RoadStation(1000 + x, x, 0, 0, 1, 0, 6, 0), abs(y)

    assert filter_barriers([wall], [opening], another_branch) == [wall]


def test_absent_opening_source_is_an_identity(tmp_path: Path) -> None:
    walls: list[BarrierSegment] = [(0, -8, 40, -8, 1, 1.95, .15)]
    assert filter_barriers(walls, load_openings(tmp_path, 100), nearest_straight) is walls


@pytest.mark.parametrize('invalid', [float('nan'), -1])
def test_opening_source_rejects_invalid_distances(tmp_path: Path, invalid: float) -> None:
    (tmp_path / 'protection-openings.json').write_text(json.dumps({'sections': [{
        'start_m': 12, 'end_m': 18, 'side': 1, 'max_edge_offset_m': invalid,
        'bounds_xy_m': [10, -20, 30, -6], 'source_note': 'Invalid distance',
    }]}))
    with pytest.raises(ValidationError):
        load_openings(tmp_path, 100)
