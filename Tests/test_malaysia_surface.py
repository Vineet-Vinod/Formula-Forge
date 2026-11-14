"""Sepang's legal lane, outside pavement and final hairpin must agree."""

from __future__ import annotations

import csv
import gzip
import math
import struct
import sys
from itertools import pairwise
from pathlib import Path

import pytest
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import RoadStation
from circuit_scene import CircuitScene


@pytest.fixture(scope='module')
def road() -> tuple[list[RoadStation], list[RoadStation]]:
    with (ROOT / 'build/circuits/malaysia/road.csv').open() as stream:
        current = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(stream)))
    with gzip.open(ROOT / 'Attribution/Sources/malaysia/racing-surface-baseline.csv.gz', 'rt') as stream:
        baseline = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(stream)))
    return current, baseline


def test_legal_lane_preserves_alignment_and_the_existing_outside_corridor(
    road: tuple[list[RoadStation], list[RoadStation]],
) -> None:
    current, baseline = road
    assert len(current) == len(baseline)
    for new, old in zip(current, baseline, strict=True):
        assert (new.station, new.x, new.y, new.tx, new.ty) == (old.station, old.x, old.y, old.tx, old.ty)
        assert new.half_width == 8
        for new_shoulder, old_shoulder in ((new.left_shoulder, old.left_shoulder),
                                            (new.right_shoulder, old.right_shoulder)):
            change = new.half_width + new_shoulder - old.half_width - old_shoulder
            assert -.0015 <= change <= .055
            if new.station >= 5300 or new.station <= 300:
                assert abs(change) <= .0015
        if not 4800 <= new.station <= 5300:
            assert new.z == pytest.approx(old.z, abs=.000002)
    assert max(p.z for p in current) - min(p.z for p in current) == pytest.approx(
        max(p.z for p in baseline) - min(p.z for p in baseline), abs=.000002
    )


def test_final_hairpin_falls_outward_and_rises_through_its_exit(
    road: tuple[list[RoadStation], list[RoadStation]],
) -> None:
    current, _baseline = road
    core = [p for p in current if 5050 <= p.station <= 5095]
    assert core
    for p in core:
        assert p.height(-p.half_width) > p.height(p.half_width)
        assert p.slope(-p.half_width) < p.slope(p.half_width) < 0
        assert abs(p.slope(14)) < abs(p.slope(p.half_width))
    turn = [p for p in current if 5020 <= p.station <= 5130]
    assert all(b.z > a.z for a, b in pairwise(turn))
    assert all(p.bank == p.bank_quadratic == p.bank_fade == 0
               for p in current if p.station < 4980 or p.station > 5180)


def test_actual_packed_road_follows_the_native_curved_cross_section() -> None:
    scene = CircuitScene('malaysia')
    scene.road_surfaces('Grass')
    errors = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            if tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]] != 'Road':
                continue
            for vertex in range(3):
                x, y, z = struct.unpack_from('<3f', tile.triangles, offset + 4 + vertex * 32)
                x, y, z = -y / 100, -x / 100, z / 100
                p, _distance = scene.nearest(x, y)
                if not 5030 < p.station < 5130:
                    continue
                lane = (x - p.x) * p.ty - (y - p.y) * p.tx
                errors.append(abs(z - p.height(lane) - .006))
    assert errors and all(math.isfinite(error) for error in errors)
    assert max(errors) < .015


def test_baked_apron_contact_matches_the_actual_packed_pavement_vertices() -> None:
    from circuit_dataclasses import Point
    from circuit_partition_dataclasses import SceneManifest
    from shapely.geometry import Point as ShapePoint
    from shapely.geometry import box
    from shapely.strtree import STRtree

    scratch = ROOT / 'build/circuits/malaysia'
    manifest = TypeAdapter(SceneManifest).validate_json((scratch / 'manifest.json').read_bytes())
    visible: list[Point] = []
    for tile in manifest.tiles:
        if not tile.name.startswith('Tile_Street'):
            continue
        raw = (scratch / tile.file).read_bytes()
        for offset in range(12, len(raw), 100):
            material = tile.materials[struct.unpack_from('<I', raw, offset)[0]]
            if material not in {'Runoff', 'RunoffGreen', 'Gravel'}:
                continue
            for vertex in range(3):
                x, y, z = struct.unpack_from('<3f', raw, offset + 4 + vertex * 32)
                visible.append((-y / 100, -x / 100, z / 100))
    assert visible
    tree = STRtree([ShapePoint(x, y) for x, y, _z in visible])
    encoded = bytearray()
    native: set[Point] = set()
    for line in (ROOT / 'Source/FormulaForge/Native/track_data/malaysia_paving.inc').read_text().splitlines():
        if not line.startswith('    {{'):
            continue
        values = [float(value.strip().removesuffix('f')) for value in line.strip()[2:-3].split(',')]
        assert len(values) == 9
        packed = struct.pack('<9f', *values)
        encoded.extend(packed)
        values = list(struct.unpack('<9f', packed))
        native.update((values[i], values[i + 1], values[i + 2]) for i in (0, 3, 6))
    assert native
    contact = (ROOT / 'Content/Generated/Malaysia/Data/drive_surface.bin').read_bytes()
    assert contact[-len(encoded):] == encoded
    tolerance = .00025
    for point in native:
        x, y, _z = point
        candidates = tree.query(box(x - tolerance, y - tolerance, x + tolerance, y + tolerance))
        assert any(max(abs(a - b) for a, b in zip(point, visible[int(index)], strict=True)) <= tolerance
                   for index in candidates), point
