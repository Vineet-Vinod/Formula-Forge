"""The Niyazi Street concert hall, with its rotunda and two roof belvederes."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon

from venues.east_architecture import frame
from venues.west_architecture import dome


def philharmonic_hall(scene: CircuitScene) -> None:
    building = scene.footprint(152190848)
    original = Polygon(building.ring)
    footprint = original.difference(scene.road_mask.buffer(1.2))
    if not isinstance(footprint, Polygon) or footprint.is_empty:
        raise ValueError("Philharmonic must retain its mapped hall outline")
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(footprint)
    base = min(scene.ground(x, y) for x, y in building.ring)
    center, axis, side, _, _ = frame(building)
    height = 11.5
    kind = "Building_Philharmonic"
    ring = list(footprint.exterior.coords)
    if not footprint.exterior.is_ccw:
        ring.reverse()
    for a, b in pairwise(ring):
        span = math.dist(a, b)
        if span < .15:
            continue
        tangent = ((b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.0)
        normal = tangent[1], -tangent[0], 0.0
        pa, pb = (*a, base), (*b, base)
        scene.banner(pa, pb, height, "BakuPhilharmonicOchre", kind)
        for z, breadth in ((.4, .28), (5.3, .38), (9.6, .25), (11.4, .55)):
            scene.beam(kind, "White", add(pa, (0, 0, z)), add(pb, (0, 0, z)), breadth, .32)
        bays = max(1, round(span / 4.0))
        for bay in range(bays):
            offset = (bay + .5) * span / bays
            c = add(add(pa, mul(tangent, offset)), mul(normal, .08))
            width = min(2.35, span / bays * .59)
            for z, window_height in ((.7, 3.8), (6.1, 2.6)):
                left = add(c, add(mul(tangent, -width / 2), (0, 0, z)))
                right = add(left, mul(tangent, width))
                scene.banner(left, right, window_height, "Glass", kind)
                for p in (left, right):
                    scene.beam(kind, "White", p, add(p, (0, 0, window_height)), .2)
                spring = z + window_height
                last = add(c, add(mul(tangent, -width / 2), (0, 0, spring)))
                for step in range(1, 13):
                    angle = math.pi * (1 - step / 12)
                    point = add(c, add(mul(tangent, math.cos(angle) * width / 2),
                                       (0, 0, spring + math.sin(angle) * .7)))
                    scene.beam(kind, "White", last, point, .18)
                    last = point
            column = add(add(pa, mul(tangent, span * bay / bays)), mul(normal, .16))
            scene.beam(kind, "White", add(column, (0, 0, .4)), add(column, (0, 0, 10.9)), .35)
        if span > 3:
            scene.beam(kind, "White", add(pa, (0, 0, 12.15)), add(pb, (0, 0, 12.15)), .22)
            count = max(1, round(span / .7))
            for post in range(count + 1):
                p = add(pa, add(mul(tangent, span * post / count), (0, 0, 11.55)))
                scene.beam(kind, "White", p, add(p, (0, 0, .6)), .12)
    for triangle in constrained_delaunay_triangles(footprint).geoms:
        points: list[Point] = [(*p, base + height) for p in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            points.reverse()
        scene.triangle(kind, "Roof", points[0], points[1], points[2])

    def location(u: float, v: float, z: float) -> Point:
        return add(add((center[0], center[1], base + z), mul(axis, u)), mul(side, v))

    # The curved mapped rotunda is centred near local(12,4), independent of the long wing.
    dome_center = location(12, 4, height)
    dome(scene, dome_center, 14.0, 5.3, "Roof")
    for angle in range(0, 360, 15):
        a, b = math.radians(angle), math.radians(angle + 15)
        p = add(dome_center, (14 * math.cos(a), 14 * math.sin(a), 0))
        q = add(dome_center, (14 * math.cos(b), 14 * math.sin(b), 0))
        scene.beam(kind, "White", p, q, .28)
    for u, v in ((37, -23), (-35, -22)):
        tower_center = location(u, v, 0)
        square = [location(u + x, v + y, 0)[:2]
                  for x, y in ((-3.1, -3.1), (3.1, -3.1), (3.1, 3.1), (-3.1, 3.1))]
        if not original.buffer(.4).covers(Polygon(square)):
            raise ValueError("Philharmonic belvedere escaped its registered building")
        scene.box(kind, "BakuPhilharmonicOchre", add(tower_center, (0, 0, 14.2)), 6.2, 6.2, 5.4,
                  math.atan2(axis[1], axis[0]))
        for x, y in ((-2.8, -2.8), (2.8, -2.8), (2.8, 2.8), (-2.8, 2.8)):
            p = location(u + x, v + y, 16.8)
            scene.beam(kind, "White", p, add(p, (0, 0, 5.2)), .55)
        for a, b in pairwise(square + square[:1]):
            scene.beam(kind, "White", (*a, base + 16.9), (*b, base + 16.9), .5)
            scene.beam(kind, "White", (*a, base + 21.9), (*b, base + 21.9), .5)
            peak = location(u, v, 24.0)
            scene.triangle(kind, "Roof", (*a, base + 22.2), (*b, base + 22.2), peak)
        scene.beam(kind, "White", location(u, v, 24), location(u, v, 25.1), .15)
    scene.landmarks.append({
        "name": "Azerbaijan State Philharmonic Hall", "osm_id": building.osm_id,
        "wall_height_m": height, "belvedere_peak_m": base + 25.1,
        "body_footprint_area_m2": footprint.area, "road_registration_clip_m2": original.area - footprint.area,
        "source": "philharmonic-architecture.json. Actual OSM hall/rotunda outline; yellow Renaissance walls, white pilasters/arcades, balustrades, dome and twin open belvederes from the construction supervisor's published Niyazi Street photograph. Heights/roof sections are disclosed visual estimates, not measured elevations.",
    })
