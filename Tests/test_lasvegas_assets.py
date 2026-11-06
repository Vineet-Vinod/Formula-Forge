"""Check the contact/visual coordinate contract and the two terrain-header regressions."""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'Content/Generated/LasVegas/Data'
SOURCES = ROOT / 'Attribution/Sources/lasvegas'


def test_terrain_payload_and_datum() -> None:
    source = (SOURCES / 'elevation/bare_earth.bin').read_bytes()
    terrain = (DATA / 'terrain.bin').read_bytes()
    assert source[:8] == b'FFDEM1\0\0'
    assert terrain[:8] == b'FFTRN1\0\0'
    assert source[8:36] == terrain[8:36]
    _, _, step, columns, rows = struct.unpack_from('<ddfII', source, 8)
    assert step == 4
    assert len(source) == len(terrain) == 36 + 4 * columns * rows
    survey = json.loads((SOURCES / 'reconstruction.json').read_text())
    datum = survey['elevation_datum_removed_m']
    for (absolute,), (relative,) in zip(struct.iter_unpack('<f', source[36:]), struct.iter_unpack('<f', terrain[36:]), strict=True):
        assert math.isfinite(absolute) and math.isfinite(relative)
        assert 600 < absolute < 700
        assert abs(absolute - datum - relative) < .001


def test_rendered_road_matches_contact_triangles() -> None:
    manifest = json.loads((ROOT / 'build/lasvegas/manifest.json').read_text())
    contact: list[tuple[float, float, float]] = []
    rendered: list[tuple[float, float, float]] = []
    for triangle in struct.iter_unpack('<9f', (DATA / 'drive_surface.bin').read_bytes()[12:]):
        for offset in (0, 3, 6):
            x, y, z = triangle[offset:offset + 3]
            contact.append(struct.unpack('<3f', struct.pack('<3f', -y * 100, -x * 100, z * 100)))
    for tile in manifest['tiles']:
        paving_materials = {index for index,name in enumerate(tile['materials']) if name in ('Road','Runoff','BlueRunoff')}
        if not paving_materials:
            continue
        payload = (ROOT / 'build/lasvegas' / tile['file']).read_bytes()
        assert payload[:8] == b'FFLVM1\0\0'
        for offset in range(12, len(payload), 100):
            if struct.unpack_from('<I', payload, offset)[0] not in paving_materials:
                continue
            for corner in range(3):
                x, y, z, nx, ny, nz, u, v = struct.unpack_from('<8f', payload, offset + 4 + corner * 32)
                assert nz > .95
                assert all(math.isfinite(value) for value in (x, y, z, nx, ny, nz, u, v))
                rendered.append((x, y, z))
    from collections import Counter

    assert len(contact) > 73728
    # The decorative, fenced-off pit apron is additional visible paving.
    assert not (Counter(contact) - Counter(rendered))


def test_manifest_assets_and_collision_walls() -> None:
    manifest = json.loads((ROOT / 'build/lasvegas/manifest.json').read_text())
    lines = (DATA / 'render_tiles.csv').read_text().splitlines()
    assert len(lines) == len(manifest['tiles'])
    assert len(lines) == len({line.split(',')[0] for line in lines})
    concrete_triangles = 0
    for tile in manifest['tiles']:
        assert (ROOT / 'Content/Generated/LasVegas/Track' / (tile['name'] + '.uasset')).is_file()
        assert all(math.isfinite(bound) for bound in tile['bounds'])
        assert all(tile['bounds'][index] < tile['bounds'][index + 3] for index in range(3))
        if 'Concrete' not in tile['materials']:
            continue
        material = tile['materials'].index('Concrete')
        payload = (ROOT / 'build/lasvegas' / tile['file']).read_bytes()
        concrete_triangles += sum(struct.unpack_from('<I', payload, offset)[0] == material for offset in range(12, len(payload), 100))
    walls = len((ROOT / 'build/lasvegas/barriers.csv').read_text().splitlines()) - 1
    assert walls > 2800
    # End walls use tire stacks; every remaining visible segment is the collision segment.
    import csv
    import sys

    sys.path.insert(0,str(ROOT / 'tools'))
    from lasvegas_geometry import Scenery

    scenery = Scenery()
    visible_walls = sum(not scenery.escape_end((float(row['ax'])+float(row['bx']))/2,
                                             (float(row['ay'])+float(row['by']))/2)
                        for row in csv.DictReader((ROOT/'build/lasvegas/barriers.csv').open()))
    assert concrete_triangles == visible_walls * 12


def test_street_profile_has_no_preconstruction_drop() -> None:
    import csv

    stations = list(csv.DictReader((ROOT / 'build/lasvegas/road.csv').open()))
    heights = [float(sample['z']) for sample in stations]
    spacing = 6201 / len(heights)
    grades = [(heights[(index + 1) % len(heights)] - height) / spacing for index, height in enumerate(heights)]
    assert max(abs(grade) for grade in grades) < .04
    assert max(abs(grades[(index + 1) % len(grades)] - grade) for index, grade in enumerate(grades)) < .004


def test_curves_and_driver_facing_braking_boards() -> None:
    import csv

    road = list(csv.DictReader((ROOT / 'build/lasvegas/road.csv').open()))
    assert len(road) == 12288
    for a, b in zip(road, road[1:] + road[:1], strict=True):
        assert math.hypot(float(b['x']) - float(a['x']), float(b['y']) - float(a['y'])) < .51
    boards = json.loads((ROOT / 'build/lasvegas/braking_boards.json').read_text())
    assert len(boards) == 18
    assert len({(board['apex'], board['distance']) for board in boards}) == 18
    for board in boards:
        assert abs(board['apex'] - board['station'] - board['distance']) < .51
    triangles = {name: 0 for name in ('50', '100', '150')}
    manifest = json.loads((ROOT / 'build/lasvegas/manifest.json').read_text())
    for tile in manifest['tiles']:
        payload = (ROOT / 'build/lasvegas' / tile['file']).read_bytes()
        for offset in range(12, len(payload), 100):
            material = tile['materials'][struct.unpack_from('<I', payload, offset)[0]]
            if material in triangles:
                triangles[material] += 1
    assert triangles == {'50': 24, '100': 24, '150': 24}


def test_sands_fast_bends_and_post_strip_chicane() -> None:
    import csv

    road = [{key: float(value) for key, value in row.items()}
            for row in csv.DictReader((ROOT / 'build/lasvegas/road.csv').open())]

    def heading_change(begin: float, end: float) -> float:
        a = min(road, key=lambda row: abs(row['station'] - begin))
        b = min(road, key=lambda row: abs(row['station'] - end))
        return math.atan2(a['tx'] * b['ty'] - a['ty'] * b['tx'], a['tx'] * b['tx'] + a['ty'] * b['ty'])

    # FIA 2025 map: T14 left, T15 right, T16 left before the eastbound Harmon straight.
    assert heading_change(660, 704) > 1.2
    assert heading_change(704, 750) < -.6
    assert heading_change(750, 820) > .6
    # Sands has no slow lateral jog before its broad T10/T11 sweep.
    for station in range(4190, 4350, 10):
        assert abs(heading_change(station - 12, station + 12)) < .15
    survey = (ROOT / 'Source/FormulaForge/Native/track_data/lasvegas_survey.inc').read_text()
    turns = survey.split('kLasVegasTurns[] = {')[1].split('};')[0]
    assert turns.count('TrackTurnDirection::') == 17
    for number in range(1, 18):
        assert turns.count(f'"Turn {number}"') == 1


def test_encore_tower_is_separate_from_low_casino_podium() -> None:
    scene = json.loads((SOURCES / 'scenery.json').read_text())
    buildings = {landmark['osm_id']: landmark for landmark in scene['landmarks'] if 'osm_id' in landmark}
    assert buildings[27910891]['name'] == 'Encore Las Vegas'
    assert 180 < buildings[27910891]['height_m'] < 200
    assert buildings[135291730]['height_m'] < 25


def test_true_road_edges_have_no_source_polygon_kinks() -> None:
    import csv

    road = [{key:float(value) for key,value in row.items()}
            for row in csv.DictReader((ROOT/'build/lasvegas/road.csv').open())]
    for side in (0,-1,1):
        points=[(p['x']+side*p['ty']*p['half_width'],p['y']-side*p['tx']*p['half_width']) for p in road]
        maximum=0.0
        for i,b in enumerate(points):
            a,c=points[i-1],points[(i+1)%len(points)]
            first=(b[0]-a[0],b[1]-a[1])
            second=(c[0]-b[0],c[1]-b[1])
            angle=abs(math.atan2(first[0]*second[1]-first[1]*second[0],
                                 first[0]*second[0]+first[1]*second[1]))
            maximum=max(maximum,angle)
        assert maximum < math.radians(5), (side,math.degrees(maximum))


def test_escape_roads_are_open_paved_and_outside_white_line_limits() -> None:
    import csv

    import numpy as np
    from shapely.geometry import LineString, MultiLineString, Polygon
    from shapely.ops import unary_union

    contact = np.frombuffer((DATA/'drive_surface.bin').read_bytes(),dtype='<f4',offset=12).reshape(-1,3,3)
    limits = np.frombuffer((DATA/'track_limits.bin').read_bytes(),dtype='<f4',offset=8).reshape(-1,3,2)
    record=json.loads((SOURCES/'boundaries.json').read_text())
    barriers=MultiLineString([[(float(p['ax']),float(p['ay'])),(float(p['bx']),float(p['by']))]
                             for p in csv.DictReader((ROOT/'build/lasvegas/barriers.csv').open())])

    def covered(triangles: np.ndarray, point: tuple[float,float]) -> bool:
        values=[]
        for i in range(3):
            a,b=triangles[:,i,:2],triangles[:,(i+1)%3,:2]
            values.append((b[:,0]-a[:,0])*(point[1]-a[:,1])-(b[:,1]-a[:,1])*(point[0]-a[:,0]))
        return bool(np.any(np.logical_or(np.logical_and.reduce([v>=-.00001 for v in values]),
                                        np.logical_and.reduce([v<=.00001 for v in values]))))

    for region in record['regions']:
        if region['paint'] != 'Runoff':
            continue
        ring=region['ring']
        start=((ring[0][0]+ring[1][0])/2,(ring[0][1]+ring[1][1])/2)
        end=((ring[2][0]+ring[3][0])/2,(ring[2][1]+ring[3][1])/2)
        def point(t: float, start: tuple[float,float] = start, end: tuple[float,float] = end) -> tuple[float,float]:
            return start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t
        assert not barriers.intersects(LineString([point(.12),point(.95)])), region['name']
        assert barriers.intersects(LineString([point(.95),point(1.1)])), region['name']
        p=point(.8)
        assert covered(contact,p), region['name']
        assert not covered(limits,(p[0],-p[1])), region['name']
    # A paved island and every outer wall form closed protection loops.
    road=[{k:float(v) for k,v in row.items()} for row in csv.DictReader((ROOT/'build/lasvegas/road.csv').open())]
    outer=[(p['x']+p['ty']*(p['half_width']+.95),p['y']-p['tx']*(p['half_width']+.95)) for p in road]
    inner=[(p['x']-p['ty']*(p['half_width']+.95),p['y']+p['tx']*(p['half_width']+.95)) for p in road]
    deck=unary_union([Polygon(outer,[inner]),*[Polygon(r['ring']) for r in record['regions']]])
    assert deck.is_valid
    assert abs(deck.area-record['paved_area_m2']) < 1
    assert barriers.hausdorff_distance(deck.boundary) < .01


def test_sidewalk_panels_do_not_overhang_escape_roads() -> None:
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    scratch = ROOT/'build/lasvegas'
    escapes = unary_union([Polygon(region['ring']) for region in
                           json.loads((SOURCES/'boundaries.json').read_text())['regions']])
    dtype = np.dtype([('material','<u4'),('vertices','<f4',(3,8))])
    for tile in json.loads((scratch/'manifest.json').read_text())['tiles']:
        if 'Pavement' not in tile['materials']:
            continue
        rows = np.frombuffer((scratch/tile['file']).read_bytes(),dtype=dtype,offset=12)
        triangles = rows['vertices'][rows['material']==tile['materials'].index('Pavement')]
        for triangle in triangles:
            footprint = Polygon([(-float(p[1])/100,-float(p[0])/100) for p in triangle])
            assert footprint.intersection(escapes).area < .0001, tile['name']


def test_barriers_follow_continuous_pavement_heights() -> None:
    import csv

    walls = [{key: float(value) for key,value in row.items()}
             for row in csv.DictReader((ROOT/'build/lasvegas/barriers.csv').open())]
    payload = (SOURCES/'barrier_heights.bin').read_bytes()
    assert payload[:8] == b'FFWALL1\0'
    assert struct.unpack_from('<I',payload,8)[0] == len(walls)
    heights = list(struct.iter_unpack('<2f',payload[12:]))
    assert len(heights) == len(walls)
    starts = {(round(w['ax'],3),round(w['ay'],3)):i for i,w in enumerate(walls)}
    for i,(wall,(za,zb)) in enumerate(zip(walls,heights,strict=True)):
        nxt = starts[(round(wall['bx'],3),round(wall['by'],3))]
        assert abs(zb-heights[nxt][0]) < .002, (i,nxt,zb,heights[nxt][0])
        assert abs(wall['bottom']-min(za,zb)) < .001
        assert wall['top'] >= max(za,zb)+.949
        # A one-metre section must not jump between street and escape-deck heights.
        assert abs(wall['bottom']-walls[nxt]['bottom']) < .15, i


def test_saved_fence_panels_share_their_uprights_and_overhang_edges() -> None:
    from collections import Counter

    manifest = json.loads((ROOT/'build/lasvegas/manifest.json').read_text())
    seams: Counter[tuple[tuple[float,...],tuple[float,...]]] = Counter()
    for tile in manifest['tiles']:
        if 'Fence' not in tile['materials']:
            continue
        material = tile['materials'].index('Fence')
        payload = (ROOT/'build/lasvegas'/tile['file']).read_bytes()
        for offset in range(12,len(payload),100):
            if struct.unpack_from('<I',payload,offset)[0] != material:
                continue
            points = [struct.unpack_from('<3f',payload,offset+4+corner*32) for corner in range(3)]
            for a,b in zip(points,points[1:]+points[:1]):
                if abs(a[2]-b[2]) > 30:
                    ends = sorted(tuple(round(v,1) for v in p) for p in (a,b))
                    seams[(ends[0],ends[1])] += 1
    assert seams
    assert all(count == 2 for count in seams.values())



def test_full_route_frontages_and_vegetation_are_present() -> None:
    scene = json.loads((SOURCES/'scenery.json').read_text())
    buildings = {p['osm_id'] for p in scene['landmarks'] if 'osm_id' in p}
    assert {111322055,111367819,100519310,238675785,276427203,95223231,128622185,181282568} <= buildings
    assert any(p['name'] == 'Wynn Plaza curved digital monument' for p in scene['landmarks'])
    assert any(p['name'] == 'Opening sequence hospitality gallery' for p in scene['landmarks'])
    names = {p['name'] for p in scene['landmarks']}
    assert {name+' integrated street frontage' for name in ('Flamingo','Linq','Harrahs','CasinoRoyale','Cosmopolitan')} <= names
    display = next(p for p in scene['landmarks'] if p['name'] == 'Harmon Corner upper curved LED and retail balconies')
    assert math.isclose(display['screen_width_m'],306*.3048)
    assert math.isclose(display['screen_height_m'],60*.3048)
    assert display['base_height_m'] >= 14
    profiles = json.loads((SOURCES/'landmark-architecture.json').read_text())['profiles']
    volumes = {part['osm_id']:part['height_m'] for part in scene['landmarks'] if 'osm_id' in part}
    assert volumes[276427203]+profiles['276427203']['crown_m'] == 128
    assert volumes[95223231]+profiles['95223231']['crown_m'] == 145
    assert scene['route_environment_sha256'] == hashlib.sha256((SOURCES/'route-environment.json').read_bytes()).hexdigest()
    sectors = json.loads((SOURCES/'route-environment.json').read_text())['sectors']
    assert sectors[0]['start_m'] == 0 and sectors[-1]['end_m'] == 6201
    assert all(a['end_m'] == b['start_m'] for a,b in itertools.pairwise(sectors))
    for sector in sectors:
        if sector['tree_spacing_m'] == 0:
            continue
        trees = [tree for tree in scene['vegetation'] if tree['sector'] == sector['name']]
        assert len(trees) >= 6, sector['name']
        assert any(tree['kind'] == 'broadleaf' for tree in trees), sector['name']
    assert scene['night_lighting']['fixture_count'] >= 500


def test_koval_floodlight_field_retains_local_contrast() -> None:
    import csv
    import statistics

    from PIL import Image

    x0,y0,width,height = json.loads((SOURCES/'night-field.json').read_text())['world_bounds_cm']
    field = Image.open(ROOT/'build/lasvegas/art/FloodlightField.png').convert('RGB')
    values = []
    for sample in csv.DictReader((ROOT/'build/lasvegas/road.csv').open()):
        if not 2500 < float(sample['station']) < 3100:
            continue
        x,y = -float(sample['y'])*100,-float(sample['x'])*100
        col,row = int((x-x0)/width*field.width),int((y-y0)/height*field.height)
        values.append(field.getpixel((col,row))[0])
    assert max(values)-min(values) > 40
    assert statistics.median(values) < 180


def test_resort_outlines_do_not_hide_mapped_component_volumes() -> None:
    scene = json.loads((SOURCES/'scenery.json').read_text())
    volumes = {part['osm_id']:part['height_m'] for part in scene['landmarks'] if 'osm_id' in part}
    assert volumes[116761428] < 20
    assert 22 < volumes[116761035] < 25
    assert 29 < volumes[116761280] < 32
    assert volumes[134795273] < 45
    assert volumes[27897905] > 150 and volumes[472669744] > 150
