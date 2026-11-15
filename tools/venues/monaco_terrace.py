"""Measured garden and estimated stone retaining band: graded lawn, short masonry band, lower rock support."""

from __future__ import annotations

import math
import struct
from collections.abc import Iterable
from itertools import pairwise

from circuit_dataclasses import Point as XYZ
from circuit_mesh import MeshScene, cross, norm, sub, world
from shapely import constrained_delaunay_triangles, get_parts, make_valid
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from venues.monaco_terrace_dataclasses import TerraceAudit, TerraceFloor, TerraceSpec
from venues.monaco_terrace_stone import StoneFacing
from venues.monaco_underarch_plants import plane_height

TERRACE = "Building_HermosaTerrace"


def wall_quad(
    scene: MeshScene,
    material: str,
    a: XYZ,
    b: XYZ,
    c: XYZ,
    d: XYZ,
    uv: tuple[tuple[float, float], ...],
) -> None:
    scene.triangle(TERRACE, material, a, b, c, (uv[0], uv[1], uv[2]))
    scene.triangle(TERRACE, material, a, c, d, (uv[0], uv[2], uv[3]))


def encoded(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value * 100))[0] / 100


def encode_polygon(poly: Polygon) -> BaseGeometry:
    def ring(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        for x, y in points:
            point = (encoded(x), encoded(y))
            if not result or point != result[-1]:
                result.append(point)
        if len(result) > 1 and result[0] == result[-1]:
            result.pop()
        return result
    exterior = ring(poly.exterior.coords)
    if len(exterior) < 3:
        return Polygon()
    holes = [ring(r.coords) for r in poly.interiors]
    return make_valid(Polygon(exterior, [r for r in holes if len(r) >= 3]))


def lawn_triangle(scene: MeshScene, points: list[XYZ]) -> None:
    # The new top is triangulated after XY encoding; normals use actual packed XYZ.
    points = [(encoded(x), encoded(y), encoded(z)) for x, y, z in points]
    normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
    if normal[2] <= 0:
        raise ValueError("A newly encoded lawn face is collapsed or faces down")
    normal = norm(normal)
    tile = scene.tile("Tile_HermosaGardenLawn", points[0])
    if "MonacoGardenLawn" not in tile.materials:
        tile.materials.append("MonacoGardenLawn")
    tile.triangles.extend(struct.pack("<I", tile.materials.index("MonacoGardenLawn")))
    for point in points:
        native = world(point)
        tile.triangles.extend(struct.pack("<8f", *native, -normal[1], -normal[0], normal[2], point[0] / 8, point[1] / 8))
        for axis in range(3):
            tile.minimum[axis] = min(tile.minimum[axis], native[axis])
            tile.maximum[axis] = max(tile.maximum[axis], native[axis])


class Support:
    def __init__(self, faces: tuple[TerraceFloor, ...]) -> None:
        self.faces = faces
        self.index = STRtree([f.plan for f in faces])
        self.maximum_extrapolation = 0.0

    def height(self, x: float, y: float) -> float:
        point = Point(x, y)
        indices = self.index.query(point, predicate="covered_by")
        if not len(indices):
            nearest = int(self.index.nearest(point))
            distance = self.faces[nearest].plan.distance(point)
            if distance > 0.00003:
                raise ValueError(
                    f"No actual old Ground support at {(x, y)}; gap {distance}"
                )
            self.maximum_extrapolation = max(self.maximum_extrapolation, distance)
            indices = (nearest,)
        heights = [plane_height(self.faces[int(i)], x, y) for i in indices]
        if max(heights) - min(heights) > 0.003:
            raise ValueError("Competing actual old garden support planes")
        return max(heights)


def top_height(source: TerraceSpec, support: Support, x: float, y: float) -> float:
    source_grade = (
        source.reference_lawn_absolute_m
        + source.lawn_north_grade * (y - source.reference_northing_m)
        - source.relative_datum_m
    )
    return max(source_grade, support.height(x, y) + source.minimum_soil_cover_m)


def emit(
    scene: MeshScene,
    domain: Polygon,
    front: LineString,
    faces: tuple[TerraceFloor, ...],
    source: TerraceSpec,
) -> TerraceAudit:
    support = Support(faces)

    def level(x: float, y: float) -> float:
        return top_height(source, support, x, y)

    lawn = rock = stone = segments = balusters = hedges = 0
    minimum_soil = minimum_bury = math.inf
    maximum_band = maximum_rock = 0.0
    encoding_missing = encoding_extra = encoding_area_bound = 0.0
    minimum_top = math.inf
    maximum_top = -math.inf
    # Each top patch stays on one actual parent; the convex soil/grade envelope cannot sink into it.
    for parent in faces:
        region = parent.plan.intersection(domain)
        if region.area <= 1e-9:
            continue
        xmin, ymin, xmax, ymax = region.bounds
        for iy in range(
            math.floor(ymin / source.face_step_m), math.ceil(ymax / source.face_step_m)
        ):
            for ix in range(
                math.floor(xmin / source.face_step_m),
                math.ceil(xmax / source.face_step_m),
            ):
                part = region.intersection(
                    box(
                        ix * source.face_step_m,
                        iy * source.face_step_m,
                        (ix + 1) * source.face_step_m,
                        (iy + 1) * source.face_step_m,
                    )
                )
                for poly in get_parts(part):
                    if not isinstance(poly, Polygon) or poly.area <= 1e-9:
                        continue
                    packed = encode_polygon(poly)
                    encoding_missing += poly.difference(packed).area
                    encoding_extra += packed.difference(poly).area
                    encoding_area_bound += poly.length * 0.000022
                    for packed_poly in get_parts(packed):
                        if not isinstance(packed_poly, Polygon):
                            continue
                        for tri in constrained_delaunay_triangles(packed_poly).geoms:
                            xy = list(orient(tri).exterior.coords)[:3]
                            points = [(x, y, level(x, y)) for x, y in xy]
                            lawn_triangle(scene, points)
                            lawn += 1
                            for x, y, z in points:
                                minimum_soil = min(minimum_soil, z - support.height(x, y))
                                minimum_top = min(minimum_top, z)
                                maximum_top = max(maximum_top, z)
    boundary_levels = [level(x, y) for x, y in domain.exterior.coords]
    stone_facing = StoneFacing(domain.length, min(boundary_levels) - source.upper_stone_band_height_m - 1, max(boundary_levels) + 1, source)
    # Split every boundary at the actual old triangle crossings before closing the support.
    rings = [domain.exterior, *domain.interiors]
    representative = domain.representative_point()
    front_edges = []
    distance_along = 0.0
    for ring in rings:
        for a, b in pairwise(ring.coords):
            line = LineString((a, b))
            if front.distance(line.interpolate(0.5, normalized=True)) < 0.4:
                front_edges.append(line)
            cuts = {0.0, 1.0}
            for parent in faces:
                crossing = line.intersection(parent.plan.boundary)
                for part in get_parts(crossing):
                    if isinstance(part, Point):
                        cuts.add(line.project(part, normalized=True))
                    elif isinstance(part, LineString):
                        for p in part.coords:
                            cuts.add(line.project(Point(p), normalized=True))
            cuts.update(
                i / max(1, math.ceil(line.length / source.face_step_m))
                for i in range(1, max(1, math.ceil(line.length / source.face_step_m)))
            )
            for lo, hi in pairwise(sorted(cuts)):
                if hi - lo < 1e-8:
                    continue
                p, q = (
                    line.interpolate(lo, normalized=True),
                    line.interpolate(hi, normalized=True),
                )
                if p.distance(q) < 0.00003:
                    continue
                bottom = [
                    support.height(v.x, v.y) - source.retaining_burial_m for v in (p, q)
                ]
                top = [level(v.x, v.y) for v in (p, q)]
                band = [
                    max(bottom[i], top[i] - source.upper_stone_band_height_m)
                    for i in (0, 1)
                ]
                middle = line.interpolate((lo + hi) / 2, normalized=True)
                is_front = front.distance(middle) < 0.4
                minimum_bury = min(
                    minimum_bury,
                    *(support.height(v.x, v.y) - z for v, z in zip((p, q), bottom)),
                )
                maximum_band = max(maximum_band, *(top[i] - band[i] for i in (0, 1)))
                maximum_rock = max(maximum_rock, *(band[i] - bottom[i] for i in (0, 1)))
                count = 24
                previous = [(p.x, p.y, bottom[0]), (q.x, q.y, bottom[1])]
                for j in range(1, count + 1):
                    t = j / count
                    current = []
                    for i, v in enumerate((p, q)):
                        dx, dy = representative.x - v.x, representative.y - v.y
                        length = math.hypot(dx, dy)
                        inset = (
                            source.rock_inset_m
                            * math.sin(t * math.pi)
                            * (0.65 + 0.35 * math.sin(v.x * 1.7 + v.y * 0.9 + j * 0.73))
                        )
                        x, y = v.x + dx / length * inset, v.y + dy / length * inset
                        if not domain.buffer(0.00003).covers(Point(x, y)):
                            x, y = v.x, v.y
                        current.append((x, y, bottom[i] + (band[i] - bottom[i]) * t))
                    if max(band[i] - bottom[i] for i in (0, 1)) > 1e-7:
                        wall_quad(
                            scene,
                            "MonacoRockGround",
                            previous[0],
                            previous[1],
                            current[1],
                            current[0],
                            (
                                (
                                    (distance_along + lo * line.length) / 2,
                                    previous[0][2] / 2,
                                ),
                                (
                                    (distance_along + hi * line.length) / 2,
                                    previous[1][2] / 2,
                                ),
                                (
                                    (distance_along + hi * line.length) / 2,
                                    current[1][2] / 2,
                                ),
                                (
                                    (distance_along + lo * line.length) / 2,
                                    current[0][2] / 2,
                                ),
                            ),
                        )
                        rock += 2
                    previous = current
                if max(top[i] - band[i] for i in (0, 1)) > 1e-7:
                    wall_quad(
                        scene,
                        "MonacoTerraceMortar" if is_front else "MonacoRockGround",
                        (p.x, p.y, band[0]),
                        (q.x, q.y, band[1]),
                        (q.x, q.y, top[1]),
                        (p.x, p.y, top[0]),
                        (
                            ((distance_along + lo * line.length) / 3, band[0] / 3),
                            ((distance_along + hi * line.length) / 3, band[1] / 3),
                            ((distance_along + hi * line.length) / 3, top[1] / 3),
                            ((distance_along + lo * line.length) / 3, top[0] / 3),
                        ),
                    )
                    if is_front:
                        stone_facing.emit(scene, p, q, band, top, distance_along + lo * line.length, distance_along + hi * line.length)
                        stone += 2
                    else:
                        rock += 2
                segments += 1
                if is_front and p.distance(q) > 0.03:
                    for zoff, width in (
                        (0.06, 0.16),
                        (source.balustrade_height_m, 0.16),
                    ):
                        scene.beam(
                            TERRACE,
                            "White",
                            (p.x, p.y, top[0] + zoff),
                            (q.x, q.y, top[1] + zoff),
                            width,
                            0.10,
                        )
            distance_along += line.length
    combined_front = unary_union(front_edges)
    actual_front = combined_front if isinstance(combined_front, LineString) else linemerge(combined_front)
    # An original open balustrade profile follows the estimated pale rim; no traversable steps invented.
    line = actual_front
    for part in get_parts(line):
        if not isinstance(part, LineString):
            continue
        count = max(1, round(part.length / 0.40))
        for i in range(count + 1):
            v = part.interpolate(i / count, normalized=True)
            z = level(v.x, v.y) + 0.12
            sections = (
                (0, 0.085),
                (0.12, 0.085),
                (0.22, 0.055),
                (0.42, 0.105),
                (0.61, 0.055),
                (0.78, 0.065),
                (0.84, 0.085),
            )
            for (za, ra), (zb, rb) in pairwise(sections):
                for k in range(8):
                    a, b = k * math.tau / 8, (k + 1) * math.tau / 8
                    scene.quad(
                        TERRACE,
                        "White",
                        (v.x + ra * math.cos(b), v.y + ra * math.sin(b), z + za),
                        (v.x + ra * math.cos(a), v.y + ra * math.sin(a), z + za),
                        (v.x + rb * math.cos(a), v.y + rb * math.sin(a), z + zb),
                        (v.x + rb * math.cos(b), v.y + rb * math.sin(b), z + zb),
                    )
            balusters += 1
    # The photograph shows a continuous clipped hedge, not separated tall nursery stems.
    planted = domain.buffer(-0.1)
    for part in get_parts(actual_front):
        if not isinstance(part, LineString):
            continue
        count = max(1, math.ceil(part.length / 0.65))
        for i in range(count):
            v = part.interpolate((i + 0.5) / count, normalized=True)
            before = part.interpolate(max(0, part.project(v) - 0.05))
            after = part.interpolate(min(part.length, part.project(v) + 0.05))
            dx, dy = after.x - before.x, after.y - before.y
            length = math.hypot(dx, dy)
            candidates = [(v.x - dy / length * 0.9, v.y + dx / length * 0.9),
                          (v.x + dy / length * 0.9, v.y - dx / length * 0.9)]
            x, y = max(candidates, key=lambda p: domain.intersection(Point(*p).buffer(0.58)).area)
            height = 4.8
            if not planted.covers(Point(x, y).buffer(height * 0.41 * 0.28)):
                continue
            temporary = MeshScene()
            temporary.broadleaf(
                (x, y, level(x, y) - height * 0.46), height, 94399624 + i
            )
            for tile in temporary.tiles.values():
                for offset in range(0, len(tile.triangles), 100):
                    material = tile.materials[
                        struct.unpack_from("<I", tile.triangles, offset)[0]
                    ]
                    values = struct.unpack_from("<24f", tile.triangles, offset + 4)
                    points = []
                    uv = []
                    for start in (0, 8, 16):
                        px, py, pz = (
                            -values[start + 1] / 100,
                            -values[start] / 100,
                            values[start + 2] / 100,
                        )
                        points.append((x + (px - x) * 0.28, y + (py - y) * 0.28, pz))
                        uv.append((values[start + 6], values[start + 7]))
                    scene.triangle(
                        TERRACE, material, points[0], points[1], points[2], tuple(uv)
                    )
            hedges += 1
    return TerraceAudit(
        domain.area,
        lawn,
        rock,
        stone,
        segments,
        support.maximum_extrapolation,
        minimum_soil,
        minimum_bury,
        maximum_band,
        maximum_rock,
        balusters,
        hedges,
        minimum_top + source.relative_datum_m,
        maximum_top + source.relative_datum_m,
        encoding_missing, encoding_extra, encoding_area_bound,
        stone_facing.omitted_facing_faces, stone_facing.omitted_facing_area_m2,
        len(stone_facing.stones), stone_facing.faces, stone_facing.maximum_relief_m,
    )
