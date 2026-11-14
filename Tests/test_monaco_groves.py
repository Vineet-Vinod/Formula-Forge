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
from circuit_scene import CircuitScene
from venues.monaco_groves import LANDMARK, add_groves
from venues.monaco_groves_dataclasses import WestBankGroves
from venues.monaco_ravine import finish_terrain as finish_ravine
from venues.monaco_ravine_dataclasses import RavineSource


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
    ravine = TypeAdapter(RavineSource).validate_json(
        (scene.sources / 'architecture/ravine-source.json').read_bytes())
    baseline = TypeAdapter(WestBankGroves).validate_json(
        (scene.sources / 'architecture/ravine-canopy-baseline.json').read_bytes())
    rows = [(row.tile, row.material, bytes.fromhex(row.attributes_hex), row.copies)
            for row in ravine.original_ground_rows]
    existing = {(name, material, payload) for name, material, payload, _ in rows}
    rows.extend((row.tile, row.material, bytes.fromhex(row.attributes_hex), 1)
                for row in baseline.supports
                if (row.tile, row.material, bytes.fromhex(row.attributes_hex)) not in existing)
    for name, material, payload, copies in rows:
        tile = scene.tiles.setdefault(name, MeshTile())
        if material not in tile.materials:
            tile.materials.append(material)
        tile.triangles.extend((struct.pack('<I', tile.materials.index(material)) + payload) * copies)
        values = struct.unpack('<24f', payload)
        for vertex in (0, 8, 16):
            for axis in range(3):
                tile.minimum[axis] = min(tile.minimum[axis], values[vertex + axis])
                tile.maximum[axis] = max(tile.maximum[axis], values[vertex + axis])
    finish_ravine(scene)
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
