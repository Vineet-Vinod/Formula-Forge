from __future__ import annotations

import math
from itertools import pairwise

from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_foundation_dataclasses import XY, FoundationCorner, FoundationSource
from venues.baku_khagani_dataclasses import FrontWall
from venues.baku_khagani_geometry import band, glazing, lathe, masonry, relief
from venues.baku_philharmonic_geometry import column

KIND = 'Building_Foundation'
STONE = 'BakuStone'
TRIM = 'Cream'
BLUE = 'BakuFoundationBlueRoof'


def rounded(source: FoundationSource) -> tuple[Polygon, FoundationCorner]:
    ring = source.ring_xy_m
    v = ring[0]
    to_previous = tuple((b - a) / math.dist(v, ring[-1]) for a, b in zip(v, ring[-1]))
    to_next = tuple((b - a) / math.dist(v, ring[1]) for a, b in zip(v, ring[1]))
    cosine = sum(a * b for a, b in zip(to_previous, to_next))
    half_angle = math.acos(max(-1., min(1., cosine))) / 2
    tangent = source.corner_radius_m / math.tan(half_angle)
    bisector = tuple(a + b for a, b in zip(to_previous, to_next))
    magnitude = math.hypot(*bisector)
    center: XY = (v[0] + bisector[0] / magnitude * source.corner_radius_m / math.sin(half_angle),
                  v[1] + bisector[1] / magnitude * source.corner_radius_m / math.sin(half_angle))
    a = tuple(x + y * tangent for x, y in zip(v, to_previous))
    b = tuple(x + y * tangent for x, y in zip(v, to_next))
    start = math.atan2(a[1] - center[1], a[0] - center[0])
    end = math.atan2(b[1] - center[1], b[0] - center[0])
    sweep = (end - start + math.pi) % math.tau - math.pi
    arc = tuple((center[0] + source.corner_radius_m * math.cos(start + sweep * i / 24),
                 center[1] + source.corner_radius_m * math.sin(start + sweep * i / 24)) for i in range(25))
    shape = orient(Polygon((*arc, *ring[1:])), sign=1)
    if not shape.is_valid or shape.difference(Polygon(ring).buffer(1e-8)).area > 1e-8:
        raise ValueError('The photographed corner must stay inside its mapped owner')
    # The arc emitter traverses its surface counterclockwise for outward winding.
    arc_start = start if sweep > 0 else end
    corner = FoundationCorner(center, source.corner_radius_m, arc_start, abs(sweep), source.floor_relative_m)
    return shape, corner


def face(a: XY, b: XY, z: float) -> CourtFace:
    length = math.dist(a, b)
    tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.)
    return CourtFace((*a, z), tangent, (tangent[1], -tangent[0], 0.), length, length)


def openings(length: float, source: FoundationSource, primary: bool,
             panel_center: float | None = None) -> list[CourtOpening]:
    candidates = [length * (i + .5) / max(1, round(length / 4.4))
                  for i in range(max(1, round(length / 4.4)))]
    if panel_center is not None:
        candidates = [x for x in candidates if abs(x - panel_center) > 3.0]
    result = []
    for row, (low, high) in enumerate(pairwise(source.floor_bands_m)):
        for u in candidates:
            width = min(1.65, length * .48)
            bottom = low + (.85 if row == 0 else .65)
            height = min(2.65, high - bottom - .45)
            result.append(_opening(u, width, bottom, height, primary and row == 4, False))
    if panel_center is not None:
        result.append(_opening(panel_center, 2.5, 0., 4.0, False, True))
    return result


def star_panel(scene: CircuitScene, wall: CourtFace, u: float) -> None:
    width, low, high = 3.25, 6.0, 25.3
    relief(scene, wall, box(u - width / 2, low, u + width / 2, high), .025, -.10, 'BakuFoundationRecess')
    for edge in (u - width / 2 - .14, u + width / 2 + .14):
        relief(scene, wall, box(edge - .10, low - .15, edge + .10, high + .15), .20, .02, TRIM)
    # Original geometric relief conveys the photographed patterned stone panel.
    for row in range(27):
        z = low + .38 + row * (high - low - .76) / 26
        for col in range(4):
            x = u - 1.1 + col * .73
            points = [(x + (.26 if i % 2 == 0 else .12) * math.cos(i * math.pi / 8),
                       z + (.26 if i % 2 == 0 else .12) * math.sin(i * math.pi / 8)) for i in range(16)]
            for a, b in pairwise([*points, points[0]]):
                scene.beam(KIND, TRIM, _point(wall, *a, .10), _point(wall, *b, .10), .038)
    for offset in (-2.42, -1.94, 1.94, 2.42):
        center = _point(wall, u + offset, 4.9, .14)
        column(scene, center, .15, 19.75, TRIM, KIND)
        for z, thickness in ((4.8, .25), (24.3, .28), (24.6, .30)):
            relief(scene, wall, box(u + offset - .27, z, u + offset + .27, z + thickness), .37, -.01, TRIM)


def straight(scene: CircuitScene, wall: CourtFace, source: FoundationSource,
             primary: bool, panel_fraction: float | None) -> None:
    panel = wall.length_m * panel_fraction if panel_fraction is not None else None
    holes = openings(wall.length_m, source, primary, panel)
    masonry(scene, FrontWall(133160748, -1, wall, ((0., -.70), (wall.length_m, -.70)),
                            (0., wall.length_m)), source.body_height_m, holes, STONE, .38)
    for opening in holes:
        glazing(scene, wall, opening, -.28, 'Glass', stone=True)
    for z in source.floor_bands_m[1:-1]:
        intervals = ((0., wall.length_m),) if panel is None else ((0., panel - 1.82), (panel + 1.82, wall.length_m))
        for interval in intervals:
            band(scene, wall, z - .14, .18, .16, TRIM, interval)
    for low, thick, depth in ((.0, .22, .11), (25.3, .22, .20), (25.55, .25, .31),
                              (26.0, .45, .15), (26.5, .22, .28), (26.88, .32, .40)):
        band(scene, wall, low, thick, depth, TRIM)
    if primary:
        for i in range(max(1, round(wall.length_m / .58))):
            x = wall.length_m * (i + .5) / max(1, round(wall.length_m / .58))
            relief(scene, wall, box(x - .09, 26.68, x + .09, 26.87), .32, .16, TRIM)
        for z in (1.4, 2.25, 3.1, 3.95):
            # Rustication is split around the actual apertures, avoiding dark glass overlaps.
            strip = box(0., z, wall.length_m, z + .025).difference(unary_union([h.shape.buffer(.13) for h in holes]))
            if isinstance(strip, (Polygon, MultiPolygon)):
                relief(scene, wall, strip, .035, .015, TRIM)
    if panel is not None:
        star_panel(scene, wall, panel)


def curved_panel(scene: CircuitScene, corner: FoundationCorner, shape: Polygon,
                 depth: float, material: str, segments: int = 24) -> None:
    length = corner.radius_m * corner.sweep_rad
    for i in range(segments):
        part = shape.intersection(box(length * i / segments, -2, length * (i + 1) / segments, 50))
        if part.is_empty:
            continue
        for tri in constrained_delaunay_triangles(part).geoms:
            coords = list(orient(tri, sign=1).exterior.coords)[:3]
            p = [corner.point(u, z, depth) for u, z in coords]
            scene.triangle(KIND, material, p[0], p[1], p[2])


def corner_body(scene: CircuitScene, corner: FoundationCorner, source: FoundationSource) -> None:
    length = corner.radius_m * corner.sweep_rad
    holes = []
    for row, (low, high) in enumerate(pairwise(source.floor_bands_m)):
        for fraction in (.22, .50, .78):
            holes.append(_opening(length * fraction, .95, low + .8,
                                  min(2.5, high - low - 1.25), row == 4, False))
    body = box(0., -.70, length, source.body_height_m).difference(unary_union([o.shape for o in holes]))
    if not isinstance(body, Polygon):
        raise TypeError('Corner masonry lost its one perforated surface')
    curved_panel(scene, corner, body, 0., STONE)
    for opening in holes:
        curved_panel(scene, corner, opening.shape, -.25, 'Glass')
        for a, b in pairwise(opening.shape.exterior.coords):
            # Curved returns and original opening borders, without artificial facet mullions.
            steps = max(1, math.ceil(abs(b[0] - a[0]) / .18))
            for j in range(steps):
                u0, z0 = (a[k] + (b[k] - a[k]) * j / steps for k in (0, 1))
                u1, z1 = (a[k] + (b[k] - a[k]) * (j + 1) / steps for k in (0, 1))
                scene.quad(KIND, TRIM, corner.point(u0, z0), corner.point(u1, z1),
                           corner.point(u1, z1, -.25), corner.point(u0, z0, -.25))
                scene.beam(KIND, TRIM, corner.point(u0, z0, .055), corner.point(u1, z1, .055), .075)
    for z in (*source.floor_bands_m[1:-1], 25.3, 25.55, 26.0, 26.5, 26.88):
        ring = box(0., z - .08, length, z + .10)
        curved_panel(scene, corner, ring, .17 if z < 25.3 else .32, TRIM)


def roof(scene: CircuitScene, shape: Polygon, corner: FoundationCorner,
         source: FoundationSource) -> None:
    z = source.floor_relative_m + source.body_height_m
    for tri in constrained_delaunay_triangles(shape).geoms:
        coords = list(orient(tri, sign=1).exterior.coords)[:3]
        p = [(float(x), float(y), z + .08) for x, y in coords]
        scene.triangle(KIND, BLUE, p[0], p[1], p[2])
    center = (*corner.center, z)
    # Eight visible drum facets and a rounded sheet-metal crown are estimates from the retained views.
    drum_ring = [(corner.center[0] + source.dome_radius_m * math.cos(i * math.tau / 8),
                  corner.center[1] + source.dome_radius_m * math.sin(i * math.tau / 8)) for i in range(8)]
    for a, b in pairwise([*drum_ring, drum_ring[0]]):
        wall = face(a, b, z)
        hole = _opening(wall.length_m / 2, .85, .65, 1.9, True, False)
        masonry(scene, FrontWall(133160748, -1, wall, ((0., -.05), (wall.length_m, -.05)),
                                (0., wall.length_m)), 3.1, [hole], STONE, .25)
        glazing(scene, wall, hole, -.18)
        band(scene, wall, 2.85, .26, .17, TRIM)
    rings = ((3.1, 2.95), (3.25, 2.97), (3.8, 2.83), (4.5, 2.46),
             (5.2, 1.88), (5.8, 1.05), (6.2, .24), (6.45, .12))
    lathe(scene, center, rings, BLUE, 40)
    for i in range(10):
        angle = i * math.tau / 10
        p = [(center[0] + r * math.cos(angle), center[1] + r * math.sin(angle), center[2] + h)
             for h, r in rings]
        for rib_a, rib_b in pairwise(p):
            scene.beam(KIND, 'Steel', rib_a, rib_b, .025)
    lathe(scene, center, ((6.4, .15), (6.65, .23), (6.85, .12), (7.35, .035)), 'Steel', 12)


def build(scene: CircuitScene, source: FoundationSource) -> Polygon:
    shape, corner = rounded(source)
    primary = {0: LineString([source.ring_xy_m[0], source.ring_xy_m[1]]),
               6: LineString([source.ring_xy_m[6], source.ring_xy_m[0]])}
    ring = list(shape.exterior.coords)
    for a, b in pairwise(ring):
        middle = LineString([a, b]).interpolate(.5, normalized=True)
        # Arc chords are emitted as a separate continuous surface.
        if (all(line.distance(middle) > .00001 for line in primary.values())
                and math.dist(middle.coords[0], corner.center) < source.corner_radius_m + .001):
            continue
        wall = face(a, b, source.floor_relative_m)
        owner = next((key for key, line in primary.items() if line.distance(middle) < .00001), None)
        fraction = .37 if owner == 6 else None
        straight(scene, wall, source, owner is not None, fraction)
    corner_body(scene, corner, source)
    roof(scene, shape, corner, source)
    return shape
