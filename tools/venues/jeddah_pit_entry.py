"""Recessed hospitality end glazing inside the unchanged Jeddah pit envelope."""

from __future__ import annotations

import math
from pathlib import Path

from circuit_dataclasses import CircuitLight, Point, RoadStation
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.jeddah_pit_entry_dataclasses import PitEntryDetail
from venues.jeddah_pit_exit_geometry import solid

SOURCE = Path(__file__).resolve().parents[2] / "Attribution/Sources/jeddah/pit-entry-frontage.json"


def source_record() -> PitEntryDetail:
    source = TypeAdapter(PitEntryDetail).validate_json(SOURCE.read_bytes())
    if (source.station_m, source.width_m, source.height_m) != (6009, 26, 18.4):
        raise ValueError("Pit-entry glazing must preserve the registered compound envelope")
    if source.floor_height_m * source.levels != source.height_m:
        raise ValueError("Pit-entry bands must match the existing compound floors")
    return source


def position(sample: RoadStation, lane: float, depth: float, lift: float) -> Point:
    x, y, z = sample.point(lane, lift)
    return x + sample.tx * depth, y + sample.ty * depth, z


def entry_lights(scene: CircuitScene) -> tuple[CircuitLight, ...]:
    source = source_record()
    lights = []
    for index in range(source.wing_light_count):
        station = source.wing_start_m + (source.station_m - source.wing_start_m) * (index + .5) / source.wing_light_count
        sample = scene.at(station)
        front = -sample.half_width - 13
        lights.append(CircuitLight(
            sample.point(front - 2.2, 3.8), sample.z, 14, source.lobby_light_power,
            sample.point(front - source.wing_depth_m + .25, 1.5),
        ))
    return tuple(lights)


def end_elevation(
    scene: MeshScene, sample: RoadStation, front: float, rear: float, source: PitEntryDetail
) -> None:
    width = front - rear
    count = max(1, math.ceil(width / source.bay_width_m))
    heading = math.atan2(-sample.tx, sample.ty)
    scene.box(
        "Building_JeddahPitEntryLobbySill", "JeddahEditionStone",
        position(sample, (front + rear) / 2, 0.35, 0.08),
        width, 0.7, 0.16, heading,
    )
    for floor in range(source.levels):
        low = floor * source.floor_height_m
        high = (floor + 1) * source.floor_height_m
        scene.box(
            "Building_JeddahPitEntrySlabBands", "JeddahEditionStone",
            position(sample, (front + rear) / 2, 0.35, high - source.band_height_m / 2),
            width, 0.7, source.band_height_m, heading,
        )
        for bay in range(count):
            left = rear + source.bay_width_m * bay
            right = min(front, left + source.bay_width_m)
            a, b = left + source.pier_width_m / 2, right - source.pier_width_m / 2
            bottom, top = low + 0.16, high - source.band_height_m
            p0 = position(sample, a, source.glazing_depth_m, bottom)
            p1 = position(sample, b, source.glazing_depth_m, bottom)
            p2 = position(sample, b, source.glazing_depth_m, top)
            p3 = position(sample, a, source.glazing_depth_m, top)
            scene.quad(
                "Building_JeddahPitEntryGlazing", "JeddahEditionGuardGlass", p0, p1, p2, p3,
            )
            backs = [position(sample, lane, source.backing_depth_m, lift)
                     for lane, lift in ((a, bottom), (b, bottom), (b, top), (a, top))]
            scene.quad(
                "Building_JeddahPitEntryOccupiedBacks",
                "White" if floor == 0 else "JeddahEditionCharcoal",
                backs[0], backs[1], backs[2], backs[3],
            )
            for kind, material, points in (
                ("SideReturns", "JeddahEditionCharcoal", (p0, backs[0], backs[3], p3)),
                ("SideReturns", "JeddahEditionCharcoal", (backs[1], p1, p2, backs[2])),
                ("Ceilings", "JeddahEditionStone", (p3, backs[3], backs[2], p2)),
                ("Sills", "JeddahEditionStone", (p1, backs[1], backs[0], p0)),
            ):
                scene.quad("Building_JeddahPitEntry" + kind, material, *points)
            scene.box(
                "Building_JeddahPitEntryPiers", "JeddahEditionStone",
                position(sample, left + source.pier_width_m / 2, 0.35, (bottom + top) / 2),
                source.pier_width_m, 0.7, top - bottom, heading,
            )
            for lane in (a, b):
                scene.beam(
                    "Building_JeddahPitEntryFineFrames", "Steel",
                    position(sample, lane, source.glazing_depth_m - 0.03, bottom),
                    position(sample, lane, source.glazing_depth_m - 0.03, top), 0.045,
                )
        scene.box(
            "Building_JeddahPitEntryPiers", "JeddahEditionStone",
            position(sample, front - source.pier_width_m / 2, 0.35,
                     (low + 0.16 + high - source.band_height_m) / 2),
            source.pier_width_m, 0.7, high - source.band_height_m - low - 0.16, heading,
        )


def wing_footprint(scene: CircuitScene, source: PitEntryDetail) -> Polygon:
    samples = [scene.at(source.wing_start_m + (source.station_m - source.wing_start_m) * i / 16)
               for i in range(17)]
    ring = [sample.point(-sample.half_width - 13)[:2] for sample in samples]
    ring.extend(sample.point(-sample.half_width - 13 - source.wing_depth_m)[:2]
                for sample in reversed(samples))
    shape = Polygon(ring)
    first = samples[0]
    front = -first.half_width - 13
    return_shell = Polygon([
        position(first, lane, depth, 0)[:2]
        for lane, depth in ((front, 0), (front, source.backing_depth_m),
                            (front - source.wing_depth_m, source.backing_depth_m),
                            (front - source.wing_depth_m, 0))
    ])
    joined = shape.union(return_shell)
    if not isinstance(joined, Polygon):
        raise TypeError("The entry return must join the wing occupied footprint")
    shape = joined
    if not shape.is_valid or shape.is_empty:
        raise ValueError("Entry hospitality wing must have one valid occupied footprint")
    return shape


def build_entry(scene: CircuitScene, sample: RoadStation, front: float, rear: float) -> None:
    source = source_record()
    if abs(sample.station - source.station_m) > .01 or abs(front - rear - source.width_m) > .01:
        raise ValueError("Pit-entry elevation was moved from the registered start/end plane")
    if not 5935 <= source.wing_start_m <= 5965 or not 0 < source.wing_depth_m < source.width_m:
        raise ValueError("Entry wing exceeds its source-estimated longitudinal/depth scope")
    footprint = wing_footprint(scene, source)
    scene.terrain_cutouts.append(footprint)
    end_elevation(scene, sample, front - source.wing_depth_m, rear, source)
    first = scene.at(source.wing_start_m)
    end_elevation(scene, first, -first.half_width - 13,
                  -first.half_width - 13 - source.wing_depth_m, source)
    for floor in range(source.levels + 1):
        level = floor * source.floor_height_m
        solid(scene, footprint, sample.z + level - source.band_height_m, sample.z + level,
              "JeddahEditionStone", "Building_JeddahPitEntryWingSlabs")
    for index in range(16):
        a = scene.at(source.wing_start_m + (source.station_m - source.wing_start_m) * index / 16)
        b = scene.at(source.wing_start_m + (source.station_m - source.wing_start_m) * (index + 1) / 16)
        front_a, front_b = -a.half_width - 13, -b.half_width - 13
        for floor in range(source.levels):
            low = floor * source.floor_height_m + .18
            high = (floor + 1) * source.floor_height_m - source.band_height_m
            inset = source.glazing_depth_m if floor == 0 else 1.15
            pa, pb = a.point(front_a - inset, low), b.point(front_b - inset, low)
            pc, pd = b.point(front_b - inset, high), a.point(front_a - inset, high)
            scene.quad("Building_JeddahPitEntryWingGlazing", "JeddahEditionGuardGlass",
                       pa, pb, pc, pd)
            back_a, back_b = front_a - source.wing_depth_m + .12, front_b - source.wing_depth_m + .12
            qa, qb = a.point(back_a, low), b.point(back_b, low)
            qc, qd = b.point(back_b, high), a.point(back_a, high)
            scene.quad("Building_JeddahPitEntryWingRoomBacks", "White", qa, qb, qc, qd)
            scene.quad("Building_JeddahPitEntryWingRoomFloors", "JeddahEditionStone",
                       pa, pb, qb, qa, up=True)
            scene.quad("Building_JeddahPitEntryWingRoomCeilings", "JeddahEditionStone",
                       pd, qd, qc, pc, up=False)
            if index:
                scene.beam("Building_JeddahPitEntryWingMullions", "Steel", pa, pd, .045)
        scene.quad("Building_JeddahPitEntryWingRear", "JeddahEditionStone",
                   b.point(front_b - source.wing_depth_m), a.point(front_a - source.wing_depth_m),
                   a.point(front_a - source.wing_depth_m, source.height_m),
                   b.point(front_b - source.wing_depth_m, source.height_m))
    for light in entry_lights(scene):
        scene.box("Building_JeddahPitEntryWingLobbyLamp", "Lamp",
                  (light.position[0], light.position[1], light.position[2] + .05),
                  1.2, .1, .035, math.atan2(sample.ty, sample.tx))
