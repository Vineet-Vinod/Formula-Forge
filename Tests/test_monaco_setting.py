"""The bridge and engineered garden must join retained ground without moving it."""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from circuit_dataclasses import Point
from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from venues import monaco, monaco_setting_scene
from venues.monaco_belvedere import half_disc
from venues.monaco_dataclasses import (
    BridgeApproach,
    CasaGardenSetting,
    CostaGroundFace,
    LarvottoBridge,
    SettingCypress,
)
from venues.monaco_landcover import interpolate
from venues.monaco_west_dataclasses import BelvedereArchitecture


@pytest.fixture(scope='module')
def setting() -> tuple[CircuitScene, list[CostaGroundFace], list[tuple[str, str, CostaGroundFace]]]:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    scene.tiles.clear()
    scene.terrain_cutouts.extend(Polygon(b.ring) for b in scene.buildings)
    monaco.casino_gardens(scene)
    originals: list[CostaGroundFace] = []
    records: list[tuple[str, str, CostaGroundFace]] = []
    old_faces = monaco_setting_scene.original_faces

    def original_faces(s: CircuitScene, cells: list[Polygon]) -> list[CostaGroundFace]:
        result = old_faces(s, cells)
        originals.extend(result)
        return result

    def capture(kind: str, material: str, a: Point, b: Point, c: Point,
                uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                normals: tuple[Point, ...] | None = None) -> None:
        area_normal = cross(sub(b, a), sub(c, a))
        if sum(value * value for value in area_normal) < 1e-12:
            return
        values = normals or ((0., 0., 0.),) * 3
        records.append((kind, material, CostaGroundFace((a, b, c), (values[0], values[1], values[2]))))
        if kind == 'Tile_CostaSetting':
            for point, texcoord in zip((a, b, c), uv, strict=True):
                assert texcoord == pytest.approx((point[0] / 8, point[1] / 8), abs=1e-10)

    grid, road, cutouts = scene.grid, list(scene.road), list(scene.terrain_cutouts)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(scene, 'triangle', capture)
        patch.setattr(monaco_setting_scene, 'original_faces', original_faces)
        monaco_setting_scene.costa_setting(scene)
    assert scene.grid == grid and scene.road == road and scene.terrain_cutouts == cutouts
    return scene, originals, records


def test_setting_replacement_covers_original_surfaces_once_and_preserves_all_outer_planes(
    setting: tuple[CircuitScene, list[CostaGroundFace], list[tuple[str, str, CostaGroundFace]]],
) -> None:
    scene, originals, records = setting
    original_shapes = [Polygon([p[:2] for p in f.points]) for f in originals]
    index = STRtree(original_shapes)
    surfaces = []
    for kind, _material, face in records:
        if kind in {'Tile_CostaSetting', 'Tile_WestCliff', 'Building_LarvottoApproach',
                    'Building_CasaGardenPatio', 'Building_CasaGardenTreads',
                    'Building_WestBelvedereRimWalk', 'Building_WestBelvedereRetainedGarden',
                    'Building_WestBelvedereParapetSeat'}:
            surfaces.append(Polygon([p[:2] for p in face.points]))
        if kind != 'Tile_CostaSetting':
            continue
        shape = Polygon([p[:2] for p in face.points])
        center = shape.representative_point()
        source = next(originals[int(i)] for i in index.query(center, predicate='intersects'))
        for point, normal in zip(face.points, face.normals, strict=True):
            height, expected_normal = interpolate(source, point[0], point[1])
            assert point[2] == pytest.approx(height, abs=1e-9), (shape.area, face, source)
            assert normal == pytest.approx(expected_normal, abs=1e-9)
        midpoint = tuple(sum(p[axis] for p in face.points) / 3 for axis in range(3))
        height, normal = interpolate(source, midpoint[0], midpoint[1])
        assert midpoint[2] == pytest.approx(height, abs=1e-9)
        assert tuple(sum(p[axis] for p in face.normals) / 3 for axis in range(3)) == pytest.approx(normal, abs=1e-9)
    belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / 'architecture/west-belvedere.json').read_bytes()
    )
    original = unary_union(original_shapes)
    expected = unary_union([original, half_disc(belvedere, belvedere.radius_m - .18)])
    candidate = unary_union(surfaces)
    assert candidate.symmetric_difference(expected).area < 1e-7
    assert sum(s.area for s in surfaces) == pytest.approx(expected.area, abs=1e-7)


def test_garden_landing_and_tread_edges_have_retaining_or_riser_closure(
    setting: tuple[CircuitScene, list[CostaGroundFace], list[tuple[str, str, CostaGroundFace]]],
) -> None:
    _scene, originals, records = setting
    levels: dict[float, list[Polygon]] = defaultdict(list)
    closures: dict[float, list[LineString]] = defaultdict(list)
    for kind, _material, face in records:
        if kind in {'Building_CasaGardenPatio', 'Building_CasaGardenTreads'}:
            assert max(p[2] for p in face.points) - min(p[2] for p in face.points) < 1e-9
            levels[round(face.points[0][2], 8)].append(Polygon([p[:2] for p in face.points]))
        if kind not in {'Building_CasaGardenRetaining', 'Building_CasaGardenRisers'}:
            continue
        for a, b in zip(face.points, (*face.points[1:], face.points[0]), strict=True):
            if abs(a[2] - b[2]) < 1e-9:
                closures[round(a[2], 8)].append(LineString([a[:2], b[:2]]))
    assert len(levels) >= 34
    for level, shapes in levels.items():
        boundary = unary_union(shapes).boundary
        assert boundary.difference(unary_union(closures[level]).buffer(3e-7)).length < 1e-5
    original_shapes = [Polygon([p[:2] for p in f.points]) for f in originals]
    index = STRtree(original_shapes)
    for kind, _material, face in records:
        if kind != 'Building_CasaGardenRetaining':
            continue
        tied = 0
        for point in face.points:
            marker = LineString([point[:2], (point[0] + 1e-10, point[1])]).centroid
            candidates = index.query(marker.buffer(1e-8))
            tied += any(original_shapes[int(i)].distance(marker) < 1e-8
                        and abs(interpolate(originals[int(i)], point[0], point[1])[0] - point[2]) < 1e-8
                        for i in candidates)
        assert tied >= 1


def test_source_stair_rhythm_and_held_property_limits(
    setting: tuple[CircuitScene, list[CostaGroundFace], list[tuple[str, str, CostaGroundFace]]],
) -> None:
    scene, _originals, records = setting
    config = TypeAdapter(CasaGardenSetting).validate_json(
        (scene.sources / 'architecture/casa-garden.json').read_bytes()
    )
    treads = [f for kind, _material, f in records if kind == 'Building_CasaGardenTreads']
    assert len(treads) == 2 * (22 + 12)
    assert scene.landmarks[-1]['central_stair_count'] == 22
    assert scene.landmarks[-1]['lower_stair_count'] == 12
    assert scene.landmarks[-1]['patio_property_exclusion_m2'] == pytest.approx(5.9313111071, abs=1e-6)
    assert config.patio_anchor_absolute_m < 30.05
    assert config.central_stair_bottom_absolute_m > config.lower_stair_top_absolute_m > config.lower_stair_bottom_absolute_m


def test_invalid_vegetation_support_fails_before_any_geometry_mutation(
    setting: tuple[CircuitScene, list[CostaGroundFace], list[tuple[str, str, CostaGroundFace]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene, _originals, _records = setting
    garden = TypeAdapter(CasaGardenSetting).validate_json(
        (scene.sources / 'architecture/casa-garden.json').read_bytes()
    )
    bridge = TypeAdapter(LarvottoBridge).validate_json(
        (scene.sources / 'architecture/larvotto-bridge.json').read_bytes()
    )
    approaches = TypeAdapter(list[BridgeApproach]).validate_json(
        (scene.sources / 'architecture/larvotto-approaches.json').read_bytes()
    )
    body = Polygon(scene.footprint(94399990).ring).representative_point()
    invalid = replace(garden, cypresses=(SettingCypress((body.x, body.y), 11., 1),))
    previous_cells = set(scene.emitted_terrain_cells)
    previous_cutouts = list(scene.terrain_cutouts)
    scene.emitted_terrain_cells.clear()

    def reject(kind: str, material: str, a: Point, b: Point, c: Point,
               uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
               normals: tuple[Point, ...] | None = None) -> None:
        raise AssertionError('An invalid support emitted geometry before its guard')

    monkeypatch.setattr(scene, 'triangle', reject)
    try:
        with pytest.raises(ValueError, match='cypress'):
            monaco_setting_scene.bridge_setting(scene, bridge, approaches, invalid)
        assert not scene.emitted_terrain_cells
        assert scene.terrain_cutouts == previous_cutouts
    finally:
        scene.emitted_terrain_cells.update(previous_cells)
