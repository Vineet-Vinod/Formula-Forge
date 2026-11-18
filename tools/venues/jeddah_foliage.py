"""Separated palm fronds and irregular, smoothly shaded Corniche crowns."""

from __future__ import annotations

import math
import random

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, cross, mul, norm, sub
from circuit_scene import CircuitScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon


def branch(scene: MeshScene, a: Point, b: Point, first_radius: float,
           last_radius: float, material: str = "Trunk", sides: int = 8) -> None:
    direction = norm(sub(b, a))
    across = norm(cross(direction, (0., 0., 1.) if abs(direction[2]) < .95 else (0., 1., 0.)))
    up = cross(direction, across)
    for index in range(sides):
        first, last = math.tau * index / sides, math.tau * (index + 1) / sides
        na = add(mul(across, math.cos(first)), mul(up, math.sin(first)))
        nb = add(mul(across, math.cos(last)), mul(up, math.sin(last)))
        pa, pb = add(a, mul(na, first_radius)), add(a, mul(nb, first_radius))
        qa, qb = add(b, mul(na, last_radius)), add(b, mul(nb, last_radius))
        scene.triangle("Building_JeddahVegetation", material, pa, pb, qb, normals=(na, nb, nb))
        scene.triangle("Building_JeddahVegetation", material, pa, qb, qa, normals=(na, nb, na))


def leaflet(scene: MeshScene, root: Point, tip: Point, width: float, material: str) -> None:
    across = norm(cross(sub(tip, root), (0., 0., 1.)))
    center = add(root, mul(sub(tip, root), .53))
    ridge = add(center, (0., 0., .025))
    left, right = add(center, mul(across, -width)), add(center, mul(across, width))
    for a, b, c in ((root, left, ridge), (left, tip, ridge),
                    (tip, right, ridge), (right, root, ridge)):
        scene.triangle("Building_JeddahPalmLeaflets", material, a, b, c)


def palm(scene: MeshScene, base: Point, height: float, seed: int) -> None:
    rng = random.Random(seed)
    phase = rng.random() * math.tau
    trunk_height = height * .82
    lean = (.12 + rng.random() * .35) * math.cos(phase), (.12 + rng.random() * .35) * math.sin(phase)

    def trunk(t: float) -> Point:
        return base[0] + lean[0] * t * t, base[1] + lean[1] * t * t, base[2] + trunk_height * t

    for index in range(18):
        t0, t1 = index / 18, (index + 1) / 18
        r0, r1 = .23 - .055 * t0, .23 - .055 * t1
        branch(scene, trunk(t0), trunk(t1), r0, r1, "JeddahPalmBark", 12)
        branch(scene, trunk(t0), add(trunk(t0), (0., 0., .055)),
               r0 + .018, r0, "JeddahPalmBarkLight", 12)
    crown = trunk(1)
    # Successive frond whorls have different rise, reach and droop.
    for ring, count, reach, rise, drop in ((0, 11, 3.9, .45, 2.45),
                                         (1, 13, 3.7, 1.75, 1.0),
                                         (2, 9, 2.65, 2.25, -.15)):
        for index in range(count):
            angle = phase + (index + ring * .37) * math.tau / count + rng.uniform(-.12, .12)
            along = math.cos(angle), math.sin(angle), 0.
            across = -along[1], along[0], 0.
            length = reach * rng.uniform(.85, 1.12)
            start = add(crown, (0., 0., ring * .15))

            def rachis(t: float, start: Point = start, along: Point = along,
                       length: float = length, rise: float = rise, drop: float = drop) -> Point:
                return add(start, add(mul(along, length * t),
                                      (0., 0., rise * math.sin(math.pi * t * .8) - drop * t * t)))

            for section in range(12):
                t0, t1 = section / 12, (section + 1) / 12
                branch(scene, rachis(t0), rachis(t1), .026 * (1 - .8 * t0),
                       .026 * (1 - .8 * t1), "JeddahPalmLeaf", 6)
            for pair in range(21):
                t = .13 + pair / 21 * .84
                span = (.12 + .76 * math.sin(math.pi * t) ** .7) * rng.uniform(.85, 1.10)
                for side in (-1, 1):
                    root = rachis(t + rng.uniform(-.009, .009))
                    tip = add(root, add(mul(across, side * span),
                                        add(mul(along, span * .34), (0., 0., -span * .28))))
                    material = ("JeddahPalmLeaf", "JeddahPalmLeafLight", "JeddahPalmLeafShade")[(index + pair + ring) % 3]
                    leaflet(scene, root, tip, .028 + .02 * math.sin(math.pi * t), material)


def broadleaf(scene: MeshScene, base: Point, height: float, seed: int) -> None:
    rng = random.Random(seed)
    fork = add(base, (0., 0., height * .40))
    branch(scene, base, fork, .20, .13, sides=12)
    crown_center = add(base, (0., 0., height * .69))
    crown_radius = height * .31
    for cluster in range(25):
        angle = cluster * 2.399963 + seed * .19
        radius = crown_radius * math.sqrt((cluster + .5) / 25) * .78
        z = height * (.62 + .21 * (1 - radius / crown_radius)) + rng.uniform(-.045, .045) * height
        center = add(base, (math.cos(angle) * radius, math.sin(angle) * radius, z))
        if cluster < 8:
            branch(scene, fork, center, .075, .018, sides=7)
        column, row = (2, 5)[cluster % 2], (seed + cluster) % 3
        u0, u1 = (column + .02) / 6, (column + .98) / 6
        v0, v1 = (row + .02) / 6, (row + .98) / 6
        width = height * rng.uniform(.22, .30)
        tall = width * rng.uniform(.85, 1.15)
        for plane in range(3):
            heading = angle + plane * math.pi / 3
            axis = math.cos(heading), math.sin(heading), 0.
            normal = -axis[1], axis[0], 0.
            points = []
            for y in range(3):
                for x in range(3):
                    p = add(center, add(mul(axis, width * (x / 2 - .5)),
                                        add(mul(normal, .12 * width * math.sin(math.pi * x / 2)),
                                            (0., 0., tall * (y / 2 - .5)))))
                    points.append(p)
            for y in range(2):
                for x in range(2):
                    for indices in ((y * 3 + x, y * 3 + x + 1, (y + 1) * 3 + x + 1),
                                    (y * 3 + x, (y + 1) * 3 + x + 1, (y + 1) * 3 + x)):
                        face = tuple(points[i] for i in indices)
                        uv = tuple((u0 + (i % 3) / 2 * (u1 - u0),
                                    v1 - (i // 3) / 2 * (v1 - v0)) for i in indices)
                        normals = tuple(norm((p[0] - crown_center[0], p[1] - crown_center[1],
                                              (p[2] - crown_center[2]) * 1.3)) for p in face)
                        scene.triangle("Building_JeddahBroadleafCrowns", "JeddahTreeCanopy",
                                       face[0], face[1], face[2], uv=uv, normals=normals)


def planting(scene: CircuitScene, start: float, end: float, side: int, setback: float,
             spacing: float, height: float, palms: bool) -> None:
    count = max(1, math.ceil((end - start) / spacing))
    footprints = [Polygon(building.ring).buffer(2) for building in scene.buildings]
    placed = 0
    for index in range(count):
        seed = round(start) * 11 + index
        rng = random.Random(seed)
        sample = scene.at(start + (end - start) * (index + .5) / count + rng.uniform(-2, 2))
        shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
        lane = side * (sample.half_width + .95 + shoulder + setback + rng.uniform(0, 3.5))
        p = sample.point(lane)
        point = ShapePoint(p[:2])
        nearest, distance = scene.nearest(*p[:2])
        if distance < nearest.half_width + 5.5:
            continue
        if any(shape.covers(point) for shape in (*scene.water_shapes, *footprints)):
            continue
        base = p[0], p[1], scene.ground(*p[:2])
        tree_height = height * rng.uniform(.90, 1.16)
        if palms:
            palm(scene, base, tree_height, seed)
        else:
            broadleaf(scene, base, tree_height, seed)
        placed += 1
    scene.vegetation.append({"type": "Corniche pinnate palms" if palms else "Corniche broadleaf",
                             "start_m": start, "end_m": end, "side": side, "count": placed,
                             "setback_m": setback,
                             "placement": "Video-estimated sparse urban planting; varied crowns and height, all-road, water and property root clearances."})
