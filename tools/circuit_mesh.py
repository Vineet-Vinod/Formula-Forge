"""Shared native mesh primitives; venue layout and scenery remain separately authored."""

from __future__ import annotations

import math
import struct

from circuit_dataclasses import MeshTile, Point


def add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def mul(a: Point, value: float) -> Point:
    return a[0] * value, a[1] * value, a[2] * value


def cross(a: Point, b: Point) -> Point:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Point) -> Point:
    length = math.sqrt(sum(value * value for value in a))
    return mul(a, 1 / max(length, 1e-9))


def world(p: Point) -> Point:
    return -p[1] * 100, -p[0] * 100, p[2] * 100


class MeshScene:
    def __init__(self) -> None:
        self.tiles: dict[str, MeshTile] = {}

    def tile(self, kind: str, point: Point) -> MeshTile:
        category = (
            "Tile_Street"
            if kind.startswith("Tile_")
            else (
                "Building_Crowd"
                if kind.startswith("Building_Crowd")
                else "Building_City"
            )
        )
        step = 240 if category == "Tile_Street" else 360
        name = f"{category}_{math.floor(point[0] / step):02d}_{math.floor(point[1] / step):02d}".replace(
            "-", "m"
        )
        return self.tiles.setdefault(name, MeshTile())

    def triangle(
        self,
        kind: str,
        material: str,
        a: Point,
        b: Point,
        c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        normal = cross(sub(b, a), sub(c, a))
        if sum(value * value for value in normal) < 1e-12:
            return
        if kind.startswith("Tile_") and normal[2] < -0.35:
            b, c = c, b
            uv = (uv[0], uv[2], uv[1])
            normal = mul(normal, -1)
            if normals is not None:
                normals = (normals[0], normals[2], normals[1])
        normal = norm(normal)
        if material == "Concrete":
            if abs(normal[2]) > 0.7:
                uv = tuple((p[0] / 4, p[1] / 4) for p in (a, b, c))
            elif abs(normal[0]) > abs(normal[1]):
                uv = tuple((p[1] / 4, -p[2] / 4) for p in (a, b, c))
            else:
                uv = tuple((p[0] / 4, -p[2] / 4) for p in (a, b, c))
        tile = self.tile(kind, mul(add(add(a, b), c), 1 / 3))
        if material not in tile.materials:
            tile.materials.append(material)
        tile.triangles.extend(struct.pack("<I", tile.materials.index(material)))
        for point, texcoord, vertex_normal in zip(
            (a, b, c), uv, normals or (normal, normal, normal)
        ):
            n = -vertex_normal[1], -vertex_normal[0], vertex_normal[2]
            p = world(point)
            tile.triangles.extend(struct.pack("<8f", *p, *n, *texcoord))
            for axis in range(3):
                tile.minimum[axis] = min(tile.minimum[axis], p[axis])
                tile.maximum[axis] = max(tile.maximum[axis], p[axis])

    def quad(
        self,
        kind: str,
        material: str,
        a: Point,
        b: Point,
        c: Point,
        d: Point,
        u: float = 1,
        v: float = 1,
        up: bool | None = None,
    ) -> None:
        if up is not None and (cross(sub(b, a), sub(c, a))[2] > 0) != up:
            b, d = d, b
        self.triangle(kind, material, a, b, c, ((0, 0), (u, 0), (u, v)))
        self.triangle(kind, material, a, c, d, ((0, 0), (u, v), (0, v)))

    def beam(
        self,
        kind: str,
        material: str,
        a: Point,
        b: Point,
        width: float,
        depth: float | None = None,
    ) -> None:
        tangent = norm(sub(b, a))
        side = mul(
            norm(cross(tangent, (0, 0, 1) if abs(tangent[2]) < 0.95 else (0, 1, 0))),
            width / 2,
        )
        up = mul(
            norm(cross(side, tangent)), (depth if depth is not None else width) / 2
        )
        corners = [
            add(a, add(side, up)),
            add(a, sub(up, side)),
            sub(a, add(side, up)),
            add(a, sub(side, up)),
            add(b, add(side, up)),
            add(b, sub(up, side)),
            sub(b, add(side, up)),
            add(b, sub(side, up)),
        ]
        for indices in [
            (0, 1, 2, 3),
            (7, 6, 5, 4),
            (0, 4, 5, 1),
            (1, 5, 6, 2),
            (2, 6, 7, 3),
            (3, 7, 4, 0),
        ]:
            self.quad(
                kind,
                material,
                corners[indices[0]],
                corners[indices[1]],
                corners[indices[2]],
                corners[indices[3]],
            )

    def box(
        self,
        kind: str,
        material: str,
        center: Point,
        length: float,
        width: float,
        height: float,
        heading: float = 0,
    ) -> None:
        direction = math.cos(heading), math.sin(heading), 0.0
        self.beam(
            kind,
            material,
            sub(center, mul(direction, length / 2)),
            add(center, mul(direction, length / 2)),
            width,
            height,
        )

    def banner(
        self,
        a: Point,
        b: Point,
        height: float,
        material: str,
        kind: str = "Tile_Detail",
        u0: float = 0,
        repeat: float = 1,
    ) -> None:
        u = math.dist(a, b) / 0.15 if material == "Fence" else repeat
        v = height / 0.15 if material == "Fence" else 1
        if "Facade" in material:
            u, v = math.dist(a, b) / 16, height / 14.4
        top_a, top_b = add(a, (0, 0, height)), add(b, (0, 0, height))
        self.triangle(
            kind, material, top_a, top_b, b, ((u0, 0), (u0 + u, 0), (u0 + u, v))
        )
        self.triangle(kind, material, top_a, b, a, ((u0, 0), (u0 + u, v), (u0, v)))
        if material == "Fence":
            return
        self.triangle(kind, material, top_b, top_a, a, ((u0 + u, 0), (u0, 0), (u0, v)))
        self.triangle(kind, material, top_b, a, b, ((u0 + u, 0), (u0, v), (u0 + u, v)))

    def spectators(self, a: Point, b: Point, row: int, kind: str) -> None:
        span = sub(b, a)
        count = max(1, round(math.dist(a, b) / 0.62))
        direction = norm(span)
        for person in range(count):
            center = add(a, mul(span, (person + 0.5) / count))
            left = sub(center, mul(direction, 0.40))
            right = add(center, mul(direction, 0.40))
            top_left, top_right = add(left, (0, 0, 1.35)), add(right, (0, 0, 1.35))
            column = (person + row) % 3
            u0, u1 = column / 3, (column + 1) / 3
            self.triangle(
                kind,
                "Crowd",
                top_left,
                top_right,
                right,
                ((u0, 0.5), (u1, 0.5), (u1, 1)),
            )
            self.triangle(
                kind, "Crowd", top_left, right, left, ((u0, 0.5), (u1, 1), (u0, 1))
            )
            self.triangle(
                kind,
                "Crowd",
                top_right,
                top_left,
                left,
                ((u1, 0.5), (u0, 0.5), (u0, 1)),
            )
            self.triangle(
                kind, "Crowd", top_right, left, right, ((u1, 0.5), (u0, 1), (u1, 1))
            )

    def broadleaf(self, base: Point, height: float, seed: int) -> None:
        fork = add(base, (0, 0, height * 0.52))
        self.beam("Building_Trees", "Trunk", base, fork, 0.25)
        for cluster in range(5):
            azimuth = cluster * math.tau / 5 + seed * 0.13
            center = add(
                base,
                (
                    math.cos(azimuth) * height * 0.16,
                    math.sin(azimuth) * height * 0.16,
                    height * (0.68 + 0.04 * (cluster % 3)),
                ),
            )
            self.beam("Building_Trees", "Trunk", fork, center, 0.10)
            column, row = (2, 5)[(seed + cluster) % 2], (seed + cluster) % 3
            u0, u1 = (column + 0.012) / 6, (column + 0.988) / 6
            v0, v1 = (row + 0.012) / 6, (row + 0.988) / 6
            for plane in range(3):
                angle = plane * math.pi / 3 + azimuth
                axis = (math.cos(angle), math.sin(angle), 0.0)
                bottom = add(center, (0, 0, -height * 0.23))
                a, b = (
                    sub(bottom, mul(axis, height * 0.25)),
                    add(bottom, mul(axis, height * 0.25)),
                )
                ta, tb = add(a, (0, 0, height * 0.5)), add(b, (0, 0, height * 0.5))
                self.triangle(
                    "Building_Trees",
                    "TreeCanopy",
                    ta,
                    tb,
                    b,
                    ((u0, v0), (u1, v0), (u1, v1)),
                )
                self.triangle(
                    "Building_Trees",
                    "TreeCanopy",
                    ta,
                    b,
                    a,
                    ((u0, v0), (u1, v1), (u0, v1)),
                )

    def palm(self, base: Point, height: float) -> None:
        top = add(base, (0.4, 0.2, height))
        for row in range(8):
            z0, z1 = height * row / 8, height * (row + 1) / 8
            r0, r1 = 0.23 - row * 0.008, 0.23 - (row + 1) * 0.008
            for column in range(8):
                a0, a1 = column * math.tau / 8, (column + 1) * math.tau / 8

                def trunk(z: float, radius: float, angle: float) -> Point:
                    return (
                        base[0] + 0.4 * z / height + radius * math.cos(angle),
                        base[1] + 0.2 * z / height + radius * math.sin(angle),
                        base[2] + z,
                    )

                self.quad(
                    "Building_Palms",
                    "Trunk",
                    trunk(z0, r0, a0),
                    trunk(z0, r0, a1),
                    trunk(z1, r1, a1),
                    trunk(z1, r1, a0),
                )
        for frond in range(25):
            angle = frond * math.tau / 25 + base[0] % 1
            direction = math.cos(angle), math.sin(angle), 0.0
            side = -math.sin(angle), math.cos(angle), 0.0
            length = 3.8 + (frond % 4) * 0.35
            previous = top
            previous_width = 0.02
            for segment in range(1, 13):
                t = segment / 12
                point = add(
                    top,
                    add(
                        mul(direction, length * t),
                        (0, 0, 2 * math.sin(t * math.pi) - t * 1.7),
                    ),
                )
                self.beam("Building_Palms", "Leaves", previous, point, 0.035)
                width = 0.8 * math.sin(t * math.pi) + 0.04
                self.quad(
                    "Building_Palms",
                    "Leaves",
                    sub(previous, mul(side, previous_width)),
                    sub(point, mul(side, width * 0.45)),
                    add(point, mul(side, width * 0.45)),
                    add(previous, mul(side, previous_width)),
                )
                previous_width = width * 0.45
                for sign in (-1, 1):
                    last = point
                    leaf_side = norm(
                        cross(add(mul(side, sign), mul(direction, 0.25)), (0, 0, 1))
                    )
                    for blade_step in range(1, 3):
                        fraction = blade_step / 2
                        blade = add(
                            point,
                            add(
                                mul(side, sign * width * fraction),
                                mul(direction, 0.3 * fraction),
                            ),
                        )
                        blade = add(blade, (0, 0, -0.28 * fraction * fraction))
                        half_width = 0.10 * (1 - fraction) + 0.016
                        self.quad(
                            "Building_Palms",
                            "Leaves",
                            sub(last, mul(leaf_side, half_width)),
                            sub(blade, mul(leaf_side, half_width)),
                            add(blade, mul(leaf_side, half_width)),
                            add(last, mul(leaf_side, half_width)),
                        )
                        last = blade
                previous = point
