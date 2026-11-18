from __future__ import annotations

import struct
from dataclasses import replace

import pytest
from circuit_portals_dataclasses import Barrier, Portal
from pit_routes import candidate, encode_barriers, encode_route
from pit_routes_dataclasses import PitRoute, PitSection


def route() -> PitRoute:
    return PitRoute('test',['https://example.org/source'],'Test source coordinates',[
        PitSection(10,20,3,2,5990,0,0,-1),
        PitSection(15,20,3.1,2,6000,5,0,-1),
        PitSection(20,20,3.2,2,6010,10,0,-1)],2,8,60)


def test_route_encoder_matches_runtime_frame_and_unwrapped_progress() -> None:
    data = encode_route(route())
    assert struct.unpack_from('<8sI3f',data) == (b'FFPIT2\0\0',3,2,8,60)
    assert struct.unpack_from('<9f',data,24) == (10,-20,3,2,5990,0,0,1,0)
    assert struct.unpack_from('<9f',data,24+72)[4] == 6010


def test_asymmetric_working_apron_uses_v3_without_changing_fast_lane_width() -> None:
    source = route()
    source.sections[1] = replace(source.sections[1], negative_extent=8)
    data = encode_route(source)
    assert struct.unpack_from('<8sI3f', data) == (b'FFPIT3\0\0', 3, 2, 8, 60)
    assert len(data) == 24 + 3 * 44
    assert struct.unpack_from('<11f', data, 24)[-2:] == (2, 2)
    middle = struct.unpack_from('<11f', data, 24 + 44)
    assert middle[3] == 2
    assert middle[-2:] == (2, 8)
    symmetric = replace(source, sections=[replace(s, positive_extent=s.half_width,
                                                   negative_extent=s.half_width) for s in route().sections])
    assert encode_route(symmetric) == encode_route(route())


def test_working_apron_cannot_shrink_the_fast_lane_or_exceed_runtime_extent() -> None:
    for extent in (1, 12.1, float('nan')):
        source = route()
        source.sections[1] = replace(source.sections[1], negative_extent=extent)
        with pytest.raises(ValueError):
            encode_route(source)


def test_portal_encoder_flips_north_and_preserves_runtime_counterclockwise() -> None:
    portal = Portal('entry',((0,0),(2,0),(2,2),(0,2)),1,3,'Exact test quad')
    data = encode_barriers([portal],[Barrier(0,1,2,1,1,2,.2)])
    assert struct.unpack_from('<8sII',data) == (b'FFBAR2\0\0',1,1)
    assert struct.unpack_from('<7f',data,16)[:6] == (0,-17,34,-17,17,34)
    quad = struct.unpack_from('<10f',data,44)
    points = [(quad[i],quad[i+1]) for i in range(0,8,2)]
    assert sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])) > 0
    assert quad[8:] == (17,51)


def test_route_rejects_a_station_jump_back_across_start_finish() -> None:
    source = route()
    source.sections[-1] = PitSection(20,20,3.2,2,10,10,0,-1)
    with pytest.raises(ValueError,match='reversing progress'):
        encode_route(source)


def test_route_rejects_unsupported_height_step() -> None:
    source = route()
    source.sections[-1] = PitSection(20,20,8,2,6010,10,0,-1)
    with pytest.raises(ValueError,match='excessive grade'):
        encode_route(source)


def test_portals_reject_a_nonconvex_cut() -> None:
    with pytest.raises(ValueError,match='strictly convex'):
        encode_barriers([Portal('bad',((0,0),(2,0),(1,.1),(0,2)),0,2,'Bad test')],[])


def test_source_selection_keeps_the_f1_spa_pit_separate_from_support_and_kart_pits() -> None:
    assert [way.osm_id for way in candidate('spa').ways] == [323851541]


def test_nonfinite_portal_and_barrier_values_cannot_reach_runtime() -> None:
    with pytest.raises(ValueError,match='Nonfinite'):
        encode_barriers([Portal('bad',((0,0),(2,0),(2,2),(0,2)),0,float('nan'),'Bad')],[])
    with pytest.raises(ValueError,match='Nonfinite'):
        encode_barriers([Portal('good',((0,0),(2,0),(2,2),(0,2)),0,2,'Good')],
                        [Barrier(0,0,float('nan'),2,0,1,.15)])


def test_local_floor_join_preserves_source_controls_and_complete_plan() -> None:
    from pit_floor_transitions import resolve_floor_joins
    source = PitRoute('join',['https://example.org'],'Retained level controls',[
        PitSection(2*i,0,0 if i<30 else 3,2,2*i,2*i,0,-1)
        for i in range(61)],4,116,80)
    result,proof = resolve_floor_joins(source)
    assert len(proof)==1
    assert result.sections[0]==source.sections[0]
    assert result.sections[-1]==source.sections[-1]
    for before,after in zip(source.sections,result.sections):
        assert (before.x,before.y,before.track_station)==(after.x,after.y,after.track_station)
        if not proof[0].start_distance_m<=before.distance<=proof[0].end_distance_m:
            assert before==after
    assert max(abs(b.z-a.z)/(b.distance-a.distance) for a,b in zip(result.sections,result.sections[1:]))<=.15
    encode_route(result)
