"""Reopen saved Las Vegas meshes in a fresh editor process and check their payloads."""
from __future__ import annotations

import json
from pathlib import Path

import unreal

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'build/lasvegas/manifest.json').read_text())
for tile in manifest['tiles']:
    mesh = unreal.load_asset('/Game/Generated/LasVegas/Track/' + tile['name'])
    if (mesh is None or mesh.get_num_triangles(0) != tile['triangles']
            or unreal.EditorAssetLibrary.get_metadata_tag(mesh, 'LasVegasSourceSHA256') != tile['sha256']):
        raise RuntimeError(f'Saved mesh differs from generated geometry: {tile["name"]}')
    for index, name in enumerate(tile['materials']):
        expected = 'Night_' + name if name in ('Road', 'Runoff', 'Concrete', 'Crowd') else name
        material = mesh.get_material(index)
        if material is None or material.get_path_name() != f'/Game/Generated/LasVegas/Materials/{expected}.{expected}':
            raise RuntimeError(f'Saved material differs from generated geometry: {tile["name"]} slot {index}')
unreal.log_warning(f'LASVEGAS_SAVED_ASSETS_PASS {len(manifest["tiles"])} tiles')
