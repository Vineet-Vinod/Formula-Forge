"""Recessed hospitality end glazing inside the unchanged Jeddah pit envelope."""

from __future__ import annotations

import math
from pathlib import Path

from circuit_dataclasses import CircuitLight, Point, RoadStation
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.jeddah_pit_entry_dataclasses import PitEntryDetail

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
    sample = scene.at(source.station_m)
    front, rear = -sample.half_width - 13, -sample.half_width - 39
    return tuple(
        CircuitLight(
            position(sample, rear + (front - rear) * fraction, 0.9, 3.6),
            sample.z, 14, source.lobby_light_power,
            position(sample, rear + (front - rear) * fraction, 1.65, 1.5),
        )
        for fraction in (0.17, 0.5, 0.83)
    )


def build_entry(
    scene: MeshScene, sample: RoadStation, front: float, rear: float
) -> None:
    source = source_record()
    if abs(sample.station - source.station_m) > 0.01 or abs(front - rear - source.width_m) > 0.01:
        raise ValueError("Pit-entry elevation was moved from the registered start/end plane")
    count = round(source.width_m / source.bay_width_m)
    heading = math.atan2(-sample.tx, sample.ty)
    scene.box(
        "Building_JeddahPitEntryLobbySill", "JeddahEditionStone",
        position(sample, (front + rear) / 2, 0.35, 0.08),
        source.width_m, 0.7, 0.16, heading,
    )
    for floor in range(source.levels):
        low = floor * source.floor_height_m
        high = (floor + 1) * source.floor_height_m
        scene.box(
            "Building_JeddahPitEntrySlabBands", "JeddahEditionStone",
            position(sample, (front + rear) / 2, 0.35, high - source.band_height_m / 2),
            source.width_m, 0.7, source.band_height_m, heading,
        )
        for bay in range(count):
            left = rear + (front - rear) * bay / count
            right = rear + (front - rear) * (bay + 1) / count
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
    for fraction in (0.17, 0.5, 0.83):
        lane = rear + (front - rear) * fraction
        scene.beam(
            "Building_JeddahPitEntryLobbyLamp", "Lamp",
            position(sample, lane - 0.55, 0.9, 3.7),
            position(sample, lane + 0.55, 0.9, 3.7), 0.08, 0.035,
        )
