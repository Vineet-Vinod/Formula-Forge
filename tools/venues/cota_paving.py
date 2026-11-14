"""Export the actual flat back-straight apron planes for native contact."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import cast

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.cota import apron_cells

PavingTriangle = tuple[Point, Point, Point]


def backstraight_paving(scene: CircuitScene) -> list[PavingTriangle]:
    if scene.slug != 'cota':
        raise ValueError('The back-straight contact requires the COTA source frame')
    cover = unary_union([
        cell for side in (-1, 1)
        for cell, _sample in apron_cells(scene, 2520, 3590, side, .15, 3.2)
    ])
    triangles = []
    for a, b, c in scene.surface_points:
        plan = Polygon([a[:2], b[:2], c[:2]])
        if plan.area < 1e-8 or not plan.intersects(cover):
            continue
        determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        for triangle in constrained_delaunay_triangles(plan.intersection(cover)).geoms:
            if triangle.area <= .0001:
                continue
            points = []
            xy = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                xy.reverse()
            for x, y in xy:
                u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
                v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
                points.append((x, y, u * a[2] + v * b[2] + (1 - u - v) * c[2] - .001))
            packed = [cast(Point, struct.unpack('<3f', struct.pack('<3f', *point))) for point in points]
            if Polygon([point[:2] for point in packed]).area <= .0001:
                continue
            triangles.append((packed[0], packed[1], packed[2]))
    if not triangles:
        raise ValueError('The rendered back-straight apron has no physical planes')
    return triangles


def write_backstraight_paving(scene: CircuitScene, path: Path) -> None:
    triangles = backstraight_paving(scene)
    lines = [
        '// Flat COTA back-straight apron contact in source east/north metres.',
        f'constexpr std::array<std::array<float, 9>, {len(triangles)}> kCotaBackstraightPaving{{{{',
    ]
    for triangle in triangles:
        values = ', '.join(f'{value:.9f}f' for point in triangle for value in point)
        lines.append('    {{' + values + '}},')
    lines.append('}};')
    path.write_text('\n'.join(lines) + '\n')
