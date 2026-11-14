"""Context bodies must clear local streets and replace only their covered ground."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import MeshTile, Point
from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union
from shapely.strtree import STRtree
from venues import jeddah_context_ground
from venues.jeddah_context import build_context
from venues.jeddah_context_dataclasses import (
    ContextGroundFace,
    ContextGroundLookup,
    ContextResidency,
    MallArchitecture,
    SailArchitecture,
)
from venues.jeddah_context_ground import ground_at, sample
from venues.jeddah_context_shapes import rectangle
from venues.jeddah_context_skyline import context_residency
from venues.jeddah_mall import curved_front, validate_service_clearance
from venues.jeddah_sail import site_frame


@pytest.fixture(scope='module')
def context() -> tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                       list[tuple[str, str, ContextGroundFace]]]:
    folder = ROOT / 'Attribution/Sources/jeddah'
    sail = TypeAdapter(SailArchitecture).validate_json((folder / 'sail-architecture.json').read_bytes())
    mall = TypeAdapter(MallArchitecture).validate_json((folder / 'mall-architecture.json').read_bytes())
    scene = CircuitScene('jeddah')
    scene.road_surfaces('Runoff')
    records: list[tuple[str, str, ContextGroundFace]] = []
    originals: list[ContextGroundFace] = []
    old_faces = jeddah_context_ground.original_ground

    def original_faces(s: CircuitScene, cells: list[tuple[int, int, Polygon]]) -> list[ContextGroundFace]:
        faces = old_faces(s, cells)
        originals.extend(faces)
        return faces

    def capture(kind: str, material: str, a: Point, b: Point, c: Point,
                uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                normals: tuple[Point, ...] | None = None) -> None:
        area = cross(sub(b, a), sub(c, a))
        if sum(value * value for value in area) < 1e-12:
            return
        values = normals or ((0., 0., 0.),) * 3
        records.append((kind, material, ContextGroundFace((a, b, c), (values[0], values[1], values[2]))))
        if kind == 'Tile_JeddahContextGround':
            for p, tex in zip((a, b, c), uv, strict=True):
                assert tex == pytest.approx((p[0] / 8, p[1] / 8), abs=1e-10)

    grid, road, cutouts = scene.grid, list(scene.road), list(scene.terrain_cutouts)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(scene, 'triangle', capture)
        patch.setattr(jeddah_context_ground, 'original_ground', original_faces)
        build_context(scene, sail, mall)
    assert scene.grid == grid and scene.road == road and scene.terrain_cutouts == cutouts
    return scene, sail, mall, originals, records


def test_source_tower_is_separate_from_podium_and_has_recessed_balconies(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
) -> None:
    scene, sail, _mall, _originals, records = context
    frame, site = site_frame(sail, scene.geo)
    plate = rectangle(frame, 0, 0, sail.length_m, sail.width_m)
    assert plate.area == pytest.approx(79264 / 65, rel=.01)
    assert plate.area < site.area / 7
    rooms = [face for kind, _m, face in records if kind == 'Building_SailRecessedRooms']
    screens = [face for kind, _m, face in records if kind == 'Building_SailUpperWeatherScreen']
    slabs = [face for kind, _m, face in records if kind == 'Building_SailFloorSlabs']
    room_levels = {round(min(p[2] for p in face.points), 5) for face in [*rooms, *screens]}
    assert len(room_levels) == sail.floors
    for face in [*rooms, *screens]:
        assert all(plate.buffer(-.8).covers(ShapePoint(p[:2])) for p in face.points)
    assert screens
    assert all(material == 'Glass' for kind, material, _face in records
               if kind == 'Building_SailUpperWeatherScreen')
    occupied_limit = sail.base_relative_m + 243.7
    assert all(max(p[2] for p in face.points) <= occupied_limit
               for kind, material, face in records
               if kind == 'Building_SailRecessedRooms' and material == 'WarmGlass')
    assert len({round(p[2], 5) for face in slabs for p in face.points}) == 2 * (sail.floors + 1)
    top = max(p[2] for kind, _m, face in records if kind.startswith('Building_Sail') for p in face.points)
    assert top - sail.base_relative_m == pytest.approx(264.7, abs=1e-9)


def test_bowed_mall_facade_clears_estimated_service_and_parking_lane_widths(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
) -> None:
    scene, _sail, mall, _originals, records = context
    site = Polygon([scene.geo(lat, lon) for lon, lat in mall.site.outer_wgs84])
    body, frontage = curved_front(site, *mall.frontage_source_range, mall.frontage_inset_m)
    validate_service_clearance(body, mall, scene.geo)
    assert len(frontage) > 300
    assert body.difference(site).area < 1e-8
    projected = MultiLineString([[*tuple(p[:2] for p in face.points), face.points[0][:2]]
                                 for kind, _m, face in records if kind.startswith('Building_Mall')])
    for road in mall.service_roads:
        line = LineString([scene.geo(lat, lon) for lon, lat in road.path_wgs84])
        assert projected.distance(line) >= road.estimated_width_m / 2 + road.facade_clearance_m
    roof_heights = {round(p[2], 4) for kind, _m, face in records
                    if kind == 'Building_MallPrimaryGlazedRoof' for p in face.points}
    assert len(roof_heights) > 10


def test_covered_grid_cells_keep_all_original_outside_planes_normals_and_coverage(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
) -> None:
    scene, sail, mall, originals, records = context
    frame, sail_site = site_frame(sail, scene.geo)
    tower = rectangle(frame, 0, 0, sail.length_m, sail.width_m)
    mall_site = Polygon([scene.geo(lat, lon) for lon, lat in mall.site.outer_wgs84])
    mask = unary_union([sail_site, tower, mall_site])
    old_shapes = [Polygon([p[:2] for p in f.points]) for f in originals]
    index = STRtree(old_shapes)
    shapes = []
    for kind, _material, face in records:
        if kind != 'Tile_JeddahContextGround':
            continue
        shape = Polygon([p[:2] for p in face.points])
        shapes.append(shape)
        source = next(originals[int(i)] for i in index.query(shape.representative_point(), predicate='intersects'))
        for p, normal in zip(face.points, face.normals, strict=True):
            height, expected = sample(source, p[0], p[1])
            assert p[2] == pytest.approx(height, abs=1e-9)
            assert normal == pytest.approx(expected, abs=1e-9)
    expected = unary_union(old_shapes).difference(mask)
    actual = unary_union(shapes)
    assert expected.symmetric_difference(actual).area < 1e-7
    assert sum(s.area for s in shapes) == pytest.approx(expected.area, abs=1e-7)


def test_sail_residency_changes_only_named_csv_north_bounds(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene, _sail, _mall, _originals, _records = context
    source = TypeAdapter(ContextResidency).validate_json(
        (ROOT / 'Attribution/Sources/jeddah/context-residency.json').read_bytes()
    )
    tiles = {entry.tile_name: MeshTile(bytearray(b'preserved'),
                                      list(entry.actual_baseline_bounds_ue_cm[:3]),
                                      list(entry.actual_baseline_bounds_ue_cm[3:]), ['Glass'])
             for entry in source.tiles}
    diamond = MeshTile(bytearray(b'diamond'), [-179606., 1399., 35.], [-84195., 30075., 32815.], ['Concrete'])
    tiles['Building_City_m1_04'] = diamond
    with monkeypatch.context() as patch:
        patch.setattr(scene, 'tiles', tiles)
        context_residency(scene, source)
    for entry in source.tiles:
        tile = tiles[entry.tile_name]
        assert tile.triangles == b'preserved' and tile.materials == ['Glass']
        assert tile.minimum == [entry.actual_baseline_bounds_ue_cm[0] - entry.north_margin_m * 100,
                                *entry.actual_baseline_bounds_ue_cm[1:3]]
        assert tile.maximum == list(entry.actual_baseline_bounds_ue_cm[3:])
    assert diamond.minimum == [-179606., 1399., 35.]
    assert diamond.maximum == [-84195., 30075., 32815.]
    assert diamond.triangles == b'diamond'
    for entry in source.tiles:
        tiles[entry.tile_name].minimum = list(entry.actual_baseline_bounds_ue_cm[:3])
    tiles[source.tiles[1].tile_name].minimum[0] += 1.
    first_before = list(tiles[source.tiles[0].tile_name].minimum)
    with monkeypatch.context() as patch:
        patch.setattr(scene, 'tiles', tiles)
        with pytest.raises(ValueError, match='baseline bounds changed'):
            context_residency(scene, source)
    assert tiles[source.tiles[0].tile_name].minimum == first_before


def test_night_occupancy_and_fin_highlights_do_not_turn_the_facades_emissive(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
) -> None:
    _scene, _sail, _mall, _originals, records = context
    warm_area = 0.
    glazing_area = 0.
    warm_kinds = set()
    for kind, material, face in records:
        if material not in {'Glass', 'WarmGlass'}:
            continue
        normal = cross(sub(face.points[1], face.points[0]), sub(face.points[2], face.points[0]))
        area = sum(v * v for v in normal) ** .5 / 2
        glazing_area += area
        if material == 'WarmGlass':
            warm_area += area
            warm_kinds.add(kind)
    assert 0 < warm_area < 2000
    assert warm_area / glazing_area < .08
    assert {'Building_SailFinLightStrips', 'Building_SailLobbyGlazing',
            'Building_MallOccupiedStorefronts'} <= warm_kinds
    assert all(material != 'WarmGlass' for kind, material, _face in records
               if kind in {'Building_SailFloorSlabs', 'Building_MallPrimaryGlazedRoof',
                           'Building_MallCrossBoulevardRoof'})


def test_unsupported_bowed_frontage_fails_before_scene_mutation(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene, sail, mall, _originals, _records = context
    invalid = replace(mall, service_roads=(replace(mall.service_roads[0], estimated_width_m=12.),
                                           *mall.service_roads[1:]))
    cells = set(scene.emitted_terrain_cells)
    cutouts = list(scene.terrain_cutouts)

    def reject(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('An unsupported facade emitted geometry before clearance validation')

    with monkeypatch.context() as patch:
        patch.setattr(scene, 'triangle', reject)
        with pytest.raises(ValueError, match='service-road reserve'):
            build_context(scene, sail, invalid)
    assert scene.emitted_terrain_cells == cells and scene.terrain_cutouts == cutouts


def test_foundations_and_patio_retaining_close_against_actual_original_planes(
    context: tuple[CircuitScene, SailArchitecture, MallArchitecture, list[ContextGroundFace],
                   list[tuple[str, str, ContextGroundFace]]],
) -> None:
    _scene, sail, mall, originals, records = context
    shapes = tuple(Polygon([p[:2] for p in face.points]) for face in originals)
    lookup = ContextGroundLookup(tuple(originals), shapes, STRtree(shapes), unary_union(shapes).bounds)
    bottoms = {'Building_SailTowerFoundation': sail.foundation_bottom_relative_m,
               'Building_SailPodiumFoundation': sail.foundation_bottom_relative_m,
               'Building_MallLowRetailBody': mall.lower_ground_relative_m}
    checked = 0
    for kind, _material, face in records:
        if kind in bottoms:
            lower = [p for p in face.points if abs(p[2] - bottoms[kind]) < 1e-8]
            if len(lower) != 2:
                continue
            line = LineString([p[:2] for p in lower])
            for index in lookup.index.query(line, predicate='intersects'):
                cut = line.intersection(shapes[int(index)])
                if isinstance(cut, LineString) and not cut.is_empty:
                    for xy in cut.coords:
                        assert ground_at(lookup, xy[:2]) >= bottoms[kind] - 1e-8
                        checked += 1
        elif kind == 'Building_ContextCourtyardRetaining':
            lower = [p for p in face.points
                     if min(abs(p[2] - sail.base_relative_m), abs(p[2] - mall.street_relative_m)) > 1e-8]
            for p in lower:
                assert p[2] == pytest.approx(ground_at(lookup, p[:2]), abs=1e-9)
            if len(lower) == 2:
                midpoint = tuple((a + b) / 2 for a, b in zip(lower[0], lower[1], strict=True))
                assert midpoint[2] == pytest.approx(ground_at(lookup, midpoint[:2]), abs=1e-9)
    assert checked > 500
