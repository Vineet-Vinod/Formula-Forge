from __future__ import annotations

import gzip
import hashlib
import math
import struct
from collections import Counter
from pathlib import Path
from typing import cast

import numpy as np
from circuit_dataclasses import Point
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles, from_wkt
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from venues.baku_ground import _weights
from venues.baku_ground_dataclasses import (
    ControlFieldSource,
    GroundPatchSource,
    PackedPatchRow,
    PackedTriangle,
)


def decode(tile: str, material: str, payload: bytes) -> PackedTriangle:
    raw = struct.unpack("<24f", payload)
    attributes = raw[:8], raw[8:16], raw[16:]
    points = cast(
        tuple[Point, Point, Point],
        tuple((-p[1] / 100, -p[0] / 100, p[2] / 100) for p in attributes),
    )
    return PackedTriangle(tile, material, payload, points, attributes)


def _native_xy(x: float, y: float) -> tuple[float, float]:
    return (
        -struct.unpack("<f", struct.pack("<f", -x * 100))[0] / 100,
        -struct.unpack("<f", struct.pack("<f", -y * 100))[0] / 100,
    )


def _original_vertex(row: PackedTriangle, x: float, y: float) -> bytes:
    x, y = _native_xy(x, y)
    for i, point in enumerate(row.points):
        if point[:2] == (x, y):
            return row.payload[i * 32 : (i + 1) * 32]
    weights = _weights(row.points, x, y)
    attributes = [
        sum(w * p[k] for w, p in zip(weights, row.attributes)) for k in range(8)
    ]
    attributes[0], attributes[1] = -y * 100, -x * 100
    return struct.pack("<8f", *attributes)


def scene_rows(
    scene: CircuitScene, source: ControlFieldSource
) -> tuple[list[PackedTriangle], list[PackedTriangle]]:
    region = box(*source.rebuild_window_xy_m)
    ground: list[PackedTriangle] = []
    road: list[PackedTriangle] = []
    for name, tile in scene.tiles.items():
        if not name.startswith("Tile_Street_"):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            if material not in ("Concrete", "Runoff", "Grass", "Road"):
                continue
            row = decode(
                name, material, bytes(tile.triangles[offset + 4 : offset + 100])
            )
            if Polygon([p[:2] for p in row.points]).intersects(region):
                (road if material == "Road" else ground).append(row)
    return ground, road


def author_patch(
    source: ControlFieldSource,
    original: list[PackedTriangle],
    road: list[PackedTriangle],
) -> GroundPatchSource:
    shapes = [Polygon([p[:2] for p in row.points]) for row in original]
    original_index = STRtree(shapes)
    asphalt = [Polygon([p[:2] for p in row.points]) for row in road]
    asphalt_index = STRtree(asphalt)
    actual_road = unary_union(asphalt)
    field = [
        (source.points[a], source.points[b], source.points[c])
        for a, b, c in source.faces
    ]
    field_shapes = [Polygon([p[:2] for p in triangle]) for triangle in field]
    field_index = STRtree(field_shapes)
    grass = unary_union(
        [shape for row, shape in zip(original, shapes) if row.material == "Grass"]
    )
    mask = from_wkt(source.patch_domain_wkt).difference(grass)
    rendered = mask.difference(
        unary_union([from_wkt(source.body_cutouts_wkt), actual_road])
    )
    concrete = unary_union(
        [
            from_wkt(source.concrete_core_wkt),
            *[
                shape
                for row, shape in zip(original, shapes)
                if row.material == "Concrete"
            ],
        ]
    ).intersection(rendered)
    regions = concrete, rendered.difference(concrete)
    removed: Counter[tuple[str, str, bytes]] = Counter()
    added: Counter[tuple[str, str, bytes]] = Counter()
    for row, shape in zip(original, shapes):
        if (
            row.material == "Grass"
            or not shape.intersects(mask)
            or shape.intersection(mask).area < 1e-12
        ):
            continue
        removed[row.tile, row.material, row.payload] += 1
        for triangle in constrained_delaunay_triangles(shape.difference(mask)).geoms:
            payload = b"".join(
                _original_vertex(row, x, y)
                for x, y in list(triangle.exterior.coords)[:3]
            )
            fragment = decode(row.tile, row.material, payload)
            if Polygon([p[:2] for p in fragment.points]).area > 1e-12:
                added[row.tile, row.material, payload] += 1
    normals = np.zeros((len(source.points), 3))
    for indices, triangle, shape in zip(source.faces, field, field_shapes):
        area = shape.intersection(rendered).area
        if area < 1e-12:
            continue
        a, b, c = (np.asarray(p) for p in triangle)
        normal = np.cross(b - a, c - a) * (area / shape.area)
        if normal[2] < 0:
            normal = -normal
        for i in indices:
            normals[i] += normal
    normals /= np.maximum(1e-12, np.linalg.norm(normals, axis=1))[:, None]
    for i, point in enumerate(source.points):
        q = ShapePoint(point[:2])
        if actual_road.distance(q) < 0.0003:
            row = road[int(asphalt_index.nearest(q))]
        elif mask.boundary.distance(q) <= 0.0002:
            candidates = original_index.query(q.buffer(0.0002), predicate="intersects")
            if not len(candidates):
                continue
            chosen = min(
                (int(j) for j in candidates), key=lambda j: shapes[j].distance(q)
            )
            row = original[chosen]
        else:
            continue
        weights = _weights(row.points, *point[:2])
        n = [sum(w * p[k] for w, p in zip(weights, row.attributes)) for k in (3, 4, 5)]
        normals[i] = -n[1], -n[0], n[2]
    for ids, shape in zip(source.faces, field_shapes):
        for region, material in zip(regions, ("Concrete", "Runoff")):
            if not region.intersects(shape):
                continue
            for triangle in constrained_delaunay_triangles(
                shape.intersection(region)
            ).geoms:
                payloads = []
                positions = []
                for x, y in list(triangle.exterior.coords)[:3]:
                    x, y = _native_xy(x, y)
                    sample_x, sample_y = x, y
                    sample_ids = ids
                    q = ShapePoint(x, y)
                    if not shape.covers(q):
                        hits = field_index.query(q, predicate="covered_by")
                        if len(hits):
                            sample_ids = source.faces[int(hits[0])]
                        else:
                            nearest = int(field_index.nearest(q))
                            projected = nearest_points(field_shapes[nearest], q)[0]
                            if q.distance(projected) > source.maximum_projection_m:
                                raise ValueError(
                                    "The Baku rebuild leaves its authored control field"
                                )
                            sample_x, sample_y = projected.x, projected.y
                            sample_ids = source.faces[nearest]
                    points = cast(
                        tuple[Point, Point, Point],
                        tuple(source.points[i] for i in sample_ids),
                    )
                    positive = [
                        max(0.0, min(1.0, weight))
                        for weight in _weights(points, sample_x, sample_y)
                    ]
                    total = sum(positive)
                    packed_weights = [w / total for w in positive]
                    z = sum(w * p[2] for w, p in zip(packed_weights, points))
                    n = [
                        sum(
                            w * float(normals[i, k])
                            for w, i in zip(packed_weights, sample_ids)
                        )
                        for k in range(3)
                    ]
                    scale = 4 if material == "Concrete" else 8
                    payloads.append(
                        struct.pack(
                            "<8f",
                            -y * 100,
                            -x * 100,
                            z * 100,
                            -n[1],
                            -n[0],
                            n[2],
                            x / scale,
                            y / scale,
                        )
                    )
                    positions.append((x, y, z))
                payload = b"".join(payloads)
                tx = math.floor(sum(p[0] for p in positions) / 720)
                ty = math.floor(sum(p[1] for p in positions) / 720)
                tile = f"Tile_Street_{tx:02d}_{ty:02d}".replace("-", "m")
                row = decode(tile, material, payload)
                if Polygon([p[:2] for p in row.points]).area > 1e-12:
                    added[tile, material, payload] += 1
    common = removed & added
    removed -= common
    added -= common
    return GroundPatchSource(
        1,
        {
            relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for relative in source.protected_source_paths
        },
        [
            PackedPatchRow(tile, material, payload, copies)
            for (tile, material, payload), copies in sorted(removed.items())
        ],
        [
            PackedPatchRow(tile, material, payload, copies)
            for (tile, material, payload), copies in sorted(added.items())
        ],
        source.source_note,
    )


def rebuild(
    scene: CircuitScene, control_path: Path, output_path: Path
) -> GroundPatchSource:
    source = TypeAdapter(ControlFieldSource).validate_json(
        gzip.decompress(control_path.read_bytes())
    )
    ground, road = scene_rows(scene, source)
    patch = author_patch(source, ground, road)
    encoded = TypeAdapter(GroundPatchSource).dump_json(patch)
    output_path.write_bytes(gzip.compress(encoded, mtime=0))
    return patch
