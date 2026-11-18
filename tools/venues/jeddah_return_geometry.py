"""Open pointed arcades and curved masonry roofs for the Corniche Mosque."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, norm
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient

from venues.jeddah_return_context_dataclasses import MosqueOpening


def pointed(opening: MosqueOpening) -> Polygon:
    half = opening.width_m / 2
    rise = opening.crown_m - opening.spring_m
    curve = []
    for index in range(17):
        t = index / 16
        x = opening.center_m - half + opening.width_m * t
        z = opening.spring_m + rise * (1 - abs(2 * t - 1)) ** 0.72
        curve.append((x, z))
    return Polygon(
        [
            (opening.center_m - half, opening.bottom_m),
            (opening.center_m + half, opening.bottom_m),
            *reversed(curve),
        ]
    )


def profile_solid(
    scene: MeshScene,
    a: Point,
    b: Point,
    profile: Polygon,
    thickness: float,
    kind: str,
) -> None:
    length = math.dist(a[:2], b[:2])
    tx, ty = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = ty, -tx

    def point(u: float, z: float, depth: float) -> Point:
        return a[0] + tx * u - nx * depth, a[1] + ty * u - ny * depth, a[2] + z

    profile = orient(profile)
    for triangle in constrained_delaunay_triangles(profile).geoms:
        vertices = list(orient(triangle).exterior.coords)[:3]
        for depth, ring in ((0, vertices), (thickness, list(reversed(vertices)))):
            points = [point(u, z, depth) for u, z in ring]
            scene.triangle(
                kind,
                "Cream",
                points[0],
                points[1],
                points[2],
                tuple((u / 3, -z / 3) for u, z in ring),
            )
    for contour in (profile.exterior, *profile.interiors):
        for first, last in pairwise(contour.coords):
            scene.quad(
                kind,
                "Cream",
                point(first[0], first[1], 0),
                point(first[0], first[1], thickness),
                point(last[0], last[1], thickness),
                point(last[0], last[1], 0),
            )


def wall(
    scene: MeshScene,
    a: Point,
    b: Point,
    height: float,
    openings: tuple[MosqueOpening, ...],
    kind: str,
    thickness: float = 0.45,
) -> None:
    profile = box(0, 0, math.dist(a[:2], b[:2]), height)
    for opening in openings:
        cut = profile.difference(pointed(opening))
        if not isinstance(cut, Polygon):
            raise TypeError("Mosque arcade must remain connected above its openings")
        profile = cut
    profile_solid(scene, a, b, profile, thickness, kind)


def dome(
    scene: MeshScene,
    center: Point,
    radius: float,
    height: float,
    kind: str,
    segments: int = 48,
    rings: int = 12,
    smooth: bool = True,
) -> None:
    def vertex(theta: float, phi: float) -> Point:
        return (
            center[0] + radius * math.cos(phi) * math.cos(theta),
            center[1] + radius * math.cos(phi) * math.sin(theta),
            center[2] + height * math.sin(phi),
        )

    def normal(theta: float, phi: float) -> Point:
        return norm(
            (
                math.cos(phi) * math.cos(theta) / radius,
                math.cos(phi) * math.sin(theta) / radius,
                math.sin(phi) / height,
            )
        )

    for row in range(rings):
        low, high = row * math.pi / (2 * rings), (row + 1) * math.pi / (2 * rings)
        for column in range(segments):
            first, last = (
                column * math.tau / segments,
                (column + 1) * math.tau / segments,
            )
            a, b, c, d = (
                vertex(first, low),
                vertex(last, low),
                vertex(last, high),
                vertex(first, high),
            )
            na, nb, nc, nd = (
                normal(first, low),
                normal(last, low),
                normal(last, high),
                normal(first, high),
            )
            scene.triangle(
                kind, "Cream", a, b, c, normals=(na, nb, nc) if smooth else None
            )
            scene.triangle(
                kind, "Cream", a, c, d, normals=(na, nc, nd) if smooth else None
            )
            if row == 0:
                scene.triangle(kind, "Cream", center, b, a)


def finial(scene: MeshScene, point: Point) -> None:
    scene.beam(
        "Building_CornicheFinials",
        "Cream",
        point,
        (point[0], point[1], point[2] + 0.65),
        0.045,
    )
    for index in range(3):
        center = point[0], point[1], point[2] + 0.1 + index * 0.13
        dome(
            scene,
            center,
            0.075 - index * 0.012,
            0.09,
            "Building_CornicheFinials",
            12,
            4,
            False,
        )
    previous = None
    for index in range(19):
        angle = math.radians(30 + index * 300 / 18)
        current = (
            point[0] + 0.22 * math.sin(angle),
            point[1],
            point[2] + 0.82 + 0.22 * math.cos(angle),
        )
        if previous is not None:
            scene.beam("Building_CornicheCrescents", "Cream", previous, current, 0.025)
        previous = current


def barrel(scene: MeshScene, center: Point, length: float, width: float) -> None:
    outer: list[tuple[float, float]] = [(0, 0), (width, 0)]
    outer.extend(
        (
            width / 2 + width / 2 * math.cos(i * math.pi / 24),
            1.8 * math.sin(i * math.pi / 24),
        )
        for i in range(1, 24)
    )
    inner: list[tuple[float, float]] = [(0.25, -0.2), (width - 0.25, -0.2)]
    inner.extend(
        (
            width / 2 + (width / 2 - 0.25) * math.cos(i * math.pi / 24),
            1.5 * math.sin(i * math.pi / 24),
        )
        for i in range(25)
    )
    profile = Polygon(outer).difference(Polygon(inner))
    if not isinstance(profile, Polygon):
        raise TypeError("The porch barrel must retain one masonry roof shell")
    profile_solid(
        scene,
        (center[0] + length / 2, center[1] - width / 2, center[2]),
        (center[0] + length / 2, center[1] + width / 2, center[2]),
        profile,
        length,
        "Building_CornichePorchVault",
    )
