"""Check the contact/visual coordinate contract and the two terrain-header regressions."""
from __future__ import annotations

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
            contact.append((-y * 100, -x * 100, z * 100))
    for tile in manifest['tiles']:
        if 'Road' not in tile['materials']:
            continue
        material = tile['materials'].index('Road')
        payload = (ROOT / 'build/lasvegas' / tile['file']).read_bytes()
        assert payload[:8] == b'FFLVM1\0\0'
        for offset in range(12, len(payload), 100):
            if struct.unpack_from('<I', payload, offset)[0] != material:
                continue
            for corner in range(3):
                x, y, z, nx, ny, nz, u, v = struct.unpack_from('<8f', payload, offset + 4 + corner * 32)
                assert nz > .95
                assert all(math.isfinite(value) for value in (x, y, z, nx, ny, nz, u, v))
                rendered.append((x, y, z))
    assert len(contact) == len(rendered) == 9216
    for a, b in zip(sorted(contact), sorted(rendered), strict=True):
        assert math.dist(a, b) < .025


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
    assert concrete_triangles == walls * 12


def test_street_profile_has_no_preconstruction_drop() -> None:
    import csv

    stations = list(csv.DictReader((ROOT / 'build/lasvegas/road.csv').open()))
    heights = [float(sample['z']) for sample in stations]
    spacing = 6201 / len(heights)
    grades = [(heights[(index + 1) % len(heights)] - height) / spacing for index, height in enumerate(heights)]
    assert max(abs(grade) for grade in grades) < .04
    assert max(abs(grades[(index + 1) % len(grades)] - grade) for index, grade in enumerate(grades)) < .004
