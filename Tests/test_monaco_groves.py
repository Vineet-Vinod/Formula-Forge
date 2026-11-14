"""Frozen canopy geometry must keep its real support and all existing scene rows."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from dataclasses import replace
from pathlib import Path
from typing import Literal

import pytest
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import MeshTile, Point
from circuit_partition_dataclasses import SceneManifest
from circuit_scene import CircuitScene
from venues.monaco_groves import LANDMARK, add_groves
from venues.monaco_groves_dataclasses import WestBankGroves


class GroveScene(CircuitScene):
    emit_geometry = False

    def triangle(
        self, kind: str, material: str, a: Point, b: Point, c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if self.emit_geometry:
            super().triangle(kind, material, a, b, c, uv, normals)


def ground_scene() -> GroveScene:
    scene = GroveScene('monaco')
    scene.road_surfaces('Runoff')
    source = TypeAdapter(WestBankGroves).validate_json(
        (scene.sources / 'architecture/west-bank-groves.json').read_bytes())
    names = {row.tile for row in source.supports}
    manifest = TypeAdapter(SceneManifest).validate_json((scene.scratch / 'manifest.json').read_bytes())
    for row in manifest.tiles:
        if row.name not in names:
            continue
        data = (scene.scratch / row.file).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row.sha256
        scene.tiles[row.name] = MeshTile(materials=list(row.materials), triangles=bytearray(data[12:]),
                                        minimum=list(row.bounds[:3]), maximum=list(row.bounds[3:]))
    scene.emit_geometry = True
    return scene


def test_canopy_trial_keeps_actual_support_old_ground_and_native_data() -> None:
    scene = ground_scene()
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    data = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scene.data.glob('*.bin')}
    grid, road, cutouts = scene.grid, list(scene.road), list(scene.terrain_cutouts)
    add_groves(scene)
    assert scene.grid == grid and scene.road == road and scene.terrain_cutouts == cutouts
    assert all(bytes(scene.tiles[name].triangles) == rows for name, rows in before.items())
    assert data == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scene.data.glob('*.bin')}
    generated = []
    for name, tile in scene.tiles.items():
        if name in before:
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            generated.append(material.encode() + b'\0' + tile.triangles[offset + 4:offset + 100])
    receipt = json.loads((scene.sources / 'architecture/west-bank-groves-proof.json').read_text())
    assert len(generated) == receipt['triangles'] == 714
    assert hashlib.sha256(b''.join(sorted(generated))).hexdigest() == receipt['geometry_sha256']
    landmark = next(row for row in scene.landmarks if row['name'] == LANDMARK)
    assert landmark['canopy_clumps'] == 7
    assert float(landmark['minimum_packed_trunk_embed_m']) >= .0999


@pytest.mark.parametrize('case', ('missing_plane', 'wrong_frame', 'duplicate'))
def test_changed_support_frame_or_duplicate_call_fails_before_emission(
    case: Literal['missing_plane', 'wrong_frame', 'duplicate'],
) -> None:
    scene = ground_scene()
    if case == 'missing_plane':
        source = TypeAdapter(WestBankGroves).validate_json(
            (scene.sources / 'architecture/west-bank-groves.json').read_bytes())
        row = source.supports[0]
        tile = scene.tiles[row.tile]
        expected = bytes.fromhex(row.attributes_hex)
        for offset in range(0, len(tile.triangles), 100):
            if tile.triangles[offset + 4:offset + 100] == expected:
                del tile.triangles[offset:offset + 100]
                break
    elif case == 'wrong_frame':
        scene.provenance = replace(scene.provenance, route=replace(
            scene.provenance.route, uniform_scale=scene.provenance.route.uniform_scale + .001))
    else:
        add_groves(scene)
    before = {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
    with pytest.raises(ValueError):
        add_groves(scene)
    assert before == {name: bytes(tile.triangles) for name, tile in scene.tiles.items()}
