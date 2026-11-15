"""Bounded Sainte-Dévote silhouette; aerial flashing is not a ridge control."""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import partial
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.polygon import orient

from venues.monaco_chapel_dataclasses import ChapelFrame, NaveSource, WallFrame

KIND = "Building_SainteDevoteRoof"
STONE = "MonacoChapelStone"
PLASTER = "MonacoChapelOchre"


def absolute_point(frame: ChapelFrame, u: float, depth: float, z: float) -> Point:
    return frame.point(u, depth, z - frame.floor_absolute_m)


def roof_point(
    frame: ChapelFrame,
    u: float,
    depth: float,
    *,
    height: Callable[[float, float], float],
    lowering: float,
) -> Point:
    return absolute_point(frame, u, depth, height(u, depth) - lowering)


def polygons(shape: Polygon | MultiPolygon) -> list[Polygon]:
    return [shape] if isinstance(shape, Polygon) else list(shape.geoms)


def solid(
    scene: MeshScene,
    shape: Polygon,
    outer: Callable[[float, float], Point],
    inner: Callable[[float, float], Point],
    material: str,
) -> None:
    shape = orient(shape, sign=1)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coords = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coords.reverse()
        a, b, c = [outer(float(x), float(y)) for x, y in coords]
        scene.triangle(KIND, material, a, b, c)
        a, b, c = [inner(float(x), float(y)) for x, y in coords]
        scene.triangle(KIND, material, c, b, a)
    for ring in (shape.exterior, *shape.interiors):
        for a, b in pairwise(ring.coords):
            scene.quad(KIND, material, outer(*a), inner(*a), inner(*b), outer(*b))


def arch(center: float, width: float, bottom: float, top: float) -> Polygon:
    radius = width / 2
    spring = top - radius
    return Polygon(
        [
            (center - radius, bottom),
            (center + radius, bottom),
            *[
                (
                    center + radius * math.cos(math.pi * i / 24),
                    spring + radius * math.sin(math.pi * i / 24),
                )
                for i in range(25)
            ],
        ]
    )


def nave(scene: MeshScene, frame: ChapelFrame, source: NaveSource) -> None:
    occupied = Polygon(source.owner_uv_m)
    lo, _, hi, rear = occupied.bounds
    ridge = source.estimated_ridge_u_m
    domain = occupied.intersection(box(lo - 1, source.front_depth_m, hi + 1, rear + 1))
    tower = source.tower
    shaft = box(
        tower.center_u_m - tower.width_m / 2,
        tower.center_depth_m - tower.depth_m / 2,
        tower.center_u_m + tower.width_m / 2,
        tower.center_depth_m + tower.depth_m / 2,
    )
    domain = domain.difference(shaft)
    if not isinstance(domain, (Polygon, MultiPolygon)):
        raise TypeError("Nave roof must occupy only the literal church")
    zones = [
        Polygon([(lo, 0), (ridge, 0), (ridge, source.hip_start_depth_m), (lo, rear)]),
        Polygon([(ridge, 0), (hi, 0), (hi, rear), (ridge, source.hip_start_depth_m)]),
        Polygon([(lo, rear), (ridge, source.hip_start_depth_m), (hi, rear)]),
    ]
    rise = source.ridge_absolute_m - source.eaves_absolute_m
    height_functions: list[Callable[[float, float], float]] = [
        lambda u, _d: source.eaves_absolute_m + rise * (u - lo) / (ridge - lo),
        lambda u, _d: source.eaves_absolute_m + rise * (hi - u) / (hi - ridge),
        lambda _u, d: (
            source.eaves_absolute_m
            + rise * (rear - d) / (rear - source.hip_start_depth_m)
        ),
    ]
    for zone, height in zip(zones, height_functions, strict=True):
        section = domain.intersection(zone)
        if not isinstance(section, (Polygon, MultiPolygon)):
            continue
        for piece in polygons(section):
            if piece.area < 1e-8:
                continue
            solid(
                scene,
                piece,
                partial(roof_point, frame, height=height, lowering=0),
                partial(
                    roof_point, frame, height=height, lowering=source.roof_thickness_m
                ),
                "Terracotta",
            )
    # Unphotographed side details stay plain; no apartment windows or invented floors.
    body = occupied.intersection(box(lo - 1, source.front_depth_m, hi + 1, rear + 1))
    if not isinstance(body, (Polygon, MultiPolygon)):
        raise TypeError("Nave body leaves literal owner")
    for piece in polygons(body):
        solid(
            scene,
            piece,
            lambda u, d: absolute_point(
                frame, u, d, source.eaves_absolute_m - source.roof_thickness_m
            ),
            lambda u, d: absolute_point(frame, u, d, source.foundation_absolute_m),
            PLASTER,
        )
    # Discrete rounded ridge caps supply the photographed tiled silhouette.
    for index in range(
        math.floor((source.hip_start_depth_m - source.front_depth_m) / 0.36)
    ):
        d0 = source.front_depth_m + index * 0.36
        d1 = min(d0 + 0.34, source.hip_start_depth_m)
        cap = Polygon(
            [
                (-0.12, source.ridge_absolute_m),
                (0.12, source.ridge_absolute_m),
                *[
                    (
                        0.12 * math.cos(step * math.pi / 8),
                        source.ridge_absolute_m + 0.12 * math.sin(step * math.pi / 8),
                    )
                    for step in range(9)
                ],
            ]
        )
        cap_frame = WallFrame(frame, (ridge, d0), (1, 0), (0, 1))
        solid(
            scene,
            cap,
            partial(cap_frame.point, inset=0),
            partial(cap_frame.point, inset=d1 - d0),
            "Terracotta",
        )


def lathe(
    scene: MeshScene,
    frame: ChapelFrame,
    center: tuple[float, float],
    profile: tuple[tuple[float, float], ...],
    material: str,
    segments: int = 32,
) -> None:
    for (z0, r0), (z1, r1) in pairwise(profile):
        for index in range(segments):
            a, b = index * math.tau / segments, (index + 1) * math.tau / segments
            point = lambda angle, z, r: absolute_point(
                frame,
                center[0] + r * math.cos(angle),
                center[1] + r * math.sin(angle),
                z,
            )
            scene.quad(
                KIND,
                material,
                point(a, z0, r0),
                point(b, z0, r0),
                point(b, z1, r1),
                point(a, z1, r1),
            )
    for (z, radius), reverse in ((profile[0], True), (profile[-1], False)):
        if radius <= 1e-8:
            continue
        c = absolute_point(frame, *center, z)
        for index in range(segments):
            a, b = index * math.tau / segments, (index + 1) * math.tau / segments
            pa = absolute_point(
                frame,
                center[0] + radius * math.cos(a),
                center[1] + radius * math.sin(a),
                z,
            )
            pb = absolute_point(
                frame,
                center[0] + radius * math.cos(b),
                center[1] + radius * math.sin(b),
                z,
            )
            scene.triangle(
                KIND, material, c, pb if reverse else pa, pa if reverse else pb
            )


def tower(scene: MeshScene, frame: ChapelFrame, source: NaveSource) -> None:
    s = source.tower
    u0, u1 = s.center_u_m - s.width_m / 2, s.center_u_m + s.width_m / 2
    d0, d1 = s.center_depth_m - s.depth_m / 2, s.center_depth_m + s.depth_m / 2
    footprint = box(u0, d0, u1, d1)
    solid(
        scene,
        footprint,
        lambda u, d: absolute_point(frame, u, d, s.bell_stage_bottom_absolute_m),
        lambda u, d: absolute_point(frame, u, d, source.foundation_absolute_m),
        PLASTER,
    )
    walls = [
        ((u0, d0), (1.0, 0.0), (0.0, 1.0), s.width_m),
        ((u1, d0), (0.0, 1.0), (-1.0, 0.0), s.depth_m),
        ((u1, d1), (-1.0, 0.0), (0.0, -1.0), s.width_m),
        ((u0, d1), (0.0, -1.0), (1.0, 0.0), s.depth_m),
    ]
    for origin, axis, inward, span in walls:
        wall = WallFrame(frame, origin, axis, inward)
        point = wall.point
        opening = arch(
            span / 2,
            s.opening_width_m,
            s.opening_bottom_absolute_m,
            s.opening_top_absolute_m,
        )
        face = box(
            0, s.bell_stage_bottom_absolute_m, span, s.bell_stage_top_absolute_m
        ).difference(opening)
        if not isinstance(face, Polygon):
            raise TypeError("Bell-stage opening must remain in its shaft wall")
        solid(
            scene,
            face,
            partial(wall.point, inset=0),
            partial(wall.point, inset=0.22),
            PLASTER,
        )
        outer = arch(
            span / 2,
            s.opening_width_m + 0.22,
            s.opening_bottom_absolute_m - 0.08,
            s.opening_top_absolute_m + 0.11,
        )
        surround = outer.difference(opening)
        if not isinstance(surround, Polygon):
            raise TypeError("Bell arch surround lost its opening")
        solid(
            scene,
            surround,
            partial(wall.point, inset=-0.055),
            partial(wall.point, inset=0.01),
            STONE,
        )
        for x in (0.07, span - 0.07):
            scene.beam(
                KIND,
                STONE,
                point(x, s.bell_stage_bottom_absolute_m, -0.035),
                point(x, s.bell_stage_top_absolute_m, -0.035),
                0.105,
                0.07,
            )
    for absolute, width, thickness in (
        (17.15, 2.45, 0.08),
        (17.4, 2.60, 0.17),
        (21.91, 2.8, 0.19),
        (22.08, 2.65, 0.10),
    ):
        scene.box(
            KIND,
            STONE,
            absolute_point(frame, s.center_u_m, s.center_depth_m, absolute),
            width,
            width,
            thickness,
            math.atan2(frame.axis[1], frame.axis[0]),
        )
    drum_radius, bottom, top = 1.12, 22.13, 22.82
    for index in range(8):
        a, b = (
            math.pi / 8 + index * math.tau / 8,
            math.pi / 8 + (index + 1) * math.tau / 8,
        )
        start = (
            s.center_u_m + drum_radius * math.cos(a),
            s.center_depth_m + drum_radius * math.sin(a),
        )
        end = (
            s.center_u_m + drum_radius * math.cos(b),
            s.center_depth_m + drum_radius * math.sin(b),
        )
        span = math.dist(start, end)
        axis = ((end[0] - start[0]) / span, (end[1] - start[1]) / span)
        inward = (-axis[1], axis[0])
        wall = WallFrame(frame, start, axis, inward)
        face = box(0, bottom, span, top)
        if index % 2 == 1:
            oval = Polygon(
                [
                    (
                        span / 2 + 0.235 * math.cos(t * math.tau / 32),
                        22.48 + 0.115 * math.sin(t * math.tau / 32),
                    )
                    for t in range(32)
                ]
            )
            face = face.difference(oval)
        if not isinstance(face, Polygon):
            raise TypeError("Crown vent leaves its drum wall")
        solid(
            scene,
            face,
            partial(wall.point, inset=0),
            partial(wall.point, inset=0.14),
            STONE,
        )
    center = (s.center_u_m, s.center_depth_m)
    profile = tuple(
        (
            top + 0.89 * math.sin(math.pi * i / 20),
            drum_radius * math.cos(math.pi * i / 20),
        )
        for i in range(11)
    )
    lathe(scene, frame, center, profile, STONE)
    lathe(scene, frame, center, ((23.69, 0.13), (23.78, 0.13), (23.81, 0.07)), STONE)
    sphere = tuple(
        (23.89 - 0.11 * math.cos(math.pi * i / 10), 0.11 * math.sin(math.pi * i / 10))
        for i in range(11)
    )
    lathe(scene, frame, center, sphere, STONE, 20)
    # Three dark bells are visible in the retained front primary photograph.
    for z, radius in ((18.5, 0.30), (19.45, 0.26), (20.38, 0.22)):
        lathe(
            scene,
            frame,
            center,
            (
                (z, radius),
                (z + 0.08, radius),
                (z + 0.35, radius * 0.6),
                (z + 0.46, radius * 0.4),
                (z + 0.51, 0.05),
            ),
            "Black",
            20,
        )
        scene.beam(
            KIND,
            "Steel",
            absolute_point(frame, u0 + 0.2, s.center_depth_m, z + 0.55),
            absolute_point(frame, u1 - 0.2, s.center_depth_m, z + 0.55),
            0.06,
        )


def emit(scene: MeshScene, frame: ChapelFrame, source: NaveSource) -> None:
    nave(scene, frame, source)
    tower(scene, frame, source)
