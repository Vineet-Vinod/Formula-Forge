from __future__ import annotations

import bisect
import csv
import hashlib
import itertools
import math
import struct
from collections import Counter
from copy import copy
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from typing import cast

from circuit_dataclasses import MeshTile, Point, RoadStation
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely import prepare as prepare_geometry
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Polygon,
    box,
)
from shapely.geometry import Point as GeoPoint
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

from venues.buddh_first_sector_dataclasses import (
    ContactTriangle,
    FirstSectorProposal,
    FirstSectorResult,
    FirstSectorState,
    NativeCurve,
    RetainedBaseline,
    RetainedSplitOwner,
    SurfaceFace,
    SurfaceRole,
)


def load_road(path: Path) -> tuple[RoadStation, ...]:
    with path.open() as handle:
        return tuple(
            TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(handle)))
        )


def sample(road: tuple[RoadStation, ...], station: float) -> RoadStation:
    index = min(
        len(road) - 2,
        max(0, bisect.bisect_right([p.station for p in road], station) - 1),
    )
    a, b = road[index], road[index + 1]
    t = min(1.0, max(0.0, (station - a.station) / (b.station - a.station)))
    return RoadStation(
        station,
        a.x + t * (b.x - a.x),
        a.y + t * (b.y - a.y),
        a.z + t * (b.z - a.z),
        a.tx + t * (b.tx - a.tx),
        a.ty + t * (b.ty - a.ty),
        a.half_width + t * (b.half_width - a.half_width),
        a.bank + t * (b.bank - a.bank),
        a.left_shoulder + t * (b.left_shoulder - a.left_shoulder),
        a.right_shoulder + t * (b.right_shoulder - a.right_shoulder),
        a.bank_quadratic,
        a.bank_fade,
        a.bank_outer_positive,
        a.bank_outer_negative,
    )


def smooth(t: float) -> float:
    return t * t * t * (10 + t * (-15 + 6 * t))


def interpolate(controls: list[tuple[float, float]], station: float) -> float:
    positions = [p[0] for p in controls]
    i = min(len(positions) - 2, max(0, bisect.bisect_right(positions, station) - 1))
    lengths = [b[0] - a[0] for a, b in itertools.pairwise(controls)]
    slopes = [
        (b[1] - a[1]) / length
        for a, b, length in zip(controls[:-1], controls[1:], lengths, strict=True)
    ]
    tangents = [0.0]
    for j in range(1, len(controls) - 1):
        left, right = slopes[j - 1], slopes[j]
        if left * right <= 0:
            tangents.append(0.0)
        else:
            w1, w2 = 2 * lengths[j] + lengths[j - 1], lengths[j] + 2 * lengths[j - 1]
            tangents.append((w1 + w2) / (w1 / left + w2 / right))
    tangents.append(0.0)
    t = min(1.0, max(0.0, (station - positions[i]) / lengths[i]))
    a, b = controls[i][1], controls[i + 1][1]
    return (
        (2 * t**3 - 3 * t**2 + 1) * a
        + (t**3 - 2 * t**2 + t) * lengths[i] * tangents[i]
        + (-2 * t**3 + 3 * t**2) * b
        + (t**3 - t**2) * lengths[i] * tangents[i + 1]
    )


def correction(
    proposal: FirstSectorProposal, road: tuple[RoadStation, ...], station: float
) -> float:
    if station <= proposal.start_m or station >= proposal.end_m:
        return 0.0
    target = interpolate([(p.station_m, p.width_m) for p in proposal.targets], station)
    reduction = 2 * sample(road, station).half_width - target
    if reduction < -1e-4:
        raise ValueError(
            "The private correction would expand beyond retained old racing asphalt"
        )
    return max(0.0, reduction)


def corrected(
    proposal: FirstSectorProposal, road: tuple[RoadStation, ...], point: RoadStation
) -> RoadStation:
    half_delta = correction(proposal, road, point.station) / 2
    if half_delta == 0:
        return point
    return replace(
        point,
        half_width=point.half_width - half_delta,
        left_shoulder=point.left_shoulder + half_delta,
        right_shoulder=point.right_shoulder + half_delta,
    )


def sampled_road(
    proposal: FirstSectorProposal, road: tuple[RoadStation, ...], step: float = 1.0
) -> tuple[RoadStation, ...]:
    return tuple(
        corrected(proposal, road, sample(road, station))
        for station in [
            proposal.start_m + i * step
            for i in range(math.ceil((proposal.end_m - proposal.start_m) / step) + 1)
        ]
    )


def band(
    road: tuple[RoadStation, ...],
    inner: float,
    outer: float,
    side: int,
    legal_offset: bool = True,
) -> BaseGeometry:
    pieces = []
    for a, b in itertools.pairwise(road):
        ha = a.half_width if legal_offset else 0.0
        hb = b.half_width if legal_offset else 0.0
        p = Polygon(
            [
                a.point(side * (ha + inner))[:2],
                b.point(side * (hb + inner))[:2],
                b.point(side * (hb + outer))[:2],
                a.point(side * (ha + outer))[:2],
            ]
        )
        if not p.is_valid:
            raise ValueError("A proposed surface band folds across itself")
        if p.area > 1e-10:
            pieces.append(p)
    return unary_union(pieces)


def road_mask(road: tuple[RoadStation, ...]) -> BaseGeometry:
    return unary_union(
        [
            Polygon(
                [
                    a.point(-a.half_width - 0.15)[:2],
                    b.point(-b.half_width - 0.15)[:2],
                    b.point(b.half_width + 0.15)[:2],
                    a.point(a.half_width + 0.15)[:2],
                ]
            )
            for a, b in itertools.pairwise(road)
        ]
    )


def half_road(road: tuple[RoadStation, ...], side: int) -> BaseGeometry:
    shapes = []
    for a, b in pairwise(road):
        shape = Polygon(
            [
                (a.x, a.y),
                (b.x, b.y),
                b.point(side * (b.half_width + 0.15))[:2],
                a.point(side * (a.half_width + 0.15))[:2],
            ]
        )
        if not shape.is_valid:
            raise ValueError("An actual retained half-road cell folds across itself")
        if shape.area > 1e-10:
            shapes.append(shape)
    return unary_union(shapes)


def road_interval(
    road: tuple[RoadStation, ...], start: float, end: float
) -> tuple[RoadStation, ...]:
    return (
        sample(road, start),
        *(p for p in road if start < p.station < end),
        sample(road, end),
    )


def playable_domain(path: Path, witness: RoadStation) -> BaseGeometry:
    with path.open() as handle:
        lines = [
            LineString(
                [
                    (round(float(row["ax"]), 4), round(float(row["ay"]), 4)),
                    (round(float(row["bx"]), 4), round(float(row["by"]), 4)),
                ]
            )
            for row in csv.DictReader(handle)
        ]
    parts = list(polygonize(unary_union(lines)))
    from shapely.geometry import Point

    point = Point(witness.x, witness.y)
    candidates = [part for part in parts if part.buffer(0.01).covers(point)]
    if not candidates:
        raise ValueError(
            "The retained barrier loops do not enclose the source road witness"
        )
    return max(candidates, key=lambda p: p.area)


def t1_apron(
    proposal: FirstSectorProposal,
    road: tuple[RoadStation, ...],
    protected: BaseGeometry,
    legal: BaseGeometry,
) -> BaseGeometry:
    controls = proposal.t1_outer_reaches_m
    pieces = []
    for a, b in itertools.pairwise(controls):
        rows = road_interval(road, a[0], b[0])
        for p, q in itertools.pairwise(rows):
            pa = a[1] + smooth((p.station - a[0]) / (b[0] - a[0])) * (b[1] - a[1])
            qa = a[1] + smooth((q.station - a[0]) / (b[0] - a[0])) * (b[1] - a[1])
            pa, qa = max(pa, p.half_width + 0.15), max(qa, q.half_width + 0.15)
            shape = Polygon(
                [
                    p.point(-p.half_width - 0.15)[:2],
                    q.point(-q.half_width - 0.15)[:2],
                    q.point(-qa)[:2],
                    p.point(-pa)[:2],
                ]
            )
            if shape.is_valid and shape.area > 1e-10:
                pieces.append(shape)
    return unary_union(pieces).intersection(protected.buffer(-0.25)).difference(legal)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def emit_road(
    scene: MeshScene,
    road: tuple[RoadStation, ...],
    length: float,
    start: float,
    end: float,
    markings: bool = False,
    cells: set[int] | None = None,
) -> None:
    from circuit_mesh import norm

    ds = length / len(road)
    for i, a in enumerate(road):
        b = road[(i + 1) % len(road)]
        if (
            (cells is not None and i not in cells)
            or b.station < start
            or a.station > end
        ):
            continue
        previous, following = road[(i - 1) % len(road)], road[(i + 2) % len(road)]

        def normal(p: RoadStation, grade: float) -> tuple[float, float, float]:
            return norm(
                (-grade * p.tx - p.bank * p.ty, -grade * p.ty + p.bank * p.tx, 1.0)
            )

        na = normal(a, (b.z - previous.z) / (2 * ds))
        nb = normal(b, (following.z - a.z) / (2 * ds))
        points = (
            a.point(-a.half_width - 0.15, 0.006),
            b.point(-b.half_width - 0.15, 0.006),
            b.point(b.half_width + 0.15, 0.006),
            a.point(a.half_width + 0.15, 0.006),
        )
        uv = (
            (a.station / 2, -a.half_width / 2),
            ((a.station + ds) / 2, -b.half_width / 2),
            ((a.station + ds) / 2, b.half_width / 2),
            (a.station / 2, a.half_width / 2),
        )
        scene.triangle(
            "Tile_Road", "Road", points[0], points[1], points[2], uv[:3], (na, nb, nb)
        )
        scene.triangle(
            "Tile_Road",
            "Road",
            points[0],
            points[2],
            points[3],
            (uv[0], uv[2], uv[3]),
            (na, nb, na),
        )
        if markings:
            for side in (-1, 1):
                scene.quad(
                    "Tile_WhiteLine",
                    "White",
                    a.point(side * (a.half_width - 0.12), 0.019),
                    b.point(side * (b.half_width - 0.12), 0.019),
                    b.point(side * b.half_width, 0.019),
                    a.point(side * a.half_width, 0.019),
                    up=True,
                )


def variable_band(
    road: tuple[RoadStation, ...],
    controls: list[tuple[float, float]],
    side: int,
    inner: float,
    absolute_outer: bool = False,
) -> BaseGeometry:
    shapes = []
    for a, b in itertools.pairwise(controls):
        rows = road_interval(road, a[0], b[0])
        for p, q in itertools.pairwise(rows):
            wa = interpolate(controls, p.station)
            wb = interpolate(controls, q.station)
            oa = max(p.half_width + inner, wa if absolute_outer else p.half_width + wa)
            ob = max(q.half_width + inner, wb if absolute_outer else q.half_width + wb)
            polygon = Polygon(
                [
                    p.point(side * (p.half_width + inner))[:2],
                    q.point(side * (q.half_width + inner))[:2],
                    q.point(side * ob)[:2],
                    p.point(side * oa)[:2],
                ]
            )
            if not polygon.is_valid:
                raise ValueError(
                    "The source-reconstructed variable apron folds over itself"
                )
            if polygon.area > 1e-10:
                shapes.append(polygon)
    return unary_union(shapes)


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def scalar(curve: NativeCurve, station: float, length: float) -> float:
    station = float32(math.fmod(float32(station), float32(length)))
    index = bisect.bisect_right(curve.positions, station)
    if index == 0:
        return curve.values[0]
    if index == len(curve.positions):
        return curve.values[-1]
    a, b = curve.positions[index - 1 : index + 1]
    first, second = curve.values[index - 1 : index + 1]
    span = max(float32(0.001), float32(b - a))
    t = float32(float32(station - a) / span)
    return float32(first + float32(float32(second - first) * t))


def retained_road(
    source: RetainedBaseline, road: tuple[RoadStation, ...]
) -> tuple[RoadStation, ...]:
    if len(road) != source.sample_count:
        raise ValueError(
            "Retained Buddh profiles require the qualified native sample lattice"
        )
    widths = NativeCurve(
        tuple(float32(a) for a, _b in source.width_controls),
        tuple(float32(b) for _a, b in source.width_controls),
    )
    positions = tuple(float32(a) for a, _b, _c in source.shoulder_controls)
    left = NativeCurve(
        positions, tuple(float32(b) for _a, b, _c in source.shoulder_controls)
    )
    right = NativeCurve(
        positions, tuple(float32(c) for _a, _b, c in source.shoulder_controls)
    )
    output = []
    for point in road:
        half = float32(scalar(widths, point.station, source.length_m) * float32(0.5))
        shoulders = []
        for side, curve in ((1, left), (-1, right)):
            shoulder = max(
                float32(0.05),
                min(float32(24), scalar(curve, point.station, source.length_m)),
            )
            for zone in source.runtime_minima:
                s = float32(point.station)
                a, b = float32(zone.start_m), float32(zone.end_m)
                inside = a <= s <= b if a <= b else s >= a or s <= b
                if inside and zone.side in (0, side):
                    shoulder = max(
                        shoulder, float32(float32(zone.width_m) - float32(0.95))
                    )
            shoulders.append(float(format(shoulder, ".9g")))
        output.append(
            replace(
                point,
                half_width=float(format(half, ".9g")),
                left_shoulder=shoulders[0],
                right_shoulder=shoulders[1],
            )
        )
    return tuple(output)


def scalar_hash(road: tuple[RoadStation, ...]) -> str:
    result = hashlib.sha256()
    for p in road:
        result.update(
            struct.pack(
                "<4d", p.station, p.half_width, p.left_shoulder, p.right_shoulder
            )
        )
    return result.hexdigest()


def spatial_hash(road: tuple[RoadStation, ...]) -> str:
    result = hashlib.sha256()
    for p in road:
        result.update(struct.pack("<7d", p.station, p.x, p.y, p.z, p.tx, p.ty, p.bank))
    return result.hexdigest()


def native_width_controls(
    proposal: FirstSectorProposal, baseline: RetainedBaseline
) -> list[tuple[float, float]]:
    targets = [(p.station_m, p.width_m) for p in proposal.targets]
    rows = {
        station: width
        for station, width in baseline.width_controls
        if station <= proposal.start_m or station >= proposal.end_m
    }
    stations = {
        s
        for s, _width in baseline.width_controls
        if proposal.start_m < s < proposal.end_m
    }
    stations.update(
        float32(
            float32(baseline.length_m * float32(i)) / float32(baseline.sample_count)
        )
        for i in range(baseline.sample_count)
    )
    stations.update((proposal.start_m, proposal.end_m))
    for station in stations:
        if proposal.start_m <= station <= proposal.end_m:
            native_station = float32(station)
            rows[native_station] = interpolate(targets, native_station)
    return sorted(rows.items())


LEGACY_CURBS = (
    (260.0, 345.0, -1),
    (1000.0, 1080.0, 1),
    (1125.0, 1200.0, -1),
    (1370.0, 1475.0, 1),
    (2650.0, 2780.0, 1),
)


def load_source(scene: CircuitScene) -> tuple[FirstSectorProposal, RetainedBaseline]:
    return (
        TypeAdapter(FirstSectorProposal).validate_json(
            (scene.sources / "first-sector.json").read_bytes()
        ),
        TypeAdapter(RetainedBaseline).validate_json(
            (scene.sources / "first-sector-baseline.json").read_bytes()
        ),
    )


def prepare_scene(scene: CircuitScene) -> FirstSectorState:
    proposal, baseline = load_source(scene)
    return prepare(scene, proposal, baseline)


def prepare(
    scene: CircuitScene, proposal: FirstSectorProposal, baseline: RetainedBaseline
) -> FirstSectorState:
    if (
        scene.slug != "buddh"
        or max(
            abs(scene.provenance.route.uniform_scale - baseline.expected_scene_scale),
            abs(scene.provenance.origin.latitude - baseline.expected_origin_latitude),
            abs(scene.provenance.origin.longitude - baseline.expected_origin_longitude),
        )
        > 1e-12
    ):
        raise ValueError(
            "The first-sector reconstruction requires the qualified Buddh source frame"
        )
    candidate = tuple(scene.road)
    if spatial_hash(candidate) != baseline.spatial_rows_sha256:
        raise ValueError(
            "The qualified Buddh alignment/elevation/tangent/bank source rows changed"
        )
    retained = retained_road(baseline, candidate)
    if scalar_hash(retained) != baseline.scalar_rows_sha256:
        raise ValueError(
            "Retained native profiles no longer replay the qualified source lattice"
        )
    if any(p.bank != 0 or p.bank_fade != 0 or p.bank_quadratic != 0 for p in candidate):
        raise ValueError(
            "The qualified first-sector surface planes require the retained unbanked road"
        )
    for old, new in zip(retained, candidate, strict=True):
        expected = corrected(proposal, retained, old)
        outside = old.station <= proposal.start_m or old.station >= proposal.end_m
        for field in ("half_width", "left_shoulder", "right_shoulder"):
            error = abs(getattr(new, field) - getattr(expected, field))
            if error > (0.0 if outside else 0.0001):
                raise ValueError(
                    f"The actual compiled {field} differs from the approved profile at {old.station:.6f} m"
                )
        if max(new.left_shoulder, new.right_shoulder) > 24:
            raise ValueError(
                "The compiled effective shoulder exceeds the retained runtime clamp"
            )
    changed = tuple(
        i
        for i, a in enumerate(retained)
        if a.half_width != candidate[i].half_width
        or retained[(i + 1) % len(retained)].half_width
        != candidate[(i + 1) % len(retained)].half_width
    )
    scene.road = list(retained)
    return FirstSectorState(proposal, baseline, retained, candidate, changed)


def template(scene: CircuitScene, road: tuple[RoadStation, ...]) -> CircuitScene:
    result = copy(scene)
    result.tiles = {}
    result.road = list(road)
    result.verge_patches = []
    result.terrain_cutouts = []
    result.surface_ranges = []
    result.extra_corridors = []
    result.surface_shapes = []
    result.surface_points = []
    result.surface_index = None
    result._ground_normals = {}
    result.road_surfaces()
    return result


def curb_template(
    scene: CircuitScene, state: FirstSectorState, retained: bool
) -> tuple[CircuitScene, tuple[SurfaceFace, ...]]:
    from venues.buddh_first_sector_rows import face

    result = template(scene, state.retained_road if retained else state.candidate_road)
    before = {name: len(tile.triangles) for name, tile in result.tiles.items()}
    intervals = (
        LEGACY_CURBS
        if retained
        else tuple((c.start_m, c.end_m, c.side) for c in state.proposal.raised_curbs)
    )
    for start, end, side in intervals:
        result.kerb(start, end, int(side), width=1.2)
    faces = []
    for name, tile in result.tiles.items():
        for offset in range(before.get(name, 0), len(tile.triangles), 100):
            source = face(tile, name, offset)
            if source.plan.area > 1e-10:
                faces.append(source)
    if not retained:
        faces = continuous_corrected_curb(result, state, faces)
    return result, tuple(faces)


def continuous_corrected_curb(
    scene: CircuitScene, state: FirstSectorState, faces: list[SurfaceFace]
) -> list[SurfaceFace]:
    from venues.buddh_first_sector_rows import face, lookup

    if not scene.terrain_cutouts:
        return faces
    domain = unary_union(scene.terrain_cutouts)
    support = MeshScene()
    road = state.candidate_road
    for a, b in pairwise(road):
        if b.station < 990 or a.station > 1090:
            continue
        support.quad(
            "Tile_T1Grade",
            "Road",
            a.point(-a.half_width - 3),
            b.point(-b.half_width - 3),
            b.point(b.half_width + 3),
            a.point(a.half_width + 3),
        )
    grade = lookup(
        tuple(
            face(tile, name, offset)
            for name, tile in support.tiles.items()
            for offset in range(0, len(tile.triangles), 100)
        )
    )
    output = []
    boundary = scene.road_mask.boundary
    acquisition = domain.buffer(0.0003)
    for source in faces:
        if not acquisition.covers(source.plan):
            output.append(source)
            continue
        repaired = MeshScene()
        points = []
        for x, y, _z in source.points:
            point = GeoPoint(x, y)
            distance = boundary.distance(point) * (
                -1 if scene.road_mask.covers(point) else 1
            )
            fraction = max(0.0, min(1.0, (distance + 0.01) / 1.2))
            points.append((x, y, grade(x, y) + 0.021 + 0.034 * fraction))
        repaired.triangle(
            "Tile_Kerb",
            source.material,
            points[0],
            points[1],
            points[2],
            tuple((v[6], v[7]) for v in source.vertices),
        )
        for name, tile in repaired.tiles.items():
            for offset in range(0, len(tile.triangles), 100):
                rebuilt = face(tile, name, offset)
                if min(v[5] for v in rebuilt.vertices) < 0.9:
                    longest = max(
                        math.dist(a[:2], b[:2])
                        for a, b in pairwise((*rebuilt.points, rebuilt.points[0]))
                    )
                    altitude = 2 * rebuilt.plan.area / longest
                    if rebuilt.plan.area > 0.000005 or altitude > 0.00003:
                        raise ValueError(
                            "Corrected T1 retains a meaningful near-vertical curb top"
                        )
                    continue
                output.append(
                    replace(rebuilt, tile_name=source.tile_name, offset=source.offset)
                )
    return output


def changed_plan(state: FirstSectorState) -> BaseGeometry:
    road = state.retained_road
    return unary_union(
        [
            Polygon(
                [
                    road[i].point(-road[i].half_width - 0.15)[:2],
                    road[(i + 1) % len(road)].point(
                        -road[(i + 1) % len(road)].half_width - 0.15
                    )[:2],
                    road[(i + 1) % len(road)].point(
                        road[(i + 1) % len(road)].half_width + 0.15
                    )[:2],
                    road[i].point(road[i].half_width + 0.15)[:2],
                ]
            )
            for i in state.changed_cells
        ]
    )


def legacy_green(
    faces: tuple[SurfaceFace, ...],
    road: tuple[RoadStation, ...],
    start: float,
    end: float,
    side: int,
) -> BaseGeometry:
    domain = band(road_interval(road, start, end), 0.14, 2.61, side).buffer(0.05)
    return unary_union(
        [
            f.plan
            for f in faces
            if f.material == "RunoffGreen"
            and f.plan.intersection(domain).area > 0.5 * f.plan.area
        ]
    )


def legacy_paving(
    faces: tuple[SurfaceFace, ...], domain: BaseGeometry, material: str
) -> BaseGeometry:
    domain = domain.buffer(0.05)
    return unary_union(
        [
            f.plan
            for f in faces
            if f.material == material
            and f.plan.intersection(domain).area > 0.5 * f.plan.area
        ]
    )


def roles(
    scene: CircuitScene,
    state: FirstSectorState,
    raised: BaseGeometry,
    old_curbs: BaseGeometry,
    floors: tuple[SurfaceFace, ...],
) -> list[SurfaceRole]:
    old, new = state.retained_road, state.candidate_road
    source = state.proposal
    full_old = road_mask((*old, old[0]))
    full_new = road_mask((*new, new[0]))
    released = changed_plan(state).difference(full_new)
    protected = playable_domain(scene.scratch / "barriers.csv", sample(old, 1041))
    apron = t1_apron(source, new, protected, full_new).difference(raised)
    pit = (
        legacy_paving(
            floors, band(road_interval(old, 470, 870), 1.21, 23.5, 1), "Runoff"
        )
        .difference(full_new)
        .difference(raised)
    )
    t16 = (
        legacy_paving(
            floors, band(road_interval(old, 230, 370), 0.15, 13, 1), "RunoffGreen"
        )
        .difference(full_new)
        .difference(raised)
    )
    t3 = legacy_paving(
        floors, band(road_interval(old, 1330, 1505), 0.15, 18, -1), "Runoff"
    ).difference(full_old)
    t4 = (
        legacy_paving(
            floors, band(road_interval(old, 2600, 2820), 0.15, 18, -1), "RunoffGreen"
        )
        .difference(full_new)
        .difference(raised)
    )
    pit_fill = (
        half_road(road_interval(old, 470, 870), 1)
        .intersection(released)
        .difference(raised)
    )
    t16_fill = (
        half_road(road_interval(old, 345, 470), 1)
        .intersection(released)
        .difference(raised)
    )
    t4_fill = (
        half_road(road_interval(old, 2600, 2680), -1)
        .intersection(released)
        .difference(raised)
    )
    blue = (
        variable_band(new, source.t3_blue_widths_m, -1, 0.15)
        .intersection(protected.buffer(-0.25))
        .difference(full_new)
        .difference(raised)
    )
    gravel = (
        variable_band(new, source.t3_gravel_outer_reaches_m, -1, 1.34, True)
        .intersection(protected.buffer(-0.25))
        .difference(full_new)
        .difference(raised)
        .difference(blue)
    )
    t3_inner = (
        band(road_interval(new, 1370, 1475), 1.34, 2.6, 1)
        .difference(full_new)
        .difference(raised)
    )
    t16_inner_old = (
        legacy_green(floors, old, 260, 345, -1).difference(full_new).difference(raised)
    )
    t4_inner_old = (
        legacy_green(floors, old, 2650, 2780, 1).difference(full_new).difference(raised)
    )
    t16_inner_fill = (
        half_road(road_interval(old, 304, 345), -1)
        .intersection(released)
        .difference(raised)
    )
    t4_inner_fill = (
        half_road(road_interval(old, 2650, 2680), 1)
        .intersection(released)
        .difference(raised)
    )
    flat = unary_union(
        [
            pit,
            t16,
            t4,
            pit_fill,
            t16_fill,
            t4_fill,
            blue,
            apron,
            t3_inner,
            t16_inner_old,
            t4_inner_old,
            t16_inner_fill,
            t4_inner_fill,
        ]
    )
    drain = unary_union(
        [
            band(road_interval(new, source.start_m, source.end_m), 0.15, 0.45, s)
            for s in (-1, 1)
        ]
    )
    drain = (
        drain.difference(full_new)
        .difference(raised)
        .difference(flat)
        .difference(gravel)
    )
    old_t3_inner = legacy_green(floors, old, 1370, 1475, 1)
    grass = (
        unary_union([released, t3, old_t3_inner, old_curbs])
        .difference(full_new)
        .difference(raised)
        .difference(flat)
        .difference(gravel)
        .difference(drain)
    )
    candidates = [
        SurfaceRole("T1 flat green apron", "RunoffGreen", apron, "paved"),
        SurfaceRole("T3 blue paved crescent", "RunoffBlue", blue, "paved"),
        SurfaceRole("T3 outer gravel", "Gravel", gravel, "gravel"),
        SurfaceRole("Restored natural verges and island", "Grass", grass, "grass"),
        SurfaceRole("Narrow flat drain", "Runoff", drain, "paved"),
        SurfaceRole("T3 narrow inner green", "RunoffGreen", t3_inner, "paved"),
        SurfaceRole("Pit retained floor", "Runoff", pit, "paved", False),
        SurfaceRole("T16 retained outer floor", "RunoffGreen", t16, "paved", False),
        SurfaceRole("T4 retained outer floor", "RunoffGreen", t4, "paved", False),
        SurfaceRole(
            "T16 retained inner floor", "RunoffGreen", t16_inner_old, "paved", False
        ),
        SurfaceRole(
            "T4 retained inner floor", "RunoffGreen", t4_inner_old, "paved", False
        ),
        SurfaceRole("Pit connecting floor", "Runoff", pit_fill, "paved"),
        SurfaceRole("T16 connecting outer paint", "RunoffGreen", t16_fill, "paved"),
        SurfaceRole("T4 connecting outer paint", "RunoffGreen", t4_fill, "paved"),
        SurfaceRole(
            "T16 connecting inner paint", "RunoffGreen", t16_inner_fill, "paved"
        ),
        SurfaceRole("T4 connecting inner paint", "RunoffGreen", t4_inner_fill, "paved"),
    ]
    result = []
    claimed: BaseGeometry = Polygon()
    for role in candidates:
        plan = role.plan.difference(claimed)
        if plan.area > 1e-8:
            result.append(replace(role, plan=plan))
            claimed = unary_union([claimed, plan])
    return result


def polygon_parts(shape: BaseGeometry) -> list[Polygon]:
    if isinstance(shape, Polygon):
        return [shape]
    if isinstance(shape, (MultiPolygon, GeometryCollection)):
        return [part for child in shape.geoms for part in polygon_parts(child)]
    return []


def white_bars(
    road: tuple[RoadStation, ...],
    start: float,
    end: float,
    inner: float,
    outer: float,
    domain: BaseGeometry,
) -> BaseGeometry:
    shapes = []
    station = start
    while station < end:
        a, b, c, d = (
            sample(road, min(end, station + offset)) for offset in (0.0, 5.0, 12.0, 7.0)
        )
        shape = Polygon(
            [
                a.point(-inner)[:2],
                b.point(-inner)[:2],
                c.point(-outer)[:2],
                d.point(-outer)[:2],
            ]
        )
        if shape.is_valid:
            shapes.extend(polygon_parts(shape.intersection(domain)))
        station += 12
    return unary_union(shapes)


def under_curb_support(
    scene: CircuitScene, domain: BaseGeometry
) -> tuple[SurfaceFace, ...]:
    from venues.buddh_first_sector_rows import capture

    result = copy(scene)
    result.tiles = {}
    result._ground_normals = {}
    for shape, material, road in scene.verge_patches:
        if material != "Grass" or not shape.intersects(domain):
            continue
        piece = shape.intersection(domain)
        if piece.area > 1e-9:
            result.polygon_surface(piece, "Grass", sample=road, smooth_ground=True)
    return capture(result, domain, {"Grass"})


def line_parts(shape: BaseGeometry) -> list[LineString]:
    if isinstance(shape, LineString):
        return [shape]
    if isinstance(shape, (MultiLineString, GeometryCollection)):
        return [line for child in shape.geoms for line in line_parts(child)]
    return []


def low_apron_closure(
    scene: MeshScene, floors: tuple[SurfaceFace, ...], apron: BaseGeometry
) -> tuple[float, float]:
    from venues.buddh_first_sector_rows import height

    road_faces = [source for source in floors if source.material == "Road"]
    road_plan = unary_union([source.plan for source in road_faces])
    seam = road_plan.boundary.intersection(apron)
    index = STRtree([source.plan for source in road_faces])
    emitted = []
    maximum = 0.0
    for source in floors:
        if source.material != "Grass":
            continue
        for line in line_parts(seam.intersection(source.plan.buffer(0.0001))):
            for a, b in pairwise(list(line.coords)):
                if math.dist(a, b) < 1e-6:
                    continue
                tops = []
                bottoms = []
                for x, y in (a, b):
                    road = road_faces[int(index.nearest(GeoPoint(x, y)))]
                    top = height(road, x, y) + 0.001
                    bottom = min(top - 0.002, height(source, x, y) - 0.001)
                    tops.append((x, y, top))
                    bottoms.append((x, y, bottom))
                    maximum = max(maximum, top - bottom)
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                right = GeoPoint(
                    (a[0] + b[0]) / 2 + dy / length * 0.002,
                    (a[1] + b[1]) / 2 - dx / length * 0.002,
                )
                if road_plan.covers(right):
                    tops.reverse()
                    bottoms.reverse()
                scene.quad(
                    "Tile_BuddhLowDrain",
                    "Concrete",
                    bottoms[0],
                    bottoms[1],
                    tops[1],
                    tops[0],
                )
                emitted.append(LineString([a, b]))
    missing = seam.difference(unary_union(emitted).buffer(0.0003)).length
    if missing > 0.01:
        raise ValueError(
            f"The actual T1 apron leaves {missing:.6f} m without a low drain closure"
        )
    return maximum, missing


def project_roles(
    scene: MeshScene,
    regions: list[SurfaceRole],
    floors: tuple[SurfaceFace, ...],
    candidate: tuple[RoadStation, ...],
) -> tuple[tuple[ContactTriangle, ...], int]:
    from venues.buddh_first_sector_rows import height, interpolate, partitions

    source_parts = partitions(floors)
    contact = []
    count = 0
    for role in regions:
        print(f"Projecting {role.name}: {role.plan.area:.3f} square metres", flush=True)
        prepare_geometry(role.plan)
        local_masks: dict[tuple[int, int, int, int], BaseGeometry] = {}
        covered = []
        bars: BaseGeometry = Polygon()
        if role.name == "T1 flat green apron":
            bars = white_bars(candidate, 1010, 1100, 9, 22, role.plan)
        if role.name == "T4 retained outer floor":
            bars = white_bars(candidate, 2600, 2750, 14, 31, role.plan)
        for source, plan in source_parts:
            if not role.plan.intersects(plan):
                continue
            x0, y0, x1, y1 = plan.bounds
            key = (
                math.floor(x0 / 64),
                math.floor(y0 / 64),
                math.floor(x1 / 64) + 1,
                math.floor(y1 / 64) + 1,
            )
            if key not in local_masks:
                local_masks[key] = role.plan.intersection(box(*(v * 64 for v in key)))
            piece = unary_union(polygon_parts(plan.intersection(local_masks[key])))
            if piece.area < 1e-10:
                continue
            covered.append(piece)
            shift = 0.001 if role.rebuild else 0.0
            if role.contact in ("grass", "gravel"):
                shift = (
                    -0.021
                    if source.material == "Road"
                    else (
                        -0.016 if source.material in ("Runoff", "RunoffGreen") else 0.0
                    )
                )
            painted = (
                [(role.material, piece)]
                if bars.is_empty
                else [
                    (role.material, piece.difference(bars)),
                    ("White", piece.intersection(bars)),
                ]
            )
            for material, part in painted:
                for triangle in constrained_delaunay_triangles(part).geoms:
                    xy = list(triangle.exterior.coords)[:3]
                    if not triangle.exterior.is_ccw:
                        xy.reverse()
                    points = [(x, y, height(source, x, y) + shift) for x, y in xy]
                    a, b, c = points
                    if role.rebuild:
                        normals = [interpolate(source, x, y) for x, y in xy]
                        tile = scene.tile(
                            "Tile_BuddhFirstSector",
                            cast(
                                Point,
                                tuple(sum(p[j] for p in points) / 3 for j in range(3)),
                            ),
                        )
                        before = len(tile.triangles)
                        scene.triangle(
                            "Tile_BuddhFirstSector",
                            material,
                            a,
                            b,
                            c,
                            tuple((x / 8, y / 8) for x, y in xy),
                            tuple((-v[4], -v[3], v[5]) for v in normals),
                        )
                        if len(tile.triangles) == before:
                            continue
                        packed = struct.unpack_from("<I24f", tile.triangles, before)
                        points = [
                            (
                                -packed[2 + i * 8] / 100,
                                -packed[1 + i * 8] / 100,
                                packed[3 + i * 8] / 100,
                            )
                            for i in range(3)
                        ]
                        count += 1
                    lift = 0.001 if role.rebuild and role.contact == "paved" else 0.0
                    physical = cast(
                        tuple[Point, Point, Point],
                        tuple((p[0], p[1], p[2] - lift) for p in points),
                    )
                    support = cast(
                        tuple[Point, Point, Point],
                        tuple((x, y, z + shift - lift) for x, y, z in source.points),
                    )
                    contact.append(ContactTriangle(physical, role.contact, support))
        missing = role.plan.difference(unary_union(covered).buffer(0.0003)).area
        if missing > 0.01:
            raise ValueError(
                f"{role.name} lacks {missing:.6f} square metres of actual source support"
            )
    return tuple(contact), count


def finish_terrain(scene: CircuitScene, state: FirstSectorState) -> FirstSectorResult:
    from venues.buddh_first_sector_rows import (
        FLOOR_MATERIALS,
        add_raw,
        append,
        capture,
        face,
        fragments,
        lookup,
        rows,
    )

    old_template, old_curbs = curb_template(scene, state, True)
    new_template, new_curbs = curb_template(scene, state, False)
    old_curb_plan = unary_union([source.plan for source in old_curbs])
    raised = unary_union([source.plan for source in new_curbs])
    road_change = changed_plan(state)
    broad = LineString(
        [(p.x, p.y) for p in road_interval(state.retained_road, 230, 2820)]
    ).buffer(55)
    floors = capture(scene, broad, FLOOR_MATERIALS)
    missing_under_curb = unary_union(old_template.terrain_cutouts).difference(
        unary_union([source.plan for source in floors])
    )
    support = under_curb_support(scene, missing_under_curb)
    floors = (*floors, *support)
    regions = roles(scene, state, raised, old_curb_plan, floors)
    # Repaint the retained T4 apron without moving its physical boundary.
    regions = [
        replace(role, rebuild=True) if role.name == "T4 retained outer floor" else role
        for role in regions
    ]
    rebuilt = unary_union([role.plan for role in regions if role.rebuild])
    if any(
        a.plan.intersection(b.plan).area > 1e-7
        for i, a in enumerate(regions)
        for b in regions[:i]
    ):
        raise ValueError("First-sector source roles overlap before replacement")
    output = MeshScene()
    contact, emitted = project_roles(output, regions, floors, state.candidate_road)
    old_replay = MeshScene()
    emit_road(
        old_replay,
        state.retained_road,
        scene.length,
        0,
        scene.length,
        cells=set(state.changed_cells),
    )
    remove_road = rows(old_replay, "Road")
    remove_curbs = Counter((source.material, source.raw[4:]) for source in old_curbs)
    actual_curbs = Counter(
        {("Red", raw): count for raw, count in rows(scene, "Red").items()}
    )
    actual_curbs.update(
        {("White", raw): count for raw, count in rows(scene, "White").items()}
    )
    if remove_road - rows(scene, "Road") or remove_curbs - actual_curbs:
        raise ValueError(
            "The actual retained road/curb producer differs before any replacement"
        )
    paint_remove = unary_union(
        [
            road_change,
            old_curb_plan,
            band(road_interval(state.retained_road, 1330, 1505), 0.15, 18, -1),
        ]
    )
    processing = unary_union([rebuilt, paint_remove])
    prepare_geometry(rebuilt)
    prepare_geometry(paint_remove)
    prepare_geometry(processing)
    changed = []
    retained_splits = []
    preserved = split = removed_road = removed_curb = 0
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
        if not processing.intersects(bounds):
            preserved += len(tile.triangles) // 100
            continue
        data = bytearray()
        touched = False
        for offset in range(0, len(tile.triangles), 100):
            raw = bytes(tile.triangles[offset : offset + 100])
            material = tile.materials[struct.unpack_from("<I", raw)[0]]
            if material == "Road" and remove_road[raw[4:]]:
                remove_road[raw[4:]] -= 1
                removed_road += 1
                touched = True
                continue
            if material == "Road":
                data.extend(raw)
                preserved += 1
                continue
            if remove_curbs[(material, raw[4:])]:
                remove_curbs[(material, raw[4:])] -= 1
                removed_curb += 1
                touched = True
                continue
            if material not in FLOOR_MATERIALS | {"White", "Red", "RunoffBlue"}:
                data.extend(raw)
                preserved += 1
                continue
            source = face(tile, name, offset)
            if source.plan.area < 1e-10 or min(v[5] for v in source.vertices) < 0.05:
                data.extend(raw)
                preserved += 1
                continue
            mask = (
                paint_remove if material in ("White", "Red", "RunoffBlue") else rebuilt
            )
            if not mask.intersects(source.plan):
                data.extend(raw)
                preserved += 1
                continue
            overlap = source.plan.intersection(mask)
            if overlap.area < 1e-9:
                data.extend(raw)
                preserved += 1
                continue
            owner_fragments = []
            for vertices in fragments(source, source.plan.difference(mask)):
                append(data, tile, material, vertices)
                owner_fragments.append(bytes(data[-100:]))
            retained_splits.append(
                RetainedSplitOwner(name, offset, raw, tuple(owner_fragments))
            )
            touched = True
            split += 1
        if touched:
            tile.triangles = data
            changed.append(name)
    if any(remove_road.values()) or any(remove_curbs.values()):
        raise ValueError(
            "Actual emitted road/curb rows differ from the qualified retained producer"
        )
    emit_road(
        scene,
        state.candidate_road,
        scene.length,
        0,
        scene.length,
        cells=set(state.changed_cells),
    )
    # Keep the established corrected T1 edge path for the new white lines as well.
    white = capture(new_template, road_change, {"White"})
    curb_rows = {(source.tile_name, source.offset) for source in new_curbs}
    for source in white:
        if (source.tile_name, source.offset) in curb_rows:
            continue
        tile = scene.tiles.setdefault(source.tile_name, MeshTile())
        for vertices in fragments(source, source.plan.intersection(road_change)):
            append(tile.triangles, tile, "White", vertices)
    for name, tile in output.tiles.items():
        for offset in range(0, len(tile.triangles), 100):
            add_raw(scene, face(tile, name, offset))
    apron = next(role.plan for role in regions if role.name == "T1 flat green apron")
    closure_height, closure_missing = low_apron_closure(scene, floors, apron)
    for source in new_curbs:
        add_raw(scene, source)
    final_floors = capture(scene, raised.buffer(0.02), FLOOR_MATERIALS | {"RunoffBlue"})
    source_height = lookup(final_floors)
    curb_height = lookup(new_curbs)
    for polygon in polygon_parts(raised):
        polygon = orient(polygon)
        for ring in (polygon.exterior, *polygon.interiors):
            for a, b in pairwise(list(ring.coords)):
                tops = [(x, y, curb_height(x, y)) for x, y in (a, b)]
                bottoms = [
                    (x, y, min(z - 0.005, source_height(x, y) - 0.005))
                    for x, y, z in tops
                ]
                scene.quad(
                    "Tile_BuddhCurbSupport",
                    "Concrete",
                    bottoms[0],
                    bottoms[1],
                    tops[1],
                    tops[0],
                )
    contact = (
        *contact,
        *(ContactTriangle(source.points, "paved") for source in new_curbs),
    )
    scene.road = list(state.candidate_road)
    scene.road_mask = new_template.road_mask
    return FirstSectorResult(
        tuple(contact),
        tuple(changed),
        preserved,
        split,
        removed_road,
        removed_curb,
        emitted,
        missing_under_curb.area,
        {role.name: role.plan.area for role in regions},
        unary_union([processing, raised]),
        closure_height,
        closure_missing,
        tuple(retained_splits),
    )
