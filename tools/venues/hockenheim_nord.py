"""Continuous Nordtribüne terraces inside the retained curved stand footprint."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import add, mul, sub
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points

from venues.pit_compounds import roof_shell


def front_boundary(scene: CircuitScene, polygon: Polygon) -> LineString:
    ring = list(polygon.exterior.coords)[:-1]
    winding = 1 if polygon.exterior.is_ccw else -1
    facing = []
    for a, b in zip(ring, ring[1:] + ring[:1]):
        span = math.dist(a, b)
        tangent = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        midpoint = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        road, distance = scene.nearest(*midpoint)
        toward = (road.x - midpoint[0]) * -tangent[1] * winding + (road.y - midpoint[1]) * tangent[0] * winding
        facing.append(toward < -distance * .25 and abs(road.tx * tangent[0] + road.ty * tangent[1]) > .35)
    start = next((index + 1 for index, selected in enumerate(facing) if not selected), 0)
    chains: list[list[tuple[float, float]]] = []
    chain: list[tuple[float, float]] = []
    for offset in range(len(ring)):
        index = (start + offset) % len(ring)
        if facing[index]:
            if not chain:
                chain.append(ring[index])
            chain.append(ring[(index + 1) % len(ring)])
        elif chain:
            chains.append(chain)
            chain = []
    if chain:
        chains.append(chain)
    return max((LineString(points) for points in chains), key=lambda line: line.length)


def lines(shape: BaseGeometry) -> list[LineString]:
    if isinstance(shape, LineString):
        return [shape]
    if isinstance(shape, MultiLineString):
        return list(shape.geoms)
    return [piece for piece in getattr(shape, "geoms", ()) if isinstance(piece, LineString)]


def nord_stand(scene: CircuitScene) -> None:
    building = scene.footprint(232009789)
    polygon = orient(Polygon(building.ring))
    shape = polygon.difference(scene.road_mask.buffer(1.2))
    front = front_boundary(scene, polygon)
    winding = 1 if polygon.exterior.is_ccw else -1
    datum = min(scene.nearest(*point)[0].z for point in building.ring) - .015
    floor_start, row_pitch, rise, rows = datum + 1.2, .9, .46, 24
    for row in range(rows):
        band = front.buffer((row + 1) * row_pitch, cap_style="flat", join_style="round").difference(
            front.buffer(row * row_pitch, cap_style="flat", join_style="round")
        ).intersection(shape)
        height = floor_start + row * rise
        for triangle in constrained_delaunay_triangles(band).geoms:
            points = [(x, y, height) for x, y in list(orient(triangle).exterior.coords)[:3]]
            scene.triangle("Building_NordTreads", "Concrete", points[0], points[1], points[2])
            scene.triangle("Building_NordTreadSoffits", "Concrete", add(points[2], (0, 0, -.18)),
                           add(points[1], (0, 0, -.18)), add(points[0], (0, 0, -.18)))
        parts = [band] if isinstance(band, Polygon) else [p for p in getattr(band, "geoms", ()) if isinstance(p, Polygon)]
        lower = datum if row == 0 else height - rise
        for part in parts:
            part = orient(part)
            for boundary in (part.exterior, *part.interiors):
                for a, b in pairwise(boundary.coords):
                    scene.quad("Building_NordRisers", "Concrete", (a[0], a[1], lower),
                               (b[0], b[1], lower), (b[0], b[1], height), (a[0], a[1], height))
        centerline = front.offset_curve(winding * (row + .5) * row_pitch, join_style="round")
        for seat in lines(centerline.intersection(shape.buffer(-.2))):
            for a, b in pairwise(seat.coords):
                if math.dist(a, b) < .25:
                    continue
                pa, pb = (a[0], a[1], height + .15), (b[0], b[1], height + .15)
                scene.beam("Building_NordSeats", "SeatRed", pa, pb, .35, .16)
                scene.spectators(add(pa, (0, 0, .2)), add(pb, (0, 0, .2)), row, "Building_Crowd_Nord")
    assert isinstance(shape, Polygon)
    roof_height = datum + 15.2
    roof_shell(scene, shape, lambda x, y: roof_height, "Building_NordCanopy",
               "Roof", "Concrete", "Concrete", thickness=.22)
    rear = polygon.boundary.difference(front.buffer(.02))
    columns = 0
    for chain in lines(rear):
        count = max(1, math.ceil(chain.length / 8))
        for index in range(count + 1):
            outer = chain.interpolate(chain.length * index / count)
            toward = nearest_points(outer, front)[1]
            span = outer.distance(toward)
            if span < 4:
                continue
            inward = (toward.x - outer.x) / span, (toward.y - outer.y) / span
            column = outer.x + inward[0] * .65, outer.y + inward[1] * .65, datum
            if not shape.buffer(-.3).covers(ShapePoint(column[:2])):
                continue
            top = column[0], column[1], roof_height - .22
            nose: Point = toward.x - inward[0] * .65, toward.y - inward[1] * .65, roof_height - .45
            if not shape.buffer(-.15).covers(LineString([column[:2], nose[:2]])):
                continue
            scene.beam("Building_NordRearColumns", "Steel", column, top, .32)
            scene.beam("Building_NordRoofTrusses", "Steel", add(top, (0, 0, -.2)), nose, .18, .24)
            scene.beam("Building_NordRoofTrusses", "Steel", add(top, (0, 0, -1.5)), nose, .16, .20)
            for step in range(5):
                a, b = step / 5, (step + 1) / 5
                pa = add(top, mul(sub(nose, top), a))
                pb = add(top, mul(sub(nose, top), b))
                scene.beam("Building_NordRoofTrusses", "Steel", (pa[0], pa[1], pa[2] - (.2 if step % 2 else 1.5) * (1-a)),
                           (pb[0], pb[1], pb[2] - (1.5 if step % 2 else .2) * (1-b)), .10)
            columns += 1
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({"name": "Nordtribüne continuous mapped terraces", "osm_id": building.osm_id,
                            "rows_estimate": rows, "foundation_datum_m": datum,
                            "front_floor_above_datum_m": 1.2, "row_pitch_m": row_pitch,
                            "row_rise_m": rise, "roof_height_above_datum_m": 15.2,
                            "roof_rear_frame_bays": columns,
                            "source_note": "Continuous supplied 136/137/138 s shows coherent Nord seating and a supported roof through the first right corner. Actual mapped curved footprint and road-facing boundary set the plan. Constant owned foundation and continuous distance-band rows replace bay-local DSM lifts. Roof level, terrace section and approximately 8 m rear support spacing are visual estimates, not an engineering survey. No shared stand producer or native track profile changed."})
