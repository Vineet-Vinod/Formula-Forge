"""Bounded mapped woodland, with detailed edges and inexpensive distant crowns."""
from __future__ import annotations

import hashlib
import math
import random

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.woodland_dataclasses import WoodlandPatch


def stand_with_clearing(scene: CircuitScene, start: float, end: float, side: int, *,
                        rows: int, setback: float, seat_material: str) -> BaseGeometry:
    scene.stand(start, end, side, rows=rows, setback=setback, seat_material=seat_material)
    span = (end - start) % scene.length
    steps = math.ceil(span / 8)
    strips = []
    for step in range(steps):
        a, b = scene.at(start + span * step / steps), scene.at(start + span * (step + 1) / steps)
        near_a = a.half_width + .95 + (a.left_shoulder if side > 0 else a.right_shoulder) + setback
        near_b = b.half_width + .95 + (b.left_shoulder if side > 0 else b.right_shoulder) + setback
        shape = Polygon([a.point(side * near_a)[:2], b.point(side * near_b)[:2],
                         b.point(side * (near_b + rows * .88))[:2],
                         a.point(side * (near_a + rows * .88))[:2]])
        if shape.is_valid:
            strips.append(shape)
    return unary_union(strips)


def mapped_woodland(scene: CircuitScene, clearings: tuple[BaseGeometry, ...] = ()) -> None:
    records = TypeAdapter(list[WoodlandPatch]).validate_json(
        (scene.sources / 'vegetation/woodland-polygons.json').read_bytes()
    )
    grid = scene.grid
    bounds = box(grid.x, grid.y, grid.x + (grid.columns - 1) * grid.step,
                 grid.y + (grid.rows - 1) * grid.step)
    blocked = unary_union([scene.corridor_mask.buffer(12),
                           *[shape.buffer(12) for shape in clearings],
                           *[shape.buffer(12) for shape in scene.extra_corridors],
                           *[shape.buffer(12) for shape in scene.water_shapes],
                           *[Polygon(building.ring).buffer(12) for building in scene.buildings]])
    occupied = Polygon()
    area, count, detailed, needles = 0., 0, 0, 0
    minimum_clearance = math.inf
    for record in records:
        shape = Polygon([scene.geo(lat, lon) for lon, lat in record.outer],
                        [[scene.geo(lat, lon) for lon, lat in ring] for ring in record.holes])
        shape = shape.intersection(bounds).difference(blocked).difference(occupied)
        occupied = occupied.union(shape)
        area += shape.area
        if shape.is_empty:
            continue
        interior = shape.buffer(-5)
        seed_text = f'{record.source_id}/{record.component}'.encode()
        rng = random.Random(int.from_bytes(hashlib.sha256(seed_text).digest()[:8]))
        xmin, ymin, xmax, ymax = shape.bounds
        spacing = 12.
        y = ymin + rng.uniform(0, spacing)
        while y < ymax:
            x = xmin + rng.uniform(0, spacing)
            while x < xmax:
                px, py = x + rng.uniform(-3.6, 3.6), y + rng.uniform(-3.6, 3.6)
                position = ShapePoint(px, py)
                if not interior.covers(position):
                    x += spacing
                    continue
                distance = scene.nearest(px, py)[1]
                edge = shape.boundary.distance(position)
                height = rng.uniform(17, 28)
                base = (px, py, scene.ground(px, py))
                fraction = 1. if record.leaf_type == 'needleleaved' else 0. if record.leaf_type == 'broadleaved' else .65 if scene.slug == 'austria' else .5
                needle = rng.random() < fraction
                seed = count * 137 + 941
                height *= random.Random(seed + 1709).uniform(.88, 1.08)
                if not needle:
                    height = min(height, edge * 2.3)
                near = distance < 250
                if needle:
                    needleleaf_tree(scene, base, height, seed, near, edge * .96)
                elif near:
                    scene.broadleaf(base, height, seed)
                else:
                    distant_broadleaf(scene, base, height, seed)
                detailed += int(near)
                count += 1
                needles += int(needle)
                crown_radius = min(height * .42, edge * .96)
                minimum_clearance = min(minimum_clearance, scene.corridor_mask.distance(position) - crown_radius)
                x += spacing
            y += spacing
    scene.vegetation.append({'name': 'Mapped continuous woodland',
                             'source': 'vegetation/woodland-provenance.json',
                             'patches': len(records), 'woodland_area_m2': area,
                             'reconstructed_trees': count, 'detailed_edge_trees': detailed,
                             'needleleaf_trees': needles,
                             'minimum_crown_clearance_from_corridor_m': minimum_clearance,
                             'detailed_range_m': 250,
                             'placement_status': 'Actual OSM forest/wood polygons and holes, clipped to retained classified-ground coverage. Roads, protection, aprons, buildings and water excluded. Tree positions, approximately 10–31 m edge/interior heights and mixed proportions where untagged are original reference-guided estimates; grounded layered crowns preserve canopy continuity without extending woodland into mapped clearings.'})


def needleleaf_tree(scene: CircuitScene, base: Point, height: float, seed: int,
                    detailed: bool, crown_limit: float) -> None:
    rng = random.Random(seed)
    lean_x, lean_y = rng.uniform(-.025, .025), rng.uniform(-.025, .025)
    top = add(base, (lean_x * height, lean_y * height, height))
    scene.beam('Building_WoodlandTrunks', 'Trunk', base, top, height * .012)
    layers = rng.randrange(14, 19) if detailed else rng.randrange(8, 11)
    bottom = rng.uniform(.13, .22)
    spread = rng.uniform(.25, .31)
    turn = rng.uniform(0, math.tau)
    profile = rng.uniform(.7, 1.15)
    for layer in range(layers):
        fraction = layer / max(1, layers - 1)
        level = bottom + fraction * (1.01 - bottom) + rng.uniform(-.012, .012)
        radius = height * (spread * (1 - fraction) ** profile + .018) * rng.uniform(.88, 1.1)
        radius = min(radius, max(.1, (crown_limit - math.hypot(lean_x, lean_y) * height) / 1.1))
        depth = height * (.14 + .035 * (1 - fraction)) * rng.uniform(.88, 1.08)
        angle = turn + layer * 2.39996
        offset = radius * .10
        center = add(base, (lean_x * height * level + math.cos(angle) * offset,
                            lean_y * height * level + math.sin(angle) * offset,
                            height * level))
        if detailed and layer % 4 == 0:
            root = add(base, (lean_x * height * level, lean_y * height * level, height * (level + .035)))
            branch = add(center, (math.cos(angle) * radius * .72, math.sin(angle) * radius * .72, -depth * .16))
            scene.beam('Building_WoodlandBranches', 'Trunk', root, branch, height * .003)
        column, row = (2, 5)[rng.randrange(2)], rng.randrange(6)
        u0, u1 = (column + .012) / 6, (column + .988) / 6
        v0, v1 = (row + .012) / 6, (row + .988) / 6
        for plane in range(3):
            azimuth = angle + plane * math.pi / 3 + rng.uniform(-.12, .12)
            dx, dy = math.cos(azimuth) * radius, math.sin(azimuth) * radius
            low = center[2] - depth * .48
            a, b = (center[0] - dx, center[1] - dy, low), (center[0] + dx, center[1] + dy, low)
            ta, tb = add(a, (lean_x * depth, lean_y * depth, depth)), add(b, (lean_x * depth, lean_y * depth, depth))
            scene.triangle('Building_WoodlandNeedles', 'TreeCanopy', ta, tb, b,
                           ((u0, v0), (u1, v0), (u1, v1)))
            scene.triangle('Building_WoodlandNeedles', 'TreeCanopy', ta, b, a,
                           ((u0, v0), (u1, v1), (u0, v1)))


def distant_broadleaf(scene: CircuitScene, base: Point, height: float, seed: int) -> None:
    rng = random.Random(seed)
    column, row = (0, 1, 3, 4)[rng.randrange(4)], rng.randrange(6)
    u0, u1 = (column + .012) / 6, (column + .988) / 6
    v0, v1 = (row + .012) / 6, (row + .988) / 6
    scene.beam('Building_WoodlandTrunks', 'Trunk', base, add(base, (0, 0, height * .58)), height * .01)
    turn = rng.uniform(0, math.tau)
    for plane in range(3):
        angle = turn + plane * math.pi / 3
        dx, dy = math.cos(angle) * height * .34, math.sin(angle) * height * .34
        a, b = (base[0] - dx, base[1] - dy, base[2]), (base[0] + dx, base[1] + dy, base[2])
        ta, tb = add(a, (0, 0, height)), add(b, (0, 0, height))
        scene.triangle('Building_WoodlandBroadleaf', 'TreeCanopy', ta, tb, b,
                       ((u0, v0), (u1, v0), (u1, v1)))
        scene.triangle('Building_WoodlandBroadleaf', 'TreeCanopy', ta, b, a,
                       ((u0, v0), (u1, v1), (u0, v1)))
