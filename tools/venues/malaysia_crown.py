"""Mapped round end umbrella of Sepang's double-frontage main stand."""

from __future__ import annotations

import math
from collections.abc import Callable

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely.geometry import LineString, Polygon

from venues.east_architecture import cylinder
from venues.pit_compounds import roof_shell


def end_umbrella(
    scene: CircuitScene,
    footprint: Polygon,
    origin: Point,
    axis: Point,
    side: Point,
    base_z: float,
    join_height: Callable[[float, float], float],
) -> None:
    center_u, center_v, radius = 293.99818933, -6.12008151, 32.29200334
    join_u = 268.4

    def xy(u: float, v: float) -> tuple[float, float]:
        return (
            origin[0] + axis[0] * u + side[0] * v,
            origin[1] + axis[1] * u + side[1] * v,
        )

    def height(x: float, y: float) -> float:
        dx, dy = x - origin[0], y - origin[1]
        u, v = dx * axis[0] + dy * axis[1], dx * side[0] + dy * side[1]
        radial = min(1.0, math.hypot(u - center_u, v - center_v) / radius)
        angle = math.atan2(v - center_v, u - center_u)
        folded = math.sin(12 * angle) ** 2
        crown = base_z + 22.4 + 2.1 * radial * radial + folded * radial**1.3
        blend = max(0.0, min(1.0, (u - join_u) / 11.6))
        blend = blend * blend * (3 - 2 * blend)
        return join_height(u, v) * (1 - blend) + crown * blend

    roof_shell(
        scene, footprint, height, "Building_SepangEndUmbrella", "White", "White", "White"
    )
    center_x, center_y = xy(center_u, center_v)
    cylinder(scene, (center_x, center_y, base_z + .2), 3.2, 3.2, 20.3, "Concrete", 24)
    cylinder(scene, (center_x, center_y, base_z + 18.8), 5.2, 5.2, 1.5, "Concrete", 32)
    center = center_x, center_y, height(center_x, center_y) - .3
    for rib in range(24):
        angle = math.tau * rib / 24
        previous = center
        for step in range(1, 17):
            distance = (radius - .6) * step / 16
            x, y = xy(center_u + distance * math.cos(angle), center_v + distance * math.sin(angle))
            current = x, y, height(x, y) - .3
            if footprint.covers(LineString([previous[:2], current[:2]]).buffer(.13)):
                scene.beam("Building_SepangEndUmbrellaRibs", "White", previous, current, .22)
            previous = current
        collar = center_x, center_y, base_z + 19.7
        x, y = xy(center_u + 14 * math.cos(angle), center_v + 14 * math.sin(angle))
        tip = x, y, height(x, y) - .5
        if footprint.covers(LineString([collar[:2], tip[:2]]).buffer(.14)):
            scene.beam("Building_SepangEndUmbrellaBranches", "White", collar, tip, .26)
    scene.beam(
        "Building_SepangEndUmbrellaSpire", "Steel",
        (center_x, center_y, base_z + 20.3), (center_x, center_y, base_z + 35), .28,
    )
    for height_index in range(3):
        z = base_z + 27.4 + height_index * .55
        ring_radius = 1.65 - height_index * .45
        for segment in range(24):
            a, b = segment * math.tau / 24, (segment + 1) * math.tau / 24
            scene.beam(
                "Building_SepangEndUmbrellaSpireCage", "Steel",
                (center_x + ring_radius * math.cos(a), center_y + ring_radius * math.sin(a), z),
                (center_x + ring_radius * math.cos(b), center_y + ring_radius * math.sin(b), z), .09,
            )
    scene.landmarks.append({
        "name": "Sepang round T15-end umbrella",
        "osm_id": 144247993,
        "mapped_diameter_m": radius * 2,
        "center_x_m": center_x,
        "center_y_m": center_y,
        "concourse_datum_m": base_z,
        "radial_ribs": 24,
        "spire_above_concourse_m": 35.0,
        "source": "Operator architecture photograph; actual mapped circular end outline. Roof height/radial section, pier and spire dimensions are visual estimates, not a structural survey. Native5060 forward camera misses the crown; no relocation is made for that view.",
    })
