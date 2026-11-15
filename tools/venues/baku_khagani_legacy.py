"""Retain the two old bodies outside their qualified street-front replacements."""

from __future__ import annotations

import hashlib
import math
import struct

import numpy as np
from circuit_dataclasses import MeshTile, Point
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from numpy.typing import NDArray
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.baku_civic import _point
from venues.baku_hotel_geometry import frame
from venues.baku_khagani_dataclasses import KhaganiSource, LegacyFamily, LegacyRow
from venues.east_architecture import facade


class LegacyScene(CircuitScene):
    def __init__(self, source: CircuitScene) -> None:
        super().__init__("baku")
        self.road_mask = source.road_mask
        self.surface_ranges = list(source.surface_ranges)
        self.ground_patches = list(source.ground_patches)
        self.records: list[LegacyRow] = []
        self.edges: list[LineString] = []
        self.active_edge = -1

    def beam(
        self,
        kind: str,
        material: str,
        a: Point,
        b: Point,
        width: float,
        depth: float | None = None,
    ) -> None:
        previous = self.active_edge
        centre = ShapePoint((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        self.active_edge = min(
            range(len(self.edges)), key=lambda i: self.edges[i].distance(centre)
        )
        super().beam(kind, material, a, b, width, depth)
        self.active_edge = previous

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
        previous = self.active_edge
        centre = ShapePoint((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        self.active_edge = min(
            range(len(self.edges)), key=lambda i: self.edges[i].distance(centre)
        )
        super().banner(a, b, height, material, kind, u0, repeat)
        self.active_edge = previous

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
        centre = (
            (a[0] + b[0] + c[0]) / 3,
            (a[1] + b[1] + c[1]) / 3,
            (a[2] + b[2] + c[2]) / 3,
        )
        tile = self.tile(kind, centre)
        before = len(tile.triangles)
        super().triangle(kind, material, a, b, c, uv, normals)
        if len(tile.triangles) > before:
            name = next(name for name, item in self.tiles.items() if item is tile)
            self.records.append(
                LegacyRow(
                    name,
                    kind,
                    material,
                    bytes(tile.triangles[before + 4 : before + 100]),
                    self.active_edge,
                )
            )


def emission_hash(rows: list[LegacyRow]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row.kind.encode() + b"\0" + row.material.encode() + b"\0")
        digest.update(row.payload)
        digest.update(struct.pack("<i", row.edge))
    return digest.hexdigest()


def packed_xy(point: tuple[float, ...]) -> tuple[float, float]:
    y, x = struct.unpack("<2f", struct.pack("<2f", -point[1] * 100, -point[0] * 100))
    return -x / 100, -y / 100


def native_values(payload: bytes) -> NDArray[np.float64]:
    return np.asarray(struct.unpack("<24f", payload)).reshape(3, 8)


def source_points(native: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.stack(
        (-native[:, 1] / 100, -native[:, 0] / 100, native[:, 2] / 100), axis=1
    )


def roof_union(rows: list[LegacyRow]) -> BaseGeometry:
    pieces = []
    for row in rows:
        if row.kind == "Building_Roof":
            shape = Polygon(source_points(native_values(row.payload))[:, :2])
            if shape.area > 1e-12:
                pieces.append(shape)
    return unary_union(pieces)


def roof_domain(
    source: KhaganiSource,
    family: LegacyFamily,
    rows: list[LegacyRow],
) -> BaseGeometry:
    if family.osm_id == 177428532:
        face = source.library.front.face
        start = packed_xy(face.start)
        end = packed_xy(_point(face, face.length_m, 0))
        edge = frame((*start, face.start[2]), (*end, face.start[2]))
        length, depth = edge.length_m, source.library.gallery_depth_m
    else:
        a, b = family.ring[18:20]
        edge = frame((*packed_xy(b), family.datum_m), (*packed_xy(a), family.datum_m))
        writer_start = min(
            front.wall.original_along_m[0]
            for front in source.historic_fronts
            if front.address in (23, 25)
        )
        length = (math.dist(a, b) - writer_start) / math.dist(a, b) * edge.length_m
        depth = 3.0
    strip = Polygon(
        [
            _point(edge, along, 0, inset)[:2]
            for along, inset in ((0, 0), (length, 0), (length, -depth), (0, -depth))
        ]
    )
    return strip.intersection(roof_union(rows))


def clip_roof(row: LegacyRow, domain: BaseGeometry) -> list[LegacyRow]:
    native = native_values(row.payload)
    xyz = source_points(native)
    shape = Polygon(xyz[:, :2])
    if not shape.intersects(domain) or shape.intersection(domain).area < 1e-10:
        return [row]
    outside = shape.difference(domain)
    if outside.is_empty:
        return []
    inverse = np.linalg.inv(np.column_stack((xyz[:, 0], xyz[:, 1], np.ones(3))).T)
    sign = np.cross(xyz[1] - xyz[0], xyz[2] - xyz[0])[2]
    result = []
    for part in outside.geoms if hasattr(outside, "geoms") else (outside,):
        if not isinstance(part, Polygon):
            continue
        for triangle in constrained_delaunay_triangles(part).geoms:
            coordinates = list(triangle.exterior.coords)[:3]
            if (triangle.exterior.is_ccw and sign < 0) or (
                not triangle.exterior.is_ccw and sign > 0
            ):
                coordinates.reverse()
            emitted = []
            for x, y in coordinates:
                distances = np.linalg.norm(xyz[:, :2] - (x, y), axis=1)
                if distances.min() < 1e-8:
                    values = native[int(distances.argmin())].copy()
                else:
                    weights = inverse @ np.asarray((x, y, 1))
                    values = weights @ native
                emitted.append(struct.pack("<8f", *values))
            payload = b"".join(emitted)
            if Polygon(source_points(native_values(payload))[:, :2]).area <= 1e-12:
                continue
            result.append(LegacyRow(row.tile, row.kind, row.material, payload, -1))
    return result


def retained_rows(
    scene: CircuitScene,
    source: KhaganiSource,
    families: tuple[LegacyFamily, ...],
) -> list[LegacyRow]:
    legacy = LegacyScene(scene)
    retained = []
    for family in families:
        legacy.tiles.clear()
        legacy.records.clear()
        legacy.edges = [
            LineString([a, b])
            for a, b in zip(family.ring, (*family.ring[1:], family.ring[0]))
        ]
        facade(legacy, family.osm_id, family.height_m, "classical", "Cream")
        if emission_hash(legacy.records) != family.emission_sha256:
            raise ValueError(
                "Baku Khagani legacy body changed; requalify retained faces"
            )
        domain = roof_domain(source, family, legacy.records)
        for row in legacy.records:
            if row.edge in family.replaced_edges:
                continue
            retained.extend(
                clip_roof(row, domain) if row.kind == "Building_Roof" else [row]
            )
    return retained


def append_rows(scene: MeshScene, rows: list[LegacyRow]) -> None:
    for row in rows:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        tile.triangles.extend(
            struct.pack("<I", tile.materials.index(row.material)) + row.payload
        )
        for i in (0, 32, 64):
            point = struct.unpack_from("<3f", row.payload, i)
            for axis, value in enumerate(point):
                tile.minimum[axis] = min(tile.minimum[axis], value)
                tile.maximum[axis] = max(tile.maximum[axis], value)
