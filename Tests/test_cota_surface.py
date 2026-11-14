"""A bounded legal-edge correction must preserve COTA's existing road and protection."""

from __future__ import annotations

import csv
import gzip
import json
import struct
import sys
from pathlib import Path
from typing import cast

import pytest
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import Point, RoadStation
from circuit_scene import CircuitScene
from venues.cota import circuit_edges, t11_approach_edges


def test_compiled_lane_retains_alignment_elevation_and_protection() -> None:
    with (ROOT / 'build/circuits/cota/road.csv').open() as stream:
        current = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(stream)))
    source = ROOT / 'Attribution/Sources/cota'
    with gzip.open(source / 't11-racing-surface-baseline.csv.gz', 'rt') as stream:
        baseline = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(stream)))
    corrections = [json.loads((source / name).read_text()) for name in (
        't11-width-evidence.json', 'backstraight-width-evidence.json',
    )]
    assert len(current) == len(baseline)
    cores: list[list[float]] = [[] for _correction in corrections]
    for new, old in zip(current, baseline, strict=True):
        assert (new.station, new.x, new.y, new.z, new.tx, new.ty,
                new.bank, new.bank_quadratic, new.bank_fade) == (
                    old.station, old.x, old.y, old.z, old.tx, old.ty,
                    old.bank, old.bank_quadratic, old.bank_fade)
        for new_shoulder, old_shoulder in ((new.left_shoulder, old.left_shoulder),
                                            (new.right_shoulder, old.right_shoulder)):
            assert new.half_width + new_shoulder == pytest.approx(
                old.half_width + old_shoulder, abs=.001)
        if not any(correction['interval_m'][0] < new.station < correction['interval_m'][1]
                   for correction in corrections):
            assert new.half_width == pytest.approx(old.half_width, abs=.000002)
        for correction, core in zip(corrections, cores, strict=True):
            core_low, core_high = correction['source_supported_core_m']
            if core_low <= new.station <= core_high:
                core.append(new.half_width * 2)
    for correction, core in zip(corrections, cores, strict=True):
        assert core
        assert min(core) == pytest.approx(correction['core_legal_width_m_estimate'], abs=.001)
        assert max(core) == pytest.approx(correction['core_legal_width_m_estimate'], abs=.001)


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


def triangle_height(points: tuple[Point, Point, Point], x: float, y: float) -> float:
    a, b, c = points
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    return u * a[2] + v * b[2] + (1 - u - v) * c[2]


def test_flat_backstraight_paint_has_matching_native_contact() -> None:
    scene = CircuitScene('cota')
    scene.road_surfaces()
    circuit_edges(scene)
    painted: list[tuple[Point, Point, Point]] = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            if tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]] != 'RunoffRed':
                continue
            points = []
            for corner in range(3):
                wx, wy, wz = struct.unpack_from('<3f', tile.triangles, offset + 4 + corner * 32)
                points.append((-wy / 100, -wx / 100, wz / 100))
            painted.append((points[0], points[1], points[2]))
    raw = (ROOT / 'Content/Generated/COTA/Data/drive_surface.bin').read_bytes()
    assert raw[:8] == b'FFSURF1\0'
    count = struct.unpack_from('<I', raw, 8)[0]
    assert len(raw) == 12 + count * 36
    physical = []
    for row in struct.iter_unpack('<9f', raw[12:]):
        points = [cast(Point, row[i:i + 3]) for i in (0, 3, 6)]
        physical.append((points[0], points[1], points[2]))
    paint_shapes = [Polygon([point[:2] for point in triangle]) for triangle in painted]
    physical_shapes = [Polygon([point[:2] for point in triangle]) for triangle in physical]
    paint_index = STRtree(paint_shapes)
    physical_index = STRtree(physical_shapes)
    for station in (2540, 2580, 2860, 3100, 3340, 3400, 3560):
        sample = scene.at(station)
        for side in (-1, 1):
            for outside in (1.0, 2.8):
                x, y, _z = sample.point(side * (sample.half_width + outside))
                point = ShapePoint(x, y)
                paint_hits = [triangle_height(painted[int(i)], x, y)
                              for i in paint_index.query(point.buffer(.0002))
                              if paint_shapes[int(i)].buffer(.0002).covers(point)]
                contact_hits = [triangle_height(physical[int(i)], x, y)
                                for i in physical_index.query(point.buffer(.0002))
                                if physical_shapes[int(i)].buffer(.0002).covers(point)]
                assert paint_hits and contact_hits, (station, side, outside)
                assert max(paint_hits) - max(contact_hits) == pytest.approx(.006, abs=.004)

    # Native Height uses unbuffered XY cell lookup and barycentric containment.
    probes = [(1521.140380859375, 731.0155029296875)]
    for station in range(2521, 3590, 3):
        sample = scene.at(station)
        for side in (-1, 1):
            for outside in (.4, 1.0, 2.8):
                x, y, _z = sample.point(side * (sample.half_width + outside))
                probes.append((x, y))
    maximum_overlap_height_difference = 0.0
    for x, y in probes:
        point = ShapePoint(x, y)
        hits = []
        for raw_index in physical_index.query(point):
            i = int(raw_index)
            a, b, c = physical[i]
            determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
            v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
            if min(u, v, 1 - u - v) >= -.00001:
                hits.append(triangle_height(physical[i], x, y))
        assert hits, (x, y)
        maximum_overlap_height_difference = max(maximum_overlap_height_difference, max(hits) - min(hits))
    assert maximum_overlap_height_difference < .004
