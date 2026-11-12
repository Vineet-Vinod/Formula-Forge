"""Bounded mapped woodland, with detailed edges and inexpensive distant crowns."""
from __future__ import annotations

import hashlib
import math
import random

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.west_architecture import conifer
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
                height = min(rng.uniform(17, 28), max(12, edge * 2.1))
                base = (px, py, scene.ground(px, py))
                fraction = 1. if record.leaf_type == 'needleleaved' else 0. if record.leaf_type == 'broadleaved' else .65 if scene.slug == 'austria' else .5
                needle = rng.random() < fraction
                seed = count * 137 + 941
                if distance < 65:
                    if needle:
                        conifer(scene, base, height, seed)
                    else:
                        scene.broadleaf(base, height, seed)
                    detailed += 1
                else:
                    distant_crown(scene, base, height, seed, needle)
                count += 1
                needles += int(needle)
                minimum_clearance = min(minimum_clearance, scene.corridor_mask.distance(position) - height * .42)
                x += spacing
            y += spacing
    scene.vegetation.append({'name': 'Mapped continuous woodland',
                             'source': 'vegetation/woodland-provenance.json',
                             'patches': len(records), 'woodland_area_m2': area,
                             'reconstructed_trees': count, 'detailed_edge_trees': detailed,
                             'needleleaf_trees': needles,
                             'minimum_crown_clearance_from_corridor_m': minimum_clearance,
                             'placement_status': 'Actual OSM forest/wood polygons and holes, clipped to retained classified-ground coverage. Roads, protection, aprons, buildings and water excluded. Tree positions, 12–28m edge/interior heights and mixed proportions where untagged are original reference-guided estimates; distant layered foliage preserves canopy continuity without extending woodland into mapped clearings.'})


def distant_crown(scene: CircuitScene, base: Point, height: float, seed: int,
                   needle: bool) -> None:
    rng = random.Random(seed)
    layers = 3 if needle else 2
    for layer in range(layers):
        level = (.42 + layer * .19) if needle else (.59 + layer * .17)
        radius = height * ((.26 - layer * .065) if needle else .27)
        depth = height * (.43 if needle else .45)
        turn = rng.uniform(0, math.tau)
        column, row = (2, 5)[rng.randrange(2)], rng.randrange(3)
        u0, u1 = (column + .012) / 6, (column + .988) / 6
        v0, v1 = (row + .012) / 6, (row + .988) / 6
        for plane in range(3):
            angle = turn + plane * math.pi / 3
            dx, dy = math.cos(angle) * radius, math.sin(angle) * radius
            bottom = base[2] + height * level - depth / 2
            a = base[0] - dx, base[1] - dy, bottom
            b = base[0] + dx, base[1] + dy, bottom
            ta, tb = (a[0], a[1], bottom + depth), (b[0], b[1], bottom + depth)
            scene.triangle('Building_Woodland', 'TreeCanopy', ta, tb, b,
                           ((u0, v0), (u1, v0), (u1, v1)))
            scene.triangle('Building_Woodland', 'TreeCanopy', ta, b, a,
                           ((u0, v0), (u1, v1), (u0, v1)))
