"""The measured Beausoleil district visible behind Casino Square."""
from __future__ import annotations

import math
import random
from itertools import pairwise

from circuit_dataclasses import Building, Point, RetainedTerrainSource
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.ops import split, unary_union

from venues.monaco_dataclasses import HillsideBuilding, HillsideVegetation


def hillside_city(scene: CircuitScene) -> None:
    records = TypeAdapter(list[HillsideBuilding]).validate_json(
        (scene.sources / 'architecture/hillside-buildings.json').read_bytes()
    )
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    tiled = 0
    for record in records:
        outer = [(*scene.geo(lat, lon), z - datum)
                 for (lon, lat), z in zip(record.outer, record.roof_outline_m, strict=True)]
        holes = [[(*scene.geo(lat, lon), z - datum)
                  for (lon, lat), z in zip(ring, heights, strict=True)]
                 for ring, heights in zip(record.holes, record.holes_roof_m, strict=True)]
        if not Polygon(outer).exterior.is_ccw:
            outer.reverse()
        for ring in holes:
            if Polygon(ring).exterior.is_ccw:
                ring.reverse()
        roof_outline = Polygon(outer, holes)
        footprint = Polygon([p[:2] for p in outer], [[p[:2] for p in ring] for ring in holes])
        if not footprint.is_valid:
            raise ValueError(f'Invalid measured hillside footprint {record.source_id}')
        scene.terrain_cutouts.append(footprint)
        identifier = -(int(record.source_id.removeprefix('BATIMENT')) * 100 + record.component)
        base, eaves = record.ground_m - datum, record.eaves_m - datum
        ring_height = max(record.roof_outline_m) - min(record.roof_outline_m)
        pitched = record.roof_material == 'Terracotta' and .4 < record.roof_m - record.eaves_m < 6 and ring_height < 1.5
        rectangle = list(footprint.minimum_rotated_rectangle.exterior.coords)
        a, b = max(pairwise(rectangle), key=lambda edge: math.dist(*edge))
        length = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        nx, ny = -ty, tx
        across = [p[0] * nx + p[1] * ny for p in outer]
        low, high = min(across), max(across)
        middle = (low + high) / 2

        def roof_height(x: float, y: float, *,
                        normal_x: float = nx, normal_y: float = ny,
                        center: float = middle, depth: float = high - low,
                        bottom: float = eaves, rise: float = record.roof_m - record.eaves_m) -> float:
            return bottom + rise * max(0, 1 - 2 * abs(x * normal_x + y * normal_y - center) / depth)

        floor_height = (eaves - base) / record.floors if record.floors else 3.4
        if not 2.3 <= floor_height <= 4.5:
            floor_height = 3.4
        floors = record.floors or max(1, math.ceil((record.roof_m - record.ground_m) / floor_height))
        window_base = eaves - floors * floor_height if record.floors else base
        for coordinates in [outer, *holes]:
            for p, q in pairwise(coordinates):
                span = math.dist(p[:2], q[:2])
                if span < .2:
                    continue
                top_p = roof_height(*p[:2]) if pitched else p[2]
                top_q = roof_height(*q[:2]) if pitched else q[2]
                kind = 'Building_IGNHillside'
                scene.quad(kind, 'Cream', (p[0], p[1], min(base, scene.ground(*p[:2]))),
                           (q[0], q[1], min(base, scene.ground(*q[:2]))),
                           (q[0], q[1], top_q), (p[0], p[1], top_p))
                dx, dy = (q[0] - p[0]) / span, (q[1] - p[1]) / span
                bays = max(1, round(span / 3.6))
                for floor in range(floors):
                    bottom = window_base + floor * floor_height + .8
                    top = min(bottom + 1.65, top_p - .35, top_q - .35)
                    if top <= bottom:
                        continue
                    for bay in range(bays):
                        u = (bay + .5) * span / bays
                        x, y = p[0] + dx * u + dy * .025, p[1] + dy * u - dx * .025
                        first, last = (x - dx * .5, y - dy * .5, bottom), (x + dx * .5, y + dy * .5, bottom)
                        scene.banner(first, last, top - bottom, 'Glass', kind)
                        if record.roof_material == 'Terracotta' and floors <= 4:
                            for offset in [-.68, .68]:
                                a = (x + dx * (offset - .13), y + dy * (offset - .13), bottom)
                                b = (a[0] + dx * .26, a[1] + dy * .26, bottom)
                                scene.banner(a, b, top - bottom, 'MonacoShutter', kind)
        surfaces = [roof_outline]
        if pitched:
            center = footprint.centroid
            displacement = middle - center.x * nx - center.y * ny
            cx, cy = center.x + nx * displacement, center.y + ny * displacement
            ridge = LineString([(cx - tx * length * 2, cy - ty * length * 2),
                                (cx + tx * length * 2, cy + ty * length * 2)])
            surfaces = [part for part in split(footprint, ridge).geoms if isinstance(part, Polygon)]
            tiled += 1
        for surface in surfaces:
            for triangle in constrained_delaunay_triangles(surface).geoms:
                points: list[Point] = []
                for coordinate in list(triangle.exterior.coords)[:3]:
                    x, y = coordinate[:2]
                    z = roof_height(x, y) if pitched else coordinate[2]
                    points.append((x, y, z))
                if not triangle.exterior.is_ccw:
                    points[1], points[2] = points[2], points[1]
                scene.triangle('Building_IGNHillside', record.roof_material, points[0], points[1], points[2])
        scene.buildings.append(Building(identifier, record.source_id, 'apartments', eaves - base,
                                        [p[:2] for p in outer], {'source': 'IGN BDTopo', 'height': str(eaves - base)}))
        scene.modeled_buildings.add(identifier)
    scene.landmarks.append({'name': 'Measured Beausoleil urban hillside',
                            'source_building_components': len(records), 'pitched_tile_roofs': tiled,
                            'source': 'architecture/hillside-buildings.json and hillside-architecture-provenance.json',
                            'dimensions_status': 'Actual bounded IGN footprints, storeys where supplied, ground/eaves/ridge levels, source precision and documented roof-material codes. Native road and RGE ground are unchanged. Complex roofs retain original 3D boundary heights; simple tile roofs use an estimated ridge axis within measured eaves/ridge limits. Facade openings and shutter details are original contextual reconstruction; no generic constant-height city strip.'})
    hillside_vegetation(scene)


def hillside_vegetation(scene: CircuitScene) -> None:
    records = TypeAdapter(list[HillsideVegetation]).validate_json(
        (scene.sources / 'architecture/hillside-vegetation.json').read_bytes()
    )
    grid = scene.grid
    bounds = box(grid.x, grid.y, grid.x + (grid.columns - 1) * grid.step,
                 grid.y + (grid.rows - 1) * grid.step)
    blocked = unary_union([scene.corridor_mask.buffer(2), *scene.extra_corridors,
                           *scene.water_shapes, *[Polygon(b.ring).buffer(1) for b in scene.buildings]])
    count, area = 0, 0.0
    for record in records:
        original = Polygon([scene.geo(lat, lon) for lon, lat in record.outer],
                           [[scene.geo(lat, lon) for lon, lat in ring] for ring in record.holes])
        shape = original.intersection(bounds).difference(blocked)
        if shape.is_empty:
            continue
        area += shape.area
        components = [shape] if isinstance(shape, Polygon) else list(getattr(shape, 'geoms', []))
        scene.terrain_cutouts.extend(p for p in components if isinstance(p, Polygon))
        xmin, ymin, xmax, ymax = shape.bounds
        for row in range(max(0, int((ymin - grid.y) // grid.step)), min(grid.rows - 1, math.ceil((ymax - grid.y) / grid.step))):
            for column in range(max(0, int((xmin - grid.x) // grid.step)), min(grid.columns - 1, math.ceil((xmax - grid.x) / grid.step))):
                x, y = grid.x + column * grid.step, grid.y + row * grid.step
                cell = shape.intersection(box(x, y, x + grid.step, y + grid.step))
                if not cell.is_empty:
                    scene.polygon_surface(cell, 'Grass', smooth_ground=True)
        randomizer = random.Random(int(record.source_id.removeprefix('ZONEVEGE')))
        tree_area = shape.buffer(-.5)
        hedge = record.nature == 'Haie'
        spacing = 5 if hedge else 9
        y = ymin
        while y < ymax:
            x = xmin
            while x < xmax:
                px, py = x + randomizer.uniform(-1.5, 1.5), y + randomizer.uniform(-1.5, 1.5)
                if tree_area.covers(ShapePoint(px, py)):
                    height = randomizer.uniform(2.5, 4) if hedge else randomizer.uniform(7, 12)
                    z = scene.ground(px, py) - (height * .35 if hedge else 0)
                    scene.broadleaf((px, py, z), height, count + 741)
                    count += 1
                x += spacing
            y += spacing
    scene.landmarks.append({'name': 'Measured Beausoleil woodland and hedges',
                            'vegetation_area_m2': area, 'reconstructed_trees': count,
                            'source': 'architecture/hillside-vegetation.json',
                            'dimensions_status': 'Seven exact IGN orthophotographic conifer/mixed-forest and hedge polygons. Ground surfaces follow the unchanged RGE grid; no green blanket outside these regions. Roads, buildings and water excluded. Individual trees and heights are bounded original reconstruction, not measured tree positions.'})
