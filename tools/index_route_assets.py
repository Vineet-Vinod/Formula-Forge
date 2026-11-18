"""Index only native meshes intersecting a validated finite route overlay plan."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
match = re.search(r'-FFRoutePlan=(?:"([^"]+)"|(\S+))', unreal.SystemLibrary.get_command_line())
if match is None:
    raise ValueError('Pass -FFRoutePlan=<validated repository build plan>')
plan_path = Path(match[1] or match[2])
plan = json.loads(plan_path.read_text())
validation = json.loads(plan_path.with_suffix('.validated.json').read_text())
assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == validation['plan_sha256']


def overlaps(bounds, portal) -> bool:
    xs = [-point[1] * 100 for point in portal['polygon_xy_m']]
    ys = [-point[0] * 100 for point in portal['polygon_xy_m']]
    return not (bounds[3] < min(xs) or bounds[0] > max(xs) or bounds[4] < min(ys)
                or bounds[1] > max(ys) or bounds[5] < portal['bottom_m'] * 100
                or bounds[2] > portal['top_m'] * 100)


for entry in plan['circuits']:
    manifest_path = ROOT / entry['manifest']
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == validation['manifest_sha256'][entry['manifest']]
    manifest = json.loads(manifest_path.read_text())
    if manifest['circuit'] != entry['circuit']:
        raise ValueError('Route index circuit differs from its manifest')
    volumes = manifest['portals'] + manifest['paint_domains'] + manifest.get('cosmetic_portals', [])
    data = ROOT / 'Content/Generated' / entry['content_dir']
    directory = entry['content_dir'].removesuffix('/Data')
    directory = '' if directory == 'Data' else directory
    prefix = '/Game/Generated/' + (directory + '/' if directory else '') + 'Track/'
    records = []
    with (data / 'render_tiles.csv').open() as stream:
        for row in csv.reader(stream):
            name, bounds = row[0], [float(value) for value in row[1:]]
            if not name.startswith('Tile_') or name.startswith('Tile_Route_'):
                continue
            if not any(overlaps(bounds, volume) for volume in volumes):
                continue
            asset = prefix + name
            mesh = unreal.load_asset(asset)
            if not isinstance(mesh, unreal.StaticMesh):
                raise TypeError('Missing native route candidate ' + asset)
            slots = [{'slot': str(slot.material_slot_name),
                      'material': slot.material_interface.get_path_name() if slot.material_interface else None}
                     for slot in mesh.get_editor_property('static_materials')]
            records.append({'name': name, 'asset': asset, 'bounds': bounds, 'slots': slots})
            del mesh
            unreal.SystemLibrary.collect_garbage()
    output = (ROOT / entry['index']).resolve()
    if not output.is_relative_to(ROOT / 'build'):
        raise ValueError('Write native route indexes only under build/')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'slug': entry['circuit'], 'frame': 'Unreal world centimetres',
        'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(), 'assets': records}, indent=2) + '\n')
    unreal.log('ROUTE_NATIVE_INDEX ' + entry['circuit'] + ' ' + str(len(records)))
