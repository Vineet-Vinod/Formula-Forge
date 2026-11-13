"""Measured quay properties and the open balconies above Mirabeau."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_mesh import add
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint

from venues.monaco_dataclasses import GardenFrontage, PropertyEnvelope


def property_envelopes(scene: CircuitScene) -> None:
    records = TypeAdapter(list[PropertyEnvelope]).validate_json(
        (scene.sources / 'architecture/property-envelopes.json').read_bytes()
    )
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    for record in records:
        outer = [(*scene.geo(lat, lon), z - datum)
                 for (lon, lat), z in zip(record.outer, record.roof_outline_m, strict=True)]
        holes = [[(*scene.geo(lat, lon), z - datum)
                  for (lon, lat), z in zip(ring, heights, strict=True)]
                 for ring, heights in zip(record.holes, record.holes_roof_m, strict=True)]
        footprint = Polygon(outer, holes)
        if not footprint.is_valid:
            raise ValueError(f'Invalid retained property {record.source_id}')
        scene.modeled_buildings.add(record.osm_id)
        scene.modeled_buildings.update(record.covered_osm_ids)
        base = record.ground_m - datum
        if record.style == 'ermanno':
            ermanno(scene, record, base, datum)
            continue
        if record.style not in ('rascasse', 'annex'):
            scene.terrain_cutouts.append(Polygon(
                [p[:2] for p in footprint.exterior.coords],
                [[p[:2] for p in ring.coords] for ring in footprint.interiors],
            ))
        surfaces = [footprint]
        if record.roof_step is not None:
            step = record.roof_step
            first, last = step.start_vertex, step.end_vertex
            low_a = (*outer[first][:2], step.lower_endpoint_m[0] - datum)
            low_b = (*outer[last][:2], step.lower_endpoint_m[1] - datum)
            high_a = (*outer[first][:2], step.upper_endpoint_m[0] - datum)
            high_b = (*outer[last][:2], step.upper_endpoint_m[1] - datum)
            join = [scene.geo(lat, lon) for lon, lat in step.seam]
            seam = LineString([outer[first][:2], *join, outer[last][:2]])
            lower_join: list[Point] = []
            upper_join: list[Point] = []
            for point in join:
                t = seam.project(ShapePoint(point)) / seam.length
                lower_join.append((*point, low_a[2] * (1 - t) + low_b[2] * t))
                upper_join.append((*point, high_a[2] * (1 - t) + high_b[2] * t))
            low = Polygon([*outer[:first], low_a, *lower_join, low_b, *outer[last + 1:]])
            high = Polygon([high_a, *outer[first + 1:last], high_b, *reversed(upper_join)], holes)
            if not low.is_valid or not high.is_valid:
                raise ValueError('The quay roof seam must preserve its separate inner source component')
            if abs(low.area + high.area - footprint.area) > 1e-5:
                raise ValueError('The Ruscino roof step must partition its complete footprint')
            surfaces = [low, high]
        for surface in surfaces:
            if record.style == 'ruscino':
                ruscino(scene, surface, base)
            elif record.style == 'rascasse':
                rascasse(scene, surface, base)
            else:
                quay_component(scene, surface, base, record)
        scene.landmarks.append({
            'name': record.name, 'osm_id': record.osm_id, 'ign_id': record.source_id,
            'base_z_m': base, 'roof_min_z_m': min(record.roof_outline_m) - datum,
            'roof_max_z_m': record.roof_peak_m - datum,
            'source': 'architecture/property-envelopes.json',
            'dimensions_status': 'Retained IGN BDTopo 3D footprint and roof edges with1.5 m stated vertical precision. The parent roof excludes a separate measured inner component, rendered from its own source record. Internal roof-step join and quay-front facade details are reconstructed from the registered494-498 s supplied views; they are not survey measurements. La Rascasse and the low western annexes keep their own measured small envelopes.',
        })


def roof_surface(scene: CircuitScene, footprint: Polygon, material: str, kind: str) -> None:
    for triangle in constrained_delaunay_triangles(footprint).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        points: list[Point] = [(p[0], p[1], p[2]) for p in coordinates]
        if not triangle.exterior.is_ccw:
            points.reverse()
        scene.triangle(kind, material, points[0], points[1], points[2])


def ruscino(scene: CircuitScene, footprint: Polygon, base: float) -> None:
    kind = 'Building_QuaiAntoineResidential'
    rings = [footprint.exterior, *footprint.interiors]
    for index, boundary in enumerate(rings):
        ring = [(p[0], p[1], p[2]) for p in boundary.coords]
        if boundary.is_ccw != (index == 0):
            ring.reverse()
        for a, b in pairwise(ring):
            span = math.dist(a[:2], b[:2])
            if span < .15:
                continue
            tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
            nx, ny = ty, -tx
            scene.quad(kind, 'MonacoRuscinoRose',
                       (a[0], a[1], min(base, scene.ground(*a[:2]) - .1)),
                       (b[0], b[1], min(base, scene.ground(*b[:2]) - .1)), b, a)
            bays = max(1, round(span / 4.8))
            floors = max(1, math.ceil((max(a[2], b[2]) - base) / 3.5))
            for floor in range(floors):
                z = base + floor * 3.5
                for bay in range(bays):
                    center = (bay + .5) * span / bays
                    roof = a[2] + (b[2] - a[2]) * center / span
                    bottom = z + (.35 if floor == 0 else .75)
                    top = min(z + 2.75, roof - .45)
                    if top < bottom + .5:
                        continue
                    width = min(3.45, span / bays * .74)
                    p = (a[0] + tx * (center - width / 2) + nx * .035,
                         a[1] + ty * (center - width / 2) + ny * .035, bottom)
                    q = add(p, (tx * width, ty * width, 0))
                    if floor == 0 and bay % 2 == 0 and span > 12:
                        arch(scene, p, q, top - bottom, kind)
                    else:
                        scene.banner(p, q, top - bottom, 'Glass', kind)
                        scene.beam(kind, 'White', add(p, (0, 0, -.075)), add(q, (0, 0, -.075)), .10)
                        scene.beam(kind, 'White', add(p, (0, 0, top - bottom + .075)),
                                   add(q, (0, 0, top - bottom + .075)), .10)
                        for endpoint in [p, q]:
                            scene.beam(kind, 'White', endpoint, add(endpoint, (0, 0, top - bottom)), .08)
                        middle = add(p, (tx * width / 2, ty * width / 2, 0))
                        scene.beam(kind, 'Steel', middle, add(middle, (0, 0, top - bottom)), .045)
                if floor > 0:
                    usable = min(a[2], b[2]) - .2
                    if z < usable:
                        first, last = (a[0] + nx * .02, a[1] + ny * .02, z), (b[0] + nx * .02, b[1] + ny * .02, z)
                        scene.banner(first, last, .025, 'Cream', kind)
                if floor in (1, floors - 1) and span > 18 and index == 0:
                    balcony_rail(scene, a, b, z + .12, .48, kind)
            columns = max(1, math.ceil(span / 1.35))
            for column in range(1, columns):
                t = column / columns
                x, y = a[0] + (b[0] - a[0]) * t + nx * .015, a[1] + (b[1] - a[1]) * t + ny * .015
                scene.banner((x, y, base), (x + tx * .014, y + ty * .014, base),
                             a[2] + (b[2] - a[2]) * t - .1 - base, 'Cream', kind)
            rows = max(1, math.ceil((max(a[2], b[2]) - base) / 1.15))
            for row in range(1, rows):
                z = base + row * 1.15
                if z < min(a[2], b[2]) - .15:
                    scene.banner((a[0] + nx * .016, a[1] + ny * .016, z),
                                 (b[0] + nx * .016, b[1] + ny * .016, z), .012, 'Cream', kind)
            scene.beam(kind, 'White', a, b, .22, .25)
    roof_surface(scene, footprint, 'Roof', kind)


def arch(scene: CircuitScene, first: Point, last: Point, height: float, kind: str) -> None:
    width = math.dist(first, last)
    tangent = ((last[0] - first[0]) / width, (last[1] - first[1]) / width)
    radius = min(width / 2, height * .32)
    spring = height - radius
    center = add(first, ((last[0] - first[0]) / 2, (last[1] - first[1]) / 2, spring))
    scene.banner(first, last, spring, 'Black', kind)
    previous = add(center, (-tangent[0] * width / 2, -tangent[1] * width / 2, 0))
    for segment in range(1, 13):
        angle = math.pi - segment * math.pi / 12
        point = add(center, (tangent[0] * width / 2 * math.cos(angle),
                             tangent[1] * width / 2 * math.cos(angle), radius * math.sin(angle)))
        scene.triangle(kind, 'Black', center, previous, point)
        scene.triangle(kind, 'Black', center, point, previous)
        scene.beam(kind, 'Cream', previous, point, .11)
        previous = point
    for endpoint in [first, last]:
        scene.beam(kind, 'Cream', endpoint, add(endpoint, (0, 0, spring)), .11)


def balcony_rail(scene: CircuitScene, a: Point, b: Point, z: float, depth: float, kind: str) -> None:
    span = math.dist(a[:2], b[:2])
    tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    first, last = (a[0] + ty * depth, a[1] - tx * depth, z), (b[0] + ty * depth, b[1] - tx * depth, z)
    scene.quad(kind, 'White', (a[0], a[1], z), (b[0], b[1], z), last, first, up=True)
    scene.quad(kind, 'Cream', add(last, (0, 0, -.14)), (b[0], b[1], z - .14),
               (a[0], a[1], z - .14), add(first, (0, 0, -.14)), up=False)
    for height in [.12, .88]:
        scene.beam(kind, 'White', add(first, (0, 0, height)), add(last, (0, 0, height)), .075)
    count = max(1, math.ceil(span / .32))
    for column in range(count + 1):
        p = add(first, (tx * span * column / count, ty * span * column / count, .15))
        scene.beam(kind, 'White', p, add(p, (0, 0, .69)), .035)


def rascasse(scene: CircuitScene, footprint: Polygon, base: float) -> None:
    kind = 'Building_LaRascasse'
    plan = Polygon([p[:2] for p in footprint.exterior.coords],
                   [[p[:2] for p in ring.coords] for ring in footprint.interiors])
    core = plan.intersection(Polygon(scene.footprint(112681614).ring))
    if not isinstance(core, Polygon) or core.is_empty:
        raise ValueError('La Rascasse requires its mapped ground body below the larger measured roof')
    scene.terrain_cutouts.append(core)
    ring = [(p[0], p[1], roof_height(footprint, p[0], p[1]) - .18) for p in core.exterior.coords]
    if not core.exterior.is_ccw:
        ring.reverse()
    for a, b in pairwise(ring):
        span = math.dist(a[:2], b[:2])
        if span < .15:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        scene.quad(kind, 'Steel', (a[0], a[1], min(base, scene.ground(*a[:2]) - .1)),
                   (b[0], b[1], min(base, scene.ground(*b[:2]) - .1)), b, a)
        count = max(1, round(span / 3.2))
        for bay in range(count):
            t = (bay + .5) / count
            roof = a[2] + (b[2] - a[2]) * t
            width = min(2.65, .84 * span / count)
            for floor in range(2):
                z = base + .45 + floor * 3.4
                h = min(2.25, roof - z - .35)
                if h < .5:
                    continue
                p = (a[0] + tx * (t * span - width / 2) + ty * .035,
                     a[1] + ty * (t * span - width / 2) - tx * .035, z)
                scene.banner(p, add(p, (tx * width, ty * width, 0)), h, 'Glass', kind)
        scene.beam(kind, 'Steel', a, b, .18, .22)
        steps = max(1, math.ceil(span / 4.5))
        for column in range(steps + 1):
            t = column / steps
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            scene.beam(kind, 'Steel', (x, y, base), (x, y, roof_height(footprint, x, y) - .18), .13)
    roof_shell(scene, footprint, 'Roof', kind, fence_overhead=True)


def quay_component(scene: CircuitScene, footprint: Polygon, base: float, record: PropertyEnvelope) -> None:
    kind = f'Building_QuaiComponent_{record.source_id}'
    core = footprint
    if record.style == 'annex':
        plan = Polygon([p[:2] for p in footprint.exterior.coords],
                       [[p[:2] for p in ring.coords] for ring in footprint.interiors])
        common = plan.intersection(Polygon(scene.footprint(record.osm_id).ring))
        if not isinstance(common, Polygon) or common.is_empty:
            raise ValueError('The low quay annex requires its mapped ground body')
        core = common
        scene.terrain_cutouts.append(core)
    ring = [(p[0], p[1], roof_height(footprint, p[0], p[1]) - .18) for p in core.exterior.coords]
    if not core.exterior.is_ccw:
        ring.reverse()
    for a, b in pairwise(ring):
        scene.quad(kind, 'Cream', (a[0], a[1], min(base, scene.ground(*a[:2]) - .1)),
                   (b[0], b[1], min(base, scene.ground(*b[:2]) - .1)), b, a)
        if record.style != 'annex':
            continue
        span = math.dist(a[:2], b[:2])
        if span < 3:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        count = max(1, round(span / 5))
        for bay in range(count):
            t = (bay + .5) / count
            z = base + .25
            height = min(2.4, a[2] * (1 - t) + b[2] * t - z - .2)
            if height < .7:
                continue
            p = (a[0] + tx * (span * t - .7) + ty * .025,
                 a[1] + ty * (span * t - .7) - tx * .025, z)
            scene.banner(p, add(p, (tx * 1.4, ty * 1.4, 0)), height, 'Glass', kind)
    roof_shell(scene, footprint, 'Roof', kind)


def roof_height(footprint: Polygon, x: float, y: float) -> float:
    for triangle in constrained_delaunay_triangles(footprint).geoms:
        if not triangle.buffer(1e-7).covers(ShapePoint(x, y)):
            continue
        a, b, c = list(triangle.exterior.coords)[:3]
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
        second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
        return first * a[2] + second * b[2] + (1 - first - second) * c[2]
    raise ValueError('Roof height query lies outside the measured envelope')


def roof_shell(scene: CircuitScene, footprint: Polygon, material: str, kind: str,
               fence_overhead: bool = False) -> None:
    roof_surface(scene, footprint, material, kind)
    for triangle in constrained_delaunay_triangles(footprint).geoms:
        points = [(p[0], p[1], p[2] - .18) for p in list(triangle.exterior.coords)[:3]]
        if triangle.exterior.is_ccw:
            points.reverse()
        if fence_overhead:
            scene.overhead_soffits.append((points[0], points[1], points[2]))
        scene.triangle(kind, 'Cream', points[0], points[1], points[2])
    ring = list(footprint.exterior.coords)
    if not footprint.exterior.is_ccw:
        ring.reverse()
    for a, b in pairwise(ring):
        scene.quad(kind, 'Steel', (a[0], a[1], a[2] - .18),
                   (b[0], b[1], b[2] - .18), (b[0], b[1], b[2]), (a[0], a[1], a[2]))


def ermanno(scene: CircuitScene, record: PropertyEnvelope, base: float, datum: float) -> None:
    building = scene.footprint(record.osm_id)
    footprint = Polygon(building.ring)
    scene.terrain_cutouts.append(footprint)
    top = min(record.roof_outline_m) - datum
    loggias(scene, footprint, base, top, 12, 1.7, 'Building_ErmannoPalace', 'Cream', False)
    retained = LineString([(*scene.geo(lat, lon), z - datum)
                           for (lon, lat), z in zip(record.outer, record.roof_outline_m, strict=True)])
    ring: list[Point] = []
    for x, y in footprint.exterior.coords:
        closest = retained.interpolate(retained.project(ShapePoint(x, y)))
        ring.append((x, y, closest.z))
    kind = 'Building_ErmannoRoofTerrace'
    for a, b in pairwise(ring):
        scene.quad(kind, 'Cream', (a[0], a[1], top), (b[0], b[1], top), b, a)
        scene.beam(kind, 'White', a, b, .13)
    roof_surface(scene, Polygon(ring), 'Roof', kind)
    penthouse = footprint.buffer(-3.5, join_style='mitre')
    if not isinstance(penthouse, Polygon) or penthouse.is_empty:
        raise ValueError('Ermanno requires a recessed roof terrace inside its detailed mapped ring')
    low, peak = max(record.roof_outline_m) - datum, record.roof_peak_m - datum
    for a_xy, b_xy in pairwise(list(penthouse.exterior.coords)):
        scene.banner((*a_xy, low), (*b_xy, low), peak - low - .18, 'Glass', kind)
        scene.beam(kind, 'Cream', (*a_xy, low), (*a_xy, peak), .22)
        scene.beam(kind, 'White', (*a_xy, peak), (*b_xy, peak), .25)
    cap = Polygon([(*p[:2], peak) for p in penthouse.exterior.coords])
    roof_surface(scene, cap, 'Cream', kind)
    scene.landmarks.append({
        'name': 'Ermanno Palace rounded balconies and roof terrace', 'osm_id': record.osm_id,
        'storeys': 12, 'base_z_m': base, 'eaves_z_m': top, 'maximum_roof_z_m': peak,
        'balcony_depth_m': 1.7,
        'dimensions_status': 'Detailed retained curved OSM footprint, matching IGN component BATIMENT0000000074074396 with measured ground4.9 m, eaves42.5-44.1 m and peak48.6 m absolute. Official F1 Experiences locates the penthouse on floor12; the agent exterior shows rounded balconies and an inset planted roof terrace. Balcony depth1.7 m, floor subdivision and inset roof-room plan are explicit reconstruction estimates within the measured envelope. Replaces unsupported61 m/18-storey massing.',
    })


def mirabeau(scene: CircuitScene) -> None:
    building = scene.footprint(94399524)
    footprint = Polygon(building.ring)
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)
    base = min(scene.ground(x, y) for x, y in building.ring)
    loggias(scene, footprint, base, base + 81, 26, 2.1, 'Building_LeMirabeau', 'White', True)
    # In the1176 s eastward view, the north-west wall is left of the south loggias.
    a, b = building.ring[0], building.ring[2]
    span = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    scene.banner((*a, base), (*b, base), 81, 'White', 'Building_MirabeauWestSpine')
    for floor in range(26):
        z = base + floor * 81 / 26 + .65
        for fraction in [.35, .68]:
            p = (a[0] + tx * (span * fraction - .40) + ty * .025,
                 a[1] + ty * (span * fraction - .40) - tx * .025, z)
            scene.banner(p, add(p, (tx * .8, ty * .8, 0)), 1.8, 'Glass', 'Building_MirabeauWestSpine')
    scene.landmarks.append({
        'name': 'Le Mirabeau recessed loggias and vertical spines', 'osm_id': building.osm_id,
        'height_m': 81, 'storeys': 26, 'loggia_depth_m': 2.1,
        'dimensions_status': 'Mapped twelve-vertex footprint and existing81 m/26-level envelope retained. The directly registered1176 s supplied view shows open white balconies, broad solid vertical spines and dark recessed room fronts. Depth2.1 m and spine/bay proportions are architectural estimates. A matching IGN component reports84.9 m above ground14.5 m; its height convention is retained as independent evidence, not silently substituted for the tagged envelope.',
    })


def loggias(scene: CircuitScene, footprint: Polygon, base: float, top: float, floors: int,
            depth: float, kind: str, wall: str, solid_rail: bool) -> None:
    core = footprint.buffer(-depth, join_style='mitre')
    if not isinstance(core, Polygon) or core.is_empty:
        raise ValueError('The measured balcony footprint must contain its recessed room core')
    ring = list(footprint.exterior.coords)
    if not footprint.exterior.is_ccw:
        ring.reverse()
    core_ring = list(core.exterior.coords)
    if not core.exterior.is_ccw:
        core_ring.reverse()
    floor_height = (top - base) / floors
    for a, b in pairwise(ring):
        scene.quad(kind, wall, (*a[:2], min(base - .15, scene.ground(*a[:2]) - .15)),
                   (*b[:2], min(base - .15, scene.ground(*b[:2]) - .15)),
                   (*b[:2], base), (*a[:2], base))
    for a, b in pairwise(core_ring):
        scene.quad(kind, wall, (*a[:2], min(base, scene.ground(*a[:2]) - .1)),
                   (*b[:2], min(base, scene.ground(*b[:2]) - .1)), (*b[:2], top), (*a[:2], top))
        span = math.dist(a[:2], b[:2])
        if span < .3:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        bays = max(1, round(span / 4.0))
        for floor in range(floors):
            z = base + floor * floor_height + .22
            for bay in range(bays):
                u = (bay + .08) * span / bays
                p = (a[0] + tx * u + ty * .025, a[1] + ty * u - tx * .025, z)
                q = add(p, (tx * .84 * span / bays, ty * .84 * span / bays, 0))
                scene.banner(p, q, floor_height - .48, 'Glass', kind)
    for floor in range(floors + 1):
        z = base + floor * floor_height
        slab = Polygon([(*p[:2], z) for p in footprint.exterior.coords])
        roof_surface(scene, slab, wall, kind)
        for triangle in constrained_delaunay_triangles(slab).geoms:
            points = [(p[0], p[1], z - .18) for p in list(triangle.exterior.coords)[:3]]
            if triangle.exterior.is_ccw:
                points.reverse()
            scene.triangle(kind, 'Cream', points[0], points[1], points[2])
        for a, b in pairwise(ring):
            span = math.dist(a[:2], b[:2])
            if span < .15:
                continue
            tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
            scene.banner((*a[:2], z - .18), (*b[:2], z - .18), .18, wall, kind)
            if floor == floors:
                continue
            scene.banner((*a[:2], z + .10), (*b[:2], z + .10), .58 if solid_rail else .18, wall, kind)
            scene.beam(kind, 'Steel', (*a[:2], z + .93), (*b[:2], z + .93), .045)
            count = max(1, math.ceil(span / 1.2))
            for bay in range(count + 1):
                p = (a[0] + tx * span * bay / count, a[1] + ty * span * bay / count, z + .15)
                scene.beam(kind, 'Steel', p, add(p, (0, 0, .78)), .028)
            if span > 8:
                partitions = max(1, round(span / 5.5))
                for bay in range(partitions + 1):
                    u = span * bay / partitions
                    p = (a[0] + tx * u, a[1] + ty * u, z + .10)
                    partition = LineString([p[:2], (p[0] - ty * depth, p[1] + tx * depth)]).intersection(footprint)
                    if isinstance(partition, LineString) and partition.length > .1:
                        first, last = partition.coords[0], partition.coords[-1]
                        scene.banner((*first[:2], z + .1), (*last[:2], z + .1), floor_height - .18, wall, kind)


def fairmont_garden(scene: CircuitScene) -> None:
    record = TypeAdapter(GardenFrontage).validate_json(
        (scene.sources / 'architecture/fairmont-garden-frontage.json').read_bytes()
    )
    park = Polygon([scene.geo(lat, lon) for lon, lat in record.ring])
    ring = list(park.exterior.coords)
    if not park.exterior.is_ccw:
        ring.reverse()
    protected = scene.corridor_mask.buffer(.15)
    wall_length, shrubs = 0.0, 0
    for a, b in pairwise(ring):
        span = math.dist(a[:2], b[:2])
        if span < .1:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        count = max(1, math.ceil(span / 2.0))
        for cell in range(count):
            start, end = cell * span / count, (cell + 1) * span / count
            x, y = a[0] + tx * (start + end) / 2, a[1] + ty * (start + end) / 2
            sample, distance = scene.nearest(x, y)
            signed_lane = (x - sample.x) * sample.ty - (y - sample.y) * sample.tx
            if not record.native_range_m[0] <= sample.station <= record.native_range_m[1] or distance > 12 or signed_lane < 0:
                continue
            inset = record.wall_inset_m
            strip = Polygon([(a[0] + tx * start - ty * inset, a[1] + ty * start + tx * inset),
                             (a[0] + tx * end - ty * inset, a[1] + ty * end + tx * inset),
                             (a[0] + tx * end - ty * (inset + .28), a[1] + ty * end + tx * (inset + .28)),
                             (a[0] + tx * start - ty * (inset + .28), a[1] + ty * start + tx * (inset + .28))])
            if strip.intersects(protected) or not park.buffer(.001).covers(strip):
                continue
            first = (a[0] + tx * start - ty * (inset + .14), a[1] + ty * start + tx * (inset + .14))
            last = (a[0] + tx * end - ty * (inset + .14), a[1] + ty * end + tx * (inset + .14))
            low_a, low_b = scene.ground(*first) - .15, scene.ground(*last) - .15
            kind = 'Building_FairmontGardenStone'
            for row in range(4):
                lower, upper = row * record.wall_height_m / 4, (row + 1) * record.wall_height_m / 4
                scene.quad(kind, 'Limestone', (*first, low_a + lower), (*last, low_b + lower),
                           (*last, low_b + upper - .025), (*first, low_a + upper - .025))
                scene.quad(kind, 'Limestone', (*last, low_b + lower), (*first, low_a + lower),
                           (*first, low_a + upper - .025), (*last, low_b + upper - .025))
                joint_u = start + (end - start) * (.35 if row % 2 else .65)
                joint = (a[0] + tx * joint_u - ty * (inset + .125), a[1] + ty * joint_u + tx * (inset + .125),
                         low_a + (low_b - low_a) * (joint_u - start) / (end - start) + lower)
                scene.beam(kind, 'Concrete', joint, add(joint, (0, 0, upper - lower)), .022)
            scene.beam(kind, 'Cream', (*first, low_a + record.wall_height_m),
                       (*last, low_b + record.wall_height_m), .30, .14)
            wall_length += end - start
            inward = (x - ty * (inset + 1.65), y + tx * (inset + 1.65))
            if park.buffer(-.8).covers(ShapePoint(inward)) and not protected.buffer(1).covers(ShapePoint(inward)):
                height = 3.0 + .4 * math.sin(sample.station * .21)
                scene.broadleaf((*inward, scene.ground(*inward)), height, int(sample.station) + 157719660)
                shrubs += 1
    scene.landmarks.append({
        'name': 'Le Parc Spelugues stone boundary and dense low hedge', 'osm_id': record.osm_id,
        'stone_wall_length_m': wall_length, 'reconstructed_hedge_clusters': shrubs,
        'wall_height_m': record.wall_height_m,
        'dimensions_status': record.source_note,
    })
