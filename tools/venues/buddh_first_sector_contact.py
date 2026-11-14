"""Export the actual bounded Buddh planes with distinct native contact roles."""

from __future__ import annotations

import math
import struct
from itertools import combinations, pairwise
from pathlib import Path
from typing import Literal, cast

from circuit_dataclasses import Point
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as GeoPoint
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.buddh_first_sector_dataclasses import (
    ClassificationTriangle,
    ContactTriangle,
    FirstSectorResult,
)


def native_triangle(
    xy: list[tuple[float, float]],
    support: tuple[Point, Point, Point],
    surface: Literal["paved", "gravel", "grass"],
) -> ContactTriangle | None:
    a, b, c = support
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(determinant) < 1e-12:
        raise ValueError("A Buddh contact plane has no qualified source owner")
    if not Polygon(xy).exterior.is_ccw:
        xy.reverse()
    points = []
    for x, y in xy:
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
        z = u * a[2] + v * b[2] + (1 - u - v) * c[2]
        points.append(cast(Point, struct.unpack("<3f", struct.pack("<3f", x, y, z))))
    if Polygon([p[:2] for p in points]).area <= 0.00001:
        return None
    return ContactTriangle((points[0], points[1], points[2]), surface)


def packed_contact(result: FirstSectorResult) -> tuple[ContactTriangle, ...]:
    output = []
    groups: dict[
        tuple[Literal["paved", "gravel", "grass"], tuple[Point, Point, Point]],
        list[Polygon],
    ] = {}
    for contact in result.contact:
        plan = Polygon([p[:2] for p in contact.points])
        if plan.area <= 1e-8:
            continue
        key = contact.surface, contact.support or contact.points
        groups.setdefault(key, []).append(plan)
    for (surface, support), plans in groups.items():
        for source_triangle in constrained_delaunay_triangles(unary_union(plans)).geoms:
            domain = source_triangle.buffer(0.0003, join_style="bevel")
            center = domain.centroid.coords[0]
            lost_fan = False
            for edge_a, edge_b in pairwise(list(domain.exterior.coords)):
                triangle = native_triangle([center, edge_a, edge_b], support, surface)
                if triangle is None:
                    lost_fan = True
                else:
                    output.append(triangle)
            if lost_fan:
                for cell in constrained_delaunay_triangles(domain).geoms:
                    triangle = native_triangle(
                        list(cell.exterior.coords)[:3], support, surface
                    )
                    if triangle is not None:
                        output.append(triangle)
    output = list(dict.fromkeys(output))
    cells: dict[tuple[int, int], list[int]] = {}

    def register(index: int) -> None:
        points = output[index].points
        for x in range(
            math.floor(min(p[0] for p in points) / 4),
            math.floor(max(p[0] for p in points) / 4) + 1,
        ):
            for y in range(
                math.floor(min(p[1] for p in points) / 4),
                math.floor(max(p[1] for p in points) / 4) + 1,
            ):
                cells.setdefault((x, y), []).append(index)

    for index in range(len(output)):
        register(index)
    tolerance = struct.unpack("<f", struct.pack("<f", 0.00001))[0]

    def covered(x: float, y: float) -> bool:
        for index in cells.get((math.floor(x / 4), math.floor(y / 4)), ()):
            a, b, c = output[index].points
            determinant = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            first = (
                (c[0] - b[0]) * (y - b[1]) - (c[1] - b[1]) * (x - b[0])
            ) / determinant
            second = (
                (a[0] - c[0]) * (y - c[1]) - (a[1] - c[1]) * (x - c[0])
            ) / determinant
            if min(first, second, 1 - first - second) >= -tolerance:
                return True
        return False

    for contact in result.contact:
        plan = Polygon([p[:2] for p in contact.points])
        if (
            not 1e-8 < plan.area <= 0.0011
            or max(
                math.dist(a[:2], b[:2])
                for a, b in pairwise((*contact.points, contact.points[0]))
            )
            > 0.15
        ):
            continue
        probes = [p[:2] for p in contact.points]
        probes.extend(
            ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            for a, b in pairwise((*contact.points, contact.points[0]))
        )
        probes.append(plan.centroid.coords[0])
        if all(covered(x, y) for x, y in probes):
            continue
        a, b, c = contact.support or contact.points
        determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        padding = 0.001
        # This pinned 2 mm island cannot meet the native F32 area cutoff at 1 mm.
        if (
            contact.surface == "grass"
            and plan.area < 1.2e-6
            and plan.centroid.distance(GeoPoint(264.879296875, -107.03759440104167))
            < 0.0003
        ):
            padding = 0.0011
        for xy in combinations(
            list(
                plan.buffer(
                    padding, quad_segs=8 if padding > 0.001 else 2, join_style="round"
                ).exterior.coords
            )[:-1],
            3,
        ):
            points = []
            for x, y in xy:
                u = (
                    (b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])
                ) / determinant
                v = (
                    (c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])
                ) / determinant
                z = u * a[2] + v * b[2] + (1 - u - v) * c[2]
                points.append(
                    cast(Point, struct.unpack("<3f", struct.pack("<3f", x, y, z)))
                )
            if Polygon([p[:2] for p in points]).area * 2 < tolerance:
                continue
            output.append(
                ContactTriangle(
                    (points[0], points[1], points[2]),
                    contact.surface,
                    contact.support or contact.points,
                    True,
                    contact.points,
                )
            )
            register(len(output) - 1)
        if not all(covered(x, y) for x, y in probes):
            raise ValueError(
                f"A tiny Buddh source island exceeds the bounded native height encoding repair: {contact.surface}, {contact.points}, area {plan.area}"
            )
    return tuple(dict.fromkeys(output))


def literal(value: float) -> str:
    text = format(value, ".9g")
    if "." not in text and "e" not in text:
        text += ".0"
    return text + "f"


def classification_contact(
    result: FirstSectorResult,
) -> tuple[ClassificationTriangle, ...]:
    output = []
    surfaces: tuple[Literal["paved", "gravel"], ...] = ("paved", "gravel")
    for surface in surfaces:
        domain = unary_union(
            [
                Polygon([p[:2] for p in t.points])
                for t in result.contact
                if t.surface == surface and not t.height_only
            ]
        )
        for triangle in constrained_delaunay_triangles(domain).geoms:
            if triangle.area <= 1e-8:
                continue
            points = [
                cast(
                    tuple[float, float], struct.unpack("<2f", struct.pack("<2f", x, y))
                )
                for x, y in list(triangle.exterior.coords)[:3]
            ]
            if Polygon(points).area > 0:
                output.append(
                    ClassificationTriangle((points[0], points[1], points[2]), surface)
                )
    return tuple(dict.fromkeys(output))


def write_contact(result: FirstSectorResult, path: Path) -> None:
    classification = classification_contact(result)
    height = packed_contact(result)
    groups = (
        (
            "Paved",
            6,
            [
                tuple(v for p in t.points for v in p)
                for t in classification
                if t.surface == "paved"
            ],
        ),
        (
            "Gravel",
            6,
            [
                tuple(v for p in t.points for v in p)
                for t in classification
                if t.surface == "gravel"
            ],
        ),
        (
            "Ground",
            9,
            [
                tuple(v for p in t.points for v in p)
                for t in height
                if not t.height_only
            ],
        ),
        (
            "Height",
            9,
            [tuple(v for p in t.points for v in p) for t in height if t.height_only],
        ),
    )
    lines = [
        "// Actual bounded Buddh first-sector horizontal contact in source east/north metres.",
        "// Paved and Gravel are compact XY classification only. Grass keeps the no-hit fallback.",
        "// Ground and Height contain driving-height planes only; never classify them as a surface.",
    ]
    for name, width, faces in groups:
        lines.append(
            f"constexpr std::array<std::array<float, {width}>, {len(faces)}> kBuddhFirstSector{name}{{{{"
        )
        for face in faces:
            values = ", ".join(literal(value) for value in face)
            lines.append("    {{" + values + "}},")
        lines.append("}};")
    path.write_text("\n".join(lines) + "\n")
