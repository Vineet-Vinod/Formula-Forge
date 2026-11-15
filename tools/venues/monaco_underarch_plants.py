"""Source-qualified lower woodland under the actual Larvotto bridge volume."""

from __future__ import annotations

import math
import random
import struct

import numpy as np
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from numpy.typing import NDArray
from shapely import get_parts
from shapely.geometry import MultiPoint, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.monaco_underarch_dataclasses import (
    UnderarchAudit,
    UnderarchFace,
    UnderarchPlant,
    UnderarchSpec,
)


def plane_height(face: UnderarchFace, x: float, y: float) -> float:
    a, b, c = face.points
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
    return a[2] * u + b[2] * v + c[2] * (1 - u - v)


def face_points(tile: MeshTile) -> NDArray[np.float64]:
    vertices = np.frombuffer(
        tile.triangles, dtype=np.dtype([("mat", "<u4"), ("v", "<f4", (3, 8))])
    )["v"][:, :, :3]
    return vertices[:, :, [1, 0, 2]].astype(float) * np.array([-1, -1, 1]) / 100


def plant_underarch(
    scene: MeshScene,
    mask: BaseGeometry,
    ground: tuple[UnderarchFace, ...],
    ceilings: tuple[UnderarchFace, ...],
    source: UnderarchSpec,
) -> UnderarchAudit:
    floor_index = STRtree([f.plan for f in ground])
    ceiling_index = STRtree([f.plan for f in ceilings])
    rng = random.Random(source.seed)
    xmin, ymin, xmax, ymax = mask.bounds
    plants: list[UnderarchPlant] = []
    attempted = boundary_rejected = ceiling_rejected = 0
    minimum_clearance = math.inf
    y = ymin + source.spacing_m / 2
    while y < ymax:
        x = xmin + source.spacing_m / 2
        while x < xmax:
            px, py = (
                x + rng.uniform(-source.jitter_m, source.jitter_m),
                y + rng.uniform(-source.jitter_m, source.jitter_m),
            )
            height = rng.uniform(
                source.minimum_primitive_height_m, source.maximum_primitive_height_m
            )
            seed = source.seed + attempted
            attempted += 1
            point = Point(px, py)
            if not mask.covers(point.buffer(height * 0.41 + source.wind_envelope_m)):
                boundary_rejected += 1
                x += source.spacing_m
                continue
            matches = [
                ground[int(i)] for i in floor_index.query(point, predicate="covered_by")
            ]
            if not matches:
                raise ValueError(
                    "An under-arch root has no actual old Ground owner"
                )
            levels = [plane_height(f, px, py) for f in matches]
            if max(levels) - min(levels) > 0.003:
                raise ValueError("Competing old Ground planes under a new shrub root")
            z = sum(levels) / len(levels)
            new = MeshScene()
            new.broadleaf(
                (px, py, z - height * source.root_burial_fraction), height, seed
            )
            points = np.concatenate(
                [face_points(t).reshape(-1, 3) for t in new.tiles.values()]
            )
            wind = MultiPoint(points[:, :2]).convex_hull.buffer(source.wind_envelope_m)
            if wind.difference(mask).area > 1e-8:
                boundary_rejected += 1
                x += source.spacing_m
                continue
            roof_parts = []
            minimum_ceiling = math.inf
            for i in ceiling_index.query(wind):
                face = ceilings[int(i)]
                piece = face.plan.intersection(wind)
                if piece.area <= 1e-10:
                    continue
                roof_parts.append(piece)
                for part in get_parts(piece):
                    if isinstance(part, Polygon):
                        minimum_ceiling = min(
                            minimum_ceiling,
                            *(
                                plane_height(face, q[0], q[1])
                                for q in part.exterior.coords
                            ),
                        )
            if wind.difference(unary_union(roof_parts)).area > 1e-7:
                ceiling_rejected += 1
                x += source.spacing_m
                continue
            top = float(points[:, 2].max())
            clearance = minimum_ceiling - top - source.wind_envelope_m
            if clearance < source.minimum_soffit_clearance_m:
                ceiling_rejected += 1
                x += source.spacing_m
                continue
            for name, tile in new.tiles.items():
                target = scene.tiles.setdefault(name, MeshTile())
                for offset in range(0, len(tile.triangles), 100):
                    material = tile.materials[
                        struct.unpack_from("<I", tile.triangles, offset)[0]
                    ]
                    if material not in target.materials:
                        target.materials.append(material)
                    target.triangles.extend(
                        struct.pack("<I", target.materials.index(material))
                    )
                    target.triangles.extend(tile.triangles[offset + 4 : offset + 100])
                for axis in range(3):
                    target.minimum[axis] = min(target.minimum[axis], tile.minimum[axis])
                    target.maximum[axis] = max(target.maximum[axis], tile.maximum[axis])
            plants.append(
                UnderarchPlant(
                    len(plants),
                    (px, py),
                    z,
                    (matches[0].tile, matches[0].row),
                    height,
                    top,
                    minimum_ceiling,
                    clearance,
                    wind.area,
                    seed,
                )
            )
            minimum_clearance = min(minimum_clearance, clearance)
            x += source.spacing_m
        y += source.spacing_m
    if not plants:
        raise ValueError(
            "The source-qualified under-arch mask supports no clearance-safe shrubs"
        )
    return UnderarchAudit(
        tuple(plants),
        attempted,
        boundary_rejected,
        ceiling_rejected,
        minimum_clearance,
        len(ground),
        len(ceilings),
    )
