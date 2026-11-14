"""Sepang's legal lane and the separately retained wider asphalt envelope."""

from __future__ import annotations

import csv
import gzip
import hashlib
import math
from collections.abc import Callable

from circuit_dataclasses import RoadStation
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.malaysia_dataclasses import PavementWidths

KerbRanges = tuple[tuple[float, float, int], ...]


def former_half_width(scene: CircuitScene) -> Callable[[float], float]:
    profile = TypeAdapter(PavementWidths).validate_json(
        (scene.sources / 'pavement-widths.json').read_bytes()
    )
    payload = gzip.decompress((scene.sources / profile.baseline_road_file).read_bytes())
    if hashlib.sha256(payload).hexdigest() != profile.baseline_road_sha256:
        raise ValueError('Sepang paving requires the retained native width lattice')
    rows = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(payload.decode().splitlines())))
    if len(rows) != len(scene.road) or any(p.half_width < 8 for p in rows):
        raise ValueError('Sepang paving must contain the complete 16 m racing lane')

    def sample(station: float) -> float:
        position = (station % scene.length) / scene.length * len(rows)
        index = min(int(position), len(rows) - 1)
        a, b = rows[index], rows[(index + 1) % len(rows)]
        t = position - index
        return a.half_width * (1 - t) + b.half_width * t

    return sample


def apron_fraction(station: float, side: int, length: float, kerbs: KerbRanges) -> float:
    fraction = 1.
    for start, end, kerb_side in kerbs:
        if side != kerb_side:
            continue
        progress = (station - start) % length
        span = (end - start) % length
        if progress <= span:
            return 0.
        distance = min(length - progress, progress - span)
        t = min(1., distance / 20)
        fraction = min(fraction, t * t * (3 - 2 * t))
    return fraction


def paved_margins(scene: CircuitScene, kerbs: KerbRanges) -> None:
    half_width = former_half_width(scene)
    count = math.ceil(scene.length / 2)
    for index in range(count):
        a, b = scene.at(scene.length * index / count), scene.at(scene.length * (index + 1) / count)
        for side in (-1, 1):
            edge_a, edge_b = a.half_width + .15, b.half_width + .15
            outer_a = edge_a + max(0., half_width(a.station) - a.half_width) * apron_fraction(a.station, side, scene.length, kerbs)
            outer_b = edge_b + max(0., half_width(b.station) - b.half_width) * apron_fraction(b.station, side, scene.length, kerbs)
            if max(outer_a - edge_a, outer_b - edge_b) < .0001:
                continue
            points = [a.point(side * edge_a), b.point(side * edge_b),
                      b.point(side * outer_b), a.point(side * outer_a)]
            shape = Polygon([p[:2] for p in points])
            if shape.is_valid and shape.area > 1e-8:
                patch = shape.difference(scene.road_mask)
                scene.extra_corridors.append(patch)
                scene.polygon_surface(patch, 'Runoff', .001, a, paved=True)
    scene.landmarks.append({'name': 'Sepang 16 m legal lane and separate asphalt margins',
                            'legal_width_m': 16,
                            'pavement_status': 'The primary designer specifies constant 16 m white-line width after 2016. The previous 16–22 m width estimates are retained only as a separate wider paving envelope, with inside kerb/grass islands kept clear. Exact pavement limits and 20 m apron tapers remain visual reconstructions, not surveyed road edges.'})


def physical_runoff(scene: CircuitScene, start: float, end: float, side: int,
                    width: float, material: str) -> None:
    half_width = former_half_width(scene)
    span = (end - start) % scene.length
    count = max(1, math.ceil(span / 2))
    support_count = max(1, math.ceil(span / 2))
    for index in range(support_count):
        first, last = start + span * index / support_count, start + span * (index + 1) / support_count
        samples = [first + (last - first) * j / 8 for j in range(9)]
        extra = max(half_width(s) - scene.at(s).half_width for s in samples)
        scene.surface_ranges.append({'type': 'runoff', 'start_m': first, 'end_m': last,
                                     'side': side, 'requested_width_m': width + extra,
                                     'material': material})
    for index in range(count):
        a, b = scene.at(start + span * index / count), scene.at(start + span * (index + 1) / count)
        # The former outer white-line estimate now separates paving from the retained escape.
        points = [a.point(side * (half_width(a.station) + .15)),
                  b.point(side * (half_width(b.station) + .15)),
                  b.point(side * (half_width(b.station) + width)),
                  a.point(side * (half_width(a.station) + width))]
        shape = Polygon([p[:2] for p in points])
        if shape.is_valid and shape.area > 1e-8:
            scene.extra_corridors.append(shape)
            scene.polygon_surface(shape.difference(scene.surface_mask(a)), material, .001, a, paved=True)
