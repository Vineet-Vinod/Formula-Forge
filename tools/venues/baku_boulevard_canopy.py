"""Continuous crown lighting on the existing Baku boulevard tree geometry."""
from __future__ import annotations

import math
import struct

from circuit_dataclasses import MeshTile, Point
from circuit_mesh import MeshScene


def broadleaf(scene: MeshScene, base: Point, height: float, seed: int) -> None:
    source = MeshScene()
    source.broadleaf(base, height, seed)
    for name, tile in source.tiles.items():
        target = scene.tiles.setdefault(name, MeshTile())
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            payload = bytearray(tile.triangles[offset + 4:offset + 100])
            if material == 'TreeCanopy':
                material = 'BakuSahilCanopy'
                for vertex in range(3):
                    x, y, z = struct.unpack_from('<3f', payload, vertex * 32)
                    nx = (-y / 100 - base[0]) / (height * .41) ** 2
                    ny = (-x / 100 - base[1]) / (height * .41) ** 2
                    nz = (z / 100 - base[2] - height * .30) / (height * .70) ** 2
                    length = math.sqrt(nx * nx + ny * ny + nz * nz)
                    struct.pack_into('<3f', payload, vertex * 32 + 12,
                                     -ny / length, -nx / length, nz / length)
            if material not in target.materials:
                target.materials.append(material)
            target.triangles.extend(struct.pack('<I', target.materials.index(material)))
            target.triangles.extend(payload)
        for axis in range(3):
            target.minimum[axis] = min(target.minimum[axis], tile.minimum[axis])
            target.maximum[axis] = max(target.maximum[axis], tile.maximum[axis])
