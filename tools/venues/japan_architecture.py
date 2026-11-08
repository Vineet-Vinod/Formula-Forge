"""Suzuka's permanent grass-bank seating, distinct from steel grandstands."""

from __future__ import annotations

import math
from itertools import pairwise
from statistics import mean

from circuit_dataclasses import Point
from circuit_mesh import add, cross, mul, sub
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as GeoPoint
from shapely.geometry.base import BaseGeometry

from venues.east_architecture import frame


def earthbank_seating(scene: CircuitScene, osm_id: int, rows: int) -> None:
    building = scene.footprint(osm_id)
    shape = Polygon(building.ring)
    center, axis, outward, length, width = frame(building)
    road, _ = scene.nearest(*center[:2])
    if (center[0] - road.x) * outward[0] + (center[1] - road.y) * outward[1] < 0:
        outward = mul(outward, -1)
    front = add(center, mul(outward, -width / 2))
    positions = [length * (index / 8 - 0.5) for index in range(9)]
    fronts = [add(front, mul(axis, along)) for along in positions]
    backs = [add(point, mul(outward, width)) for point in fronts]
    front_heights = [scene.ground(*point[:2]) for point in fronts]
    back_heights = [scene.ground(*point[:2]) for point in backs]
    front_mean, back_mean = mean(front_heights), mean(back_heights)
    denominator = sum(along * along for along in positions)
    grade = (
        sum(
            along * (low + high) / 2
            for along, low, high in zip(positions, front_heights, back_heights)
        )
        / denominator
    )
    rise = max(0.0, back_mean - front_mean)

    def position(along: float, across: float) -> Point:
        return add(add(front, mul(axis, along)), mul(outward, across))

    def bank_height(x: float, y: float) -> float:
        along = (x - front[0]) * axis[0] + (y - front[1]) * axis[1]
        across = (x - front[0]) * outward[0] + (y - front[1]) * outward[1]
        plane = front_mean + grade * along + rise * across / width
        blend = min(1.0, shape.boundary.distance(GeoPoint(x, y)) / 1.2)
        return scene.ground(x, y) * (1 - blend) + plane * blend

    def surface(piece: BaseGeometry, kind: str, material: str, lift: float) -> None:
        for triangle in constrained_delaunay_triangles(piece).geoms:
            points = [
                (x, y, bank_height(x, y) + lift)
                for x, y in list(triangle.exterior.coords)[:3]
            ]
            if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                points.reverse()
            scene.triangle(kind, material, points[0], points[1], points[2])

    # Grade only the retained seating footprint; its perimeter meets existing soil.
    scene.terrain_cutouts.append(shape)
    bays = math.ceil(length / 3)
    for bay in range(bays):
        start = -length / 2 + length * bay / bays
        end = -length / 2 + length * (bay + 1) / bays
        for row in range(rows):
            low, high = width * row / rows, width * (row + 1) / rows
            cell = Polygon(
                [
                    point[:2]
                    for point in (
                        position(start, low),
                        position(end, low),
                        position(end, high),
                        position(start, high),
                    )
                ]
            ).intersection(shape)
            surface(cell, "Building_JapanEarthbank", "Grass", 0.005)
    bench_mask = shape.buffer(-0.45)
    for row in range(rows):
        across = width * (row + 0.5) / rows
        start, end = -length / 2 + 1.5, length / 2 - 1.5
        bench = Polygon(
            [
                point[:2]
                for point in (
                    position(start, across - 0.12),
                    position(end, across - 0.12),
                    position(end, across + 0.12),
                    position(start, across + 0.12),
                )
            ]
        ).intersection(bench_mask)
        surface(bench, "Building_JapanBankBench", "Concrete", 0.15)
        polygons = [bench] if isinstance(bench, Polygon) else list(bench.geoms)
        for polygon in polygons:
            if not isinstance(polygon, Polygon):
                continue
            ring = list(polygon.exterior.coords)
            for pa, pb in pairwise(ring):
                a = pa[0], pa[1], bank_height(*pa) + 0.15
                b = pb[0], pb[1], bank_height(*pb) + 0.15
                scene.quad(
                    "Building_JapanBankBenchEdge",
                    "Concrete",
                    add(a, (0, 0, -0.15)),
                    add(b, (0, 0, -0.15)),
                    b,
                    a,
                )
        crowd_line = LineString(
            [position(start, across)[:2], position(end, across)[:2]]
        ).intersection(bench_mask)
        lines = (
            [crowd_line]
            if isinstance(crowd_line, LineString)
            else list(crowd_line.geoms)
        )
        for line in lines:
            if not isinstance(line, LineString) or line.length < 1:
                continue
            pa, pb = line.coords[0], line.coords[-1]
            scene.spectators(
                (pa[0], pa[1], bank_height(*pa) + 0.2),
                (pb[0], pb[1], bank_height(*pb) + 0.2),
                row,
                "Building_Crowd_JapanBank",
            )
    scene.modeled_buildings.add(osm_id)
    scene.landmarks.append(
        {
            "name": "G-2 permanent grass-bank seating",
            "osm_id": osm_id,
            "station_m": road.station,
            "rows": rows,
            "front_ground_mean_m": front_mean,
            "rear_ground_mean_m": back_mean,
            "longitudinal_grade": grade,
            "registration": "Official Suzuka G seating map and permanent G panorama: grass between thin pale concrete benches. Exact mapped footprint retained; linear soil grade estimated from retained footprint-edge ground, blended to existing soil within 1.2 m of perimeter. No elevated stadium decks, blue risers or end retaining walls.",
        }
    )
