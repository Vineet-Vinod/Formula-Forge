"""Read actual emitted faces and retain complete untouched row attributes."""

from __future__ import annotations

import struct
from collections import Counter
from collections.abc import Callable
from typing import cast

from circuit_dataclasses import MeshTile, Point
from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from venues.buddh_first_sector_dataclasses import NativeVertex, SurfaceFace

FLOOR_MATERIALS = {"Road", "Grass", "Gravel", "Runoff", "RunoffGreen"}


def face(tile: MeshTile, name: str, offset: int) -> SurfaceFace:
    values = cast(
        tuple[float, ...], struct.unpack_from("<24f", tile.triangles, offset + 4)
    )
    vertices = cast(
        tuple[NativeVertex, NativeVertex, NativeVertex],
        tuple(tuple(values[i : i + 8]) for i in (0, 8, 16)),
    )
    points = cast(
        tuple[Point, Point, Point],
        tuple((-v[1] / 100, -v[0] / 100, v[2] / 100) for v in vertices),
    )
    material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
    return SurfaceFace(
        vertices,
        points,
        Polygon([p[:2] for p in points]),
        material,
        name,
        offset,
        bytes(tile.triangles[offset : offset + 100]),
    )


def capture(
    scene: MeshScene, domain: BaseGeometry, materials: set[str]
) -> tuple[SurfaceFace, ...]:
    output = []
    for name, tile in scene.tiles.items():
        if not name.startswith("Tile_Street"):
            continue
        bounds = Polygon(
            [
                (-tile.maximum[1] / 100, -tile.maximum[0] / 100),
                (-tile.minimum[1] / 100, -tile.maximum[0] / 100),
                (-tile.minimum[1] / 100, -tile.minimum[0] / 100),
                (-tile.maximum[1] / 100, -tile.minimum[0] / 100),
            ]
        )
        if not bounds.intersects(domain):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            if material not in materials:
                continue
            source = face(tile, name, offset)
            if (
                source.plan.area > 1e-10
                and min(v[5] for v in source.vertices) > 0.05
                and source.plan.intersection(domain).area > 1e-10
            ):
                output.append(source)
    return tuple(output)


def weights(source: SurfaceFace, x: float, y: float) -> tuple[float, float, float]:
    a, b, c = source.points
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    return first, second, 1 - first - second


def interpolate(source: SurfaceFace, x: float, y: float) -> NativeVertex:
    a, b, c = weights(source, x, y)
    return cast(
        NativeVertex,
        tuple(
            a * source.vertices[0][i]
            + b * source.vertices[1][i]
            + c * source.vertices[2][i]
            for i in range(8)
        ),
    )


def height(source: SurfaceFace, x: float, y: float) -> float:
    return sum(
        weight * point[2]
        for weight, point in zip(weights(source, x, y), source.points, strict=True)
    )


def fragments(
    source: SurfaceFace, shape: BaseGeometry
) -> tuple[tuple[NativeVertex, ...], ...]:
    if shape.is_empty or shape.area < 1e-10:
        return ()
    output = []
    for triangle in constrained_delaunay_triangles(shape).geoms:
        xy = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            xy.reverse()
        output.append(tuple(interpolate(source, x, y) for x, y in xy))
    return tuple(output)


def append(
    data: bytearray, tile: MeshTile, material: str, vertices: tuple[NativeVertex, ...]
) -> None:
    if material not in tile.materials:
        tile.materials.append(material)
    data.extend(struct.pack("<I", tile.materials.index(material)))
    for vertex in vertices:
        data.extend(struct.pack("<8f", *vertex))
        for axis in range(3):
            tile.minimum[axis] = min(tile.minimum[axis], vertex[axis])
            tile.maximum[axis] = max(tile.maximum[axis], vertex[axis])


def lookup(faces: tuple[SurfaceFace, ...]) -> Callable[[float, float], float]:
    from shapely.geometry import Point as GeoPoint

    tree = STRtree([source.plan for source in faces])

    def sample(x: float, y: float) -> float:
        point = GeoPoint(x, y)
        ids = tree.query(point.buffer(0.0003), predicate="intersects")
        if len(ids) == 0:
            raise ValueError(f"No actual retained source support at {x:.6f}, {y:.6f}")
        return min(height(faces[int(i)], x, y) for i in ids)

    return sample


def rows(scene: MeshScene, material: str) -> Counter[bytes]:
    output: Counter[bytes] = Counter()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            raw = tile.triangles[offset : offset + 100]
            if tile.materials[struct.unpack_from("<I", raw)[0]] == material:
                output[bytes(raw[4:])] += 1
    return output


def add_raw(scene: MeshScene, source: SurfaceFace) -> None:
    tile = scene.tiles.setdefault(source.tile_name, MeshTile())
    append(tile.triangles, tile, source.material, source.vertices)


def partitions(
    faces: tuple[SurfaceFace, ...],
) -> tuple[tuple[SurfaceFace, BaseGeometry], ...]:
    from shapely.ops import unary_union

    higher: BaseGeometry = Polygon()
    output: list[tuple[SurfaceFace, BaseGeometry]] = []
    for material in ("Road", "Runoff", "RunoffGreen", "Gravel", "Grass"):
        group = [source for source in faces if source.material == material]
        for source in group:
            plan = source.plan.difference(higher)
            if not plan.is_empty and plan.area > 1e-10:
                output.append((source, plan))
        higher = unary_union([higher, *[source.plan for source in group]])
    return tuple(output)
