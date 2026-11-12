"""Retain source-registered openings in otherwise closed physical/visible protection."""
from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import (
    BarrierSegment,
    ProtectionOpening,
    ProtectionOpenings,
    RoadStation,
)
from pydantic import TypeAdapter

NearestRoad = Callable[[float, float], tuple[RoadStation, float]]


def load_openings(source: Path, length: float) -> list[ProtectionOpening]:
    path = source / 'protection-openings.json'
    if not path.exists():
        return []
    sections = TypeAdapter(ProtectionOpenings).validate_json(path.read_bytes()).sections
    for section in sections:
        xmin, ymin, xmax, ymax = section.bounds_xy_m
        if not (0 <= section.start_m < section.end_m <= length and xmin < xmax and ymin < ymax):
            raise ValueError('Protection opening must have ordered lap stations and XY bounds')
    return sections


def filter_barriers(
    walls: list[BarrierSegment], sections: list[ProtectionOpening], nearest: NearestRoad,
) -> list[BarrierSegment]:
    if not sections:
        return walls
    result: list[BarrierSegment] = []
    for wall in walls:
        ax, ay, bx, by, bottom, top, radius = wall
        candidates = [section for section in sections
                      if max(ax, bx) >= section.bounds_xy_m[0]
                      and max(ay, by) >= section.bounds_xy_m[1]
                      and min(ax, bx) <= section.bounds_xy_m[2]
                      and min(ay, by) <= section.bounds_xy_m[3]]
        if not candidates:
            result.append(wall)
            continue

        def point(t: float, segment: BarrierSegment = wall) -> tuple[float, float]:
            return (segment[0] + (segment[2] - segment[0]) * t,
                    segment[1] + (segment[3] - segment[1]) * t)

        def matched(
            t: float, openings: tuple[ProtectionOpening, ...] = tuple(candidates),
            at: Callable[[float], tuple[float, float]] = point,
        ) -> bool:
            x, y = at(t)
            road, distance = nearest(x, y)
            lane = (x - road.x) * road.ty - (y - road.y) * road.tx
            for section in openings:
                xmin, ymin, xmax, ymax = section.bounds_xy_m
                if (xmin <= x <= xmax and ymin <= y <= ymax
                        and section.start_m <= road.station <= section.end_m
                        and (lane > 0) == (section.side > 0)
                        and distance - road.half_width <= section.max_edge_offset_m):
                    return True
            return False

        cuts = {0.0, 1.0}
        road_a, distance_a = nearest(ax, ay)
        road_b, distance_b = nearest(bx, by)
        for section in candidates:
            for station in (section.start_m, section.end_m):
                if min(road_a.station, road_b.station) < station < max(road_a.station, road_b.station):
                    lo, hi = 0.0, 1.0
                    ascending = road_b.station > road_a.station
                    for _ in range(32):
                        mid = (lo + hi) / 2
                        if (nearest(*point(mid))[0].station < station) == ascending:
                            lo = mid
                        else:
                            hi = mid
                    cuts.add((lo + hi) / 2)
            for origin, delta, bounds in (
                (ax, bx - ax, section.bounds_xy_m[::2]),
                (ay, by - ay, section.bounds_xy_m[1::2]),
            ):
                if delta:
                    cuts.update(t for bound in bounds if 0 < (t := (bound - origin) / delta) < 1)
            edge_a = distance_a - road_a.half_width - section.max_edge_offset_m
            edge_b = distance_b - road_b.half_width - section.max_edge_offset_m
            if edge_a * edge_b < 0:
                lo, hi = 0.0, 1.0
                for _ in range(32):
                    mid = (lo + hi) / 2
                    road, distance = nearest(*point(mid))
                    if (distance - road.half_width - section.max_edge_offset_m > 0) == (edge_a > 0):
                        lo = mid
                    else:
                        hi = mid
                cuts.add((lo + hi) / 2)
        positions = sorted(cuts)
        keep = [not matched((a + b) / 2) for a, b in pairwise(positions)]
        if all(keep):
            result.append(wall)
            continue
        retained_ranges: list[tuple[float, float]] = []
        for a, b, retained in zip(positions, positions[1:], keep):
            if not retained or b - a <= 1e-8:
                continue
            if retained_ranges and abs(retained_ranges[-1][1] - a) < 1e-8:
                retained_ranges[-1] = retained_ranges[-1][0], b
            else:
                retained_ranges.append((a, b))
        for a, b in retained_ranges:
            pa, pb = point(a), point(b)
            result.append((*pa, *pb, bottom, top, radius))
    return result
