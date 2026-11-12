"""Venue-specific floodlight structures observed in the supplied night references."""

from __future__ import annotations

import math
from functools import cache
from pathlib import Path

from circuit_dataclasses import CircuitLight, PitLane, Point, RoadStation
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter


@cache
def pit_profile(path: Path) -> PitLane | None:
    return (
        TypeAdapter(PitLane).validate_json(path.read_bytes()) if path.exists() else None
    )


def is_pit_side(scene: CircuitScene, sample: RoadStation, side: int) -> bool:
    profile = pit_profile(scene.sources / "pit-lane.json")
    return (
        profile is not None
        and profile.side == side
        and (
            (sample.station - profile.start_m) % scene.length
            <= (profile.end_m - profile.start_m) % scene.length
        )
    )


def roof_anchor(
    scene: CircuitScene, sample: RoadStation, side: int, roof_height: float
) -> Point:
    profile = pit_profile(scene.sources / "pit-lane.json")
    if profile is None:
        raise ValueError(f"Missing pit registration for {scene.slug}")
    point = sample.point(side * (sample.half_width + profile.outer_offset_m + 3))
    return point[0], point[1], sample.z + roof_height


def head_bank(
    scene: CircuitScene,
    center: Point,
    sample: RoadStation,
    side: int,
    columns: int,
    rows: int,
) -> None:
    along = sample.tx, sample.ty, 0.0
    inward = -sample.ty * side, sample.tx * side, 0.0
    vertical = add(mul(inward, 0.55), (0.0, 0.0, 0.835))
    heading = math.atan2(sample.ty, sample.tx)
    for row in range(rows):
        for column in range(columns):
            position = add(
                center,
                add(
                    mul(along, (column - (columns - 1) / 2) * 0.78),
                    mul(vertical, (row - (rows - 1) / 2) * 0.64),
                ),
            )
            scene.box(
                "Building_LightingHousing", "Black", position, 0.72, 0.3, 0.55, heading
            )
            face = add(position, mul(inward, 0.19))
            a = add(face, add(mul(along, -0.31), mul(vertical, -0.24)))
            b = add(face, add(mul(along, 0.31), mul(vertical, -0.24)))
            c = add(face, add(mul(along, 0.31), mul(vertical, 0.24)))
            d = add(face, add(mul(along, -0.31), mul(vertical, 0.24)))
            if side > 0:
                a, b, c, d = d, c, b, a
            scene.quad("Building_LightingEmitter", "Lamp", a, b, c, d)
    for row in range(rows):
        position = add(center, mul(vertical, (row - (rows - 1) / 2) * 0.64))
        scene.beam(
            "Building_LightingFrame",
            "Steel",
            add(position, mul(along, -columns * 0.4)),
            add(position, mul(along, columns * 0.4)),
            0.1,
        )


def pole_base(
    scene: CircuitScene, sample: RoadStation, side: int, setback: float
) -> Point:
    shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
    offset = shoulder + scene.kerb_margin(sample.station) + setback
    profile = pit_profile(scene.sources / "pit-lane.json")
    if profile is not None and is_pit_side(scene, sample, side):
        depth = {"bahrain": 23.0, "jeddah": 26.0, "singapore": 22.0}[scene.slug]
        offset = max(offset, profile.outer_offset_m + depth + max(3.0, setback))
    point = sample.point(side * (sample.half_width + offset))
    return point[0], point[1], scene.ground(*point[:2])


def flood_mast(
    scene: CircuitScene,
    station: float,
    side: int,
    height: float,
    setback: float,
    columns: int,
    rows: int,
    radius: float,
    power: float,
    canted: bool = False,
) -> CircuitLight:
    sample = scene.at(station)
    base = pole_base(scene, sample, side, setback)
    inward = -sample.ty * side, sample.tx * side, 0.0
    top = add(base, (0.0, 0.0, height))
    if canted:
        elbow = add(base, (0.0, 0.0, height - 5))
        top = add(top, mul(inward, 3.5))
        scene.beam("Building_CantedFloodlight", "White", base, elbow, 0.25)
        scene.beam("Building_CantedFloodlight", "White", elbow, top, 0.22)
        scene.beam(
            "Building_CantedFloodlightStay",
            "Steel",
            add(base, mul(inward, -1.5)),
            add(top, (0.0, 0.0, -1.0)),
            0.09,
        )
    else:
        scene.beam("Building_FloodlightMast", "White", base, top, 0.32)
        scene.beam(
            "Building_FloodlightMast",
            "Steel",
            add(base, (0.0, 0.0, height * 0.65)),
            add(top, (0.0, 0.0, -1.2)),
            0.18,
        )
    head_bank(scene, top, sample, side, columns, rows)
    return CircuitLight(top, base[2], radius, power)


def curved_lamp(
    scene: CircuitScene,
    station: float,
    side: int,
    height: float,
    setback: float,
    radius: float,
    power: float,
    heads: int = 2,
) -> CircuitLight:
    sample = scene.at(station)
    base = pole_base(scene, sample, side, setback)
    inward = -sample.ty * side, sample.tx * side, 0.0
    previous = base
    for distance, rise in (
        (0.0, height - 1.6),
        (0.25, height - 0.65),
        (0.8, height - 0.12),
        (1.6, height + 0.15),
        (2.4, height),
    ):
        point = add(base, add(mul(inward, distance), (0.0, 0.0, rise)))
        scene.beam("Building_CurvedLightPole", "White", previous, point, 0.16)
        previous = point
    head_bank(scene, previous, sample, side, heads, 1)
    return CircuitLight(previous, base[2], radius, power)


def roof_bank(
    scene: CircuitScene,
    sample: RoadStation,
    side: int,
    height: float,
    roof_height: float,
    columns: int,
    rows: int,
    power: float,
) -> CircuitLight:
    base = roof_anchor(scene, sample, side, roof_height)
    inward = -sample.ty * side, sample.tx * side, 0.0
    elbow = base[0], base[1], sample.z + height - 2.0
    top = add((base[0], base[1], sample.z + height), mul(inward, 2.5))
    scene.beam("Building_RoofFloodlight", "White", base, elbow, 0.22)
    scene.beam("Building_RoofFloodlight", "White", elbow, top, 0.18)
    head_bank(scene, top, sample, side, columns, rows)
    return CircuitLight(top, sample.z, 27.0, power)


def bahrain(scene: CircuitScene) -> list[CircuitLight]:
    lights = []
    # Pit-front banks are raked above the low pit roofs; open sectors use tall masts.
    for start, end, height, spacing, paired in (
        (0, 220, 24.0, 50.0, True),
        (220, 1350, 32.0, 55.0, True),
        (1350, 3150, 30.0, 55.0, False),
        (3150, 4300, 32.0, 55.0, True),
        (4300, 5100, 30.0, 50.0, False),
        (5100, scene.length, 24.0, 50.0, True),
    ):
        pit = start == 0 or start == 5100
        for index in range(math.ceil((end - start) / spacing)):
            station = start + index * spacing
            sides = (-1, 1) if paired else ((-1,) if index % 2 else (1,))
            for side in sides:
                offset = spacing * 0.4 if side > 0 and not pit else 0.0
                if station + offset >= end:
                    continue
                sample = scene.at(station + offset)
                if pit and is_pit_side(scene, sample, side):
                    lights.append(
                        roof_bank(scene, sample, side, 24.0, 11.2, 4, 2, 1.35)
                    )
                    continue
                if pit and side < 0:
                    center = sample.point(-(sample.half_width + 12), 13.0)
                    head_bank(scene, center, sample, -1, 2, 1)
                    lights.append(CircuitLight(center, sample.z, 25.0, 0.8))
                    continue
                lights.append(
                    flood_mast(
                        scene,
                        station + offset,
                        side,
                        height,
                        3.5,
                        4,
                        2 if pit else 4,
                        27.0 if pit else 34.0,
                        1.35 if pit else 2.0,
                        canted=pit,
                    )
                )
    scene.landmarks.append(
        {
            "name": "Bahrain floodlight recipe",
            "structure": "30–32 m straight multi-head masts in open sectors; 24 m canted banks above the pit roofs and 13 m underside fittings beneath the mainstand roof. Individual positions, heights and 50–55 m spacing are visual estimates.",
            "reference": "Saved/Refs/bahrain.mp4:100,120,130,170,195,200 seconds",
            "confidence": "High for bank versus streetlamp distinction; moderate for sector distribution; low for metric dimensions. Relative field powers are rendering parameters, not photometry.",
        }
    )
    return lights


def jeddah(scene: CircuitScene) -> list[CircuitLight]:
    lights = []
    for index in range(math.ceil(scene.length / 32)):
        for side in (-1, 1):
            station = index * 32 + (16 if side > 0 else 0)
            if station < scene.length:
                sample = scene.at(station)
                if is_pit_side(scene, sample, side):
                    lights.append(roof_bank(scene, sample, side, 25.0, 21.5, 3, 1, 0.9))
                else:
                    lights.append(
                        curved_lamp(scene, station, side, 16.0, 1.8, 17.0, 0.7)
                    )
    for station in (650, 1120, 1630):
        lights.append(flood_mast(scene, station, -1, 29.0, 38.0, 4, 3, 30.0, 1.6))
    scene.landmarks.append(
        {
            "name": "Jeddah floodlight recipe",
            "structure": "Slim curved-neck paired-head road poles, staggered about 32 m apart; three larger set-back stadium banks beside the early esses, and 25 m roof-mounted banks over the pit frontage.",
            "reference": "Saved/Refs/jeddah.mp4:251,255,259,263,275,287,291,315,323 seconds",
            "confidence": "High for mixed pole families; moderate for primary road-pole distribution; low for estimated 16/29 m heights and exact tower stations.",
        }
    )
    return lights


def singapore_cable_height(station: float) -> float:
    for start, low, high, end in ((1005., 1030., 1080., 1105.), (4255., 4280., 4380., 4410.)):
        if start <= station <= end:
            weight = min(1., (station - start) / (low - start), (end - station) / (end - high))
            weight = weight * weight * (3 - 2 * weight)
            return 15.5 - 6.0 * weight
    if station < 2600 or station > 2920:
        return 15.5
    if station < 2680:
        return 15.5 - (station - 2600) * 3.5 / 80
    if station > 2840:
        return 12 + (station - 2840) * 3.5 / 80
    return 12.0


def singapore(scene: CircuitScene) -> list[CircuitLight]:
    lights = []
    spacing = 7.0
    for index in range(math.ceil(scene.length / spacing)):
        a = scene.at(index * spacing)
        b = scene.at(min(scene.length - 0.01, (index + 1) * spacing))
        for side in (-1, 1):
            # Cable-mounted race fittings are separate from the lower civic streetlights.
            height = singapore_cable_height(a.station)
            center = a.point(side * (a.half_width + 0.8), height)
            following = b.point(
                side * (b.half_width + 0.8), singapore_cable_height(b.station)
            )
            for lateral in (-0.24, 0.24):
                offset = -a.ty * lateral, a.tx * lateral, 0.18
                scene.beam(
                    "Building_RaceLightCable",
                    "Steel",
                    add(center, offset),
                    add(following, offset),
                    0.025,
                )
            head_bank(scene, center, a, side, 1, 1)
            lights.append(CircuitLight(center, a.z, 11.0, 0.23))
    for index in range(math.ceil(scene.length / 42)):
        sample = scene.at(index * 42)
        height = singapore_cable_height(sample.station)
        for side in (-1, 1):
            base = (
                roof_anchor(scene, sample, side, 15.3)
                if is_pit_side(scene, sample, side)
                else pole_base(scene, sample, side, 1.5)
            )
            top = base[0], base[1], sample.z + height + 1.0
            anchor = sample.point(side * (sample.half_width + 0.8), height + 0.18)
            scene.beam("Building_RaceLightSupport", "Steel", base, top, 0.18)
            scene.beam("Building_RaceLightSupport", "Steel", top, anchor, 0.1)
    for start, end, height in (
        (1660, 2150, 12.0),
        (2500, 2660, 9.0),
        (3020, 3510, 17.0),
    ):
        for station in range(start, end, 55):
            lights.append(
                curved_lamp(scene, station, -1, height, 2.0, 10.0, 0.18, heads=1)
            )
    scene.landmarks.append(
        {
            "name": "Singapore floodlight recipe",
            "structure": "Small race fittings at roughly 7 m intervals along continuous paired cables, supported about every 42 m; pit-side cable posts attach above the garage roof. Separate civic lamps include taller curved streetlamps along Esplanade Drive. Anderson Bridge and the ECP crossings have gradual cable-height transitions. Estimated 9.5 m ECP fittings remain below the reconstructed soffit; field power and pool radius are unchanged.",
            "reference": "Saved/Refs/singapore.mp4:534,598,614,618,642,650,1254,1255,1255.8 seconds",
            "confidence": "High for continuous cable strings and separate streetlamps; moderate for bridge distinction; low for metric height/spacing estimates. Cable support registrations are authoring estimates.",
        }
    )
    return lights


def build_lighting(scene: CircuitScene) -> list[CircuitLight]:
    if scene.slug == "bahrain":
        return bahrain(scene)
    if scene.slug == "jeddah":
        return jeddah(scene)
    if scene.slug == "singapore":
        return singapore(scene)
    raise ValueError(f"No reference-backed night fixture recipe for {scene.slug}")
