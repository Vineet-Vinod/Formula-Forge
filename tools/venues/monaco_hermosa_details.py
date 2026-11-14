"""Original loggias and attic geometry within the retained measured envelope."""
from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.east_architecture import cylinder
from venues.monaco_hermosa_dataclasses import HermosaArchitecture, HermosaPhoto

RoofTriangle = tuple[Point, Point, Point]


def frontage(body: Polygon) -> tuple[tuple[float, float], tuple[float, float]]:
    return max((edge for edge in pairwise(orient(body).exterior.coords)
                if (edge[0][1] + edge[1][1]) / 2 < body.centroid.y),
               key=lambda edge: math.dist(*edge))


def roof(scene: CircuitScene, source: HermosaArchitecture) -> tuple[RoofTriangle, ...]:
    spec = HermosaPhoto()
    a, b, c, d = [(*scene.geo(lat, lon), z - source.relative_datum_m)
                   for lon, lat, z in source.eaves_wgs84]
    west, east = [(*xy, source.ridge_absolute_m - source.relative_datum_m)
                  for xy in source.ridge_xy_m]
    t = spec.mansard_front_fraction
    inner_b = (b[0] + (west[0] - b[0]) * t, b[1] + (west[1] - b[1]) * t, b[2] + spec.mansard_rise_m)
    inner_c = (c[0] + (east[0] - c[0]) * t, c[1] + (east[1] - c[1]) * t, c[2] + spec.mansard_rise_m)
    return ((a, b, inner_b), (a, inner_b, west),
            (b, c, inner_c), (b, inner_c, inner_b),
            (inner_b, inner_c, east), (inner_b, east, west),
            (c, d, inner_c), (d, east, inner_c),
            (d, a, west), (d, west, east))


def arched_panel(scene: CircuitScene, point: Callable[[float, float, float], Point],
                 along: float, base: float, width: float, height: float,
                 glazed: bool) -> None:
    kind = 'Building_HermosaAttic'
    radius = width / 2
    spring = height - radius
    ring = [(-radius, 0.0), (radius, 0.0), (radius, spring)]
    ring.extend((radius * math.cos(math.pi * i / 16), spring + radius * math.sin(math.pi * i / 16))
                for i in range(1, 17))
    shape = orient(Polygon(ring))
    opening = None
    if glazed:
        inner = radius * .62
        inner_ring = [(-inner, .35), (inner, .35), (inner, spring)]
        inner_ring.extend((inner * math.cos(math.pi * i / 16), spring + inner * math.sin(math.pi * i / 16))
                          for i in range(1, 17))
        opening = orient(Polygon(inner_ring))
    front_depth, back_depth, recess = .12, -1.1, .04

    def vertex(x: float, z: float, depth: float) -> Point:
        return point(along + x, depth, base + z)

    front = shape.difference(opening) if opening is not None else shape
    for tri in constrained_delaunay_triangles(front).geoms:
        xy = list(orient(tri).exterior.coords)[:3]
        a, b, c = [vertex(x, z, front_depth) for x, z in xy]
        scene.triangle(kind, 'Limestone', a, b, c)
    for tri in constrained_delaunay_triangles(shape).geoms:
        xy = list(orient(tri).exterior.coords)[:3]
        a, b, c = [vertex(x, z, back_depth) for x, z in xy]
        scene.triangle(kind, 'Steel', c, b, a)
    for a, b in pairwise(shape.exterior.coords):
        scene.quad(kind, 'Steel', vertex(b[0], b[1], front_depth), vertex(a[0], a[1], front_depth),
                   vertex(a[0], a[1], back_depth), vertex(b[0], b[1], back_depth))
    if opening is not None:
        for tri in constrained_delaunay_triangles(opening).geoms:
            xy = list(orient(tri).exterior.coords)[:3]
            a, b, c = [vertex(x, z, recess) for x, z in xy]
            scene.triangle(kind, 'Glass', a, b, c)
        for a, b in pairwise(opening.exterior.coords):
            scene.quad(kind, 'Limestone', vertex(a[0], a[1], front_depth), vertex(b[0], b[1], front_depth),
                       vertex(b[0], b[1], recess), vertex(a[0], a[1], recess))


def decorate(scene: CircuitScene, source: HermosaArchitecture,
             ground: Callable[[float, float], float]) -> None:
    body = Polygon(scene.footprint(source.osm_id).ring)
    a, b = frontage(body)
    span = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    nx, ny = ty, -tx
    spec = HermosaPhoto()
    kind = 'Building_HermosaLoggias'

    def point(along: float, depth: float, z: float) -> Point:
        return a[0] + tx * along + nx * depth, a[1] + ty * along + ny * depth, z

    total = sum(spec.bay_proportions)
    controls = [0.0]
    for weight in spec.bay_proportions:
        controls.append(controls[-1] + span * weight / total)
    base = source.floor_base_absolute_m - source.relative_datum_m
    for floor in range(source.floors):
        z = base + floor * source.floor_height_m
        ceiling = z + source.floor_height_m
        for bay, (low, high) in enumerate(pairwise(controls)):
            wide = bay not in (1, 4)
            depth = spec.balcony_depth_m if wide else .65
            scene.beam(kind, 'Limestone', point(low + .08, depth / 2, z - .11),
                       point(high - .08, depth / 2, z - .11), depth, .22)
            scene.beam(kind, 'Cream', point(low + .02, depth / 2, z - .02),
                       point(high - .02, depth / 2, z - .02), depth + .12, .10)
            middle = (low + high) / 2
            door_width = min(high - low - .7, 4.4) if wide else 1.45
            left, right = middle - door_width / 2, middle + door_width / 2
            lower, upper = z + .18, ceiling - .47
            p, q = point(left, .045, lower), point(right, .045, lower)
            if lower >= ground(*point(middle, 0, 0)[:2]) + .1:
                scene.banner(p, q, upper - lower, 'Glass', kind)
                for along in (left, middle, right):
                    scene.beam(kind, 'Cream', point(along, .07, lower), point(along, .07, upper), .10, .10)
                scene.beam(kind, 'Cream', point(left - .12, .06, upper), point(right + .12, .06, upper), .15, .18)
            rail_depth = depth - .1
            rail_color = 'Black' if wide else 'Limestone'
            scene.beam(kind, rail_color, point(low + .25, rail_depth, z + 1.02),
                       point(high - .25, rail_depth, z + 1.02), .045 if wide else .14, .045 if wide else .12)
            scene.beam(kind, rail_color, point(low + .25, rail_depth, z + .16),
                       point(high - .25, rail_depth, z + .16), .035 if wide else .10, .035 if wide else .12)
            count = max(2, math.ceil((high - low - .5) / (.65 if wide else .4)))
            for i in range(count + 1):
                along = low + .25 + (high - low - .5) * i / count
                scene.beam(kind, rail_color, point(along, rail_depth, z + .16),
                           point(along, rail_depth, z + 1.02), .03 if wide else .10, .03 if wide else .10)
            if wide:
                motifs = max(1, round((high - low - .6) / 1.3))
                for motif in range(motifs):
                    center = low + .3 + (high - low - .6) * (motif + .5) / motifs
                    for mirror in (-1, 1):
                        path = [point(center + mirror * .25 * math.sin(t * math.tau),
                                      rail_depth + .015, z + .2 + .76 * t)
                                for t in (i / 12 for i in range(13))]
                        for first, second in pairwise(path):
                            scene.beam(kind, 'Black', first, second, .022, .022)
        for along in controls[1:-1]:
            x, y, _z = point(along, spec.balcony_depth_m - .16, z)
            bottom = max(z + .18, ground(x, y))
            if bottom >= ceiling - .3:
                continue
            cylinder(scene, (x, y, bottom), spec.column_radius_m, spec.column_radius_m,
                     ceiling - .3 - bottom, 'MonacoRuscinoRose', segments=12)
            for cap_z in (bottom, ceiling - .3):
                scene.beam(kind, 'Limestone', point(along - .28, spec.balcony_depth_m - .16, cap_z),
                           point(along + .28, spec.balcony_depth_m - .16, cap_z), .48, .14)
        scene.beam(kind, 'Cream', point(0, .05, ceiling - .12), point(span, .05, ceiling - .12), .35, .22)
    cornice = min(p[2] for p in source.eaves_wgs84[:3]) - source.relative_datum_m
    for fraction in spec.dormer_fractions:
        arched_panel(scene, point, span * fraction, cornice + .15, 1.8, 2.5, True)
    for fraction in spec.blind_fractions:
        arched_panel(scene, point, span * fraction, cornice + .15, 1.6, 2.35, False)
    arched_panel(scene, point, span * .5, cornice + .1, 3.1, 2.8, False)
    scene.landmarks.append({'name': 'Villa Hermosa developer-photo loggias and attic',
                            'source': 'Groupe Marzocco project/photo, reviewed locally',
                            'visible_levels': source.floors, 'estimated_balcony_depth_m': spec.balcony_depth_m,
                            'limits': 'Plausible south-elevation registration; bay proportions, depths, columns, mansard break and ornament sizes estimated. Literal body and measured eaves/ridge unchanged. Unphotographed faces remain estimates; Ground/native data unchanged.'})
