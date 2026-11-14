"""Clip only occupied interiors from actual already emitted Jeddah ground rows."""

from __future__ import annotations

import math
import struct
from collections.abc import Iterator
from itertools import pairwise

from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.jeddah_masarat_dataclasses import (
    XY,
    FoundationQuad,
    GroundEdit,
    GroundFace,
    GroundLookup,
    MasaratArchitecture,
    MasaratSupport,
)
from venues.jeddah_masarat_geometry import xy


def decode_ground_face(raw: bytes, name: str, index: int) -> GroundFace:
    values = struct.unpack('<I24f', raw)

    def point(i: int) -> tuple[float, float, float]:
        return -values[2 + i * 8] / 100, -values[1 + i * 8] / 100, values[3 + i * 8] / 100

    def normal(i: int) -> tuple[float, float, float]:
        return -values[5 + i * 8], -values[4 + i * 8], values[6 + i * 8]

    def uv(i: int) -> XY:
        return values[7 + i * 8], values[8 + i * 8]

    points = point(0), point(1), point(2)
    return GroundFace(points, (normal(0), normal(1), normal(2)), (uv(0), uv(1), uv(2)),
                      Polygon([p[:2] for p in points]), name, index, raw)


def capture_ground(scene: CircuitScene, support_domain: BaseGeometry) -> GroundLookup:
    bounds = box(*support_domain.bounds).buffer(1).envelope
    faces = []
    for name, tile in sorted(scene.tiles.items()):
        if not name.startswith('Tile_Street_'):
            continue
        tile_plan = box(-tile.maximum[1] / 100, -tile.maximum[0] / 100,
                        -tile.minimum[1] / 100, -tile.minimum[0] / 100)
        if not tile_plan.intersects(bounds):
            continue
        if len(tile.triangles) % 100:
            raise ValueError('An emitted ground tile contains an incomplete packed row')
        for offset in range(0, len(tile.triangles), 100):
            material = struct.unpack_from('<I', tile.triangles, offset)[0]
            if tile.materials[material] != 'Runoff':
                continue
            raw = bytes(tile.triangles[offset:offset + 100])
            face = decode_ground_face(raw, name, offset // 100)
            a, b, c = face.points
            area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if area > 1e-8 and face.plan.intersects(bounds):
                faces.append(face)
    if not faces:
        raise ValueError('Masarat requires actual emitted terrain before its architecture is added')
    return GroundLookup(tuple(faces), STRtree([face.plan for face in faces]))


def weights(face: GroundFace, x: float, y: float) -> tuple[float, float, float]:
    a, b, c = face.points
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    return first, second, 1 - first - second


def ground_at(lookup: GroundLookup, x: float, y: float) -> float:
    marker = ShapePoint(x, y)
    values = []
    for index in lookup.index.query(marker.buffer(1e-7)):
        face = lookup.faces[int(index)]
        if face.plan.buffer(1e-7).covers(marker):
            values.append(sum(w * p[2] for w, p in zip(weights(face, x, y), face.points, strict=True)))
    if not values:
        raise ValueError(f'No actual emitted ground supports Masarat at {x}, {y}')
    if max(values) - min(values) > .002:
        raise ValueError('Masarat support crosses multiple distinct emitted ground sheets')
    return max(values)


def line_breaks(lookup: GroundLookup, line: LineString) -> set[float]:
    breaks = {0., 1.}
    for index in lookup.index.query(line):
        hit = line.intersection(lookup.faces[int(index)].plan.boundary)
        for part in getattr(hit, 'geoms', (hit,)):
            if not part.is_empty:
                breaks.update(min(1., max(0., line.project(ShapePoint(p)) / line.length)) for p in part.coords)
    return breaks


def boundary_segments(lookup: GroundLookup, plan: Polygon) -> Iterator[tuple[XY, XY]]:
    for a, b in pairwise(orient(plan, sign=1).exterior.coords):
        line = LineString([a, b])
        for first, last in pairwise(sorted(line_breaks(lookup, line))):
            if last - first < 1e-10:
                continue
            p, q = line.interpolate(first, normalized=True), line.interpolate(last, normalized=True)
            yield (p.x, p.y), (q.x, q.y)


def support(lookup: GroundLookup, config: MasaratArchitecture,
            components: tuple[tuple[str, Polygon, float], ...]) -> MasaratSupport:
    entries = [wing.entry_relative_m for wing in config.wings] + [config.entrance_relative_m] * 2
    quads = []
    burial = math.inf
    exposed = above_entry = 0.
    for (name, plan, _height), entry in zip(components, entries, strict=True):
        for a, b in boundary_segments(lookup, plan):
            ga, gb = ground_at(lookup, *a), ground_at(lookup, *b)
            za, zb = min(entry - .2, ga - .12), min(entry - .2, gb - .12)
            quads.append(FoundationQuad(name, ((*a, za), (*b, zb), (*b, entry + .03), (*a, entry + .03))))
            exposed = max(exposed, entry - ga, entry - gb)
            above_entry = max(above_entry, ga - entry, gb - entry)
            for i in range(9):
                t = i / 8
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                burial = min(burial, ground_at(lookup, x, y) - (za + (zb - za) * t))
    fence_burial = math.inf
    for i in range(75):
        u = 4 + i * 2.0
        if 122 < u < 137:
            continue
        a, b = xy(config, u, 1), xy(config, u + 1.8, 1)
        za, zb = ground_at(lookup, *a) - .12, ground_at(lookup, *b) - .12
        line = LineString([a, b])
        for t in line_breaks(lookup, line) | {j / 9 for j in range(10)}:
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            fence_burial = min(fence_burial, ground_at(lookup, x, y) - (za + (zb - za) * t))
    entrance = ground_at(lookup, *xy(config, 132, 10.5))
    step = config.entrance_relative_m - entrance
    grade = 100 * (entrance - ground_at(lookup, *xy(config, 132, 0))) / 10.5
    if burial < .1199 or fence_burial <= .02:
        raise ValueError('A Masarat foundation or entrance fence floats above actual emitted ground')
    if exposed > 5 or above_entry > 2 or not 0 < step < .6:
        raise ValueError('Actual Masarat ground no longer fits the qualified estimated entrance/support range')
    return MasaratSupport(tuple(quads), burial, exposed, above_entry, fence_burial, step, grade)


def clipped_rows(lookup: GroundLookup, mask: BaseGeometry) -> tuple[GroundEdit, ...]:
    coverage = unary_union([face.plan for face in lookup.faces])
    if mask.difference(coverage).area > 1e-6:
        raise ValueError('The Masarat footprint crosses an absent or nonterrain emitted surface')
    edits = []
    removed = 0.
    for face in lookup.faces:
        area = face.plan.intersection(mask).area
        if area < 1e-9:
            continue
        replacement = bytearray()
        remaining = face.plan.difference(mask)
        for part in getattr(remaining, 'geoms', (remaining,)):
            if not isinstance(part, Polygon):
                continue
            for triangle in constrained_delaunay_triangles(part).geoms:
                replacement.extend(face.raw[:4])
                for x, y in list(orient(triangle, sign=1).exterior.coords)[:3]:
                    w = weights(face, x, y)
                    z = sum(v * p[2] for v, p in zip(w, face.points, strict=True))
                    normal = tuple(sum(w[j] * face.normals[j][k] for j in range(3)) for k in range(3))
                    uv = tuple(sum(w[j] * face.uv[j][k] for j in range(3)) for k in range(2))
                    replacement.extend(struct.pack('<8f', -y * 100, -x * 100, z * 100,
                                                   -normal[1], -normal[0], normal[2], *uv))
        edits.append(GroundEdit(face.tile_name, face.index, face.raw, bytes(replacement), area))
        removed += area
    if abs(removed - mask.area) > 1e-5:
        raise ValueError('Masarat ground has overlapping sheets or incomplete occupied-area coverage')
    return tuple(edits)


def apply_ground_edits(scene: CircuitScene, edits: tuple[GroundEdit, ...]) -> None:
    grouped: dict[str, dict[int, GroundEdit]] = {}
    for edit in edits:
        grouped.setdefault(edit.tile_name, {})[edit.index] = edit
    replacements: dict[str, bytearray] = {}
    for name, changes in grouped.items():
        tile = scene.tiles[name]
        output = bytearray()
        for index in range(len(tile.triangles) // 100):
            raw = tile.triangles[index * 100:(index + 1) * 100]
            change = changes.get(index)
            if change is None:
                output.extend(raw)
            else:
                if bytes(raw) != change.raw:
                    raise ValueError('An emitted Masarat ground row changed after its support was captured')
                output.extend(change.replacement)
        replacements[name] = output
    for name, replacement in replacements.items():
        scene.tiles[name].triangles = replacement
