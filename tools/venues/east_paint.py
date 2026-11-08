"""Original painted shapes fitted to registered paved escape areas."""

from __future__ import annotations

import math

from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from shapely.ops import unary_union


def apron_hatching(
    scene: CircuitScene,
    start: float,
    end: float,
    side: int,
    inner: float,
    outer: float,
    material: str,
) -> None:
    apron = unary_union(scene.extra_corridors)
    for index in range(math.ceil((end - start) / 9)):
        station = start + index * 9
        a, b = scene.at(station), scene.at(min(end, station + 3))
        c, d = scene.at(min(end, station + 7)), scene.at(min(end, station + 4))
        points = [
            a.point(side * (a.half_width + inner)),
            b.point(side * (b.half_width + inner)),
            c.point(side * (c.half_width + outer)),
            d.point(side * (d.half_width + outer)),
        ]
        shape = Polygon([point[:2] for point in points])
        if shape.is_valid:
            scene.polygon_surface(
                shape.intersection(apron).difference(scene.road_mask),
                material,
                lift=0.007,
                sample=a,
            )
    scene.surface_ranges.append(
        {
            "type": "apron hatching",
            "start_m": start,
            "end_m": end,
            "side": side,
            "inner_m": inner,
            "outer_m": outer,
            "material": material,
        }
    )


def apron_fan(
    scene: CircuitScene,
    start: float,
    end: float,
    side: int,
    inner: float,
    outer: float,
    material: str,
) -> None:
    apron = unary_union(scene.extra_corridors)
    count = math.ceil((end - start) / 2)
    for index in range(count):
        t0, t1 = index / count, (index + 1) / count
        a, b = (
            scene.at(start + (end - start) * t0),
            scene.at(start + (end - start) * t1),
        )
        inset_a = outer - (outer - inner) * math.sin(math.pi * t0)
        inset_b = outer - (outer - inner) * math.sin(math.pi * t1)
        points = [
            a.point(side * (a.half_width + inset_a)),
            b.point(side * (b.half_width + inset_b)),
            b.point(side * (b.half_width + outer)),
            a.point(side * (a.half_width + outer)),
        ]
        shape = Polygon([point[:2] for point in points])
        if shape.is_valid:
            scene.polygon_surface(
                shape.intersection(apron).difference(scene.road_mask),
                material,
                lift=0.007,
                sample=a,
            )
    scene.surface_ranges.append(
        {
            "type": "apron fan",
            "start_m": start,
            "end_m": end,
            "side": side,
            "inner_m": inner,
            "outer_m": outer,
            "material": material,
        }
    )
