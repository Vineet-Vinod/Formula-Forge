from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path

from circuit_dataclasses import MeshTile, Point
from circuit_mesh import MeshScene
from circuit_scene import ROOT
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import nearest_points
from shapely.strtree import STRtree

from venues.baku_ground_dataclasses import (
    BarrierSupportSource,
    ControlFieldSource,
    GroundPatchSource,
    PackedPatchRow,
)


def _weights(
    points: tuple[Point, Point, Point], x: float, y: float
) -> tuple[float, float, float]:
    a, b, c = points
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if denominator == 0:
        raise ValueError("The Baku public field contains a collapsed face")
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
    return u, v, 1 - u - v


def public_height(source: ControlFieldSource) -> Callable[[float, float], float]:
    triangles = [
        (source.points[a], source.points[b], source.points[c])
        for a, b, c in source.faces
    ]
    shapes = [Polygon([p[:2] for p in triangle]) for triangle in triangles]
    index = STRtree(shapes)

    def height(x: float, y: float) -> float:
        point = ShapePoint(x, y)
        hits = index.query(point, predicate="covered_by")
        if len(hits):
            chosen = int(hits[0])
        else:
            chosen = int(index.nearest(point))
            projected = nearest_points(shapes[chosen], point)[0]
            if point.distance(projected) > source.maximum_projection_m:
                raise ValueError(
                    "Baku architecture leaves its bounded public control field"
                )
            x, y = projected.x, projected.y
        weights = [
            max(0.0, min(1.0, weight)) for weight in _weights(triangles[chosen], x, y)
        ]
        total = sum(weights)
        return (
            sum(weight * p[2] for weight, p in zip(weights, triangles[chosen])) / total
        )

    return height


def barrier_supports(scene: MeshScene, sources: list[BarrierSupportSource]) -> None:
    for source in sources:
        kind = f"Building_BarrierFoot_{source.retained_box_id}"
        scene.triangle(kind + "_Top", "Concrete", *source.top)
        scene.triangle(
            kind + "_Bottom",
            "Concrete",
            source.bottom[2],
            source.bottom[1],
            source.bottom[0],
        )
        for i in range(3):
            j = (i + 1) % 3
            scene.quad(
                kind + "_Side",
                "Concrete",
                source.top[i],
                source.top[j],
                source.bottom[j],
                source.bottom[i],
            )


def finish_terrain(scene: MeshScene, source_path: Path) -> None:
    source = TypeAdapter(GroundPatchSource).validate_json(
        gzip.decompress(source_path.read_bytes())
    )
    for relative, expected in source.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Baku protected input changed: {relative}")
    removals: dict[str, Counter[tuple[str, bytes]]] = defaultdict(Counter)
    additions: dict[str, list[PackedPatchRow]] = defaultdict(list)
    for row in source.removals:
        removals[row.tile][row.material, row.payload] += row.copies
    for row in source.additions:
        additions[row.tile].append(row)
    staged: dict[str, MeshTile] = {}
    for name in removals.keys() | additions.keys():
        original = scene.tiles.get(name)
        replacement = MeshTile(materials=list(original.materials) if original else [])
        remaining = removals[name].copy()
        if original:
            for offset in range(0, len(original.triangles), 100):
                raw = original.triangles[offset : offset + 100]
                material_index = struct.unpack_from("<I", raw)[0]
                key = original.materials[material_index], bytes(raw[4:])
                if remaining[key]:
                    remaining[key] -= 1
                else:
                    replacement.triangles.extend(raw)
        if +remaining:
            raise ValueError(
                f"Baku expected original Ground rows are missing in {name}"
            )
        for row in additions[name]:
            if row.material not in replacement.materials:
                replacement.materials.append(row.material)
            addition = (
                struct.pack("<I", replacement.materials.index(row.material))
                + row.payload
            )
            replacement.triangles.extend(addition * row.copies)
        for offset in range(0, len(replacement.triangles), 100):
            for vertex in range(3):
                point = struct.unpack_from(
                    "<3f", replacement.triangles, offset + 4 + vertex * 32
                )
                for axis, value in enumerate(point):
                    replacement.minimum[axis] = min(replacement.minimum[axis], value)
                    replacement.maximum[axis] = max(replacement.maximum[axis], value)
        staged[name] = replacement
    scene.tiles.update(staged)
