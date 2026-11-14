"""The separate measured Costa properties above the Sainte-Dévote ravine."""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point, RetainedTerrainSource, TerrainGrid
from circuit_mesh import add
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient

from venues.monaco_dataclasses import CostaArchitecture, CostaComponent
from venues.monaco_properties import arch, roof_height


def costa_properties(scene: CircuitScene) -> None:
    config = TypeAdapter(CostaArchitecture).validate_json(
        (scene.sources / 'architecture/costa-properties.json').read_bytes()
    )
    if abs(scene.provenance.route.uniform_scale - config.uniform_scale) > 1e-9:
        raise ValueError('The Costa properties require their retained geographic registration')
    grid = TypeAdapter(TerrainGrid).validate_json(
        (scene.sources / config.ground_grid_file).read_bytes()
    )
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m

    def ground(x: float, y: float) -> float:
        column, row = (x - grid.x) / grid.step, (y - grid.y) / grid.step
        if not (0 <= column < grid.columns - 1 and 0 <= row < grid.rows - 1):
            raise ValueError('A Costa threshold lies outside the bounded ground source')
        ix, iy = int(column), int(row)
        tx, ty = column - ix, row - iy
        a, b = grid.heights[iy * grid.columns + ix:iy * grid.columns + ix + 2]
        c, d = grid.heights[(iy + 1) * grid.columns + ix:(iy + 1) * grid.columns + ix + 2]
        return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty

    for record in config.components:
        source = Polygon([
            (*scene.geo(lat, lon), height - datum)
            for (lon, lat), height in zip(record.outer, record.roof_outline_m, strict=True)
        ])
        if not source.is_valid:
            raise ValueError(f'Invalid Costa roof component {record.source_id}')
        owner = Polygon(scene.footprint(record.osm_id).ring)
        main, porch = roof_parts(source, record, datum)
        body = owner.intersection(plan(main))
        if not isinstance(body, Polygon) or body.is_empty or body.intersects(scene.corridor_mask):
            raise ValueError(f'The Costa ground body must remain inside its actual property: {record.name}')
        scene.modeled_buildings.add(record.osm_id)
        scene.terrain_cutouts.append(body)
        walls(scene, body, main, record, datum, ground)
        hipped_roof(scene, main, record.roof_peak_m - datum, record.roof_inset_m,
                    'Steel' if record.style == 'casa_core' else 'Terracotta', record.style)
        if porch is not None:
            open_porch(scene, porch, owner, record.upper_floor_base_m - datum, ground)
            roof_skin(scene, [(porch, 'Terracotta')], porch, 'Building_CostaPorchRoof')
        scene.landmarks.append({
            'name': record.name, 'osm_id': record.osm_id, 'ign_id': record.source_id,
            'roof_min_absolute_m': min(record.roof_outline_m),
            'roof_max_absolute_m': record.roof_peak_m,
            'ground_body_area_m2': body.area,
            'roof_overhang_area_m2': plan(main).difference(body).area,
            'source': 'architecture/costa-properties.json and costa-properties-provenance.json',
            'dimensions_status': 'Separate literal IGN 3D roof components, actual OSM ground-body intersections, '
                                 'and unchanged RGE vertical datum. Plan/height precision 2.5/1.5 m. '
                                 'The core/porch step, hip inset, visible storey subdivisions and facade details '
                                 'are declared architectural reconstruction from the owner photograph and '
                                 'official 2019 orthophoto; 2 m RGE samples locate local thresholds, not a new survey. '
                                 'Roof overhangs do not become ground walls. Native terrain and racing geometry are unchanged.',
        })


def plan(shape: Polygon) -> Polygon:
    return Polygon([p[:2] for p in shape.exterior.coords],
                   [[p[:2] for p in ring.coords] for ring in shape.interiors])


def roof_parts(source: Polygon, record: CostaComponent, datum: float) -> tuple[Polygon, Polygon | None]:
    step = record.roof_step
    if step is None:
        return source, None
    if step.seam:
        raise ValueError('The qualified Casa Mia porch step is a straight source-corner chord')
    ring = [(p[0], p[1], p[2]) for p in source.exterior.coords]
    first, last = step.start_vertex, step.end_vertex
    low_a = (*ring[first][:2], step.lower_endpoint_m[0] - datum)
    low_b = (*ring[last][:2], step.lower_endpoint_m[1] - datum)
    high_a = (*ring[first][:2], step.upper_endpoint_m[0] - datum)
    high_b = (*ring[last][:2], step.upper_endpoint_m[1] - datum)
    porch = Polygon([*ring[:first], low_a, low_b, *ring[last + 1:]])
    core = Polygon([high_a, *ring[first + 1:last], high_b])
    if not core.is_valid or not porch.is_valid:
        raise ValueError('Casa Mia requires separate valid core and porch roofs')
    if abs(core.area + porch.area - source.area) > 1e-7:
        raise ValueError('Casa Mia roof parts must preserve the complete source outline')
    return core, porch


def hipped_roof(scene: CircuitScene, source: Polygon, peak: float,
                inset: float, cap_material: str, style: str) -> None:
    if peak < max(p[2] for p in source.exterior.coords) - 1e-7:
        raise ValueError('The reconstructed roof cap cannot sit below its measured eaves')
    footprint = plan(source)
    inner = footprint.buffer(-inset, join_style='mitre')
    caps = [inner] if isinstance(inner, Polygon) else [p for p in getattr(inner, 'geoms', ()) if isinstance(p, Polygon)]
    caps = [cap for cap in caps if not cap.is_empty and cap.area > .05]
    kind = 'Building_CostaRoof_' + style
    if not caps:
        roof_skin(scene, [(source, 'Terracotta')], source, kind)
        return
    cap_rings = [[(p[0], p[1], peak) for p in cap.exterior.coords] for cap in caps]
    band = Polygon(source.exterior.coords, cap_rings)
    surfaces = [(band, 'Terracotta')]
    surfaces.extend((Polygon(ring), cap_material) for ring in cap_rings)
    roof_skin(scene, surfaces, source, kind)


def roof_skin(scene: CircuitScene, surfaces: list[tuple[Polygon, str]],
              outline: Polygon, kind: str) -> None:
    for surface, material in surfaces:
        for triangle in constrained_delaunay_triangles(surface).geoms:
            points: list[Point] = [(p[0], p[1], p[2]) for p in triangle.exterior.coords[:3]]
            if not triangle.exterior.is_ccw:
                points.reverse()
            scene.triangle(kind, material, points[0], points[1], points[2])
            scene.triangle(kind, 'Trunk', add(points[2], (0, 0, -.16)),
                           add(points[1], (0, 0, -.16)), add(points[0], (0, 0, -.16)))
    for a, b in pairwise(orient(outline).exterior.coords):
        scene.quad(kind, 'Trunk', (a[0], a[1], a[2] - .16),
                   (b[0], b[1], b[2] - .16), (b[0], b[1], b[2]), (a[0], a[1], a[2]))


def walls(scene: CircuitScene, body: Polygon, roof: Polygon, record: CostaComponent,
          datum: float, ground: Callable[[float, float], float]) -> None:
    kind = 'Building_CostaBody_' + record.style
    base = record.upper_floor_base_m - datum
    pink = record.style == 'casa_core'
    wall = 'MonacoRuscinoRose' if record.style in {'casa_core', 'casa_west'} else 'Cream'
    for a, b in pairwise(orient(body).exterior.coords):
        span = math.dist(a[:2], b[:2])
        if span < .2:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        top_a, top_b = roof_height(roof, *a[:2]) - .16, roof_height(roof, *b[:2]) - .16
        feet = [min(ground(*p[:2]), scene.ground(*p[:2]), top - .15) - .12
                for p, top in [(a, top_a), (b, top_b)]]
        split_a, split_b = min(top_a, max(feet[0], base)), min(top_b, max(feet[1], base))
        scene.quad(kind, 'Limestone', (a[0], a[1], feet[0]), (b[0], b[1], feet[1]),
                   (b[0], b[1], split_b), (a[0], a[1], split_a), span / 2, max(1., base - min(feet)) / 2)
        scene.quad(kind, wall, (a[0], a[1], split_a), (b[0], b[1], split_b),
                   (b[0], b[1], top_b), (a[0], a[1], top_a))
        count = max(1, round(span / (4.8 if pink else 3.8)))
        for floor in range(record.upper_floors):
            z = base + floor * record.upper_floor_height_m
            for bay in range(count):
                u = (bay + .5) * span / count
                x, y = a[0] + tx * u, a[1] + ty * u
                low = z + .75
                top = min(z + record.upper_floor_height_m - .55,
                          roof_height(roof, x, y) - .5)
                if low < ground(x + nx * .4, y + ny * .4) + .25 or top - low < 1:
                    continue
                width = min(1.9 if pink else 1.15, span / count * .7)
                first = (x - tx * width / 2 + nx * .035,
                         y - ty * width / 2 + ny * .035, low)
                if record.style == 'casa_west':
                    arch(scene, first, add(first, (tx * width, ty * width, 0)), top - low, kind)
                elif pink:
                    for offset in [0., width / 2 + .065]:
                        p = add(first, (tx * offset, ty * offset, 0))
                        arch(scene, p, add(p, (tx * (width / 2 - .065), ty * (width / 2 - .065), 0)), top - low, kind)
                else:
                    scene.banner(first, add(first, (tx * width, ty * width, 0)), top - low, 'Glass', kind)
                scene.beam(kind, 'Limestone', add(first, (0, 0, -.12)),
                           add(first, (tx * width, ty * width, -.12)), .16, .24)
            cornice = z + record.upper_floor_height_m - .12
            if cornice < min(top_a, top_b) - .15:
                scene.beam(kind, 'Limestone', (a[0] + nx * .025, a[1] + ny * .025, cornice),
                           (b[0] + nx * .025, b[1] + ny * .025, cornice), .10, .16)
        scene.beam(kind, 'Trunk' if pink else 'Limestone', (a[0], a[1], top_a),
                   (b[0], b[1], top_b), .16, .23)


def open_porch(scene: CircuitScene, roof: Polygon, owner: Polygon, deck_z: float,
               ground: Callable[[float, float], float]) -> None:
    footprint = plan(roof)
    deck = footprint.buffer(-.35, join_style='mitre').intersection(owner)
    if not isinstance(deck, Polygon) or deck.is_empty:
        raise ValueError('The actual Casa Mia porch must contain its open three-bay platform')
    scene.terrain_cutouts.append(deck)
    ring = list(roof.exterior.coords)
    a, b = ring[0], ring[1]
    if math.dist(a[:2], b[:2]) < 8:
        raise ValueError('Casa Mia porch needs the registered long outer front')
    span = math.dist(a[:2], b[:2])
    tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    nx, ny = -ty, tx
    if not footprint.contains(ShapePoint((a[0] + b[0]) / 2 + nx * .5,
                                        (a[1] + b[1]) / 2 + ny * .5)):
        nx, ny = -nx, -ny
    safe = deck.buffer(-.4, join_style='mitre')
    support: LineString | None = None
    for offset in [.5, .75, 1., 1.25, 1.5, 1.75, 2.]:
        section = LineString([(a[0] + nx * offset, a[1] + ny * offset),
                              (b[0] + nx * offset, b[1] + ny * offset)]).intersection(safe)
        if isinstance(section, LineString) and section.length > span * .65:
            support = section
            break
    if support is None:
        raise ValueError('The Casa Mia columns need an actual supported line inside the ground body')
    first_xy, last_xy = support.coords[0], support.coords[-1]
    if (last_xy[0] - first_xy[0]) * tx + (last_xy[1] - first_xy[1]) * ty < 0:
        first_xy, last_xy = last_xy, first_xy
    start = (first_xy[0] + tx * .1, first_xy[1] + ty * .1, deck_z)
    end = (last_xy[0] - tx * .1, last_xy[1] - ty * .1, deck_z)
    length = math.dist(start, end)
    gallery_z = deck_z - 4.0
    for level in [gallery_z, deck_z]:
        surface = Polygon([(*p[:2], level) for p in deck.exterior.coords])
        roof_skin(scene, [(surface, 'Limestone')], surface, 'Building_CostaPorchDeck')
    for p, q in pairwise(orient(deck).exterior.coords):
        side_length = math.dist(p[:2], q[:2])
        if side_length < .01:
            continue
        feet = [min(ground(*v[:2]), scene.ground(*v[:2]), gallery_z - .16) - .1 for v in [p, q]]
        scene.quad('Building_CostaPorchFoundation', 'Limestone',
                   (*p[:2], feet[0]), (*q[:2], feet[1]),
                   (*q[:2], gallery_z - .16), (*p[:2], gallery_z - .16),
                   side_length / 2, max(1., gallery_z - min(feet)) / 2)
        outward_x, outward_y = (q[1] - p[1]) / side_length, -(q[0] - p[0]) / side_length
        if outward_x * nx + outward_y * ny > -.8:
            scene.quad('Building_CostaPorchGallerySides', 'Limestone',
                       (*p[:2], gallery_z - .16), (*q[:2], gallery_z - .16),
                       (*q[:2], deck_z - .16), (*p[:2], deck_z - .16), side_length / 2, 2.)
    for index in range(4):
        u = length * index / 3
        p = (start[0] + tx * u, start[1] + ty * u, deck_z + .1)
        local_roof = roof_height(roof, p[0], p[1]) - .22
        column(scene, p, max(.2, local_roof - p[2] - .80), .22, 'Building_CostaPorchColumns')
        lower = min(gallery_z - .15, ground(p[0], p[1]) - .1, scene.ground(p[0], p[1]) - .1)
        scene.box('Building_CostaPorchPiers', 'Limestone',
                  (p[0], p[1], (lower + deck_z - .16) / 2), .55, .55, deck_z - .16 - lower)
    for bay in range(3):
        first = (start[0] + tx * (length * bay / 3 + .22),
                 start[1] + ty * (length * bay / 3 + .22), deck_z)
        last = (start[0] + tx * (length * (bay + 1) / 3 - .22),
                start[1] + ty * (length * (bay + 1) / 3 - .22), deck_z)
        arch_crown(scene, first, last, min(roof_height(roof, first[0], first[1]),
                                        roof_height(roof, last[0], last[1])) - .45,
                   .80, .22, 'Building_CostaPorchUpperArches')
        arch_crown(scene, add(first, (0, 0, -4)), add(last, (0, 0, -4)),
                   deck_z - .4, .85, .32, 'Building_CostaPorchLowerArches')
        for level in [.18, .95]:
            scene.beam('Building_CostaPorchBalustrade', 'Cream',
                       add(first, (0, 0, level)), add(last, (0, 0, level)), .10)
        divisions = max(1, math.ceil(math.dist(first, last) / .3))
        for division in range(divisions):
            u, v = division / divisions, (division + 1) / divisions
            p = (first[0] + (last[0] - first[0]) * u,
                 first[1] + (last[1] - first[1]) * u, deck_z + .2)
            q = (first[0] + (last[0] - first[0]) * v,
                 first[1] + (last[1] - first[1]) * v, deck_z + .88)
            scene.beam('Building_CostaPorchBalustrade', 'Trunk', p, q, .018)
            scene.beam('Building_CostaPorchBalustrade', 'Trunk',
                       (p[0], p[1], q[2]), (q[0], q[1], p[2]), .018)


def column(scene: CircuitScene, base: Point, height: float, radius: float, kind: str) -> None:
    for segment in range(12):
        first, last = math.tau * segment / 12, math.tau * (segment + 1) / 12
        a = add(base, (radius * math.cos(first), radius * math.sin(first), 0))
        b = add(base, (radius * math.cos(last), radius * math.sin(last), 0))
        scene.quad(kind, 'Cream', a, b, add(b, (0, 0, height)), add(a, (0, 0, height)))
    for z in [base[2], base[2] + height]:
        scene.box(kind, 'Limestone', (base[0], base[1], z), radius * 2.5, radius * 2.5, .18)


def arch_crown(scene: CircuitScene, first: Point, last: Point, crown: float,
               rise: float, thickness: float, kind: str) -> None:
    width = math.dist(first[:2], last[:2])
    tx, ty = (last[0] - first[0]) / width, (last[1] - first[1]) / width
    middle = ((first[0] + last[0]) / 2, (first[1] + last[1]) / 2)
    spring = crown - rise
    for segment in range(16):
        a, b = math.pi * segment / 16, math.pi * (segment + 1) / 16
        points: list[Point] = []
        for angle, radius_x, radius_z in [(a, width / 2, rise), (b, width / 2, rise),
                                          (b, width / 2 + thickness, rise + thickness),
                                          (a, width / 2 + thickness, rise + thickness)]:
            points.append((middle[0] + tx * radius_x * math.cos(angle),
                           middle[1] + ty * radius_x * math.cos(angle),
                           spring + radius_z * math.sin(angle)))
        scene.quad(kind, 'Limestone', points[0], points[1], points[2], points[3])
        back = [add(p, (-ty * .24, tx * .24, 0)) for p in points]
        scene.quad(kind, 'Limestone', back[3], back[2], back[1], back[0])
        scene.quad(kind, 'Limestone', points[0], back[0], back[1], points[1])
        scene.quad(kind, 'Limestone', points[2], back[2], back[3], points[3])
        if segment == 0:
            scene.quad(kind, 'Limestone', points[3], back[3], back[0], points[0])
        if segment == 15:
            scene.quad(kind, 'Limestone', points[1], back[1], back[2], points[2])
