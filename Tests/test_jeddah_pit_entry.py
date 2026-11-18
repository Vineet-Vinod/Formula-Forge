"""Glazed entry end remains inside its original envelope and faces the approach."""

from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_mesh import MeshScene, cross, sub
from circuit_scene import CircuitScene
from venues.jeddah_pit_entry import build_entry, entry_lights, source_record


def test_entry_glazing_recesses_keep_registered_end_envelope_and_packed_normals() -> None:
    scene = CircuitScene("jeddah")
    source = source_record()
    sample = scene.at(source.station_m)
    before = list(scene.road), scene.grid, list(scene.buildings)
    mesh = MeshScene()
    front, rear = -sample.half_width - 13, -sample.half_width - 39
    build_entry(mesh, sample, front, rear)
    materials = set()
    panes = 0
    for tile in mesh.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            values = struct.unpack_from("<I24f", tile.triangles, offset)
            material = tile.materials[values[0]]
            materials.add(material)
            points = [(-values[2 + i * 8] / 100, -values[1 + i * 8] / 100,
                       values[3 + i * 8] / 100) for i in range(3)]
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = math.sqrt(sum(value * value for value in normal))
            assert length > 0
            stored = (-values[5], -values[4], values[6])
            assert sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .9999
            for x, y, z in points:
                dx, dy = x - sample.x, y - sample.y
                lane = dx * sample.ty - dy * sample.tx
                depth = dx * sample.tx + dy * sample.ty
                assert rear - .0002 <= lane <= front + .0002
                assert -.0002 <= depth <= source.backing_depth_m + .0002
                assert sample.z - .0002 <= z <= sample.z + source.height_m + .0002
            if material == "JeddahEditionGuardGlass":
                panes += 1
                assert -(normal[0] * sample.tx + normal[1] * sample.ty) / length > .99999
                assert all((x - sample.x) * sample.tx + (y - sample.y) * sample.ty
                           == pytest.approx(source.glazing_depth_m, abs=.0002)
                           for x, y, _z in points)
    assert panes == 64
    assert "JeddahEditionCharcoal" in materials and "White" in materials
    assert "Glass" not in materials
    lights = entry_lights(scene)
    assert len(lights) == 3
    assert all(light.pool_radius_m == 14 and light.power == .24 for light in lights)
    assert all(light.target is not None and light.target[2] < light.position[2]
               for light in lights)
    assert before == (scene.road, scene.grid, scene.buildings)
    assert not scene.tiles
