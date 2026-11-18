"""Layered balcony bays and readable, source-qualified pit workshop interiors."""
from __future__ import annotations

import csv
import math
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import Point, RoadStation
from circuit_mesh import MeshScene, add, cross, mul, norm, world
from circuit_scene import CircuitScene
from pit_routes_dataclasses import PitSection
from pydantic import TypeAdapter

from venues.jeddah_pit_details_dataclasses import PitFacadeDetail
from venues.jeddah_pit_entry import entry_lights
from venues.jeddah_pits import (
    apron_floor_point,
    pit_floor_point,
    pit_route_source,
    route_section,
    working_lane_source,
)

SOURCE = Path(__file__).resolve().parents[2] / 'Attribution/Sources/jeddah/pit-facade-detail.json'


def detail_source() -> PitFacadeDetail:
    return TypeAdapter(PitFacadeDetail).validate_json(SOURCE.read_bytes())


def upper_bay(scene: CircuitScene, a: RoadStation, b: RoadStation, front_a: float, front_b: float,
              height: float, detail: PitFacadeDetail) -> None:
    scene.beam('Building_JeddahPitBalconySlabs', 'White',
               a.point(front_a + detail.balcony_depth_m / 2, height - detail.balcony_slab_m / 2),
               b.point(front_b + detail.balcony_depth_m / 2, height - detail.balcony_slab_m / 2),
               detail.balcony_depth_m, detail.balcony_slab_m)
    scene.banner(a.point(front_a + detail.balcony_depth_m, height - .25),
                 b.point(front_b + detail.balcony_depth_m, height - .25),
                 .32, 'White', 'Building_JeddahPitBalconyFascias')
    for sample, lane in ((a, front_a), (b, front_b)):
        scene.banner(sample.point(lane, height + .22),
                     sample.point(lane - detail.upper_glazing_recess_m, height + .22),
                     3.7, 'Cream', 'Building_JeddahPitUpperReturns')
    span = (b.station - a.station) % scene.length
    for pane in range(3):
        first = pane / 3
        last = (pane + 1) / 3
        left = scene.at(a.station + span * first)
        right = scene.at(a.station + span * last)
        left_lane = -left.half_width - 13 - detail.upper_glazing_recess_m
        right_lane = -right.half_width - 13 - detail.upper_glazing_recess_m
        scene.banner(left.point(left_lane, height + .35), right.point(right_lane, height + .35),
                     3.3, 'Glass', 'Building_JeddahPitLounges')
        scene.beam('Building_JeddahPitUpperMullions', 'Steel',
                   left.point(left_lane + .05, height + .3),
                   left.point(left_lane + .05, height + 3.75), detail.upper_mullion_m)
        rail_lane = -left.half_width - 13 + detail.balcony_depth_m - .12
        scene.beam('Building_JeddahPitBalconyRailPosts', 'Steel',
                   left.point(rail_lane, height + .12), left.point(rail_lane, height + 1.12), .045)
    scene.beam('Building_JeddahPitUpperTransoms', 'Steel',
               a.point(front_a - detail.upper_glazing_recess_m + .05, height + 2.0),
               b.point(front_b - detail.upper_glazing_recess_m + .05, height + 2.0), .055)
    for lift in (.52, 1.12):
        scene.beam('Building_JeddahPitBalconyRails', 'Steel',
                   a.point(front_a + detail.balcony_depth_m - .12, height + lift),
                   b.point(front_b + detail.balcony_depth_m - .12, height + lift), .05)


def garage_detail(scene: CircuitScene, a: RoadStation, b: RoadStation, front_a: float,
                  front_b: float, detail: PitFacadeDetail) -> None:
    route = pit_route_source()
    start_station = a.station + (scene.length if a.station < route.sections[0].track_station else 0)
    first = route_section(route, start_station, a.point(front_a))
    last_station = start_station + (b.station - a.station) % scene.length
    last = route_section(route, last_station, b.point(front_b))
    scene.quad('Building_JeddahPitWorkshopServiceFloor', 'Concrete',
               pit_floor_point(a, first, front_a - .45, .004),
               pit_floor_point(b, last, front_b - .45, .004),
               pit_floor_point(b, last, front_b - detail.garage_back_depth_m, .004),
               pit_floor_point(a, first, front_a - detail.garage_back_depth_m, .004), up=True)
    scene.banner(a.point(front_a + .17, 3.90), b.point(front_b + .17, 3.90),
                 .36, 'Black', 'Building_JeddahPitGarageHeaderInsets')
    bottom_a = pit_floor_point(a, first, front_a - detail.garage_back_depth_m, .08)
    bottom_b = pit_floor_point(b, last, front_b - detail.garage_back_depth_m, .08)
    top_a = a.point(front_a - detail.garage_back_depth_m, detail.garage_ceiling_m)
    top_b = b.point(front_b - detail.garage_back_depth_m, detail.garage_ceiling_m)
    scene.quad('Building_JeddahPitWorkshopBackwalls', 'Concrete', bottom_a, bottom_b, top_b, top_a)
    scene.quad('Building_JeddahPitWorkshopBackwalls', 'Concrete', bottom_b, bottom_a, top_a, top_b)
    for fraction in (0, 1 / 3, 2 / 3, 1):
        sample = scene.at(start_station + (last_station - start_station) * fraction)
        lane = -sample.half_width - 13 - detail.garage_back_depth_m + .04
        scene.beam('Building_JeddahPitWorkshopPanelJoints', 'Steel',
                   sample.point(lane, .12), sample.point(lane, 4.25), .035)
    for fraction in (.18, .82):
        sample = scene.at(start_station + (last_station - start_station) * fraction)
        scene.beam('Building_JeddahPitWorkshopCeilingFrames', 'Steel',
                   sample.point(-sample.half_width - 13.1, detail.garage_ceiling_m - .08),
                   sample.point(-sample.half_width - 13 - detail.garage_back_depth_m, detail.garage_ceiling_m - .08), .07, .10)
    for depth in (1.2, 4.8):
        scene.beam('Building_JeddahPitWorkshopServiceRails', 'Black',
                   a.point(front_a - depth, detail.garage_ceiling_m - .18),
                   b.point(front_b - depth, detail.garage_ceiling_m - .18), .10, .14)
    for kind, material, lift, width, depth in (
        ('Building_JeddahPitInteriorLightHousing', 'Steel', -.08, .16, .08),
        ('Building_JeddahPitInteriorLightStrip', 'Lamp', -.13, .10, .025),
    ):
        first_lamp = scene.at(start_station + .45)
        last_lamp = scene.at(last_station - .45)
        scene.beam(kind, material,
                   first_lamp.point(-first_lamp.half_width - 13 - detail.interior_light_depth_m,
                                    detail.garage_ceiling_m + lift),
                   last_lamp.point(-last_lamp.half_width - 13 - detail.interior_light_depth_m,
                                   detail.garage_ceiling_m + lift), width, depth)


def write_interior_lights(scene: CircuitScene, path: Path) -> None:
    detail, profile, route = detail_source(), working_lane_source(), pit_route_source()
    with path.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('x', 'y', 'z', 'target_x', 'target_y', 'target_z', 'power'))
        for garage in range(45):
            station = profile.start_m + 1.25 + garage * profile.bay_spacing_m + (profile.service_gap_m if garage >= 21 else 0) + 2.9
            sample = scene.at(station)
            front = -sample.half_width - profile.garage_front_offset_m
            section = route_section(route, station, sample.point(front))
            origin = sample.point(front - detail.interior_light_depth_m, detail.garage_ceiling_m - .16)
            target = pit_floor_point(sample, section, front - detail.garage_back_depth_m + .08, 1.4)
            writer.writerow([f'{value:.5f}' for value in (*world(origin), *world(target), detail.interior_light_power)])
        for fixture in entry_lights(scene):
            if fixture.target is None:
                raise ValueError('Jeddah lobby lights require registered room targets')
            writer.writerow([f'{value:.5f}' for value in
                             (*world(fixture.position), *world(fixture.target), fixture.power)])




def service_cylinder(scene: MeshScene, base: Point, axis_vector: Point) -> None:
    axis = norm(axis_vector)
    side = norm(cross(axis, (0.0, 1.0, 0.0)))
    around = cross(axis, side)
    rings = ((0.0, .075), (.10, .135), (1.28, .135), (1.40, .085), (1.48, .035))
    segments = 16
    for (first_height, first_radius), (last_height, last_radius) in pairwise(rings):
        slope = (last_radius - first_radius) / (last_height - first_height)
        for index in range(segments):
            first_angle, last_angle = math.tau * index / segments, math.tau * (index + 1) / segments
            radial_a = add(mul(side, math.cos(first_angle)), mul(around, math.sin(first_angle)))
            radial_b = add(mul(side, math.cos(last_angle)), mul(around, math.sin(last_angle)))
            a = add(add(base, mul(axis, first_height)), mul(radial_a, first_radius))
            b = add(add(base, mul(axis, first_height)), mul(radial_b, first_radius))
            c = add(add(base, mul(axis, last_height)), mul(radial_b, last_radius))
            d = add(add(base, mul(axis, last_height)), mul(radial_a, last_radius))
            na, nb = norm(add(radial_a, mul(axis, -slope))), norm(add(radial_b, mul(axis, -slope)))
            scene.triangle('Building_JeddahPitServiceCylinders', 'Black', a, b, c, normals=(na, nb, nb))
            scene.triangle('Building_JeddahPitServiceCylinders', 'Black', a, c, d, normals=(na, nb, na))
    for height, radius, direction in ((0.0, .075, -1), (1.48, .035, 1)):
        center = add(base, mul(axis, height))
        for index in range(segments):
            a = add(center, add(mul(side, radius * math.cos(math.tau * index / segments)),
                                mul(around, radius * math.sin(math.tau * index / segments))))
            b = add(center, add(mul(side, radius * math.cos(math.tau * (index + 1) / segments)),
                                mul(around, radius * math.sin(math.tau * (index + 1) / segments))))
            if direction < 0:
                a, b = b, a
            scene.triangle('Building_JeddahPitServiceCylinders', 'Black', center, a, b)
    neck = add(base, mul(axis, 1.51))
    scene.beam('Building_JeddahPitServiceCylinderValves', 'Steel',
               add(neck, mul(side, -.055)), add(neck, mul(side, .055)), .045)

def equipment_point(section: PitSection, along: float, across: float, lift: float) -> Point:
    return (section.x - section.normal_y * along + section.normal_x * across,
            section.y + section.normal_x * along + section.normal_y * across,
            section.z + section.cross_slope * across + lift)

def pit_workstations(scene: CircuitScene) -> None:
    profile, route, detail = working_lane_source(), pit_route_source(), detail_source()
    consoles = 0
    minimum_clearance = math.inf
    for garage in profile.stop_garage_centres:
        index = garage - 1
        station = profile.start_m + 1.25 + index * profile.bay_spacing_m + (profile.service_gap_m if index >= 21 else 0)
        sample = scene.at(station)
        section = route_section(route, station, sample.point(-sample.half_width - profile.garage_front_offset_m))
        cabinet_depth = -detail.garage_back_depth_m + .45
        center = apron_floor_point(scene, route, profile, station, cabinet_depth, .56)
        heading = math.atan2(sample.ty, sample.tx)
        scene.box('Building_JeddahPitWorkshopCabinets', 'White', center, 2.1, .58, 1.0, heading)
        scene.box('Building_JeddahPitWorkshopCabinetTops', 'Steel',
                  (center[0], center[1], center[2] + .54), 2.18, .64, .08, heading)
        for lift in (.20, .50, .80):
            first = scene.at(station - .98)
            last = scene.at(station + .98)
            scene.beam('Building_JeddahPitWorkshopDrawerJoints', 'Steel',
                       apron_floor_point(scene, route, profile, first.station if first.station >= profile.start_m else first.station + scene.length, cabinet_depth + .305, lift),
                       apron_floor_point(scene, route, profile, last.station if last.station >= profile.start_m else last.station + scene.length, cabinet_depth + .305, lift), .025)
        trolley_station = station + 2.0
        trolley = apron_floor_point(scene, route, profile, trolley_station, -1.1, .10)
        scene.box('Building_JeddahPitGasTrolleys', 'Steel', trolley, .67, .44, .08, heading)
        for offset in (-.18, .18):
            bottle_base = apron_floor_point(scene, route, profile, trolley_station + offset, -1.1, .14)
            service_cylinder(scene, bottle_base, (-sample.ty * .25, sample.tx * .25, 1.50))
        for offset in (-.29, .29):
            foot = apron_floor_point(scene, route, profile, trolley_station + offset, -.93, .06)
            handle = apron_floor_point(scene, route, profile, trolley_station + offset, -1.36, 1.25)
            scene.beam('Building_JeddahPitGasTrolleyFrames', 'Steel', foot, handle, .035)
        nx, ny = section.normal_x, section.normal_y
        tx, ty = -ny, nx

        corners = [equipment_point(section, along, across, 0) for along in (-1.4, 1.4) for across in (2.68, 3.42)]
        clearance = min(abs((p[0] - sample.x) * sample.ty - (p[1] - sample.y) * sample.tx)
                        - sample.half_width - .85 for p in corners)
        if clearance < .20:
            continue
        minimum_clearance = min(minimum_clearance, clearance)
        consoles += 1
        for along in (-1.32, 1.32):
            scene.beam('Building_JeddahPitWallConsoleFrames', 'White',
                       equipment_point(section, along, 3.05, .10), equipment_point(section, along, 3.05, 2.35), .10)
        scene.beam('Building_JeddahPitWallConsoleFrames', 'White',
                   equipment_point(section, -1.37, 3.05, 2.35), equipment_point(section, 1.37, 3.05, 2.35), .14, .18)
        scene.box('Building_JeddahPitWallConsoleDesk', 'Steel', equipment_point(section, 0, 3.05, 1.12),
                  2.8, .7, .10, math.atan2(ty, tx))
        for screen in range(3):
            left, right = -.1 - (1 - screen) * .84 - .32, -.1 - (1 - screen) * .84 + .32
            scene.banner(equipment_point(section, left, 2.72, 1.56), equipment_point(section, right, 2.72, 1.56),
                         .50, 'Black', 'Building_JeddahPitWallMonitors')
            for row in range(3):
                scene.beam('Building_JeddahPitWallMonitorReadouts', 'Green',
                           equipment_point(section, left + .06, 2.70, 1.66 + row * .12),
                           equipment_point(section, right - .08 - row * .05, 2.70, 1.66 + row * .12), .025, .01)
    scene.landmarks.append({'name': 'Jeddah pit-wall monitor workstations',
                            'consoles': consoles, 'racing_core_clearance_m': minimum_clearance if consoles else 0.0,
                            'source_note': 'Supplied623s shows pitwall monitor banks/white frames across fastlane. Estimated2.8m representative consoles staybehindexistingseparator andatleast.20m beyondunchangedRaceRoad+0.85mkerb. Workshopcabinetpositions areestimated completion insidegarage, notan eventequipment inventory.'})
