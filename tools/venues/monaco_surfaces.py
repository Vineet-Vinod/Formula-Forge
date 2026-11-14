"""Classify observed west-ravine surfaces while preserving the original height planes."""

from __future__ import annotations

import struct
from typing import cast

from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles, get_parts
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.monaco_surfaces_dataclasses import (
    NativeVertex,
    SourceCover,
    SourceDocument,
    SurfaceChange,
    SurfaceClass,
    SurfaceFace,
    SurfaceRegion,
)
from venues.monaco_west_dataclasses import BelvedereArchitecture

MATERIALS = {
    "lawn": "MonacoIvyGround",
    "ivy": "MonacoIvyGround",
    "rock": "MonacoRockGround",
    "paved": "Concrete",
    "natural": "MonacoNaturalGround",
}
GROUND_MATERIALS = {"Runoff", "Grass", "MonacoIvyGround", "MonacoRockGround"}


def face(tile: MeshTile, offset: int) -> SurfaceFace:
    values = cast(
        tuple[float, ...], struct.unpack_from("<24f", tile.triangles, offset + 4)
    )
    vertices = tuple(cast(NativeVertex, values[i : i + 8]) for i in (0, 8, 16))
    a, b, c = vertices
    xy = (
        (-a[1] / 100, -a[0] / 100),
        (-b[1] / 100, -b[0] / 100),
        (-c[1] / 100, -c[0] / 100),
    )
    material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
    return SurfaceFace((a, b, c), xy, Polygon(xy), material)


def interpolate(source: SurfaceFace, x: float, y: float) -> NativeVertex:
    a, b, c = source.xy
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    third = 1 - first - second
    return cast(
        NativeVertex,
        tuple(
            first * source.vertices[0][i]
            + second * source.vertices[1][i]
            + third * source.vertices[2][i]
            for i in range(8)
        ),
    )


def fragment_rows(
    source: SurfaceFace, region: BaseGeometry, material: str
) -> list[tuple[NativeVertex, ...]]:
    output = []
    for triangle in constrained_delaunay_triangles(region).geoms:
        points = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            points.reverse()
        vertices = []
        for x, y in points:
            vertex = interpolate(source, x, y)
            if material != source.material:
                divisor = 4 if material == "Concrete" else 8
                vertex = (*vertex[:6], x / divisor, y / divisor)
            vertices.append(vertex)
        output.append(tuple(vertices))
    return output


def append(
    data: bytearray, tile: MeshTile, material: str, vertices: tuple[NativeVertex, ...]
) -> None:
    if material not in tile.materials:
        tile.materials.append(material)
    data.extend(struct.pack("<I", tile.materials.index(material)))
    for vertex in vertices:
        data.extend(struct.pack("<8f", *vertex))


def replace_surfaces(
    scene: MeshScene, regions: list[SurfaceRegion],
    allowed_materials: frozenset[str] | None = None,
) -> SurfaceChange:
    materials = GROUND_MATERIALS if allowed_materials is None else allowed_materials
    plans = [region.plan for region in regions]
    index = STRtree(plans)
    cover = unary_union(plans)
    for i, plan in enumerate(plans):
        if not plan.is_valid or plan.area <= 0.05:
            raise ValueError("Surface roles require finite valid polygons")
        if any(plan.intersection(other).area > 1e-7 for other in plans[:i]):
            raise ValueError("Surface role polygons must not overlap")
    changed = []
    outside_count = split_count = emitted_count = 0
    area = 0.0
    for name, tile in list(scene.tiles.items()):
        if not name.startswith("Tile_Street_"):
            continue
        tile_plan = Polygon(
            [
                (-tile.maximum[1] / 100, -tile.maximum[0] / 100),
                (-tile.minimum[1] / 100, -tile.maximum[0] / 100),
                (-tile.minimum[1] / 100, -tile.minimum[0] / 100),
                (-tile.maximum[1] / 100, -tile.minimum[0] / 100),
            ]
        )
        if not tile_plan.intersects(cover):
            continue
        data = bytearray()
        count = 0
        for offset in range(0, len(tile.triangles), 100):
            raw = tile.triangles[offset : offset + 100]
            material = tile.materials[struct.unpack_from("<I", raw)[0]]
            if material not in materials:
                data.extend(raw)
                outside_count += 1
                continue
            source = face(tile, offset)
            if source.plan.area < 1e-10 or min(v[5] for v in source.vertices) < 0.05:
                data.extend(raw)
                outside_count += 1
                continue
            choices = [int(i) for i in index.query(source.plan)]
            intersections = [(i, source.plan.intersection(plans[i])) for i in choices]
            intersections = [
                (i, shape)
                for i, shape in intersections
                if shape.area > 1e-9
                and MATERIALS[regions[i].surface] != source.material
            ]
            if not intersections:
                data.extend(raw)
                outside_count += 1
                continue
            kept = source.plan.difference(
                unary_union([shape for i, shape in intersections])
            )
            fragments = [(source.material, kept)]
            fragments.extend(
                (MATERIALS[regions[i].surface], shape) for i, shape in intersections
            )
            if (
                abs(sum(shape.area for material, shape in fragments) - source.plan.area)
                > 1e-7
            ):
                raise ValueError("Classified surface replacement lost area")
            for material, shape in fragments:
                for vertices in fragment_rows(source, shape, material):
                    append(data, tile, material, vertices)
                    emitted_count += 1
            area += sum(shape.area for i, shape in intersections)
            split_count += 1
            count += 1
        if count:
            tile.triangles = data
            changed.append(name)
    return SurfaceChange(
        tuple(changed), split_count, outside_count, area, emitted_count
    )


def finish_terrain(scene: CircuitScene) -> None:
    if scene.slug != "monaco":
        raise ValueError(
            "The west surface roles require the retained Monaco source frame"
        )
    source = TypeAdapter(SourceDocument).validate_json(
        (scene.sources / "architecture/west-visible-surfaces.json").read_bytes()
    )
    frame = source.transform
    if (
        max(
            abs(frame.scene_origin_latitude - scene.provenance.origin.latitude),
            abs(frame.scene_origin_longitude - scene.provenance.origin.longitude),
            abs(frame.scene_scale - scene.provenance.route.uniform_scale),
        )
        > 1e-9
    ):
        raise ValueError(
            "The source surface-role registration differs from the venue frame"
        )
    belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / "architecture/west-belvedere.json").read_bytes()
    )
    exclusions = [
        Polygon([v.native_xy_m for v in record.vertices])
        for record in source.explicit_exclusions
        if record.vertices
    ]
    exclusions.extend(
        [
            Point(belvedere.center_xy_m).buffer(belvedere.radius_m + 0.3),
            scene.corridor_mask.buffer(0.25),
            *scene.extra_corridors,
            *scene.water_shapes,
            *[Polygon(b.ring).buffer(0.4) for b in scene.buildings],
        ]
    )
    blocked = unary_union(exclusions)
    classes: dict[SourceCover, SurfaceClass] = {
        "Ivy/Garden cover candidate": "lawn",
        "Ivy candidate": "ivy",
        "Ivy/Rock mixed candidate": "ivy",
        "Rock candidate": "rock",
        "Paved ground candidate": "paved",
    }
    regions = []
    for record in source.candidate_regions:
        plan = Polygon([v.native_xy_m for v in record.vertices]).difference(blocked)
        for index, part in enumerate(get_parts(plan)):
            if isinstance(part, Polygon) and part.area > 0.05:
                regions.append(
                    SurfaceRegion(
                        record.id + f"_{index}", part, classes[record.class_name]
                    )
                )
    report = replace_surfaces(scene, regions)
    scene.landmarks.append(
        {
            "name": "Source-classified west gardens, rock strips and paved circulation",
            "classified_ground_area_m2": report.classified_area_m2,
            "affected_street_tiles": len(report.tiles),
            "source": "architecture/west-visible-surfaces.json",
            "status": "Original 2019 orthophoto role interpretation, approximately ±1m boundary uncertainty. "
            "All old height planes and complete outside packed rows are preserved; clipped outside "
            "faces retain interpolated normals and UVs. Pools, paths, buildings and the belvedere "
            "are excluded. Elevated L roof/deck and uncertain pale cap are not ground evidence. "
            "No native field, road, protection, contact or camera change; fresh cooked review required.",
        }
    )
