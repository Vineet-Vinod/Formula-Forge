"""Anderson Bridge: three bowstring trusses, arched cross-ties and four portals."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import add, mul, norm, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.singapore_bridge_dataclasses import AndersonBridge


def bridge_frame(scene: CircuitScene, source: AndersonBridge) -> tuple[Point, Point, Point]:
    a, b = [(scene.geo(lat, lon)[0], scene.geo(lat, lon)[1], 0.0)
            for lon, lat in source.axis_wgs84]
    axis = norm(sub(b, a))
    road = scene.at(source.station_m)
    if axis[0] * road.tx + axis[1] * road.ty < 0:
        axis = mul(axis, -1)
    return mul(add(a, b), 0.5), axis, (axis[1], -axis[0], 0.0)


def anderson_bridge(scene: CircuitScene) -> None:
    source = TypeAdapter(AndersonBridge).validate_json(
        (scene.sources / "anderson-bridge.json").read_bytes()
    )
    if abs(scene.provenance.route.uniform_scale - source.uniform_scale) > 1e-9:
        raise ValueError("Anderson Bridge requires its registered geographic frame")
    center, axis, right = bridge_frame(scene, source)
    for side in (-1, 1):
        scene.branding(2798.0, 2905.0, side, "PanelLenovo")

    def point(along: float, across: float, height: float) -> Point:
        xy = add(center, add(mul(axis, along), mul(right, across)))
        return xy[0], xy[1], scene.at(source.station_m + along).z + height

    def top(along: float) -> float:
        t = 2 * along / source.steel_span_m
        return 0.85 + (source.main_truss_top_m - 0.85) * (1 - t * t)

    divisions = 24
    stations = [-source.steel_span_m / 2 + source.steel_span_m * i / divisions
                for i in range(divisions + 1)]
    for across in (-source.girder_pitch_m, 0.0, source.girder_pitch_m):
        for a, b in pairwise(stations):
            scene.beam("Building_AndersonLowerChords", "White",
                       point(a, across, 0.7), point(b, across, 0.7),
                       source.girder_width_m, 0.3)
            scene.beam("Building_AndersonUpperChords", "White",
                       point(a, across, top(a)), point(b, across, top(b)),
                       source.girder_width_m, 0.28)
            for begin, finish in ((point(a, across, 0.75), point(b, across, top(b))),
                                  (point(a, across, top(a)), point(b, across, 0.75))):
                scene.beam("Building_AndersonLattice", "White", begin, finish, 0.12)
            scene.beam("Building_AndersonVerticals", "White",
                       point(a, across, 0.75), point(a, across, top(a)), 0.14)

    for along in (-24.0, -16.0, -8.0, 0.0, 8.0, 16.0, 24.0):
        for opening in (-1, 0):
            for segment in range(16):
                t0, t1 = segment / 16, (segment + 1) / 16
                q0 = source.girder_pitch_m * (opening + t0)
                q1 = source.girder_pitch_m * (opening + t1)
                z0 = top(along) + source.cross_tie_rise_m * math.sin(math.pi * t0)
                z1 = top(along) + source.cross_tie_rise_m * math.sin(math.pi * t1)
                for lift in (0.0, 0.32):
                    scene.beam("Building_AndersonCrossTieChords", "White",
                               point(along, q0, z0 + lift), point(along, q1, z1 + lift),
                               0.12)
                scene.beam("Building_AndersonCrossTieWeb", "White",
                           point(along, q0, z0), point(along, q1, z1 + 0.32), 0.065)
                scene.beam("Building_AndersonCrossTieWeb", "White",
                           point(along, q0, z0 + 0.32), point(along, q1, z1), 0.065)
                # Register the actual narrow cross-tie underside for catch-fence clearance.
                qa, qb = point(along - 0.07, q0, z0 - 0.06), point(along + 0.07, q0, z0 - 0.06)
                qc, qd = point(along + 0.07, q1, z1 - 0.06), point(along - 0.07, q1, z1 - 0.06)
                scene.overhead_soffits.extend(((qa, qb, qc), (qa, qc, qd)))
        if along in (-16.0, 0.0, 16.0):
            for q in (-7.35, -2.55):
                z = top(along) + source.cross_tie_rise_m * math.sin(math.pi * (q / source.girder_pitch_m + 1))
                for edge in (q - 0.8, q + 0.8):
                    attachment = top(along) + source.cross_tie_rise_m * math.sin(math.pi * (edge / source.girder_pitch_m + 1)) - 0.06
                    scene.beam("Building_AndersonSignHangers", "Steel",
                               point(along, edge, z - 0.45), point(along, edge, attachment), 0.035)
                scene.banner(point(along, q - 0.9, z - 1.4), point(along, q + 0.9, z - 1.4),
                             0.95, "PanelLenovo", "Building_AndersonEventPanels")

    for side in (-1, 1):
        across = side * (source.girder_pitch_m + 1.5)
        a, b = -source.overall_length_m / 2, source.overall_length_m / 2
        scene.beam("Building_AndersonFootwalks", "Cream",
                   point(a, across, 0.0), point(b, across, 0.0), 2.5, 0.3)
        outer = side * (source.girder_pitch_m + 2.65)
        for height in (0.45, 1.15):
            scene.beam("Building_AndersonRailings", "Steel",
                       point(a, outer, height), point(b, outer, height), 0.065)
        for index in range(24):
            u = a + (b - a) * index / 23
            scene.beam("Building_AndersonRailingPosts", "Steel",
                       point(u, outer, 0.15), point(u, outer, 1.2), 0.065)
        for along in (a, b):
            for q in (across - 1.25, across + 1.25):
                scene.beam("Building_AndersonStonePiers", "Cream",
                           point(along, q, 0.0), point(along, q, 3.35), 0.6, 0.8)
                scene.beam("Building_AndersonPortalCaps", "White",
                           point(along - 0.5, q, 3.45), point(along + 0.5, q, 3.45), 0.82, 0.18)
            for segment in range(16):
                t0, t1 = segment * math.pi / 16, (segment + 1) * math.pi / 16
                scene.beam("Building_AndersonStoneArchways", "Cream",
                           point(along, across - math.cos(t0), 2.35 + math.sin(t0)),
                           point(along, across - math.cos(t1), 2.35 + math.sin(t1)), 0.35)

    scene.landmarks.append({
        "name": "Anderson Bridge", "osm_id": 9574530,
        "roadway_openings": 2, "longitudinal_truss_planes": 3,
        "steel_span_estimate_m": source.steel_span_m,
        "clear_opening_estimate_m": source.girder_pitch_m - source.girder_width_m,
        "source": "anderson-bridge.json and anderson-bridge-review.json",
        "road_clearance_exception": "Arched cross ties and suspended event panels are overhead; the three ground-level trusses stay outside the left-opening legal road and its protection.",
        "dimensions_status": "Mapped deck axis; heritage drawing topology and original onboard appearance. Member sizes, clear opening, arch heights and event offsets are bounded reconstructions, not a structural survey. Conflicting 20ft/26ft height descriptions remain disclosed.",
    })
