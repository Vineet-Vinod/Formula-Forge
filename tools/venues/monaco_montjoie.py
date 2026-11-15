"""Registered Villa Montjoie openings, iron balconies and small roof pavilion."""
from __future__ import annotations

import math
from itertools import pairwise

from circuit_mesh import MeshScene, Point
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon

from venues.monaco_foreground_dataclasses import (
    XY,
    MontjoieAudit,
    MontjoieFrame,
    MontjoieOpening,
    MontjoieSpec,
)

KIND = 'Building_MonacoMontjoie'
FACADE = 'MonacoMontjoieCream'
WOOD = 'MonacoMontjoieWood'
BLUE = 'MonacoMontjoieBlueRoof'

def front_frame(spec: MontjoieSpec) -> MontjoieFrame:
    first, last = (spec.owner_xy_m[i] for i in spec.front_vertex_indices)
    width = math.dist(first, last)
    tangent = (last[0] - first[0]) / width, (last[1] - first[1]) / width
    return MontjoieFrame(first, tangent, (tangent[1], -tangent[0]), width)


def point(frame: MontjoieFrame, u: float, v: float, z: float) -> Point:
    return (frame.origin[0] + frame.tangent[0] * u + frame.outward[0] * v,
            frame.origin[1] + frame.tangent[1] * u + frame.outward[1] * v, z)


def opening_contour(center: float, width: float, bottom: float,
                    height: float, arched: bool) -> tuple[XY, ...]:
    left, right = center - width / 2, center + width / 2
    if not arched:
        return ((left, bottom), (right, bottom), (right, bottom + height),
                (left, bottom + height))
    radius = width / 2
    spring = bottom + height - radius
    arch = tuple((center + radius * math.cos(i * math.pi / 20),
                  spring + radius * math.sin(i * math.pi / 20)) for i in range(21))
    return ((left, bottom), (right, bottom), *arch)


def openings(spec: MontjoieSpec) -> tuple[MontjoieOpening, ...]:
    result: list[MontjoieOpening] = []
    for floor, offset in enumerate(spec.floor_bottom_offsets_m):
        for bay, (center, width) in enumerate((
                (spec.left_bay_center_m, spec.left_opening_width_m),
                (spec.right_bay_center_m, spec.right_opening_width_m))):
            contour = opening_contour(center, width, spec.base_relative_m + offset,
                                      spec.opening_height_m, floor == 4)
            result.append(MontjoieOpening(floor, bay, contour))
    return tuple(result)


def facade_shape(spec: MontjoieSpec, frame: MontjoieFrame,
                 apertures: tuple[MontjoieOpening, ...]) -> Polygon:
    return Polygon(((0, spec.base_relative_m), (frame.width_m, spec.base_relative_m),
                    (frame.width_m, spec.main_top_relative_m), (0, spec.main_top_relative_m)),
                   [opening.contour_uz_m for opening in apertures])


def pavilion_plan(spec: MontjoieSpec, frame: MontjoieFrame) -> tuple[Point, ...]:
    center_u, center_v = spec.pavilion_center_uv_m
    return tuple(point(frame, center_u + u * spec.pavilion_width_m / 2,
                       center_v + v * spec.pavilion_depth_m / 2,
                       spec.main_top_relative_m) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)))


def validate_spec(spec: MontjoieSpec) -> MontjoieAudit:
    frame = front_frame(spec)
    owner = Polygon(spec.owner_xy_m)
    apertures = openings(spec)
    facade = facade_shape(spec, frame, apertures)
    if not owner.is_valid or owner.area <= 0 or frame.outward[1] > -.99:
        raise ValueError('Montjoie requires the valid literal south-facing owner')
    if spec.main_top_relative_m <= spec.base_relative_m or not facade.is_valid:
        raise ValueError('Opening apertures must be disjoint and contained in the front wall')
    if any(Polygon(item.contour_uz_m).distance(facade.exterior) < .25 for item in apertures):
        raise ValueError('Every opening must leave at least .25 m of enclosing wall')
    plan = pavilion_plan(spec, frame)
    if not owner.buffer(-.3).contains(Polygon([p[:2] for p in plan])):
        raise ValueError('The estimated pavilion must stay inside this owner roof')
    if any(a >= b for a, b in pairwise(spec.floor_bottom_offsets_m)):
        raise ValueError('Floor bands must increase')
    aperture_area = sum(Polygon(item.contour_uz_m).area for item in apertures)
    return MontjoieAudit(
        spec.osm_id, owner.area, frame.width_m, spec.base_relative_m,
        spec.main_top_relative_m, spec.main_top_relative_m + spec.relative_datum_m,
        len(apertures), 2, 4, 5, spec.recess_m, facade.area, aperture_area,
        spec.main_top_relative_m + spec.parapet_height_m,
        spec.main_top_relative_m + spec.pavilion_height_m,
        spec.main_top_relative_m + spec.pavilion_height_m + spec.relative_datum_m,
        plan, apertures,
    )


def face(scene: MeshScene, frame: MontjoieFrame, shape: Polygon,
         material: str, depth: float = 0) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coordinates.reverse()
        vertices = [point(frame, p[0], depth, p[1]) for p in coordinates]
        scene.triangle(KIND, material, vertices[0], vertices[1], vertices[2])


def line(scene: MeshScene, frame: MontjoieFrame, material: str,
         a: Point, b: Point, width: float, depth: float | None = None) -> None:
    scene.beam(KIND, material, point(frame, *a), point(frame, *b), width, depth)


def outline(scene: MeshScene, frame: MontjoieFrame, contour: tuple[XY, ...],
            v: float, material: str, width: float) -> None:
    for a, b in pairwise((*contour, contour[0])):
        line(scene, frame, material, (a[0], v, a[1]), (b[0], v, b[1]), width)


def recessed_opening(scene: MeshScene, spec: MontjoieSpec,
                     frame: MontjoieFrame, opening: MontjoieOpening) -> None:
    contour = opening.contour_uz_m
    for a, b in pairwise((*contour, contour[0])):
        scene.quad(KIND, 'White', point(frame, a[0], 0, a[1]),
                   point(frame, b[0], 0, b[1]), point(frame, b[0], -spec.recess_m, b[1]),
                   point(frame, a[0], -spec.recess_m, a[1]))
    shape = Polygon(contour)
    face(scene, frame, shape, 'Glass', -spec.recess_m)
    surround = shape.buffer(.17, join_style='mitre').difference(shape)
    if not isinstance(surround, Polygon):
        raise TypeError('A Montjoie molded surround must remain a single ring')
    face(scene, frame, surround, 'White', .025)
    outer = tuple((p[0], p[1]) for p in surround.exterior.coords[:-1])
    outline(scene, frame, outer, .05, 'White', .065)
    outline(scene, frame, contour, -.09, WOOD, .105)
    left, bottom, right, top = shape.bounds
    center = (left + right) / 2
    line(scene, frame, WOOD, (center, -.105, bottom), (center, -.105, top), .075)
    transom = bottom + (1.02 if opening.floor != 4 else 1.25)
    line(scene, frame, WOOD, (left, -.105, transom), (right, -.105, transom), .06)
    if opening.floor < 4:
        for z, width, thickness in ((top + .22, right - left + .50, .09),
                                    (top + .32, right - left + .64, .10)):
            line(scene, frame, 'White', (center - width / 2, .095, z),
                 (center + width / 2, .095, z), thickness, .15)
    line(scene, frame, 'White', (left - .23, .12, bottom - .10),
         (right + .23, .12, bottom - .10), .12, .26)
    # The photographed small blue crown is an ornament, not a balcony slab.
    line(scene, frame, BLUE, (center, .12, top + .20), (center, .12, top + .36), .07)
    for direction in (-1, 1):
        line(scene, frame, BLUE, (center, .12, top + .25),
             (center + direction * .13, .12, top + .37), .065)


def scroll_rail(scene: MeshScene, frame: MontjoieFrame,
                path: tuple[XY, ...], base: float, height: float) -> None:
    for level, width in ((.05, .035), (height, .045)):
        for a, b in pairwise(path):
            line(scene, frame, 'White', (a[0], a[1], base + level),
                 (b[0], b[1], base + level), width)
    distance = [0.0]
    for a, b in pairwise(path):
        distance.append(distance[-1] + math.dist(a, b))
    panels = max(2, round(distance[-1] / .48))
    for panel in range(panels + 1):
        t = distance[-1] * panel / panels
        segment = min(len(path) - 2, next((i for i in range(len(distance) - 1)
                                          if distance[i + 1] >= t), len(path) - 2))
        a, b = path[segment], path[segment + 1]
        fraction = (t - distance[segment]) / (distance[segment + 1] - distance[segment])
        u, v = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
        length = math.dist(a, b)
        tu, tv = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        line(scene, frame, 'White', (u, v, base + .04), (u, v, base + height), .023)
        if panel == panels:
            continue
        for handed in (-1, 1):
            curve: list[Point] = []
            for step in range(19):
                angle = step / 18 * 2 * math.pi
                radius = .16 * (1 - .75 * step / 18)
                du = .23 + handed * radius * math.sin(angle)
                z = base + height / 2 + handed * radius * 1.8 * math.cos(angle)
                curve.append((u + tu * du, v + tv * du, z))
            for first, last in pairwise(curve):
                line(scene, frame, 'White', first, last, .017)


def balcony_contour(center: float, halfwidth: float, depth: float,
                    scalloped: bool) -> tuple[XY, ...]:
    contour: list[XY] = []
    for step in range(41):
        theta = math.pi - math.pi * step / 40
        shoulder = .10 * math.sin(5 * theta) ** 2 if scalloped else 0.0
        contour.append((center + halfwidth * math.cos(theta),
                        -.07 + (depth + .12) * math.sin(theta) + shoulder))
    return tuple(contour)


def balcony(scene: MeshScene, spec: MontjoieSpec, frame: MontjoieFrame,
            opening: MontjoieOpening) -> None:
    bottom = min(p[1] for p in opening.contour_uz_m) - .05
    upper = opening.floor == 4
    halfwidth = spec.top_balcony_halfwidth_m if upper else spec.balcony_halfwidth_m
    depth = spec.top_balcony_depth_m if upper else spec.balcony_depth_m
    path = balcony_contour(spec.left_bay_center_m, halfwidth, depth, not upper)
    for triangle in constrained_delaunay_triangles(Polygon(path)).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        if triangle.exterior.is_ccw:
            coordinates.reverse()
        vertices = [point(frame, p[0], p[1], bottom) for p in coordinates]
        scene.triangle(KIND, 'White', vertices[0], vertices[1], vertices[2])
        vertices = [point(frame, p[0], p[1], bottom - .22) for p in coordinates]
        scene.triangle(KIND, 'White', vertices[2], vertices[1], vertices[0])
    for a, b in pairwise((*path, path[0])):
        scene.quad(KIND, 'White', point(frame, a[0], a[1], bottom - .22),
                   point(frame, b[0], b[1], bottom - .22), point(frame, b[0], b[1], bottom),
                   point(frame, a[0], a[1], bottom))
    for a, b in pairwise(path):
        for z, width in ((bottom - .03, .09), (bottom - .19, .12)):
            line(scene, frame, 'White', (a[0], a[1] + .04, z),
                 (b[0], b[1] + .04, z), width)
    scroll_rail(scene, frame, path, bottom + .04, .87)
    shell: list[list[Point]] = []
    for radial_step in range(5):
        radius = radial_step / 4
        band: list[Point] = []
        for segment in range(29):
            theta = math.pi * segment / 28
            band.append((spec.left_bay_center_m + radius * halfwidth * .8 * math.cos(theta),
                         .10 + radius * (.03 + depth * .90 * math.sin(theta)),
                         bottom - .62 + .37 * math.sin(radius * math.pi / 2)
                         - .025 * radius * math.cos(theta * 28)))
        shell.append(band)
    for lower, upper_band in pairwise(shell):
        for segment in range(28):
            scene.quad(KIND, 'White', point(frame, *lower[segment]),
                       point(frame, *lower[segment + 1]), point(frame, *upper_band[segment + 1]),
                       point(frame, *upper_band[segment]), up=False)
    for segment in range(0, 29, 2):
        for first, last in pairwise([band[segment] for band in shell]):
            line(scene, frame, 'White', first, last, .035)
    if not upper:
        for sign in (-1, 1):
            u = spec.left_bay_center_m + sign * (halfwidth - .30)
            line(scene, frame, 'White', (u, .35, bottom - .25),
                 (u, .23, bottom - .78), .27, .32)
            line(scene, frame, 'White', (u, .23, bottom - .78),
                 (u, .11, bottom - 1.06), .14, .18)


def baluster(scene: MeshScene, center: Point, height: float) -> None:
    profile = ((0, .055), (.10, .055), (.19, .085), (.36, .10),
               (.51, .055), (.64, .04), (.73, .055), (1.0, .055))
    for (z0, r0), (z1, r1) in pairwise(profile):
        for side in range(8):
            a, b = side * math.tau / 8, (side + 1) * math.tau / 8
            scene.quad(KIND, 'White',
                       (center[0] + r0 * math.cos(a), center[1] + r0 * math.sin(a), center[2] + z0 * height),
                       (center[0] + r0 * math.cos(b), center[1] + r0 * math.sin(b), center[2] + z0 * height),
                       (center[0] + r1 * math.cos(b), center[1] + r1 * math.sin(b), center[2] + z1 * height),
                       (center[0] + r1 * math.cos(a), center[1] + r1 * math.sin(a), center[2] + z1 * height))


def roof_balustrade(scene: MeshScene, spec: MontjoieSpec, frame: MontjoieFrame) -> None:
    top = spec.main_top_relative_m
    # Only the photographed front and short returns have balustrade detail.
    paths = (((0, -.05), (frame.width_m, -.05)),
             ((.08, -3), (.08, -.05)),
             ((frame.width_m - .08, -.05), (frame.width_m - .08, -2.8)))
    for a, b in paths:
        for height, width in ((.10, .25), (spec.parapet_height_m, .23)):
            line(scene, frame, 'White', (a[0], a[1], top + height),
                 (b[0], b[1], top + height), width, .15)
        count = max(1, round(math.dist(a, b) / .34))
        for i in range(1, count):
            u = a[0] + (b[0] - a[0]) * i / count
            v = a[1] + (b[1] - a[1]) * i / count
            baluster(scene, point(frame, u, v, top + .18), spec.parapet_height_m - .26)
    for u in (.10, frame.width_m / 2, frame.width_m - .10):
        line(scene, frame, 'White', (u, -.05, top), (u, -.05, top + spec.parapet_height_m), .37)


def tiled_pavilion(scene: MeshScene, spec: MontjoieSpec, frame: MontjoieFrame) -> None:
    plan = tuple(reversed(pavilion_plan(spec, frame)))
    base = spec.main_top_relative_m
    eaves = base + .70
    center = point(frame, *spec.pavilion_center_uv_m, base + spec.pavilion_height_m)
    for a, b in pairwise((*plan, plan[0])):
        scene.quad(KIND, 'White', a, b, (b[0], b[1], eaves), (a[0], a[1], eaves))
        scene.beam(KIND, 'White', (a[0], a[1], eaves), (b[0], b[1], eaves), .11)
        left, right = (a[0], a[1], eaves), (b[0], b[1], eaves)
        scene.triangle(KIND, BLUE, left, right, center)
        # Raised original fishscale contours create tile edges without photo textures.
        for row in range(9):
            lower, upper = row / 9, (row + 1) / 9
            count = max(1, round((1 - lower) * 11))
            for tile in range(count):
                s0, s1 = tile / count, (tile + 1) / count
                polygon: list[Point] = []
                for s, t in ((s0, upper), (s1, upper)):
                    edge = tuple(left[i] + (right[i] - left[i]) * s for i in range(3))
                    polygon.append((edge[0] + (center[0] - edge[0]) * t,
                                    edge[1] + (center[1] - edge[1]) * t,
                                    edge[2] + (center[2] - edge[2]) * t + .018))
                for step in range(7):
                    s = s1 - (s1 - s0) * step / 6
                    t = lower - .025 * math.sin(math.pi * step / 6)
                    edge = tuple(left[i] + (right[i] - left[i]) * s for i in range(3))
                    polygon.append((edge[0] + (center[0] - edge[0]) * t,
                                    edge[1] + (center[1] - edge[1]) * t,
                                    edge[2] + (center[2] - edge[2]) * t + .018))
                for first, last in pairwise(polygon[1:]):
                    scene.triangle(KIND, BLUE, polygon[0], last, first)


def emit_montjoie(scene: MeshScene, spec: MontjoieSpec) -> MontjoieAudit:
    """Append original meshes only; no terrain, assets, buffers or scene metadata access."""
    audit = validate_spec(spec)
    frame = front_frame(spec)
    ring = tuple(reversed(spec.owner_xy_m))
    front = {spec.owner_xy_m[i] for i in spec.front_vertex_indices}
    for a, b in pairwise((*ring, ring[0])):
        if {a, b} == front:
            continue
        scene.quad(KIND, FACADE, (*a, spec.base_relative_m), (*b, spec.base_relative_m),
                   (*b, spec.main_top_relative_m), (*a, spec.main_top_relative_m))
    face(scene, frame, facade_shape(spec, frame, audit.openings), FACADE)
    for triangle in constrained_delaunay_triangles(Polygon(spec.owner_xy_m)).geoms:
        p = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            p.reverse()
        scene.triangle(KIND, 'White', (p[0][0], p[0][1], spec.main_top_relative_m),
                       (p[1][0], p[1][1], spec.main_top_relative_m),
                       (p[2][0], p[2][1], spec.main_top_relative_m))
    for opening in audit.openings:
        recessed_opening(scene, spec, frame, opening)
        if opening.bay == 0 and opening.floor > 0:
            balcony(scene, spec, frame, opening)
        if opening.bay == 1:
            left, bottom, right, _ = Polygon(opening.contour_uz_m).bounds
            scroll_rail(scene, frame, ((left - .05, .19), (right + .05, .19)), bottom + .08, .65)
    for offset, width in ((10.38, .07), (10.53, .045), (16.54, .16), (16.78, .24)):
        z = spec.base_relative_m + offset
        line(scene, frame, 'White', (0, .075, z), (frame.width_m, .075, z), width, width * 1.5)
    for u in (.08, frame.width_m - .08):
        line(scene, frame, 'White', (u, .045, spec.base_relative_m),
             (u, .045, spec.main_top_relative_m - .45), .14, .10)
    roof_balustrade(scene, spec, frame)
    tiled_pavilion(scene, spec, frame)
    return audit
