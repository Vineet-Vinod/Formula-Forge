"""Validate typed route inputs before entering Unreal's stdlib-only Python."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from circuit_route_assets_dataclasses import RouteAssets, RoutePlan
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]


def validate_plan(path: Path) -> None:
    raw = path.read_bytes()
    plan = TypeAdapter(RoutePlan).validate_json(raw)
    if not plan.circuits or len({entry.circuit for entry in plan.circuits}) != len(plan.circuits):
        raise ValueError('A route plan needs distinct circuits')
    manifests = {}
    for entry in plan.circuits:
        manifest_path = ROOT / entry.manifest
        manifest_raw = manifest_path.read_bytes()
        manifest = TypeAdapter(RouteAssets).validate_json(manifest_raw)
        if manifest.circuit != entry.circuit:
            raise ValueError('Manifest circuit differs from plan')
        for tile in manifest.tiles:
            mesh_path = (manifest_path.parent / tile.file).resolve()
            if not mesh_path.is_relative_to(manifest_path.parent.resolve()):
                raise ValueError('Route mesh must remain inside its output directory')
            if hashlib.sha256(mesh_path.read_bytes()).hexdigest() != tile.sha256:
                raise ValueError('Route mesh changed: ' + str(mesh_path))
        for source, expected in manifest.source_sha256.items():
            if hashlib.sha256((ROOT / source).read_bytes()).hexdigest() != expected:
                raise ValueError('Route source changed: ' + source)
        manifests[entry.manifest] = hashlib.sha256(manifest_raw).hexdigest()
    path.with_suffix('.validated.json').write_text(json.dumps({
        'plan_sha256': hashlib.sha256(raw).hexdigest(), 'manifest_sha256': manifests,
    }, indent=2) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    validate_plan(parser.parse_args().plan)


if __name__ == '__main__':
    main()
