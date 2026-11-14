"""Larvotto arch. The valley height field remains separate and untouched."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, norm
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.monaco_dataclasses import BridgeFrame, BridgeProfile, LarvottoBridge

XY = tuple[float, float]
Edge = tuple[XY, XY]


def distance(frame: BridgeFrame, point: XY) -> float:
    return sum((p - o) * a for p, o, a in zip(point, frame.origin, frame.axis, strict=True))


def heights(profile: BridgeProfile, point: XY) -> tuple[float, float]:
    span = profile.frame.span
    station = min(span, max(0., distance(profile.frame, point)))
    deck = profile.east_relative_m + (profile.west_relative_m - profile.east_relative_m) * station / span
    radius = ((span / 2) ** 2 + profile.arch_rise_m ** 2) / (2 * profile.arch_rise_m)
    arch = math.sqrt(max(0., radius ** 2 - (station - span / 2) ** 2)) - (radius - profile.arch_rise_m)
    underside = deck - profile.crown_thickness_m - profile.arch_rise_m + arch
    return deck, underside


def underside_normal(profile: BridgeProfile, point: XY) -> Point:
    station = min(profile.frame.span, max(0., distance(profile.frame, point)))
    offset = station - profile.frame.span / 2
    radius = ((profile.frame.span / 2) ** 2 + profile.arch_rise_m ** 2) / (2 * profile.arch_rise_m)
    slope = ((profile.west_relative_m - profile.east_relative_m) / profile.frame.span
             - offset / math.sqrt(radius ** 2 - offset ** 2))
    return norm((profile.frame.axis[0] * slope, profile.frame.axis[1] * slope, -1.))


def split_plan(footprint: Polygon, frame: BridgeFrame, interval: float) -> list[Polygon]:
    if interval <= 0 or interval > 1:
        raise ValueError('The visible arch requires subdivisions at most one metre apart')
    tx, ty = frame.axis
    nx, ny = -ty, tx
    distances = [distance(frame, (x, y)) for x, y in footprint.exterior.coords]
    lower, upper = min(distances), max(distances)
    count = math.ceil((upper - lower) / interval)
    parts = []
    for index in range(count):
        a = lower + (upper - lower) * index / count - (1e-9 if index == 0 else 0)
        b = lower + (upper - lower) * (index + 1) / count + (1e-9 if index == count - 1 else 0)
        corners = [(frame.origin[0] + tx * s + nx * w, frame.origin[1] + ty * s + ny * w)
                   for s, w in ((a, -40.), (b, -40.), (b, 40.), (a, 40.))]
        section = footprint.intersection(Polygon(corners))
        if not isinstance(section, Polygon) or section.is_empty:
            raise ValueError('Every bridge section must remain one connected mapped strip')
        parts.append(section)
    return parts


def larvotto_bridge(scene: MeshScene, config: LarvottoBridge,
                    geo: Callable[[float, float], XY], datum: float) -> dict[str, float]:
    footprint = orient(Polygon([geo(lat, lon) for lon, lat in config.outline_wgs84]), sign=1.)
    centerline = [geo(lat, lon) for lon, lat in config.centerline_wgs84]
    east, west = centerline[0], centerline[-1]
    span = math.dist(east, west)
    frame = BridgeFrame(east, ((west[0] - east[0]) / span, (west[1] - east[1]) / span), span)
    profile = BridgeProfile(frame, config.east_deck_absolute_m - datum,
                            config.west_deck_absolute_m - datum, config.crown_thickness_m, config.arch_rise_m)
    if not footprint.is_valid or not 90 < span < 110 or not .5 < config.crown_thickness_m < 2:
        raise ValueError('The bridge must retain its qualified footprint, span and thin arch crown')
    edges: Counter[Edge] = Counter()
    directed: dict[Edge, Edge] = {}
    sections = split_plan(footprint, frame, config.sample_interval_m)
    for section in sections:
        for triangle in constrained_delaunay_triangles(section).geoms:
            xy = [(round(x, 9), round(y, 9)) for x, y in list(orient(triangle, sign=1.).exterior.coords)[:3]]
            top = [(x, y, heights(profile, (x, y))[0]) for x, y in xy]
            bottom = [(x, y, heights(profile, (x, y))[1]) for x, y in xy]
            scene.triangle('Building_LarvottoDeck', 'Runoff', top[0], top[1], top[2],
                           tuple((p[0] / 8, p[1] / 8) for p in top))
            normals = [underside_normal(profile, p) for p in xy]
            scene.triangle('Building_LarvottoArch', 'Concrete', bottom[2], bottom[1], bottom[0],
                           normals=(normals[2], normals[1], normals[0]))
            for a, b in pairwise([*xy, xy[0]]):
                key = (a, b) if a < b else (b, a)
                edges[key] += 1
                directed[key] = a, b
    boundary = [directed[edge] for edge, count in edges.items() if count == 1]
    if any(count > 2 for count in edges.values()):
        raise ValueError('Bridge strips must form one non-overlapping shell')
    parapet_length = 0.
    for a, b in boundary:
        za, ua = heights(profile, a)
        zb, ub = heights(profile, b)
        scene.quad('Building_LarvottoArch', 'Concrete', (*a, ua), (*b, ub), (*b, zb), (*a, za))
        along = abs(distance(frame, b) - distance(frame, a))
        if along < math.dist(a, b) * .6:
            continue
        # The photographed low concrete curb and slender handrail follow both long sides.
        edge_length = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / edge_length, (b[0] - a[0]) / edge_length
        inward_a = a[0] + nx * config.parapet_thickness_m / 2, a[1] + ny * config.parapet_thickness_m / 2
        inward_b = b[0] + nx * config.parapet_thickness_m / 2, b[1] + ny * config.parapet_thickness_m / 2
        ta, tb = za + .31, zb + .31
        scene.beam('Building_LarvottoParapet', 'Concrete', (*inward_a, (za + ta) / 2),
                   (*inward_b, (zb + tb) / 2), config.parapet_thickness_m, .31)
        scene.beam('Building_LarvottoHandrail', 'Steel', (*inward_a, za + config.parapet_height_m),
                   (*inward_b, zb + config.parapet_height_m), .055, .055)
        parapet_length += math.dist(a, b)
    # Posts are spaced by station on both mapped edges, rather than one per half-metre mesh strip.
    for a, b in boundary:
        sa, sb = distance(frame, a), distance(frame, b)
        edge_length = math.dist(a, b)
        if abs(sb - sa) < edge_length * .6:
            continue
        nx, ny = -(b[1] - a[1]) / edge_length, (b[0] - a[0]) / edge_length
        first = math.ceil(min(sa, sb) / 3.2)
        last = math.floor((max(sa, sb) - 1e-8) / 3.2)
        for index in range(first, last + 1):
            t = (index * 3.2 - sa) / (sb - sa)
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            x += nx * config.parapet_thickness_m / 2
            y += ny * config.parapet_thickness_m / 2
            z = heights(profile, (x, y))[0]
            scene.beam('Building_LarvottoHandrail', 'Steel', (x, y, z + .31),
                       (x, y, z + config.parapet_height_m), .055, .055)
    return {'mapped_plan_area_m2': footprint.area, 'arch_chord_m': span,
            'section_count': float(len(sections)), 'parapet_length_m': parapet_length,
            'east_deck_absolute_m': config.east_deck_absolute_m,
            'west_deck_absolute_m': config.west_deck_absolute_m}
