"""Innentribüne terraces and its separately mapped rear canopy at Sachs."""

from __future__ import annotations

import bisect
import math
from itertools import pairwise

from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_mesh import add, mul, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import delaunay_triangles
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.geometry import Point as ShapePoint

from venues.hockenheim_dataclasses import SachsStandSource
from venues.hockenheim_nord import lines
from venues.pit_compounds import roof_shell


class SachsFoundation:
    def __init__(self, scene: CircuitScene, source: SachsStandSource, front: LineString) -> None:
        terrain = TypeAdapter(RetainedTerrainSource).validate_json(
            (scene.sources / "scenery-ground.json").read_bytes()
        )
        self.datum = terrain.relative_datum_m
        self.anchors = [
            (*scene.geo(anchor.latitude, anchor.longitude), anchor.height_nhn_m - self.datum)
            for anchor in source.ground_anchors
        ]
        self.heights = {(x, y): z for x, y, z in self.anchors}
        self.cells = list(delaunay_triangles(MultiPoint([(x, y) for x, y, _ in self.anchors])).geoms)
        start, end = source.front_ring_indices
        profile = sorted(
            (front.project(ShapePoint(point[:2])), point[2])
            for anchor, point in zip(source.ground_anchors, self.anchors)
            if start <= anchor.ring_index <= end
        )
        self.stations = [station for station, _ in profile]
        self.levels = [height for _, height in profile]
        self.front = front

    def front_height(self, x: float, y: float) -> float:
        station = self.front.project(ShapePoint(x, y))
        right = max(1, min(len(self.stations) - 1, bisect.bisect_right(self.stations, station)))
        a, b = self.stations[right - 1], self.stations[right]
        t = max(0.0, min(1.0, (station - a) / max(b - a, 1e-6)))
        return self.levels[right - 1] * (1 - t) + self.levels[right] * t

    def ground(self, x: float, y: float) -> float:
        point = ShapePoint(x, y)
        cell = min(self.cells, key=lambda triangle: triangle.distance(point))
        a, b, c = list(cell.exterior.coords)[:3]
        area = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / area
        wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / area
        return wa * self.heights[a[:2]] + wb * self.heights[b[:2]] + (1 - wa - wb) * self.heights[c[:2]]


def build_sachs_stand(scene: CircuitScene) -> None:
    source = TypeAdapter(SachsStandSource).validate_json(
        (scene.sources / "sachs-stand-correction.json").read_bytes()
    )
    stand = scene.footprint(232009782)
    canopy = scene.footprint(34400102)
    shape = Polygon(stand.ring)
    roof = Polygon(canopy.ring).intersection(shape)
    if not isinstance(roof, Polygon):
        raise TypeError("Sachs canopy must be one mapped rear strip")
    start, end = source.front_ring_indices
    front = LineString(stand.ring[start:end + 1])
    foundation = SachsFoundation(scene, source, front)
    winding = 1 if shape.exterior.is_ccw else -1
    seating = shape.buffer(-.24)
    for row in range(source.row_count):
        near, far = row * source.row_pitch_m, (row + 1) * source.row_pitch_m
        band = front.buffer(far, cap_style="round", join_style="round").difference(
            front.buffer(near, cap_style="round", join_style="round")
        ).intersection(shape)
        height_offset = source.first_floor_m + row * source.row_rise_m

        def height(x: float, y: float, offset: float = height_offset) -> float:
            return foundation.front_height(x, y) + offset

        parts = [band] if isinstance(band, Polygon) else [part for part in getattr(band, "geoms", ()) if isinstance(part, Polygon)]
        for part in parts:
            if part.is_empty or part.area < 1e-8:
                continue
            roof_shell(scene, part, height, "Building_SachsTread", "Concrete", "Concrete", "Concrete", .18)
        path = front.offset_curve(winding * (near + source.row_pitch_m * .55), join_style="round")
        for chain in lines(path.intersection(seating)):
            if chain.is_empty or chain.length < .6:
                continue
            # Aisles interrupt rows at regular source-estimated section intervals.
            count = max(1, math.ceil(chain.length / 6))
            for bay in range(count):
                a = chain.interpolate((bay + .08) * chain.length / count)
                b = chain.interpolate((bay + .92) * chain.length / count)
                pa: Point = a.x, a.y, height(a.x, a.y) + .16
                pb: Point = b.x, b.y, height(b.x, b.y) + .16
                if not seating.covers(LineString([pa[:2], pb[:2]]).buffer(.19, cap_style="flat")):
                    continue
                scene.beam("Building_SachsSeats", "White", pa, pb, .34, .16)
                scene.spectators(add(pa, (0, 0, .2)), add(pb, (0, 0, .2)), row, "Building_Crowd_Sachs")
        riser = front.offset_curve(winding * near, join_style="round")
        for chain in lines(riser.intersection(shape)):
            for a, b in pairwise(chain.coords):
                low_offset = max(0.0, height_offset - source.row_rise_m)
                scene.quad("Building_SachsRiser", "Concrete",
                           (a[0], a[1], foundation.front_height(*a) + low_offset),
                           (b[0], b[1], foundation.front_height(*b) + low_offset),
                           (b[0], b[1], height(*b)), (a[0], a[1], height(*a)))
    last_offset = source.first_floor_m + (source.row_count - 1) * source.row_rise_m
    concourse = shape.difference(front.buffer(source.row_count * source.row_pitch_m, cap_style="round"))
    concourse_parts = [concourse] if isinstance(concourse, Polygon) else [part for part in getattr(concourse, "geoms", ()) if isinstance(part, Polygon)]
    for part in concourse_parts:
        if part.is_empty or part.area < 1e-8:
            continue
        roof_shell(scene, part, lambda x, y: foundation.front_height(x, y) + last_offset,
                   "Building_SachsRearConcourse", "Concrete", "Concrete", "Concrete")
    for a, b in pairwise(shape.exterior.coords):
        count = max(1, math.ceil(math.dist(a, b) / 1.5))
        for index in range(count):
            points = [(a[0] + (b[0]-a[0])*t/count, a[1] + (b[1]-a[1])*t/count) for t in (index, index+1)]
            tops = []
            for x, y in points:
                row = min(source.row_count - 1, int(front.distance(ShapePoint(x, y)) / source.row_pitch_m))
                tops.append(foundation.front_height(x, y) + source.first_floor_m + row * source.row_rise_m)
            end_a, end_b = points
            scene.quad("Building_SachsTerraceEnds", "Concrete",
                       (end_a[0], end_a[1], foundation.ground(*end_a)), (end_b[0], end_b[1], foundation.ground(*end_b)),
                       (end_b[0], end_b[1], tops[1]), (end_a[0], end_a[1], tops[0]))

    def roof_height(x: float, y: float) -> float:
        return foundation.front_height(x, y) + source.canopy_above_front_m

    roof_shell(scene, roof, roof_height, "Building_SachsCanopy", "Roof", "Concrete", "Concrete", .22)
    rear = LineString(stand.ring[end:] + stand.ring[:start + 1])
    supports = 0
    for index in range(math.ceil(rear.length / 8) + 1):
        outer = rear.interpolate(min(rear.length, index * 8))
        toward = front.interpolate(front.project(outer))
        span = outer.distance(toward)
        if span < 5:
            continue
        inward = (toward.x - outer.x) / span, (toward.y - outer.y) / span
        center = ShapePoint(outer.x + inward[0] * .65, outer.y + inward[1] * .65)
        if not roof.buffer(-.3).covers(center):
            continue
        chord = LineString([(center.x, center.y), (toward.x, toward.y)]).intersection(roof.buffer(-.3))
        components = lines(chord)
        if not components:
            continue
        nose_xy = min((p for chain in components for p in chain.coords), key=lambda p: front.distance(ShapePoint(p)))
        base: Point = center.x, center.y, foundation.ground(center.x, center.y)
        top: Point = center.x, center.y, roof_height(center.x, center.y) - .3
        nose: Point = nose_xy[0], nose_xy[1], roof_height(*nose_xy) - .35
        scene.beam("Building_SachsColumns", "White", base, top, .32)
        scene.beam("Building_SachsCantilever", "White", top, nose, .20, .27)
        scene.beam("Building_SachsCantilever", "White", add(top, (0, 0, -1.4)), nose, .14, .20)
        for step in range(4):
            pa = add(top, mul(sub(nose, top), step / 4))
            pb = add(top, mul(sub(nose, top), (step + 1) / 4))
            scene.beam("Building_SachsRoofBracing", "Steel", add(pa, (0, 0, -.2)),
                       add(pb, (0, 0, -1.1 * (1 - (step + 1) / 4))), .08)
        supports += 1
    for a, b in pairwise(roof.buffer(-.08).exterior.coords):
        count = max(1, math.ceil(math.dist(a, b) / 3))
        for index in range(count):
            rail_a = (a[0] + (b[0]-a[0])*index/count, a[1] + (b[1]-a[1])*index/count)
            rail_b = (a[0] + (b[0]-a[0])*(index+1)/count, a[1] + (b[1]-a[1])*(index+1)/count)
            za, zb = roof_height(*rail_a), roof_height(*rail_b)
            scene.beam("Building_SachsRoofRailing", "Steel", (*rail_a, za), (*rail_a, za + 1.05), .035)
            for level in (.4, .75, 1.05):
                scene.beam("Building_SachsRoofRailing", "Steel", (*rail_a, za + level), (*rail_b, zb + level), .025)
    scene.terrain_cutouts.append(Polygon([(x, y) for x, y in shape.exterior.coords]))
    scene.modeled_buildings.update((stand.osm_id, canopy.osm_id))
    scene.landmarks.append({"name": "Sachs Innentribüne", "osm_id": stand.osm_id,
                            "roof_osm_id": canopy.osm_id, "rows_estimate": source.row_count,
                            "row_pitch_m": source.row_pitch_m, "row_rise_m": source.row_rise_m,
                            "roof_rear_support_bays": supports, "ground_datum_nhn_m": foundation.datum,
                            "mapped_roof_fraction": roof.area / shape.area,
                            "source_note": "Actual curved seating footprint and separately mapped rear roof strip. Front rows stay open. Precise LGL ground anchors retain the raised rear earth terrace; section and support spacing remain visual estimates from continuous 412–420 s views and 2018 ortho."})
