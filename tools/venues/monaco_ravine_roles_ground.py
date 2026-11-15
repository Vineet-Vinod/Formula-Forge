"""Material segmentation on original packed planes; no sampled height field."""

from __future__ import annotations

import math
import struct
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import explain_validity

from venues.monaco_ravine_roles_dataclasses import GroundClipAudit, GroundRow


def packed_xy(point: tuple[float, ...]) -> tuple[float, float]:
    y, x = struct.unpack("<2f", struct.pack("<2f", -point[1] * 100, -point[0] * 100))
    return -x / 100, -y / 100

def native_values(payload: bytes) -> NDArray[np.float64]:
    return np.asarray(struct.unpack("<24f", payload)).reshape(3, 8)

def source_points(native: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.stack((-native[:, 1] / 100, -native[:, 0] / 100, native[:, 2] / 100), axis=1)


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
    if len(set(shell)) < 3:
        return Polygon()
    result = Polygon(shell, holes)
    if result.area < 1e-13:
        return Polygon()
    if not result.is_valid:
        raise ValueError(
            {"error": "Packed material boundary is invalid", "reason": explain_validity(result), "original_wkt": part.wkt, "packed_wkt": result.wkt, "nodes": sorted(nodes)}
        )
    return result


def width(plan: Polygon) -> float:
    coordinates = list(plan.exterior.coords)
    longest = max((math.dist(a, b) for a, b in pairwise(coordinates)), default=0.0)
    return 2 * plan.area / longest if longest else 0.0

def recolor(
    row: GroundRow, domain: BaseGeometry
) -> tuple[list[GroundRow], GroundClipAudit | None]:
    native = native_values(row.payload)
    xyz = source_points(native)
    original = Polygon(xyz[:, :2])
    inside = original.intersection(domain)
    if inside.area < 1e-10:
        return [row], None
    outside = original.difference(domain)
    source_xy_ulp = max(abs(float(np.spacing(np.float32(v)))) for v in native[:, :2].flat) / 100
    smallest_xy_ulp = min(abs(float(np.spacing(np.float32(v)))) for v in native[:, :2].flat) / 100
    outside_ghost = outside.area if outside.area < 1e-12 and all(
        width(p) <= smallest_xy_ulp * .5
        and len({packed_xy(tuple(xy)) for xy in p.exterior.coords}) < 3
        for p in polygon_parts(outside)
    ) else 0.0
    if outside.is_empty or outside_ghost:
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
            reassigned_zero_width_outside_area_m2=outside_ghost,
        )
        return [GroundRow("MonacoNaturalGround", row.payload)], audit
    inverse = np.linalg.inv(np.column_stack((xyz[:, 0], xyz[:, 1], np.ones(3))).T)
    zcoeff = np.linalg.solve(
        np.column_stack((xyz[:, 0], xyz[:, 1], np.ones(3))), xyz[:, 2]
    )
    cross = np.cross(xyz[1] - xyz[0], xyz[2] - xyz[0])
    sign = float(cross[2])
    shared_nodes = boundary_points(inside) | boundary_points(outside)
    inside_parts = polygon_parts(inside)
    if inside_parts and all(width(p) <= source_xy_ulp for p in inside_parts):
        try:
            packed_inside = [packed_part(p, shared_nodes) for p in inside_parts]
            unrepresentable = all(p.is_empty or p.area < 1e-13 for p in packed_inside)
        except ValueError:
            unrepresentable = True
        if unrepresentable:
            stored = np.column_stack((-native[:, 4], -native[:, 3], native[:, 5]))
            alignment = float((stored @ (cross / np.linalg.norm(cross))).min())
            audit = GroundClipAudit(original.area, 0.0, original.area, original.area,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, alignment, original.area,
                held_unrepresentable_natural_area_m2=inside.area)
            return [row], audit
    emitted = []
    emitted_shapes = []
    max_plane = 0.0
    max_bound = 0.0
    max_normal = 0.0
    max_uv = 0.0
    dropped = 0.0
    maximum_dropped_width = 0.0
    minimum = 1.0
    min_area = math.inf
    for shape, material in ((inside, "MonacoNaturalGround"), (outside, row.material)):
        if shape.is_empty:
            continue
        for original_part in polygon_parts(shape):
            # Node and quantize both sides before meshing, so collinear source
            # knots cannot become different float32 seam chords.
            part = packed_part(original_part, shared_nodes)
            if part.is_empty or part.area < 1e-13:
                dropped += original_part.area
                maximum_dropped_width = max(maximum_dropped_width, width(original_part))
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
                    maximum_dropped_width = max(maximum_dropped_width, width(triangle))
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
                emitted.append(GroundRow(material, payload))
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
    if dropped > 1e-12 or maximum_dropped_width > smallest_xy_ulp * .5:
        raise ValueError('A dropped material component exceeds its arithmetic encoding bound')
    if minimum <= 0:
        raise ValueError('A new material fragment has an inward stored normal')
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
        maximum_dropped_width_m=maximum_dropped_width,
    )
    return emitted, audit
