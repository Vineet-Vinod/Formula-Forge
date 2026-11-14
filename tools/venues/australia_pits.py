"""The reference-era Albert Park garages, glazed upper floor and roof terrace."""

from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

PIT_START = 4939.105
PIT_END = 5229.679
PIT_DEPTH = 21.0
PIT_ROOF = 9.2


def _pit_bay(scene: CircuitScene, start: float, end: float, index: int, count: int) -> None:
    first, last = scene.at(start), scene.at(end)

    def point(fraction: float, inset: float, height: float) -> Point:
        sample = first if fraction == 0 else last if fraction == 1 else scene.at(start + (end - start) * fraction)
        return sample.point(sample.half_width + 13 + inset, height)

    footprint = Polygon([
        point(0, 0, 0)[:2], point(1, 0, 0)[:2],
        point(1, PIT_DEPTH, 0)[:2], point(0, PIT_DEPTH, 0)[:2],
    ])
    scene.terrain_cutouts.append(footprint.difference(scene.road_mask))
    for height in (0.0, 4.6, PIT_ROOF - 0.2):
        scene.beam(
            "Building_AlbertParkPitSlabs", "White",
            point(0, PIT_DEPTH / 2, height),
            point(1, PIT_DEPTH / 2, height), PIT_DEPTH, 0.4,
        )
    # Upper glazing sits behind the open balcony and the exposed blue frame.
    scene.banner(
        point(0.055, 0.7, 0.25), point(0.945, 0.7, 0.25),
        3.95, "Steel", "Building_AlbertParkGarageDoors",
    )
    for height in (1.0, 1.8, 2.6, 3.4):
        scene.beam(
            "Building_AlbertParkShutterRails", "Concrete",
            point(0.055, 0.69, height), point(0.945, 0.69, height),
            0.035, 0.035,
        )
    for pane in range(3):
        left, right = pane / 3 + 0.012, (pane + 1) / 3 - 0.012
        scene.banner(
            point(left, 1.8, 4.85), point(right, 1.8, 4.85),
            3.95, "Glass", "Building_AlbertParkUpperGlazing",
        )
        scene.beam(
            "Building_AlbertParkWindowMullions", "Steel",
            point(pane / 3, 1.77, 4.8), point(pane / 3, 1.77, 8.9), 0.075,
        )
    scene.beam(
        "Building_AlbertParkWindowTransoms", "Steel",
        point(0, 1.77, 6.8), point(1, 1.77, 6.8), 0.065,
    )
    scene.beam(
        "Building_AlbertParkFrame", "SeatBlue",
        point(0, 0.15, 0), point(0, 0.15, PIT_ROOF), 0.24,
    )
    for floor in (4.6, PIT_ROOF):
        scene.beam(
            "Building_AlbertParkFascias", "White",
            point(0, 0.18, floor - 0.1), point(1, 0.18, floor - 0.1),
            0.38, 0.35,
        )
        for height in (floor + 0.45, floor + 1.05):
            scene.beam(
                "Building_AlbertParkTerraceRails", "Steel",
                point(0, 0.12, height), point(1, 0.12, height), 0.055,
            )
        for fraction in (0.0, 0.5):
            scene.beam(
                "Building_AlbertParkTerracePosts", "Steel",
                point(fraction, 0.12, floor), point(fraction, 0.12, floor + 1.05),
                0.055,
            )
    scene.banner(
        point(1, PIT_DEPTH, 0.2), point(0, PIT_DEPTH, 0.2),
        PIT_ROOF - 0.4, "White", "Building_AlbertParkRear",
    )
    if index in (0, count - 1):
        fraction = 0.0 if index == 0 else 1.0
        scene.banner(
            point(fraction, 0.2, 0.2), point(fraction, PIT_DEPTH, 0.2),
            PIT_ROOF - 0.4, "White", "Building_AlbertParkEnds",
        )
    pole = point(0.5, 0.5, PIT_ROOF)
    scene.beam(
        "Building_AlbertParkFlagpoles", "Steel", pole,
        point(0.5, 0.5, 13.0), 0.055,
    )
    def cloth(u: float, height: float) -> Point:
        return (
            pole[0] + first.tx * u + first.ty * 0.2 * math.sin(u * 3.8),
            pole[1] + first.ty * u - first.tx * 0.2 * math.sin(u * 3.8),
            pole[2] + height - 0.12 * u,
        )

    for segment in range(3):
        a, b = segment * 0.6, (segment + 1) * 0.6
        scene.quad(
            "Building_AlbertParkFlags", "Red" if index % 2 else "Black",
            cloth(a, 2.6), cloth(b, 2.6), cloth(b, 3.8), cloth(a, 3.8),
        )
        scene.quad(
            "Building_AlbertParkFlags", "Red" if index % 2 else "Black",
            cloth(a, 2.6), cloth(a, 3.8), cloth(b, 3.8), cloth(b, 2.6),
        )


def pit_building(scene: CircuitScene) -> None:
    count = math.ceil((PIT_END - PIT_START) / 8)
    for index in range(count):
        _pit_bay(
            scene, PIT_START + (PIT_END - PIT_START) * index / count,
            PIT_START + (PIT_END - PIT_START) * (index + 1) / count, index, count,
        )
    scene.landmarks.append({
        "name": "Reference-era Albert Park pit building",
        "start_m": PIT_START, "end_m": PIT_END, "side": 1,
        "depth_m": PIT_DEPTH, "storeys": 2, "roof_height_estimate_m": PIT_ROOF,
        "flag_top_estimate_m": 13.0,
        "source": "pit-facade-review.json; supplied 174/176/178 s and Parks Victoria February 2026 plan, PDF p112.",
        "qualification": "Existing horizontal envelope retained; storey arrangement is observed. Heights, framing sizes and flag spacing are bounded visual estimates, not a survey. Pre-redevelopment building, not the proposed 2028 facility.",
    })
