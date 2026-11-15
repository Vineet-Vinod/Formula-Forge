"""Material segmentation on original packed planes; no sampled height field."""

from __future__ import annotations

import math
import struct
from itertools import pairwise

import numpy as np
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.baku_khagani_dataclasses import LegacyRow
from venues.baku_khagani_legacy import native_values, packed_xy, source_points
from venues.baku_waterfront_dataclasses import GroundClipAudit


def polygon_parts(shape: BaseGeometry) -> tuple[Polygon, ...]:
    if isinstance(shape, Polygon):
        return (shape,)
    return (
        tuple(part for part in shape.geoms if isinstance(part, Polygon))
        if hasattr(shape, "geoms")
        else ()
    )


def boundary_points(shape: BaseGeometry) -> set[tuple[float, float]]:
    return {
        (float(x), float(y))
        for part in polygon_parts(shape)
        for ring in (part.exterior, *part.interiors)
        for x, y in ring.coords
    }


def packed_part(part: Polygon, nodes: set[tuple[float, float]]) -> Polygon:
    def ring(coordinates: list[tuple[float, float]]) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        for a, b in pairwise(coordinates):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length2 = dx * dx + dy * dy
            if length2 < 1e-24:
                continue
            selected = []
            for x, y in nodes:
                t = ((x - a[0]) * dx + (y - a[1]) * dy) / length2
                distance = abs((x - a[0]) * dy - (y - a[1]) * dx) / math.sqrt(length2)
                if -1e-10 <= t < 1.0 - 1e-10 and distance < 1e-8:
                    selected.append((max(0.0, t), (x, y)))
            for _, point in sorted(selected):
                q = packed_xy(point)
                if not result or q != result[-1]:
                    result.append(q)
        return result

    shell = ring(list(part.exterior.coords))
    holes = [ring(list(hole.coords)) for hole in part.interiors]
    holes = [hole for hole in holes if len(hole) >= 3 and Polygon(hole).area > 1e-13]
    if len(shell) < 3:
        return Polygon()
    result = Polygon(shell, holes)
    if not result.is_valid:
        raise ValueError(
            "Packed material boundary is invalid; source feature needs explicit diagnosis"
        )
    return result


def recolor(
    row: LegacyRow, domain: BaseGeometry
) -> tuple[list[LegacyRow], GroundClipAudit | None]:
    native = native_values(row.payload)
    xyz = source_points(native)
    original = Polygon(xyz[:, :2])
    inside = original.intersection(domain)
    if inside.area < 1e-10:
        return [row], None
    outside = original.difference(domain)
    if outside.is_empty:
        cross = np.cross(xyz[1] - xyz[0], xyz[2] - xyz[0])
        stored = np.column_stack((-native[:, 4], -native[:, 3], native[:, 5]))
        alignment = float((stored @ (cross / np.linalg.norm(cross))).min())
        audit = GroundClipAudit(
            original.area,
            original.area,
            0.0,
            original.area,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            alignment,
            original.area,
        )
        return [LegacyRow(row.tile, row.kind, "Grass", row.payload, -1)], audit
    inverse = np.linalg.inv(np.column_stack((xyz[:, 0], xyz[:, 1], np.ones(3))).T)
    zcoeff = np.linalg.solve(
        np.column_stack((xyz[:, 0], xyz[:, 1], np.ones(3))), xyz[:, 2]
    )
    cross = np.cross(xyz[1] - xyz[0], xyz[2] - xyz[0])
    sign = float(cross[2])
    shared_nodes = boundary_points(inside) | boundary_points(outside)
    emitted = []
    emitted_shapes = []
    max_plane = 0.0
    max_bound = 0.0
    max_normal = 0.0
    max_uv = 0.0
    dropped = 0.0
    minimum = 1.0
    min_area = math.inf
    for shape, material in ((inside, "Grass"), (outside, row.material)):
        if shape.is_empty:
            continue
        for original_part in polygon_parts(shape):
            # Node and quantize both sides before meshing, so collinear source
            # knots cannot become different float32 seam chords.
            part = packed_part(original_part, shared_nodes)
            if part.is_empty or part.area < 1e-13:
                dropped += original_part.area
                continue
            for triangle in constrained_delaunay_triangles(part).geoms:
                coords = list(triangle.exterior.coords)[:3]
                if (triangle.exterior.is_ccw and sign < 0) or (
                    not triangle.exterior.is_ccw and sign > 0
                ):
                    coords.reverse()
                vertices = []
                intended = []
                for x, y in coords:
                    distances = np.linalg.norm(xyz[:, :2] - (x, y), axis=1)
                    if float(distances.min()) < 1e-9:
                        values = native[int(distances.argmin())].copy()
                    else:
                        values = (inverse @ np.asarray((x, y, 1.0))) @ native
                    values[0], values[1] = -y * 100, -x * 100
                    vertices.append(struct.pack("<8f", *values))
                    intended.append(values)
                payload = b"".join(vertices)
                values = native_values(payload)
                points = source_points(values)
                poly = Polygon(points[:, :2])
                normal = np.cross(points[1] - points[0], points[2] - points[0])
                size = float(np.linalg.norm(normal))
                if size < 1e-14 or poly.area < 1e-13:
                    dropped += triangle.area
                    continue
                expected_z = (
                    np.column_stack((points[:, 0], points[:, 1], np.ones(3))) @ zcoeff
                )
                error = float(abs(points[:, 2] - expected_z).max())
                bounds = []
                for p in values:
                    ex = abs(float(np.spacing(np.float32(p[1])))) / 200
                    ey = abs(float(np.spacing(np.float32(p[0])))) / 200
                    ez = abs(float(np.spacing(np.float32(p[2])))) / 200
                    bounds.append(
                        abs(float(zcoeff[0])) * ex + abs(float(zcoeff[1])) * ey + ez
                    )
                bound = max(bounds) + 1e-9
                if error > bound * 1.01:
                    raise ValueError(
                        "Fragment left its original plane beyond native float32 quantization"
                    )
                intended_values = np.asarray(intended)
                normal_error = float(
                    abs(values[:, 3:6] - intended_values[:, 3:6]).max()
                )
                uv_error = float(abs(values[:, 6:8] - intended_values[:, 6:8]).max())
                stored = np.column_stack((-values[:, 4], -values[:, 3], values[:, 5]))
                alignment = float((stored @ (normal / size)).min())
                max_plane = max(max_plane, error)
                max_bound = max(max_bound, bound)
                max_normal = max(max_normal, normal_error)
                max_uv = max(max_uv, uv_error)
                minimum = min(minimum, alignment)
                min_area = min(min_area, poly.area)
                emitted.append(LegacyRow(row.tile, row.kind, material, payload, -1))
                emitted_shapes.append(poly)
    union = unary_union(emitted_shapes)
    bound_xy = (
        max(abs(float(np.spacing(np.float32(v)))) for v in native[:, :2].flat)
        / 100
        * 1.5
        + 1e-9
    )
    unresolved = (
        original.difference(union.buffer(bound_xy)).area
        + union.difference(original.buffer(bound_xy)).area
    )
    overlap = max(0.0, sum(p.area for p in emitted_shapes) - union.area)
    if unresolved > 1e-8 or overlap > 1e-7:
        raise ValueError(
            ("Fragment coverage/overlap exceeded quantization", unresolved, overlap)
        )
    audit = GroundClipAudit(
        original.area,
        inside.area,
        outside.area,
        sum(p.area for p in emitted_shapes),
        dropped,
        max_plane,
        max_bound,
        max_normal,
        max_uv,
        unresolved,
        overlap,
        minimum,
        min_area,
    )
    return emitted, audit
