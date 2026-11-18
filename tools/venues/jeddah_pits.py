"""Working apron and parallel stop boxes beside the retained Jeddah fast lane."""

from __future__ import annotations

import bisect
import math
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import Point, RoadStation
from circuit_scene import CircuitScene
from pit_routes_dataclasses import PitRoute, PitSection
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.jeddah_markers import limiter_signs
from venues.jeddah_pits_dataclasses import PitWorkingLane

SOURCE = Path(__file__).resolve().parents[2] / "Attribution/Sources/jeddah"


def working_lane_source() -> PitWorkingLane:
    return TypeAdapter(PitWorkingLane).validate_json((SOURCE / "pit-working-lane.json").read_bytes())


def route_section(route: PitRoute, station: float, position: Point | None = None) -> PitSection:
    stations = [section.track_station for section in route.sections]
    index = max(0, min(len(stations) - 2, bisect.bisect_right(stations, station) - 1))
    first, last = route.sections[index:index + 2]
    t = max(0.0, min(1.0, (station - first.track_station) / (last.track_station - first.track_station)))
    if position is not None:
        best_distance = math.inf
        for candidate_first, candidate_last in zip(route.sections, route.sections[1:]):
            if abs(candidate_first.track_station - station) > 50:
                continue
            dx, dy = candidate_last.x - candidate_first.x, candidate_last.y - candidate_first.y
            fraction = max(0.0, min(1.0, ((position[0] - candidate_first.x) * dx +
                                         (position[1] - candidate_first.y) * dy) / (dx * dx + dy * dy)))
            distance = math.hypot(position[0] - candidate_first.x - dx * fraction,
                                  position[1] - candidate_first.y - dy * fraction)
            if distance < best_distance:
                first, last, t = candidate_first, candidate_last, fraction
                best_distance = distance
        if not math.isfinite(best_distance):
            raise ValueError("No local source pit segment for garage frontage")
    nx = first.normal_x * (1 - t) + last.normal_x * t
    ny = first.normal_y * (1 - t) + last.normal_y * t
    size = math.hypot(nx, ny)
    return PitSection(
        first.x * (1 - t) + last.x * t,
        first.y * (1 - t) + last.y * t,
        first.z * (1 - t) + last.z * t,
        first.half_width * (1 - t) + last.half_width * t,
        first.track_station * (1 - t) + last.track_station * t,
        first.distance * (1 - t) + last.distance * t,
        nx / size,
        ny / size,
        first.cross_slope * (1 - t) + last.cross_slope * t,
    )


def pit_route_source() -> PitRoute:
    return TypeAdapter(PitRoute).validate_json((SOURCE / "pit-lane-reconstruction.json").read_bytes())


def pit_floor_point(sample: RoadStation, section: PitSection, lane: float, lift: float = 0.0) -> Point:
    point = sample.point(lane)
    lateral = (point[0] - section.x) * section.normal_x + (point[1] - section.y) * section.normal_y
    return point[0], point[1], section.z + section.cross_slope * lateral + lift


def apron_point(sample: RoadStation, section: PitSection, source: PitWorkingLane, fraction: float,
                lift: float = 0.0) -> Point:
    front = pit_floor_point(sample, section, -sample.half_width - source.garage_front_offset_m)
    # Pit normals point to source-right; the garage-side edge is negative.
    edge = (section.x - section.normal_x * section.half_width,
            section.y - section.normal_y * section.half_width,
            section.z - section.cross_slope * section.half_width)
    return (front[0] * (1 - fraction) + edge[0] * fraction,
            front[1] * (1 - fraction) + edge[1] * fraction,
            front[2] * (1 - fraction) + edge[2] * fraction + lift)


def apron_floor_point(scene: CircuitScene, route: PitRoute, source: PitWorkingLane,
                      station: float, from_garage: float, lift: float = 0.0) -> Point:
    sample = scene.at(station)
    section = route_section(route, station, sample.point(-sample.half_width - source.garage_front_offset_m))
    front, edge = apron_point(sample, section, source, 0), apron_point(sample, section, source, 1)
    width = math.hypot(edge[0] - front[0], edge[1] - front[1])
    return apron_point(sample, section, source, from_garage / width, lift)


def working_apron(scene: CircuitScene) -> None:
    source = working_lane_source()
    route = pit_route_source()
    full_start = source.start_m - source.support_taper_m
    full_length = source.length_m + 2 * source.support_taper_m
    count = math.ceil(full_length / 2)
    for index in range(count):
        start = full_start + full_length * index / count
        end = full_start + full_length * (index + 1) / count
        a, b = scene.at(start), scene.at(end)
        first = route_section(route, start, a.point(-a.half_width - source.garage_front_offset_m))
        last = route_section(route, end, b.point(-b.half_width - source.garage_front_offset_m))
        blend_a = min(1.0, (start - full_start) / source.support_taper_m,
                      (full_start + full_length - start) / source.support_taper_m)
        blend_b = min(1.0, (end - full_start) / source.support_taper_m,
                      (full_start + full_length - end) / source.support_taper_m)
        front_a = apron_point(a, first, source, 1 - blend_a)
        front_b = apron_point(b, last, source, 1 - blend_b)
        edge_a, edge_b = apron_point(a, first, source, 1), apron_point(b, last, source, 1)
        scene.quad("Tile_JeddahWorkingApron", "JeddahWorkingAsphalt", front_a, front_b, edge_b, edge_a, up=True)
        for points in ((front_a, front_b, edge_b), (front_a, edge_b, edge_a)):
            footprint = Polygon([point[:2] for point in points])
            if footprint.area < 1e-10:
                continue
            scene.surface_shapes.append(footprint)
            scene.surface_points.append(points)
            scene.terrain_cutouts.append(footprint)
        width_a = math.dist(front_a[:2], edge_a[:2])
        width_b = math.dist(front_b[:2], edge_b[:2])
        if min(blend_a, blend_b) < 1:
            continue
        if min(width_a, width_b) < source.working_strip_width_m + 2 * source.stop_half_width_m:
            raise ValueError("Jeddah working apron cannot contain its qualified stop area")
        material = "SeatBlue" if int((start - source.start_m) / 18) % 2 == 0 else "Green"
        scene.quad("Tile_JeddahWorkingStrip", material,
                   apron_point(a, first, source, 1 - source.working_strip_width_m / width_a, .008),
                   apron_point(b, last, source, 1 - source.working_strip_width_m / width_b, .008),
                   apron_point(b, last, source, 1, .008), apron_point(a, first, source, 1, .008), up=True)
        scene.quad("Tile_JeddahWorkingStripEdges", "White",
                   apron_point(a, first, source, 1 - (source.working_strip_width_m + .09) / width_a, .01),
                   apron_point(b, last, source, 1 - (source.working_strip_width_m + .09) / width_b, .01),
                   apron_point(b, last, source, 1 - source.working_strip_width_m / width_b, .01),
                   apron_point(a, first, source, 1 - source.working_strip_width_m / width_a, .01), up=True)
    scene.surface_index = None
    for garage_centre in source.stop_garage_centres:
        garage_index = garage_centre - 1
        station = source.start_m + 1.25 + garage_index * source.bay_spacing_m
        if garage_index >= 21:
            station += source.service_gap_m
        for side in (-1, 1):
            offset = source.stop_center_from_garage_m + side * source.stop_half_width_m
            scene.quad("Tile_JeddahStopGuides", "Yellow",
                       apron_floor_point(scene, route, source, station - source.stop_half_length_m, offset - .045, .012),
                       apron_floor_point(scene, route, source, station + source.stop_half_length_m, offset - .045, .012),
                       apron_floor_point(scene, route, source, station + source.stop_half_length_m, offset + .045, .012),
                       apron_floor_point(scene, route, source, station - source.stop_half_length_m, offset + .045, .012), up=True)
        scene.quad("Tile_JeddahStopMark", "Yellow",
                   apron_floor_point(scene, route, source, station + 1.55, source.stop_center_from_garage_m - source.stop_half_width_m, .012),
                   apron_floor_point(scene, route, source, station + 1.65, source.stop_center_from_garage_m - source.stop_half_width_m, .012),
                   apron_floor_point(scene, route, source, station + 1.65, source.stop_center_from_garage_m + source.stop_half_width_m, .012),
                   apron_floor_point(scene, route, source, station + 1.55, source.stop_center_from_garage_m + source.stop_half_width_m, .012), up=True)
        anchor = station - source.stop_half_length_m - .5
        base = apron_floor_point(scene, route, source, anchor, .45)
        radius = source.boom_elbow_radius_m
        elbow = apron_floor_point(scene, route, source, anchor, .45, source.boom_height_m - radius)
        members = [base, elbow]
        for step in range(1, 9):
            angle = math.pi / 2 * step / 8
            members.append(apron_floor_point(scene, route, source, anchor,
                           .45 + radius * (1 - math.cos(angle)),
                           source.boom_height_m - radius + radius * math.sin(angle)))
        tip = apron_floor_point(scene, route, source, anchor, source.boom_reach_m, source.boom_height_m)
        members.append(tip)
        scene.beam("Building_JeddahPitEquipmentCasing", "White", base, elbow, .38, .46)
        for member_start, member_end in pairwise(members[1:]):
            scene.beam("Building_JeddahPitEquipment", "White", member_start, member_end, .28, .40)
        accent = "Red" if garage_centre == 11.5 else "Green"
        accent_start = apron_floor_point(scene, route, source, anchor, source.boom_reach_m - .65, source.boom_height_m)
        scene.beam("Building_JeddahPitEquipmentAccent", accent, accent_start, tip, .285, .405)
        underside = apron_floor_point(scene, route, source, anchor, .45 + radius,
                                     source.boom_height_m - .15)
        scene.beam("Building_JeddahPitEquipment", "Black", underside,
                   (tip[0], tip[1], tip[2] - .15), .08, .035)
        hose_top = apron_floor_point(scene, route, source, anchor, source.boom_reach_m - .1, source.boom_height_m - .16)
        hose_bottom = apron_floor_point(scene, route, source, anchor, source.boom_reach_m - .1, .45)
        scene.beam("Building_JeddahPitEquipmentHose", "Black", hose_top, hose_bottom, .028)

    limiter_signs(scene, route)
    distances = [section.distance for section in route.sections]
    for distance in (route.limit_entry_m, route.limit_exit_m):
        index = max(0, min(len(distances) - 2, bisect.bisect_right(distances, distance) - 1))
        first, last = route.sections[index:index + 2]
        t = (distance - first.distance) / (last.distance - first.distance)
        section = route_section(route, first.track_station * (1 - t) + last.track_station * t)
        line_points: list[Point] = []
        for along, lateral in ((-.08, -section.half_width), (.08, -section.half_width),
                               (.08, section.half_width), (-.08, section.half_width)):
            line_points.append((section.x - section.normal_y * along + section.normal_x * lateral,
                           section.y + section.normal_x * along + section.normal_y * lateral,
                           section.z + section.cross_slope * lateral + .014))
        scene.quad("Tile_JeddahLimiterLines", "White", line_points[0], line_points[1], line_points[2], line_points[3], up=True)
