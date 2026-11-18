"""The north stand and pale arcade seen ahead at T22, within the old owner."""

from __future__ import annotations

import math
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient

from venues.jeddah_t22_frontage_dataclasses import ArcadeOpening, T22Frontage

SOURCE = Path(__file__).resolve().parents[2] / 'Attribution/Sources/jeddah/t22-stand-frontage.json'


def source_record() -> T22Frontage:
    source = TypeAdapter(T22Frontage).validate_json(SOURCE.read_bytes())
    if source.osm_id != 1257884698 or abs(math.hypot(*source.outward_xy) - 1) > 1e-8:
        raise ValueError('T22 frontage lost its literal owner or source frame')
    return source


def coordinate(x: float, y: float, source: T22Frontage) -> float:
    return ((x - source.origin_xy_m[0]) * source.outward_xy[0] +
            (y - source.origin_xy_m[1]) * source.outward_xy[1])


def front_mask(source: T22Frontage) -> Polygon:
    nx, ny = source.outward_xy
    tx, ty = ny, -nx
    return Polygon([(source.origin_xy_m[0] + tx * along + nx * across,
                     source.origin_xy_m[1] + ty * along + ny * across)
                    for along, across in ((-200, source.outer_coordinate_m - source.stand_depth_m),
                                          (200, source.outer_coordinate_m - source.stand_depth_m),
                                          (200, 200), (-200, 200))])


def faces_t22(a: tuple[float, float], b: tuple[float, float], source: T22Frontage) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    size = math.hypot(dx, dy)
    cut = source.outer_coordinate_m - source.stand_depth_m
    return (size > .3 and min(coordinate(*a, source), coordinate(*b, source)) >= cut - .00001
            and (dy * source.outward_xy[0] - dx * source.outward_xy[1]) / size > .96)


def spandrel(scene: MeshScene, vertices: tuple[Point, Point, Point, Point],
             inward: tuple[float, float], depth: float) -> None:
    backs = tuple((p[0] + inward[0] * depth, p[1] + inward[1] * depth, p[2]) for p in vertices)
    scene.quad('Building_T22ArcadeArch', 'JeddahEditionStone', *vertices)
    scene.quad('Building_T22ArcadeArch', 'JeddahEditionStone', backs[3], backs[2], backs[1], backs[0])
    for index in range(4):
        following = (index + 1) % 4
        scene.quad('Building_T22ArcadeArch', 'JeddahEditionStone',
                   vertices[index], backs[index], backs[following], vertices[following])


def build(scene: MeshScene, footprint: Polygon, base: float, canopy: float,
          source: T22Frontage) -> tuple[ArcadeOpening, ...]:
    footprint = orient(footprint)
    openings: list[ArcadeOpening] = []
    nx, ny = source.outward_xy
    west = (-ny, nx)
    front_v = source.outer_coordinate_m - 1.2

    def line_at(depth: float) -> LineString:
        return LineString([(source.origin_xy_m[0] + west[0] * along + nx * (front_v - depth),
                            source.origin_xy_m[1] + west[1] * along + ny * (front_v - depth))
                           for along in (-200, 200)])

    front = footprint.intersection(line_at(0))
    segments = [front] if isinstance(front, LineString) else list(front.geoms)
    for segment in segments:
        if not isinstance(segment, LineString) or segment.length < source.bay_pitch_m:
            continue
        edge_a, edge_b = segment.coords[0], segment.coords[-1]
        a, b = (float(edge_a[0]), float(edge_a[1])), (float(edge_b[0]), float(edge_b[1]))
        if not faces_t22(a, b, source):
            a, b = b, a
        length = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        nx, ny = ty, -tx
        heading = math.atan2(ty, tx)
        # All rows/trusses must fit the same part at the oblique road-gap ends.
        low, high = 0.0, length
        rear = 1 + (source.seating_rows - 1) * source.row_depth_m + source.row_depth_m / 2
        for depth in (.2, .2 + source.arcade_depth_m, rear, source.stand_depth_m - 1.8):
            inside = footprint.intersection(line_at(depth))
            pieces = [inside] if isinstance(inside, LineString) else list(inside.geoms)
            spans = [(min((x - a[0]) * tx + (y - a[1]) * ty for x, y in part.coords),
                      max((x - a[0]) * tx + (y - a[1]) * ty for x, y in part.coords))
                     for part in pieces if isinstance(part, LineString) and part.length > 1]
            if not spans:
                raise ValueError('The retained road gap leaves no T22 stand depth')
            start, end = max(spans, key=lambda interval: interval[1] - interval[0])
            low, high = max(low, start), min(high, end)
        margin, end_along = low + .40, high - .40
        usable = end_along - margin
        if usable < source.bay_pitch_m:
            continue
        count = max(1, round(usable / source.bay_pitch_m))
        pitch = usable / count

        def point(along: float, depth: float, height: float,
                  origin: tuple[float, float] = a, tangent: tuple[float, float] = (tx, ty),
                  inward: tuple[float, float] = (-nx, -ny)) -> Point:
            return (origin[0] + tangent[0] * along + inward[0] * depth,
                    origin[1] + tangent[1] * along + inward[1] * depth, base + height)

        for index in range(count + 1):
            along = margin + pitch * index
            pier_center = point(along, .20 + source.arcade_depth_m / 2, source.arcade_height_m / 2)
            scene.box('Building_T22ArcadePiers', 'JeddahEditionStone', pier_center,
                      source.pier_width_m, source.arcade_depth_m, source.arcade_height_m, heading)
            scene.beam('Building_T22CanopyColumns', 'White',
                       point(along, .38, source.arcade_height_m), point(along, .38, canopy - .18), .20)
            scene.beam('Building_T22CanopyTrusses', 'White',
                       point(along, .38, canopy - .28),
                       point(along, source.stand_depth_m - 1.8, canopy - 1.3), .13)
        for bay in range(count):
            center = margin + pitch * (bay + .5)
            openings.append(ArcadeOpening(point(center, .20, 1.0), (-nx, -ny)))
            radius = (pitch - source.pier_width_m) / 2
            crown = source.arch_spring_m + radius
            if crown >= source.arcade_height_m - .1:
                raise ValueError('Estimated T22 arch exceeds its retained ground deck')
            curve = [(center + radius * math.cos(math.pi - math.pi * step / 12),
                      source.arch_spring_m + radius * math.sin(math.pi - math.pi * step / 12))
                     for step in range(13)]
            for (u0, z0), (u1, z1) in pairwise(curve):
                spandrel(scene, (point(u0, .20, z0), point(u1, .20, z1),
                                  point(u1, .20, source.arcade_height_m),
                                  point(u0, .20, source.arcade_height_m)), (-nx, -ny), source.arcade_depth_m)
        # Real stepped rows replace the generic upper north glass, under its roof.
        for row in range(source.seating_rows):
            depth = 1.0 + row * source.row_depth_m
            z = source.arcade_height_m + .12 + row * source.row_rise_m
            rise = z - source.arcade_height_m
            scene.beam('Building_T22StandTreads', 'JeddahEditionStone',
                       point(margin, depth, z - rise / 2), point(end_along, depth, z - rise / 2),
                       source.row_depth_m, rise)
            scene.beam('Building_T22StandSeats', 'SeatBlue',
                       point(margin, depth, z + .18), point(end_along, depth, z + .18), .40, .14)
    return tuple(openings)
