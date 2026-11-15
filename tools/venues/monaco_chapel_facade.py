"""Source-proportioned Sainte-Dévote front with separately qualified site support."""
from __future__ import annotations

import math
from itertools import pairwise

from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon

from venues.monaco_chapel_dataclasses import ChapelFrame

KIND = 'Building_SainteDevote'


def curve(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float],
          d: tuple[float, float]) -> list[tuple[float, float]]:
    result = []
    for j in range(17):
        t = j / 16
        x = (1 - t) ** 3 * a[0] + 3 * (1 - t) ** 2 * t * b[0] + 3 * (1 - t) * t * t * c[0] + t ** 3 * d[0]
        y = (1 - t) ** 3 * a[1] + 3 * (1 - t) ** 2 * t * b[1] + 3 * (1 - t) * t * t * c[1] + t ** 3 * d[1]
        result.append((x, y))
    return result


def front(scene: MeshScene, frame: ChapelFrame, shape: Polygon, depth: float, material: str) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coordinates.reverse()
        a, b, c = [frame.point(u, depth, z) for u, z in coordinates]
        scene.triangle(KIND, material, a, b, c)


def rectangle(scene: MeshScene, frame: ChapelFrame, left: float, right: float,
              bottom: float, top: float, depth: float, material: str) -> None:
    front(scene, frame, Polygon([(left, bottom), (right, bottom), (right, top), (left, top)]), depth, material)


def moulding(scene: MeshScene, frame: ChapelFrame, points: list[tuple[float, float]],
             depth: float, width: float, material: str = 'MonacoChapelStone') -> None:
    for a, b in pairwise(points):
        scene.beam(KIND, material, frame.point(a[0], depth, a[1]), frame.point(b[0], depth, b[1]), width, width)


def arch(scene: MeshScene, frame: ChapelFrame, center: float, width: float,
         bottom: float, top: float, material: str, *, grille: bool = False) -> None:
    radius = width / 2
    spring = top - radius
    arc = [(center + radius * math.cos(math.pi * i / 24), spring + radius * math.sin(math.pi * i / 24)) for i in range(25)]
    outline = [(center - radius, bottom), (center + radius, bottom), *arc]
    front(scene, frame, Polygon(outline), -.045, material)
    moulding(scene, frame, [(center - radius, bottom), (center - radius, spring),
                           *reversed(arc), (center + radius, bottom)], -.10, .10)
    outer = [(center + (radius + .14) * math.cos(math.pi * i / 24), spring + (radius + .14) * math.sin(math.pi * i / 24)) for i in range(25)]
    moulding(scene, frame, outer, -.11, .07)
    if grille:
        for index in range(1, 6):
            u = center - radius + width * index / 6
            high = spring + math.sqrt(max(0, radius * radius - (u - center) ** 2)) - .035
            moulding(scene, frame, [(u, bottom + .03), (u, high)], -.075, .025, 'MonacoChapelIron')
        for index in range(1, math.ceil((spring - bottom) / .28)):
            z = bottom + index * .28
            moulding(scene, frame, [(center - radius + .025, z), (center + radius - .025, z)], -.077, .022, 'MonacoChapelIron')


def rosette(scene: MeshScene, frame: ChapelFrame, u: float, z: float, radius: float) -> None:
    circle = [(u + radius * math.cos(math.tau * i / 32), z + radius * math.sin(math.tau * i / 32)) for i in range(33)]
    moulding(scene, frame, circle, -.115, .065)
    for i in range(8):
        angle = math.tau * i / 8
        center = (u + radius * .50 * math.cos(angle), z + radius * .50 * math.sin(angle))
        petal = [(center[0] + radius * .26 * math.cos(math.tau * j / 12), center[1] + radius * .26 * math.sin(math.tau * j / 12)) for j in range(13)]
        moulding(scene, frame, petal, -.12, .035)


def build(scene: MeshScene, frame: ChapelFrame) -> None:
    width = frame.width_m
    center = width / 2
    left, right = center - 3.7, center + 3.7
    # The photograph establishes these forms; crown heights are broad estimates.
    base = frame.base_absolute_m - frame.floor_absolute_m
    outline = [(0, base), (width, base), (width, 6.3),
               (right, 6.3), (right, 10.5), (right - .55, 10.5),
               (right - .55, 12.0), (center + 1.25, 12.0), (center, 13.0),
               (center - 1.25, 12.0), (left + .55, 12.0), (left + .55, 10.5),
               (left, 10.5), (left, 6.3), (0, 6.3)]
    front(scene, frame, Polygon(outline), 0, 'MonacoChapelOchre')
    for edge_a, edge_b in pairwise([*outline, outline[0]]):
        scene.quad(KIND, 'MonacoChapelOchre', frame.point(edge_a[0], .65, edge_a[1]),
                   frame.point(edge_b[0], .65, edge_b[1]), frame.point(edge_b[0], 0, edge_b[1]), frame.point(edge_a[0], 0, edge_a[1]))
    for a, b in ((0, left), (right, width), (left, right)):
        top = 6.15 if a == 0 or b == width else 6.45
        for z, size in ((top, .18), (top - .25, .09), (.18, .20)):
            moulding(scene, frame, [(a, z), (b, z)], -.11, size)
    for u in (.15, left - .12, left + .16, right - .16, right + .12, width - .15):
        high = 9.6 if left < u < right else 6.15
        rectangle(scene, frame, u - .11, u + .11, .25, high, -.09, 'MonacoChapelStone')
        for z in (.30, high - .22, high - .10):
            moulding(scene, frame, [(u - .22, z), (u + .22, z)], -.13, .12)
        for du in (-.055, .055):
            moulding(scene, frame, [(u + du, .50), (u + du, high - .35)], -.125, .022)
    arch(scene, frame, center, 2.20, .18, 4.65, 'MonacoChapelDoor')
    arch(scene, frame, center - 2.15, .92, 1.6, 4.35, 'MonacoChapelDarkGlass', grille=True)
    arch(scene, frame, center + 2.15, .92, 1.6, 4.35, 'MonacoChapelDarkGlass', grille=True)
    for u in (1.65, width - 1.65):
        arch(scene, frame, u, 1.28, .20, 3.85, 'MonacoChapelDoor')
        moulding(scene, frame, [(u - .47, .45), (u + .47, .45), (u + .47, 2.65), (u - .47, 2.65), (u - .47, .45)], -.075, .045, 'MonacoChapelWoodTrim')
        rosette(scene, frame, u, 5.10, .48)
    arch(scene, frame, center, 1.70, 6.6, 9.65, 'MonacoChapelDarkGlass', grille=True)
    for u in (center - 1.48, center, center + 1.48):
        arch(scene, frame, u, 1.23, 10.25, 11.85, 'MonacoChapelRecess')
        for edge in (u - .68, u + .68):
            moulding(scene, frame, [(edge, 10.15), (edge, 11.25)], -.14, .13)
    # A small original abstract saint silhouette occupies the photographed niche.
    scene.beam(KIND, 'MonacoChapelStone', frame.point(center, -.13, 10.35), frame.point(center, -.13, 11.20), .21, .28)
    scene.beam(KIND, 'MonacoChapelStone', frame.point(center - .31, -.14, 10.95), frame.point(center + .31, -.14, 10.95), .12)
    scene.beam(KIND, 'MonacoChapelStone', frame.point(center, -.13, 11.20), frame.point(center, -.13, 11.48), .22)
    moulding(scene, frame, [(left, 9.9), (left + .65, 9.9), (left + .65, 12.18),
                           (center - 1.15, 12.18), (center, 13.12), (center + 1.15, 12.18),
                           (right - .65, 12.18), (right - .65, 9.9), (right, 9.9)], -.12, .13)
    for side in (0, 1):
        a, b = (0, left) if side == 0 else (right, width)
        middle = (a + b) / 2
        profile = [(a, 6.4), (a + .3, 7.10),
                   *curve((a + .3, 7.10), (a + .4, 6.65), (middle - .85, 6.65), (middle - .55, 6.65))[1:],
                   *curve((middle - .55, 6.65), (middle - .25, 6.65), (middle - .1, 7.35), (middle, 7.35))[1:],
                   *curve((middle, 7.35), (middle + .1, 7.35), (middle + .25, 6.65), (middle + .55, 6.65))[1:],
                   *curve((middle + .55, 6.65), (middle + .85, 6.65), (b - .4, 6.65), (b - .3, 7.10))[1:],
                   (b, 6.4)]
        front(scene, frame, Polygon([(a, 6.15), (b, 6.15), *reversed(profile)]), 0, 'MonacoChapelOchre')
        moulding(scene, frame, profile, -.12, .12)
        rosette(scene, frame, middle, 6.65, .21)
        for direction in (-1, 1):
            scroll = [(middle + direction * (.74 + (.22 - .17 * i / 32) * math.cos(math.pi + i * math.pi / 16)),
                       6.75 + (.22 - .17 * i / 32) * math.sin(math.pi + i * math.pi / 16)) for i in range(33)]
            moulding(scene, frame, scroll, -.13, .045)
        for u in (a + .3, b - .3):
            scene.beam(KIND, 'MonacoChapelStone', frame.point(u, 0, 7.12), frame.point(u, 0, 7.57), .14)
    moulding(scene, frame, [(center, 13.14), (center, 14.2)], -.03, .11)
    moulding(scene, frame, [(center - .35, 13.85), (center + .35, 13.85)], -.03, .11)
    for u, z in ((left + .55, 12.05), (right - .55, 12.05)):
        scene.beam(KIND, 'MonacoChapelStone', frame.point(u, 0, z), frame.point(u, 0, z + .60), .14)
