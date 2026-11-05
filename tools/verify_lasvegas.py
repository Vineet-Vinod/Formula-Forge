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
unreal.log_warning(f'LASVEGAS_SAVED_ASSETS_PASS {len(manifest["tiles"])} tiles')
