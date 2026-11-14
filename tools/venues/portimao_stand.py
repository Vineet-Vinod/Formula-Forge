"""Portimão’s two seating tiers, glazed VIP level and cantilever canopy."""

from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.east_architecture import double_quad, frame, upward_quad
from venues.portimao_dataclasses import StandFrame


def point(f: StandFrame, u: float, v: float, z: float) -> Point:
    p = add(f.center, add(mul(f.axis, u), mul(f.rear, v)))
    return p[0], p[1], z


def wall(
    scene: CircuitScene,
    f: StandFrame,
    u0: float,
    u1: float,
    v: float,
    bottom: float,
    top: float,
    material: str,
    kind: str,
) -> None:
    double_quad(
        scene,
        kind,
        material,
        point(f, u0, v, bottom),
        point(f, u1, v, bottom),
        point(f, u1, v, top),
        point(f, u0, v, top),
    )


def tier(
    scene: CircuitScene,
    f: StandFrame,
    u0: float,
    u1: float,
    front: float,
    level: float,
    rows: int,
    tread: float,
    rise: float,
    underside: float,
) -> None:
    bays = math.ceil((u1 - u0) / 6)
    for bay in range(bays):
        a, b = u0 + (u1 - u0) * bay / bays, u0 + (u1 - u0) * (bay + 1) / bays
        first = point(f, a, front, level + rise)
        last = point(f, b, front, level + rise)
        ga = (first[0], first[1], underside)
        gb = (last[0], last[1], underside)
        double_quad(
            scene, "Building_PortimaoStandFront", "Concrete", ga, gb, last, first
        )
        for row in range(rows):
            v0, v1 = front + row * tread, front + (row + 1) * tread
            z = level + (row + 1) * rise
            corners = (
                point(f, a, v0, z),
                point(f, b, v0, z),
                point(f, b, v1, z),
                point(f, a, v1, z),
            )
            for p in corners:
                if p[2] < scene.ground(p[0], p[1]) + 0.08:
                    raise ValueError(
                        f"Portimao stand tread intersects retained ground: {p}"
                    )
            upward_quad(scene, "Building_PortimaoStandTread", "Concrete", *corners)
            if row:
                wall(
                    scene,
                    f,
                    a,
                    b,
                    v0,
                    z - rise,
                    z,
                    "Concrete",
                    "Building_PortimaoStandRiser",
                )
            scene.beam(
                "Building_PortimaoStandSeats",
                "SeatRed",
                add(corners[0], (0, 0, 0.15)),
                add(corners[1], (0, 0, 0.15)),
                0.40,
                0.16,
            )
            scene.spectators(
                add(corners[0], (0, 0, 0.30)),
                add(corners[1], (0, 0, 0.30)),
                row,
                "Building_Crowd_Portimao",
            )
            for u in (a, b) if bay in (0, bays - 1) else ():
                if not (u == u0 or u == u1):
                    continue
                p, q = point(f, u, v0, z), point(f, u, v1, z)
                ga = (p[0], p[1], underside)
                gb = (q[0], q[1], underside)
                double_quad(
                    scene, "Building_PortimaoStandEnds", "Concrete", ga, gb, q, p
                )

        back = front + rows * tread
        wall(
            scene,
            f,
            a,
            b,
            back,
            underside,
            level + rows * rise,
            "Concrete",
            "Building_PortimaoTierBack",
        )
        double_quad(
            scene,
            "Building_PortimaoTierSoffit",
            "Concrete",
            point(f, a, front, underside),
            point(f, b, front, underside),
            point(f, b, back, underside),
            point(f, a, back, underside),
        )


def main_grandstand(scene: CircuitScene) -> dict[str, float | int]:
    building = scene.footprint(38166697)
    center, axis, rear, length, width = frame(building)
    sample, _ = scene.nearest(center[0], center[1])
    if (center[0] - sample.x) * rear[0] + (center[1] - sample.y) * rear[1] < 0:
        rear = mul(rear, -1)
    # Retain the former roof's road-derived datum while testing the new section.
    datum = sample.z
    f = StandFrame(center, axis, rear, width, datum, datum + 19.8)
    front = -width / 2 + 0.30
    vip_v = front + 12 * 0.82
    upper_v = vip_v + 3.0
    if upper_v + 11 * 0.93 > width / 2 - 0.05:
        raise ValueError("Two tiers and VIP room exceed the mapped canopy width")
    foundation_nodes = []
    bases = []
    for block in range(4):
        u0, u1 = -180 + block * 90, -180 + (block + 1) * 90
        probes = [point(f, u, front, 0) for u in (u0, (u0 + u1) / 2, u1)]
        base = max(datum + 0.8, max(scene.ground(p[0], p[1]) for p in probes) + 0.25)
        bases.append(base)
        lower_top = base + 12 * 0.45
        vip_top = lower_top + 3.10
        highest = vip_top + 11 * 0.53 + 1.6
        if highest > f.roof - 0.4:
            raise ValueError(
                f"Crowd/roof conflict at block {block}: {highest}, roof {f.roof}"
            )
        foundation = (
            min(
                scene.ground(*point(f, u0 + (u1 - u0) * i / 15, v, 0)[:2])
                for i in range(16)
                for v in (front, vip_v)
            )
            - 0.15
        )
        tier(scene, f, u0, u1, front, base, 12, 0.82, 0.45, foundation)
        tier(scene, f, u0, u1, upper_v, vip_top, 11, 0.93, 0.53, vip_top - 0.20)
        floor = (
            point(f, u0, vip_v, lower_top),
            point(f, u1, vip_v, lower_top),
            point(f, u1, upper_v, lower_top),
            point(f, u0, upper_v, lower_top),
        )
        upward_quad(scene, "Building_PortimaoVIPFloor", "Concrete", *floor)
        ceiling = tuple((p[0], p[1], vip_top) for p in floor)
        double_quad(scene, "Building_PortimaoVIPCeiling", "White", *ceiling)
        # The published 72 rooms are divided evenly for this reconstruction.
        for suite in range(18):
            a, b = u0 + (u1 - u0) * suite / 18, u0 + (u1 - u0) * (suite + 1) / 18
            wall(
                scene,
                f,
                a,
                b,
                vip_v,
                lower_top + 0.25,
                vip_top - 0.25,
                "Glass",
                "Building_PortimaoVIP",
            )
            p = point(f, a, vip_v - 0.025, lower_top + 0.15)
            scene.beam(
                "Building_PortimaoVIPFrames", "White", p, add(p, (0, 0, 2.85)), 0.10
            )
        wall(
            scene,
            f,
            u0,
            u1,
            vip_v - 0.03,
            lower_top - 0.12,
            lower_top + 0.25,
            "White",
            "Building_PortimaoVIPFascia",
        )
        wall(
            scene,
            f,
            u0,
            u1,
            vip_v - 0.03,
            vip_top - 0.25,
            vip_top + 0.10,
            "White",
            "Building_PortimaoVIPFascia",
        )
        for a in (u0, u1):
            side = [
                point(f, a, vip_v, lower_top),
                point(f, a, upper_v, lower_top),
                point(f, a, upper_v, vip_top),
                point(f, a, vip_v, vip_top),
            ]
            double_quad(scene, "Building_PortimaoVIPEnds", "White", *side)
        roof_rear = width / 2 - 0.45
        support_z = vip_top + 11 * 0.53 + 0.20
        rear_lower = (
            min(scene.ground(*point(f, u, roof_rear, 0)[:2]) for u in (u0, u1)) - 0.15
        )
        heading = math.atan2(f.axis[1], f.axis[0])
        scene.box(
            "Building_PortimaoRearBody",
            "Concrete",
            point(f, (u0 + u1) / 2, roof_rear, (rear_lower + support_z) / 2),
            u1 - u0,
            0.25,
            support_z - rear_lower,
            heading,
        )
        back = upper_v + 11 * 0.93
        ledge_bottom = vip_top + 11 * 0.53 - 0.03
        scene.box(
            "Building_PortimaoRearLedge",
            "Concrete",
            point(
                f,
                (u0 + u1) / 2,
                (back + roof_rear + 0.125) / 2,
                (ledge_bottom + support_z) / 2,
            ),
            u1 - u0,
            roof_rear + 0.125 - back,
            support_z - ledge_bottom,
            heading,
        )
        for rib in range(9):
            u = u0 + (u1 - u0) * (rib + 0.5) / 9
            p = point(f, u, roof_rear, support_z - 0.05)
            scene.beam(
                "Building_PortimaoRearStruts",
                "Steel",
                p,
                point(f, u, roof_rear - 0.8, f.roof - 0.30),
                0.18,
            )
            # Cantilever ribs stop above the seating; no front ground columns.
            scene.beam(
                "Building_PortimaoCantilever",
                "Steel",
                point(f, u, roof_rear, f.roof - 0.45),
                point(f, u, -width / 2 + 0.15, f.roof - 0.12),
                0.12,
                0.25,
            )
        foundation_nodes.extend(probes)
    if max(bases) - min(bases) > 0.001:
        raise ValueError(
            "The reconstructed continuous stand needs matching tier levels at structural joins"
        )
    for u in (-90.0, 0.0, 90.0):
        for v0, z0, rows, tread, rise in (
            (front, bases[0], 12, 0.82, 0.45),
            (upper_v, bases[0] + 12 * 0.45 + 3.10, 11, 0.93, 0.53),
        ):
            for row in range(rows):
                v = v0 + row * tread
                z = z0 + (row + 1) * rise
                upward_quad(
                    scene,
                    "Building_PortimaoJointSeal",
                    "Black",
                    point(f, u - 0.02, v, z + 0.002),
                    point(f, u + 0.02, v, z + 0.002),
                    point(f, u + 0.02, v + tread, z + 0.002),
                    point(f, u - 0.02, v + tread, z + 0.002),
                )
                wall(
                    scene,
                    f,
                    u - 0.02,
                    u + 0.02,
                    v - 0.002,
                    z - rise,
                    z,
                    "Black",
                    "Building_PortimaoJointSeal",
                )
        wall(
            scene,
            f,
            u - 0.02,
            u + 0.02,
            vip_v - 0.002,
            bases[0] + 12 * 0.45,
            bases[0] + 12 * 0.45 + 3.10,
            "Black",
            "Building_PortimaoJointSeal",
        )
    # Original mapped plan, one flat upper skin, tapered closed underside.
    roof = Polygon(building.ring)
    ring = list(roof.exterior.coords)[:-1]
    if not roof.exterior.is_ccw:
        ring.reverse()

    def under(x: float, y: float) -> float:
        v = (x - center[0]) * rear[0] + (y - center[1]) * rear[1]
        return f.roof - 0.15 - 1.35 * max(0, 1 - abs(v - width * 0.22) / (width * 0.72))

    for a, b in zip(ring, ring[1:] + ring[:1]):
        pa, pb = (a[0], a[1], f.roof), (b[0], b[1], f.roof)
        c = (center[0], center[1], f.roof)
        scene.triangle("Building_PortimaoCanopy", "Roof", c, pa, pb)
        ua, ub = (a[0], a[1], under(*a)), (b[0], b[1], under(*b))
        uc = (center[0], center[1], under(*center[:2]))
        scene.triangle("Building_PortimaoCanopy", "White", uc, ub, ua)
        double_quad(scene, "Building_PortimaoCanopyEdge", "White", ua, ub, pb, pa)
    report = {
        "mapped_roof_length_m": length,
        "mapped_roof_width_m": width,
        "roof_level_m": f.roof,
        "blocks": 4,
        "lower_rows": 12,
        "upper_rows": 11,
        "vip_suites": 72,
        "minimum_foundation_ground_m": min(
            scene.ground(p[0], p[1]) for p in foundation_nodes
        ),
        "maximum_foundation_ground_m": max(
            scene.ground(p[0], p[1]) for p in foundation_nodes
        ),
    }
    scene.landmarks.append(
        {
            **report,
            "name": "Bancada Principal two-tier architectural reconstruction",
            "source": "architecture/mainstand-section-review.json and mainstand-dimensions-correction.json",
            "dimensions_status": "Mapped roof plan and primary four90m structural blocks /72suites. "
            "Tier row counts, tread/riser dimensions, room depth, storey heights, "
            "19.8m canopy height above the retained road datum and4cm sealed joints "
            "are architectural estimates. Original road/field, pit facade and VIP tower "
            "remain unchanged; fresh cooked visual review is required.",
        }
    )
    return report
