"""Coastal water preserves islands, quays and physical racing corridors."""
from __future__ import annotations

import json
import math
import struct
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from pydantic import ValidationError
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from circuit_dataclasses import Building, RoadStation
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from venues.coastal_water import coastal_water
from venues.coastal_water_dataclasses import (
    CoastalWater,
    PierDeck,
    WaterPolygon,
    WaterWitness,
)


class CoastFixture(CircuitScene):
    def __init__(self, sources: Path) -> None:
        MeshScene.__init__(self)
        self.sources = sources
        self.road = [RoadStation(0, 10, 10, 3, 1, 0, .5, 0)]
        self.road_mask = box(9, 9, 11, 11)
        self.corridor_mask = box(8.5, 8.5, 11.5, 11.5)
        self.extra_corridors = []
        self.water_shapes = []
        self.terrain_cutouts = []
        self.buildings = [Building(1, 'Quay pavilion', 'yes', 3,
                                   [(14, 14), (16, 14), (16, 16), (14, 16)], {})]
        self.landmarks = []

    def geo(self, latitude: float, longitude: float) -> tuple[float, float]:
        return longitude, latitude


def coast_source() -> CoastalWater:
    return CoastalWater(1, [WaterPolygon([(0, 0), (20, 0), (20, 20), (0, 20)],
                                        [[(8, 8), (12, 8), (12, 12), (8, 12)]])],
                        [PierDeck(2, [(2, 6), (4, 6), (4, 8), (2, 8)], 2)],
                        [WaterWitness('Open water', 3, 3, True),
                         WaterWitness('Racing island', 10, 10, False),
                         WaterWitness('Pier', 3, 7, False)])


def test_water_keeps_islands_piers_quays_and_native_corridors(tmp_path: Path) -> None:
    data = coast_source()
    (tmp_path / 'coastal-water.json').write_text(json.dumps(asdict(data)))
    scene = CoastFixture(tmp_path)
    coastal_water(scene)
    wet = unary_union(scene.water_shapes)
    assert wet.area == pytest.approx(376)
    assert not wet.covers(Point(10, 10))
    assert not wet.covers(Point(3, 7))
    assert not wet.covers(Point(15, 15))
    assert wet.intersection(scene.corridor_mask).is_empty
    assert scene.extra_corridors == []
    water_triangles = []
    for tile in scene.tiles.values():
        for row in struct.iter_unpack('<I24f', tile.triangles):
            if tile.materials[row[0]] != 'Water':
                continue
            points = [(-row[i + 1] / 100, -row[i] / 100, row[i + 2] / 100) for i in (1, 9, 17)]
            assert [p[2] for p in points] == [1, 1, 1]
            polygon = Polygon([p[:2] for p in points])
            assert polygon.exterior.is_ccw
            water_triangles.append(polygon)
    assert unary_union(water_triangles).symmetric_difference(wet).area < 1e-6


def test_contradictory_water_witness_fails_before_drawing(tmp_path: Path) -> None:
    data = replace(coast_source(), witnesses=[WaterWitness('Unverified island', 3, 3, False)])
    (tmp_path / 'coastal-water.json').write_text(json.dumps(asdict(data)))
    scene = CoastFixture(tmp_path)
    with pytest.raises(ValueError, match='Unverified island'):
        coastal_water(scene)
    assert scene.water_shapes == []
    assert scene.tiles == {}


def test_nonfinite_sea_level_is_rejected(tmp_path: Path) -> None:
    data = replace(coast_source(), water_level_m=math.nan)
    (tmp_path / 'coastal-water.json').write_text(json.dumps(asdict(data)))
    with pytest.raises(ValidationError):
        coastal_water(CoastFixture(tmp_path))
