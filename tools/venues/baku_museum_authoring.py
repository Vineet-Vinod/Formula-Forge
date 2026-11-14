from __future__ import annotations

import gzip
import hashlib
from collections import Counter
from pathlib import Path

from circuit_scene import ROOT
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.baku_ground import _weights
from venues.baku_ground_authoring import _original_vertex, decode
from venues.baku_ground_dataclasses import (
    GroundPatchSource,
    PackedPatchRow,
    PackedTriangle,
)
from venues.baku_museum_dataclasses import MuseumClipProof, MuseumSource


def occupied_ground_patch(
    rows: list[PackedTriangle],
    occupied: Polygon | MultiPolygon,
    protected_source_sha256: dict[str, str],
) -> tuple[GroundPatchSource, MuseumClipProof]:
    removals: Counter[tuple[str, str, bytes]] = Counter()
    additions: Counter[tuple[str, str, bytes]] = Counter()
    removed_area = 0.0
    outside_vertices = 0
    missing_vertices = 0
    maximum_plane_error = 0.0
    maximum_area_error = 0.0
    minimum_area = float("inf")
    children: dict[str, list[str]] = {}
    for row in rows:
        shape = Polygon([point[:2] for point in row.points])
        intersection = shape.intersection(occupied)
        if intersection.area <= 1e-8:
            continue
        if row.material != "Runoff":
            raise ValueError(
                "Museum interior intersects a protected non-terrain surface"
            )
        removals[row.tile, row.material, row.payload] += 1
        parent = hashlib.sha256(row.payload).hexdigest()
        children[parent] = []
        removed_area += intersection.area
        outside = shape.difference(occupied)
        original_vertices = {
            row.payload[i * 32 : (i + 1) * 32]
            for i, point in enumerate(row.points)
            if not occupied.contains(Point(*point[:2]))
        }
        outside_vertices += len(original_vertices)
        emitted_vertices: set[bytes] = set()
        encoded_shapes: list[Polygon] = []
        for triangle in constrained_delaunay_triangles(outside).geoms:
            coords = list(orient(triangle, sign=1).exterior.coords)[:3]
            payload = b"".join(
                _original_vertex(row, float(x), float(y)) for x, y in coords
            )
            result = decode(row.tile, row.material, payload)
            encoded = Polygon([point[:2] for point in result.points])
            if encoded.area <= 1e-12:
                raise ValueError("Museum interior clip produced an unresolved triangle")
            minimum_area = min(minimum_area, encoded.area)
            encoded_shapes.append(encoded)
            for i, point in enumerate(result.points):
                emitted_vertices.add(payload[i * 32 : (i + 1) * 32])
                weights = _weights(row.points, point[0], point[1])
                expected = sum(w * p[2] for w, p in zip(weights, row.points))
                maximum_plane_error = max(maximum_plane_error, abs(point[2] - expected))
            additions[row.tile, row.material, payload] += 1
            children[parent].append(hashlib.sha256(payload).hexdigest())
        maximum_area_error = max(
            maximum_area_error,
            outside.symmetric_difference(unary_union(encoded_shapes)).area,
        )
        missing_vertices += len(original_vertices - emitted_vertices)
    if not removals or missing_vertices:
        raise ValueError(
            "Museum interior clipping lacks its complete outside attributes"
        )

    def packed(counter: Counter[tuple[str, str, bytes]]) -> list[PackedPatchRow]:
        return [
            PackedPatchRow(tile, material, payload, copies)
            for (tile, material, payload), copies in sorted(counter.items())
        ]

    patch = GroundPatchSource(
        1,
        protected_source_sha256,
        packed(removals),
        packed(additions),
        "Only literal occupied museum interiors removed from existing emitted Ground. Open C recess and De Bour courtyard retained; all outside planes, original vertices/normals/UVs preserved. Heights remain inherited renderer estimates.",
    )
    return patch, MuseumClipProof(
        sum(removals.values()),
        removed_area,
        outside_vertices,
        missing_vertices,
        maximum_plane_error,
        maximum_area_error,
        minimum_area,
        children,
    )


def rebuild(
    source_path: Path, original_patch_path: Path, output_path: Path
) -> GroundPatchSource:
    source = TypeAdapter(MuseumSource).validate_json(
        gzip.decompress(source_path.read_bytes())
    )
    original = TypeAdapter(GroundPatchSource).validate_json(
        gzip.decompress(original_patch_path.read_bytes())
    )
    if source.protected_source_sha256 != original.protected_source_sha256:
        raise ValueError(
            "Museum source and retained original Ground protections differ"
        )
    for relative, expected in original.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Museum protected source changed: {relative}")
    rows = [
        decode(row.tile, row.material, row.payload)
        for row in original.removals
        for _ in range(row.copies)
    ]
    occupied = unary_union(
        [
            Polygon(
                record.layout.outer_xy,
                [record.layout.courtyard_xy] if record.layout.courtyard_xy else [],
            )
            for record in source.records
        ]
    )
    patch, _ = occupied_ground_patch(rows, occupied, original.protected_source_sha256)
    output_path.write_bytes(
        gzip.compress(
            TypeAdapter(GroundPatchSource).dump_json(patch, indent=2), mtime=0
        )
    )
    return patch


if __name__ == "__main__":
    directory = ROOT / "Attribution/Sources/baku"
    rebuild(
        directory / "museums.json.gz",
        directory / "museum-interior-ground-delta.json.gz",
        directory / "museum-interior-ground-delta.json.gz",
    )
