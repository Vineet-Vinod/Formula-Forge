"""Photo-qualified narrow-leaf planting inside the existing Les Bruyères bed."""
from __future__ import annotations

import math
import random
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, cross, mul, norm, sub
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon

from venues.monaco_bamboo_dataclasses import (
    BambooAudit,
    BambooSpec,
    CaneCurve,
    CanePose,
    TwigArc,
)

KIND = 'Building_MonacoBruyeresBamboo'
CANE = 'MonacoBambooCane'
DEEP = 'MonacoBambooLeafDeep'
MID = 'MonacoBambooLeafMid'


def tetrahedron(scene: MeshScene, vertices: tuple[Point, Point, Point, Point], material: str) -> None:
    center = mul(add(add(vertices[0], vertices[1]), add(vertices[2], vertices[3])), .25)
    for indices in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)):
        a, b, c = (vertices[i] for i in indices)
        middle = mul(add(add(a, b), c), 1 / 3)
        if sum(x * y for x, y in zip(cross(sub(b, a), sub(c, a)), sub(middle, center))) < 0:
            b, c = c, b
        scene.triangle(KIND, material, a, b, c)


def tube(scene: MeshScene, points: tuple[Point, ...], radius: float) -> None:
    rings = []
    for index, p in enumerate(points):
        before, after = points[max(0, index - 1)], points[min(len(points) - 1, index + 1)]
        tangent = norm(sub(after, before))
        side = norm(cross(tangent, (0., 1., 0.)))
        second = norm(cross(tangent, side))
        rings.append(tuple(add(p, add(mul(side, radius * math.cos(i * math.tau / 6)),
                                       mul(second, radius * math.sin(i * math.tau / 6)))) for i in range(6)))
    for lower, upper in pairwise(rings):
        for i in range(6):
            j = (i + 1) % 6
            scene.quad(KIND, CANE, lower[i], lower[j], upper[j], upper[i])
    for i in range(6):
        j = (i + 1) % 6
        scene.triangle(KIND, CANE, points[0], rings[0][j], rings[0][i])
        scene.triangle(KIND, CANE, points[-1], rings[-1][i], rings[-1][j])


def blade(scene: MeshScene, base: Point, direction: Point, length: float,
          width: float, material: str, planted: Polygon) -> bool:
    tangent = norm(direction)
    side = norm(cross(tangent, (0., 0., 1.)))
    normal = norm(cross(side, tangent))
    tip = add(base, add(mul(tangent, length), (0., 0., -.018)))
    mid = add(base, add(mul(sub(tip, base), .44), mul(normal, .006)))
    vertices = (base, add(mid, mul(side, width / 2)), tip, sub(mid, mul(side, width / 2)))
    projected = Polygon([p[:2] for p in vertices])
    if (not all(planted.covers(ShapePoint(p[:2])) for p in vertices)
            or projected.difference(planted).area > 1e-10):
        return False
    tetrahedron(scene, vertices, material)
    return True


def retained_cane_poses(height: Callable[[float, float], float], planted: Polygon) -> tuple[CanePose, ...]:
    rng = random.Random(94400108)
    poses: list[CanePose] = []
    for _index in range(220):
        x, y = rng.uniform(25.4, 34.2), rng.uniform(284.6, 291.5)
        if not planted.buffer(-.25).covers(ShapePoint(x, y)):
            continue
        z = height(x, y)
        original_height = rng.uniform(1.8, 3.6)
        root = x, y, z - .05
        poses.append(CanePose(len(poses), root, (z + original_height) - root[2] - .05))
        # Retain the old six spray draws so all following root positions stay exact.
        for _level in range(6):
            rng.random()
            rng.uniform(.35, .70)
    return tuple(poses)


def emit_bamboo(scene: MeshScene, poses: tuple[CanePose, ...], source: BambooSpec,
                planted: Polygon) -> BambooAudit:
    if (source.minimum_canopy_top_absolute_m >= source.maximum_canopy_top_absolute_m
            or source.minimum_leaf_length_m > source.maximum_leaf_length_m
            or source.minimum_leaf_width_m > source.maximum_leaf_width_m
            or not poses):
        raise ValueError('Bamboo source intervals or retained roots are invalid')
    if source.minimum_canopy_top_absolute_m - source.relative_datum_m - max(p.root[2] for p in poses) < 3:
        raise ValueError('The retained roots are incompatible with the photo-qualified canopy envelope')
    permitted = planted.buffer(-source.boundary_margin_m)
    if not isinstance(permitted, Polygon) or not permitted.is_valid:
        raise ValueError('The private cane field requires its original connected planted bed')
    center = permitted.representative_point()
    minimum_clearance = math.inf
    heights = []
    branch_count = blade_count = skipped = 0
    for pose in poses:
        rng = random.Random(source.seed * 1009 + pose.index)
        root = pose.root
        top_absolute = rng.uniform(source.minimum_canopy_top_absolute_m,
                                   source.maximum_canopy_top_absolute_m)
        height = top_absolute - source.relative_datum_m - root[2]
        if height < 3:
            raise ValueError('A retained root is incompatible with the photo-qualified canopy envelope')
        heights.append(height)
        lean = rng.uniform(.25, .72)
        angle = rng.uniform(0, math.tau)
        tip_xy = (root[0] + math.cos(angle) * lean, root[1] + math.sin(angle) * lean)
        if not permitted.buffer(-.28).covers(ShapePoint(tip_xy)):
            angle = math.atan2(center.y - root[1], center.x - root[0])
            lean = min(lean, math.dist(root[:2], (center.x, center.y)) * .45)
        direction_xy = math.cos(angle), math.sin(angle)

        cane = CaneCurve(root, direction_xy, lean, height)
        nodes = tuple(cane.point(i / 7) for i in range(8))
        if any(not planted.covers(ShapePoint(p[:2])) for p in nodes):
            raise ValueError('A new cane escaped the retained planted bed')
        tube(scene, nodes, source.cane_radius_m * rng.uniform(.75, 1.2))
        fractions = sorted([rng.uniform(.08, .28), rng.uniform(.12, .40),
                            *(rng.uniform(.25, .98) for _ in range(source.branches_per_cane - 2))])
        for fraction in fractions:
            start = cane.point(fraction)
            theta = rng.uniform(0, math.tau)
            reach = rng.uniform(.45, source.maximum_branch_reach_m) * (1.12 - fraction * .38)
            horizontal = math.cos(theta), math.sin(theta), 0.
            side = -math.sin(theta), math.cos(theta), 0.
            lift, droop = rng.uniform(.12, .30), rng.uniform(.16, .38)

            twig = TwigArc(start, horizontal, reach, lift, droop)
            end = twig.point(1.)
            if not permitted.covers(ShapePoint(end[:2])):
                theta = math.atan2(center.y - start[1], center.x - start[0])
                horizontal = math.cos(theta), math.sin(theta), 0.
                side = -math.sin(theta), math.cos(theta), 0.
                reach = min(reach, math.dist(start[:2], (center.x, center.y)) * .55)
                twig = TwigArc(start, horizontal, reach, lift, droop)
                end = twig.point(1.)
            if not permitted.covers(ShapePoint(end[:2])):
                continue
            mid = twig.point(.5)
            scene.beam(KIND, CANE, start, mid, .006)
            scene.beam(KIND, CANE, mid, end, .0045)
            branch_count += 1
            for i in range(source.leaves_per_branch):
                t = (.08 + .90 * (i + rng.uniform(.05, .95)) / source.leaves_per_branch)
                base = twig.point(t)
                sign = -1 if i % 2 else 1
                leaf_direction = add(mul(horizontal, rng.uniform(.15, .45)),
                                     add(mul(side, sign * rng.uniform(.65, .95)),
                                         (0., 0., rng.uniform(-.70, .12))))
                length = rng.uniform(source.minimum_leaf_length_m, source.maximum_leaf_length_m)
                width = rng.uniform(source.minimum_leaf_width_m, source.maximum_leaf_width_m)
                material = DEEP if rng.random() < .67 else MID
                if blade(scene, base, leaf_direction, length, width, material, permitted):
                    minimum_clearance = min(minimum_clearance, planted.boundary.distance(ShapePoint(base[:2])))
                    blade_count += 1
                else:
                    skipped += 1
    return BambooAudit(len(poses), branch_count, blade_count, skipped, min(heights), max(heights),
                       source.height_uncertainty_m, minimum_clearance)
