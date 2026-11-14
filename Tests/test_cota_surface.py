"""A bounded legal-edge correction must preserve COTA's existing road and protection."""

from __future__ import annotations

import csv
import gzip
import json
import struct
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import RoadStation
from circuit_scene import CircuitScene
from venues.cota import t11_approach_edges


def test_compiled_lane_retains_alignment_elevation_and_protection() -> None:
    with (ROOT / 'build/circuits/cota/road.csv').open() as stream:
        current = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(stream)))
    source = ROOT / 'Attribution/Sources/cota'
    with gzip.open(source / 't11-racing-surface-baseline.csv.gz', 'rt') as stream:
        baseline = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(stream)))
    evidence = json.loads((source / 't11-width-evidence.json').read_text())
    low, high = evidence['interval_m']
    core_low, core_high = evidence['source_supported_core_m']
    assert len(current) == len(baseline)
    core = []
    for new, old in zip(current, baseline, strict=True):
        assert (new.station, new.x, new.y, new.z, new.tx, new.ty,
                new.bank, new.bank_quadratic, new.bank_fade) == (
                    old.station, old.x, old.y, old.z, old.tx, old.ty,
                    old.bank, old.bank_quadratic, old.bank_fade)
        for new_shoulder, old_shoulder in ((new.left_shoulder, old.left_shoulder),
                                            (new.right_shoulder, old.right_shoulder)):
            assert new.half_width + new_shoulder == pytest.approx(
                old.half_width + old_shoulder, abs=.001)
        if not low < new.station < high:
            assert new.half_width == pytest.approx(old.half_width, abs=.000002)
        if core_low <= new.station <= core_high:
            core.append(new.half_width * 2)
    assert core and min(core) == pytest.approx(13, abs=.001)
    assert max(core) == pytest.approx(13, abs=.001)


def test_actual_kerb_and_flat_red_apron_stay_separate_and_follow_the_grade() -> None:
    scene = CircuitScene('cota')
    scene.road_surfaces()
    scene.runoff(2350, 2570, 1, 24, 'Runoff')
    t11_approach_edges(scene)
    counts = {'kerb': 0, 'apron': 0}
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            role = 'kerb' if material in {'Red', 'White'} else 'apron' if material == 'RunoffRed' else None
            if role is None:
                continue
            for i in range(3):
                wx, wy, wz = struct.unpack_from('<3f', tile.triangles, offset + 4 + i * 32)
                x, y, z = -wy / 100, -wx / 100, wz / 100
                row, _distance = scene.nearest(x, y)
                lane = (x - row.x) * row.ty - (y - row.y) * row.tx
                if not 2221 < row.station < 2379:
                    continue
                lateral = abs(lane) - row.half_width
                lift = z - row.height(lane)
                if material == 'White' and lateral < .1:
                    continue
                if role == 'kerb':
                    assert .12 < lateral < 1.01
                    assert .01 < lift < .055
                else:
                    assert .97 < lateral < 3.42
                    assert -.002 < lift < .015
                counts[role] += 1
    assert counts['kerb'] > 100 and counts['apron'] > 100
