"""Retained garden roots, bounded canopy and closed native foliage."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from circuit_mesh import MeshScene, cross, sub
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box
from venues.monaco_bamboo import emit_bamboo, retained_cane_poses
from venues.monaco_bamboo_dataclasses import BambooSpec, CanePose
from venues.monaco_foreground_dataclasses import ForegroundSource

ROOT = Path(__file__).resolve().parents[1]


def test_retained_root_schedule_and_qualified_recipe() -> None:
    source = TypeAdapter(ForegroundSource).validate_json(
        (ROOT / 'Attribution/Sources/monaco/architecture/foreground-properties.json').read_bytes())
    roots = retained_cane_poses(lambda _x, _y: 7., box(24, 283, 35, 292.8))
    receipt = json.loads((ROOT / 'Attribution/Sources/monaco/architecture/bruyeres-bamboo/source-qualification.json').read_text())
    xy = b''.join(struct.pack('<2d', *root.root[:2]) for root in roots)
    assert len(roots) == receipt['retained_root_count'] == 220
    assert hashlib.sha256(xy).hexdigest() == receipt['retained_root_xy_binary_f64_sha256']
    assert all(root.root[2] == 6.95 for root in roots)
    assert source.bruyeres_bamboo.minimum_canopy_top_absolute_m == 14.7
    assert source.bruyeres_bamboo.maximum_canopy_top_absolute_m == 16.4
    assert source.bruyeres_bamboo.relative_datum_m == pytest.approx(source.relative_datum_m, abs=1e-12)


def test_closed_leaves_keep_packed_outward_normals_and_original_bed() -> None:
    scene = MeshScene()
    bed = box(24, 283, 35, 292.8)
    roots = (CanePose(0, (27., 286., 7.5), 2.5), CanePose(1, (32., 290., 9.), 2.5))
    spec = BambooSpec()
    audit = emit_bamboo(scene, roots, spec, bed)
    assert audit.root_count == 2 and audit.blade_count > 500
    material_edges: Counter[tuple[str, tuple[tuple[float, ...], tuple[float, ...]]]] = Counter()
    tops = []
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            row = struct.unpack_from('<24f', tile.triangles, offset + 4)
            points = [(-row[i + 1] / 100, -row[i] / 100, row[i + 2] / 100) for i in (0, 8, 16)]
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = sum(v * v for v in normal) ** .5
            assert length > 1e-10
            for i in (0, 8, 16):
                stored = -row[i + 4], -row[i + 3], row[i + 5]
                assert sum(a * b for a, b in zip(normal, stored)) / length > .999
            assert Polygon([p[:2] for p in points]).difference(bed.buffer(.00003)).area < 1e-10
            assert all(p[0] < 34.92 for p in points)
            tops.extend(p[2] + spec.relative_datum_m for p in points)
            if material.startswith('MonacoBambooLeaf'):
                for a, b in zip(points, (*points[1:], points[0])):
                    material_edges[material, tuple(sorted((a, b)))] += 1
    assert material_edges and all(count == 2 for count in material_edges.values())
    assert max(tops) <= spec.maximum_canopy_top_absolute_m + .3
    assert min(tops) >= 7.5 + spec.relative_datum_m - .001


def test_invalid_canopy_rejects_before_any_emission() -> None:
    scene = MeshScene()
    roots = (CanePose(0, (27., 286., 7.5), 2.5),)
    spec = replace(BambooSpec(), maximum_canopy_top_absolute_m=14.)
    with pytest.raises(ValueError, match='intervals'):
        emit_bamboo(scene, roots, spec, box(24, 283, 35, 292.8))
    assert not scene.tiles


def test_high_root_cannot_silently_extend_canopy_above_the_photo_envelope() -> None:
    scene = MeshScene()
    roots = (CanePose(0, (27., 286., 15.), 2.5),)
    with pytest.raises(ValueError, match='retained roots'):
        emit_bamboo(scene, roots, BambooSpec(), box(24, 283, 35, 292.8))
    assert not scene.tiles
