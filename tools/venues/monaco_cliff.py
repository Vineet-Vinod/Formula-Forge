"""The bounded west cliff uses retained IGN samples without changing native contact."""

from __future__ import annotations

import math
import random

from circuit_dataclasses import Point, TerrainGrid
from circuit_mesh import MeshScene, norm
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.monaco_approaches import ground_sample
from venues.monaco_dataclasses import ApproachGround, CostaGroundFace
from venues.monaco_west_dataclasses import CliffPatch


def source_height(grid: TerrainGrid, x: float, y: float) -> float:
    column, row = (x-grid.x)/grid.step, (y-grid.y)/grid.step
    if not 0 <= column < grid.columns-1 or not 0 <= row < grid.rows-1:
        raise ValueError('Cliff reconstruction lies outside its retained IGN source')
    i, j = int(column), int(row)
    a, b = column-i, row-j
    return ((grid.heights[j*grid.columns+i]*(1-a)+grid.heights[j*grid.columns+i+1]*a)*(1-b)
            +(grid.heights[(j+1)*grid.columns+i]*(1-a)+grid.heights[(j+1)*grid.columns+i+1]*a)*b)


def old_vertex(face: CostaGroundFace, x: float, y: float) -> tuple[Point, Point, tuple[float, float]]:
    from venues.monaco_landcover import interpolate

    height, normal = interpolate(face, x, y)
    return (x, y, height), normal, (x/8, y/8)


def height(ground: ApproachGround, grid: TerrainGrid, patch: Polygon,
           collar: float, x: float, y: float) -> float:
    old, _ = ground_sample(ground, (x, y))
    if not patch.covers(ShapePoint(x, y)):
        return old
    fraction = min(1., patch.boundary.distance(ShapePoint(x, y))/collar)
    blend = fraction*fraction*(3-2*fraction)
    return old+(source_height(grid, x, y)-old)*blend


def skin(scene: MeshScene, ground: ApproachGround, grid: TerrainGrid, source: CostaGroundFace,
         patch: Polygon, config: CliffPatch, shape: Polygon, inside: bool, material: str) -> int:
    count = 0
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points, normals, uvs = [], [], []
        for x, y in list(orient(triangle, sign=1.).exterior.coords)[:3]:
            point, normal, uv = old_vertex(source, x, y)
            if inside:
                z = height(ground, grid, patch, config.collar_width_m, x, y)
                fraction = min(1., patch.boundary.distance(ShapePoint(x, y))/config.collar_width_m)
                fraction = fraction*fraction*(3-2*fraction)
                epsilon = .005
                dx = (height(ground, grid, patch, config.collar_width_m, x+epsilon, y)
                      -height(ground, grid, patch, config.collar_width_m, x-epsilon, y))/(2*epsilon)
                dy = (height(ground, grid, patch, config.collar_width_m, x, y+epsilon)
                      -height(ground, grid, patch, config.collar_width_m, x, y-epsilon))/(2*epsilon)
                revised = norm((-dx, -dy, 1.))
                normal = tuple((1-fraction)*normal[i]+fraction*revised[i] for i in range(3))
                point = x, y, z
            points.append(point)
            normals.append(normal)
            uvs.append(uv)
        scene.triangle('Tile_WestCliff', material, points[0], points[1], points[2], tuple(uvs), tuple(normals))
        count += 1
    return count


def cliff_regions(scene: MeshScene, ground: ApproachGround, grid: TerrainGrid,
                  face: CostaGroundFace, config: CliffPatch) -> int:
    patch = Polygon(config.outer_xy_m)
    ivy = unary_union([Polygon(ring) for ring in config.ivy_rings_xy_m])
    plan = Polygon([p[:2] for p in face.points])
    domain = plan.intersection(patch)
    if domain.is_empty or domain.area < 1e-10:
        return 0
    xmin, ymin, xmax, ymax = domain.bounds
    step = config.render_step_m
    count = 0
    for row in range(math.floor(ymin/step), math.ceil(ymax/step)):
        for column in range(math.floor(xmin/step), math.ceil(xmax/step)):
            cell = box(column*step, row*step, (column+1)*step, (row+1)*step)
            part = cell.intersection(plan).intersection(patch)
            if part.area > 1e-10:
                count += skin(scene, ground, grid, face, patch, config, part.difference(ivy), True, 'MonacoRockGround')
                count += skin(scene, ground, grid, face, patch, config, part.intersection(ivy), True, 'MonacoIvyGround')
    return count


def cliff_preflight(ground: ApproachGround, grid: TerrainGrid, config: CliffPatch) -> None:
    patch = Polygon(config.outer_xy_m)
    ivy = unary_union([Polygon(ring) for ring in config.ivy_rings_xy_m])
    if not patch.is_valid or not 50 < patch.area < 300:
        raise ValueError('The west cliff must retain its bounded valid source domain')
    if not ivy.is_empty and (not ivy.is_valid or ivy.difference(patch).area > 1e-8):
        raise ValueError('The irregular ivy masks must remain inside the qualified cliff domain')
    for x, y in patch.exterior.coords:
        source_height(grid, x, y)
        ground_sample(ground, (x, y))


def cliff_vegetation(scene: MeshScene, ground: ApproachGround, grid: TerrainGrid,
                     config: CliffPatch) -> int:
    patch = Polygon(config.outer_xy_m)
    ivy = unary_union([Polygon(ring) for ring in config.ivy_rings_xy_m])
    xmin, ymin, xmax, ymax = patch.bounds
    rng = random.Random(44202019)
    shrubs = 0
    for row in range(math.floor(ymin/1.8), math.ceil(ymax/1.8)):
        for column in range(math.floor(xmin/1.8), math.ceil(xmax/1.8)):
            x, y = (column+.5)*1.8+rng.uniform(-.24, .24), (row+.5)*1.8+rng.uniform(-.24, .24)
            if ivy.covers(ShapePoint(x, y).buffer(.45)):
                size = rng.uniform(1.6, 2.4)
                z = height(ground, grid, patch, config.collar_width_m, x, y)
                scene.broadleaf((x, y, z-size*.43), size, 744200+shrubs)
                shrubs += 1
    return shrubs
