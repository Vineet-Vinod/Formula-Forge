"""Construct bounded escape branches without replacing a venue's barrier table."""

from __future__ import annotations

import bisect
import hashlib
import itertools
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path

from circuit_dataclasses import RoadStation
from circuit_escapes_dataclasses import (
    EscapeOverlay,
    EscapeRecipe,
    EscapeRegion,
    EscapeRoad,
    PaintDomain,
    PavingTriangle,
)
from circuit_portals_dataclasses import Barrier, Portal
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree


def load_recipe(path: Path) -> EscapeRecipe:
    return TypeAdapter(EscapeRecipe).validate_json(path.read_bytes())


def write_source_overlay(path: Path, overlay: EscapeOverlay, recipe_path: Path,
                         source_paths: Sequence[Path]) -> None:
    sources = dict.fromkeys([recipe_path, *source_paths])
    if path.resolve() in {source.resolve() for source in sources}:
        raise ValueError("Escape output must not overwrite a protected source input")
    records = asdict(overlay)
    records["audits"] = records.pop("regions")
    records.update({
        "version": 1,
        "source_frame": "XY east/north metres; Z retained scene metres",
        "source_status": load_recipe(recipe_path).source_status,
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "recipe_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
        "source_sha256": {str(source): hashlib.sha256(source.read_bytes()).hexdigest() for source in sources},
        "approval": "Reconstruction candidate; independent source/native review required",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(records, indent=2)+"\n")
    temporary.replace(path)


def interpolate(a: RoadStation, b: RoadStation, t: float) -> RoadStation:
    tx, ty = a.tx + (b.tx - a.tx) * t, a.ty + (b.ty - a.ty) * t
    norm = math.hypot(tx, ty)
    return RoadStation(
        a.station+(b.station-a.station)*t, a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t,
        a.z + (b.z-a.z)*t, tx/norm, ty/norm,
        a.half_width + (b.half_width-a.half_width)*t,
        a.bank + (b.bank-a.bank)*t,
        a.left_shoulder + (b.left_shoulder-a.left_shoulder)*t,
        a.right_shoulder + (b.right_shoulder-a.right_shoulder)*t,
        a.bank_quadratic+(b.bank_quadratic-a.bank_quadratic)*t,
        a.bank_fade+(b.bank_fade-a.bank_fade)*t,
        a.bank_outer_positive+(b.bank_outer_positive-a.bank_outer_positive)*t,
        a.bank_outer_negative+(b.bank_outer_negative-a.bank_outer_negative)*t,
    )


def road_sample(road: Sequence[RoadStation], station: float) -> RoadStation:
    distances = [sample.station for sample in road]
    index = max(0, min(len(road) - 2, bisect.bisect_right(distances, station) - 1))
    a, b = road[index], road[index + 1]
    if not a.station <= station <= b.station:
        raise ValueError("Escape approach station is outside the exported road")
    return interpolate(a, b, (station-a.station)/(b.station-a.station))


def quad(control: EscapeRoad, sample: RoadStation) -> Polygon:
    right = sample.ty, -sample.tx
    center = sample.x + right[0]*control.lateral_offset_m, sample.y + right[1]*control.lateral_offset_m
    ring = [
        (center[0] + sample.tx*along + right[0]*lane,
         center[1] + sample.ty*along + right[1]*lane)
        for along, lane in ((0, -control.width_m/2), (0, control.width_m/2),
                            (control.length_m, control.width_m/2), (control.length_m, -control.width_m/2))
    ]
    polygon = Polygon(ring)
    if not polygon.exterior.is_ccw:
        polygon = Polygon(ring[::-1])
    return polygon


def road_shape(road: Sequence[RoadStation], protected: bool) -> BaseGeometry:
    shapes = []
    for a, b in itertools.pairwise(road):
        if b.station-a.station > 5:
            continue
        al = a.half_width + (a.right_shoulder + .85 if protected else .14)
        ar = a.half_width + (a.left_shoulder + .85 if protected else .14)
        bl = b.half_width + (b.right_shoulder + .85 if protected else .14)
        br = b.half_width + (b.left_shoulder + .85 if protected else .14)
        polygon = Polygon([a.point(-al)[:2], a.point(ar)[:2], b.point(br)[:2], b.point(-bl)[:2]])
        if polygon.is_valid and polygon.area > 1e-8:
            shapes.append(polygon)
    return unary_union(shapes)


def polygon_parts(shape: BaseGeometry) -> list[Polygon]:
    if isinstance(shape, Polygon):
        return [shape] if shape.area > 1e-8 else []
    return [part for part in getattr(shape, "geoms", ()) if isinstance(part, Polygon) and part.area > 1e-8]


def floor_sampler(branch: Sequence[RoadStation], anchor: RoadStation,
                  grade: float) -> tuple[Callable[[float, float], float], Callable[[float, float], float]]:
    lines = [LineString([(a.x, a.y), (b.x, b.y)]) for a, b in itertools.pairwise(branch)]
    tree = STRtree(lines)

    def road_height(x: float, y: float) -> tuple[float, float]:
        point = Point(x, y)
        index = int(tree.nearest(point))
        a, b = branch[index], branch[index+1]
        t = lines[index].project(point, normalized=True)
        sample = interpolate(a, b, t)
        lane = (x-sample.x)*sample.ty-(y-sample.y)*sample.tx
        distance = max(0.0, math.hypot(x-sample.x, y-sample.y)-sample.half_width-.14)
        return sample.height(lane), distance

    def retained_height(x: float, y: float) -> float:
        return road_height(x, y)[0]

    def floor(x: float, y: float) -> float:
        road_z, distance = road_height(x, y)
        along = (x-anchor.x)*anchor.tx + (y-anchor.y)*anchor.ty
        continuation = anchor.z + along*grade + anchor.bank*((x-anchor.x)*anchor.ty-(y-anchor.y)*anchor.tx)
        t = min(1.0, distance/8)
        blend = t*t*(3-2*t)
        return road_z*(1-blend) + continuation*blend

    return floor, retained_height


def build_overlay(recipe: EscapeRecipe, road: Sequence[RoadStation],
                  original_barriers: Sequence[Barrier], scene_scale: float,
                  *, occupied: Sequence[Polygon]) -> EscapeOverlay:
    if not math.isclose(scene_scale, recipe.expected_scene_scale, abs_tol=1e-9, rel_tol=0):
        raise ValueError("Escape source frame differs from the qualified scene scale")
    if len(road) < 3 or any(b.station <= a.station for a, b in itertools.pairwise(road)):
        raise ValueError("Escape construction requires an ordered exported road")
    if len({control.id for control in recipe.escapes}) != len(recipe.escapes):
        raise ValueError("Escape identifiers must be unique")
    if not recipe.escapes and not recipe.paint_strips:
        raise ValueError("An escape recipe must contain a qualified correction")
    portals, barriers, paving, regions = [], [], [], []
    for control in recipe.escapes:
        anchor = road_sample(road, control.approach_station_m)
        domain = quad(control, anchor)
        local = [sample for sample in road if domain.distance(Point(sample.x, sample.y)) < 80]
        # Keep both nearby arms in exclusion tests; height comes from this approach only.
        if len(local) < 3:
            raise ValueError("Escape has no local racing-road context")
        protected = road_shape(local, True)
        legal = road_shape(local, False)
        floor_domain = domain.difference(legal)
        if any(floor_domain.intersection(body).area > .00001 for body in occupied):
            raise ValueError(f"Escape {control.id} overlaps an occupied property")
        floor_parts = polygon_parts(floor_domain)
        if not floor_parts:
            raise ValueError("Escape adds no paved area outside the legal road")
        branch = [sample for sample in road if abs(sample.station-anchor.station) < 120]
        before = road_sample(road, max(0.0, anchor.station-15))
        grade = (anchor.z-before.z) / max(.001, anchor.station-before.station)
        if abs(grade) > .15:
            raise ValueError("Escape approach grade requires a separately qualified model")

        floor, retained_height = floor_sampler(branch, anchor, grade)
        added_paving = []
        maximum_grade = 0.0
        low_x, low_y, high_x, high_y = floor_domain.bounds
        for x in range(math.floor(low_x), math.ceil(high_x)):
            for y in range(math.floor(low_y), math.ceil(high_y)):
                for part in polygon_parts(floor_domain.intersection(box(x, y, x+1, y+1))):
                    for triangle in constrained_delaunay_triangles(part).geoms:
                        ring = list(triangle.exterior.coords)[:3]
                        points = [(px, py, floor(px, py)) for px, py in ring]
                        a, b, c = points
                        det = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                        if abs(det) < 1e-10:
                            continue
                        dx = ((b[2]-a[2])*(c[1]-a[1])-(c[2]-a[2])*(b[1]-a[1]))/det
                        dy = ((b[0]-a[0])*(c[2]-a[2])-(c[0]-a[0])*(b[2]-a[2]))/det
                        maximum_grade = max(maximum_grade, math.hypot(dx, dy))
                        if det < 0:
                            b, c = c, b
                        added_paving.append(PavingTriangle(a, b, c))
        if maximum_grade > .25:
            raise ValueError(f"Escape {control.id} creates an unsupported paving grade: {maximum_grade:.3f}")
        heights = [point[2] for triangle in added_paving for point in (triangle.a, triangle.b, triangle.c)]
        if not heights:
            raise ValueError("Escape paving could not be triangulated")
        portals.append(Portal(control.id, tuple(domain.exterior.coords)[:-1], min(heights)-1,
                              max(heights)+6, control.source_note))
        exposed = domain.boundary.difference(protected)
        lines = [exposed] if isinstance(exposed, LineString) else list(getattr(exposed, "geoms", ()))
        for line in lines:
            if not isinstance(line, LineString):
                continue
            count = max(1, math.ceil(line.length))
            for index in range(count):
                a, b = line.interpolate(line.length*index/count), line.interpolate(line.length*(index+1)/count)
                if a.distance(b) < .001:
                    continue
                bottom = min(floor(a.x, a.y), floor(b.x, b.y))
                barriers.append(Barrier(a.x, a.y, b.x, b.y, bottom, bottom+.94, .15))
        original_hits = sum(domain.intersects(LineString([(wall.ax, wall.ay), (wall.bx, wall.by)])) for wall in original_barriers)
        joins = floor_domain.boundary.intersection(legal.boundary)
        join_lines = [joins] if isinstance(joins, LineString) else list(getattr(joins, "geoms", ()))
        join_errors = [abs(floor(x, y)-retained_height(x, y)) for line in join_lines
                       if isinstance(line, LineString) for x, y in line.coords]
        maximum_join_error = max(join_errors, default=0.0)
        if maximum_join_error > .0001:
            raise ValueError(f"Escape {control.id} does not join its retained road")
        regions.append(EscapeRegion(control.id, control.name, tuple(domain.exterior.coords)[:-1],
                                    anchor.station, original_hits, floor_domain.area, maximum_grade, maximum_join_error,
                                    control.source_note))
        paving.extend(added_paving)
    paint_domains = []
    for strip in recipe.paint_strips:
        if strip.end_m <= strip.start_m or strip.outer_offset_m <= strip.inner_offset_m:
            raise ValueError("Paint correction requires ordered station and lateral bounds")
        count = max(1, math.ceil((strip.end_m-strip.start_m)/2))
        for index in range(count):
            paint_start = road_sample(road, strip.start_m+(strip.end_m-strip.start_m)*index/count)
            paint_end = road_sample(road, strip.start_m+(strip.end_m-strip.start_m)*(index+1)/count)
            points = [paint_start.point(strip.side*(paint_start.half_width+strip.inner_offset_m)),
                      paint_start.point(strip.side*(paint_start.half_width+strip.outer_offset_m)),
                      paint_end.point(strip.side*(paint_end.half_width+strip.outer_offset_m)),
                      paint_end.point(strip.side*(paint_end.half_width+strip.inner_offset_m))]
            polygon = Polygon([point[:2] for point in points])
            if not polygon.is_valid or polygon.area < .0001 or not math.isclose(polygon.convex_hull.area, polygon.area, abs_tol=1e-8):
                raise ValueError(f"Paint correction {strip.id} is not a convex source quad")
            if not polygon.exterior.is_ccw:
                points.reverse()
            paint_domains.append(PaintDomain(
                f"{strip.id}-{index:03d}", tuple(point[:2] for point in points),
                min(point[2] for point in points)-.03, max(point[2] for point in points)+.03,
                strip.source_material, strip.target_material, strip.source_note))
    return EscapeOverlay(recipe.circuit, tuple(portals), tuple(barriers), tuple(paving), tuple(regions), tuple(paint_domains))
