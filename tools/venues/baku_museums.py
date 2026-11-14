from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter
from functools import partial
from pathlib import Path

from circuit_mesh import MeshScene
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points

from venues.baku_ground import _weights
from venues.baku_ground_authoring import decode
from venues.baku_ground_dataclasses import PackedPatchRow, PackedTriangle
from venues.baku_museum_dataclasses import MuseumSource
from venues.baku_museum_debour import debour
from venues.baku_museum_gymnasium import gymnasium


def validate_support_rows(scene: MeshScene, supports: list[PackedPatchRow]) -> None:
    expected = Counter(
        {(row.tile, row.material, row.payload): row.copies for row in supports}
    )
    found: Counter[tuple[str, str, bytes]] = Counter()
    for name in {row.tile for row in supports}:
        tile = scene.tiles.get(name)
        if tile is None:
            raise ValueError(f"Baku museum supporting Ground tile is missing: {name}")
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            key = name, material, bytes(tile.triangles[offset + 4 : offset + 100])
            if key in expected:
                found[key] += 1
    if found != expected:
        raise ValueError(
            "Baku museum actual supporting Ground changed; requalify the profiles"
        )


def emitted_height(rows: list[PackedTriangle], x: float, y: float) -> float:
    contained: list[float] = []
    projected: list[tuple[float, float]] = []
    point = Point(x, y)
    for row in rows:
        weights = _weights(row.points, x, y)
        if min(weights) >= -1e-9 and max(weights) <= 1 + 1e-9:
            contained.append(sum(w * p[2] for w, p in zip(weights, row.points)))
            continue
        shape = Polygon([p[:2] for p in row.points])
        distance = shape.distance(point)
        if distance <= 0.0003:
            nearest = nearest_points(shape, point)[0]
            weights = _weights(row.points, nearest.x, nearest.y)
            projected.append(
                (distance, sum(w * p[2] for w, p in zip(weights, row.points)))
            )
    if contained:
        return max(contained)
    if projected:
        return min(projected)[1]
    raise ValueError(
        "Baku museum footing has no actual Ground within native encoding tolerance"
    )


def museums(scene: CircuitScene, source_path: Path) -> None:
    source = TypeAdapter(MuseumSource).validate_json(
        gzip.decompress(source_path.read_bytes())
    )
    for relative, expected in source.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Baku museum protected input changed: {relative}")
    validate_support_rows(scene, source.ground_supports)
    rows = [
        decode(row.tile, row.material, row.payload) for row in source.ground_supports
    ]
    ground = partial(emitted_height, rows)
    for record in source.records:
        if record.name == "gymnasium":
            mapped = Polygon(scene.footprint(record.osm_id).ring)
            authored = Polygon(record.layout.outer_xy)
            if mapped.symmetric_difference(authored).area > 1e-6:
                raise ValueError(
                    "Baku gymnasium mapped footprint changed; requalify its source"
                )
            gymnasium(scene, record.layout, record.footing, record.datum_m)
        else:
            debour(
                scene,
                record.layout,
                record.footing,
                record.datum_m,
                ground,
                source.debour_dimensions,
            )
        scene.modeled_buildings.add(record.osm_id)
        scene.landmarks.append(
            {
                "name": "Mariinsky gymnasium"
                if record.name == "gymnasium"
                else "De Bour mansion",
                "osm_id": record.osm_id,
                "datum_m": record.datum_m,
                "dimensions": record.source_note,
            }
        )
