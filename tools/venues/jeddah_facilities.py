"""Registered Corniche pit compound and the documented T27 pavilion."""

from __future__ import annotations

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.east_architecture import footprint_stand, frame
from venues.jeddah_pit_details import (
    detail_source,
    garage_detail,
    pit_workstations,
    upper_bay,
)
from venues.jeddah_pits import (
    pit_floor_point,
    pit_route_source,
    route_section,
    working_apron,
)

PIT_START = 6009.0
PIT_END = 115.0


def pit_compound(scene: CircuitScene) -> None:
    route = pit_route_source()
    detail = detail_source()
    samples = [scene.at(PIT_START + index * 10) for index in range(29)]
    front_ring = [sample.point(-sample.half_width - 13)[:2] for sample in samples]
    rear_ring = [
        sample.point(-sample.half_width - 39)[:2] for sample in reversed(samples)
    ]
    scene.ground_patches.append(
        (Polygon(front_ring + rear_ring), scene.at(0).z, "Concrete")
    )
    for garage in range(45):
        start = PIT_START + 1.25 + garage * 5.8 + (16.5 if garage >= 21 else 0)
        a, b = scene.at(start), scene.at(start + 5.8)
        front_a, front_b = -a.half_width - 13, -b.half_width - 13
        section_a = route_section(route, start, a.point(front_a))
        section_b = route_section(route, start + 5.8, b.point(front_b))
        depth = 26.0
        footprint = Polygon(
            [
                a.point(front_a)[:2],
                b.point(front_b)[:2],
                b.point(front_b - depth)[:2],
                a.point(front_a - depth)[:2],
            ]
        )
        scene.terrain_cutouts.append(footprint)
        for level in range(5):
            height = level * 4.6
            scene.quad(
                "Building_JeddahPitFloors",
                "Runoff" if level == 0 else "White",
                pit_floor_point(a, section_a, front_a) if level == 0 else a.point(front_a, height),
                pit_floor_point(b, section_b, front_b) if level == 0 else b.point(front_b, height),
                pit_floor_point(b, section_b, front_b - depth) if level == 0 else b.point(front_b - depth, height),
                pit_floor_point(a, section_a, front_a - depth) if level == 0 else a.point(front_a - depth, height),
                up=True,
            )
            if level == 4:
                continue
            if level == 0:
                garage_detail(scene, a, b, front_a, front_b, detail)
                for sample, section, lane in ((a, section_a, front_a), (b, section_b, front_b)):
                    scene.banner(
                        pit_floor_point(sample, section, lane - .18, .10),
                        pit_floor_point(sample, section, lane - .65, .10),
                        3.9, "Black", "Building_JeddahPitGarageReturns",
                    )
                scene.quad(
                    "Building_JeddahPitGarageCeilings", "Black",
                    a.point(front_a, 4.43), b.point(front_b, 4.43),
                    b.point(front_b - detail.garage_back_depth_m - .5, 4.43),
                    a.point(front_a - detail.garage_back_depth_m - .5, 4.43),
                    up=False,
                )
                scene.beam(
                    "Building_JeddahPitGarageLintels", "White",
                    a.point(front_a, 4.15), b.point(front_b, 4.15), .3, .55,
                )
            else:
                upper_bay(scene, a, b, front_a, front_b, height, detail)
            scene.banner(
                a.point(front_a - depth, height + 0.25),
                b.point(front_b - depth, height + 0.25),
                4.1,
                "White",
                "Building_JeddahPitRear",
            )
        for lane_a, lane_b in ((front_a, front_b), (front_a - depth, front_b - depth)):
            scene.beam(
                "Building_JeddahPitFrame",
                "White",
                a.point(lane_a),
                a.point(lane_a, 18.4),
                0.4,
            )
            scene.beam(
                "Building_JeddahPitFrame",
                "White",
                b.point(lane_b),
                b.point(lane_b, 18.4),
                0.4,
            )
    # The service passage between garages21/22 stays open at ground level.
    a, b = (
        scene.at(PIT_START + 1.25 + 21 * 5.8),
        scene.at(PIT_START + 1.25 + 21 * 5.8 + 16.5),
    )
    for deck_height in (4.6, 9.2, 13.8, 18.4):
        scene.beam(
            "Building_JeddahPitServiceBridge",
            "White",
            a.point(-a.half_width - 26, deck_height),
            b.point(-b.half_width - 26, deck_height),
            26,
            0.3,
        )
    for roof in range(10):
        a, b = scene.at(PIT_START + roof * 28), scene.at(PIT_START + (roof + 1) * 28)
        height = 19.2 + (1.3 if 3 <= roof <= 6 else 0.0)
        near_a, near_b = -a.half_width - 8, -b.half_width - 8
        far_a, far_b = -a.half_width - 39, -b.half_width - 39
        first = [
            a.point(near_a, height),
            b.point(near_b, height),
            b.point(far_b, height + 1.4),
            a.point(far_a, height + 1.4),
        ]
        second = [add(point, (0, 0, -0.22)) for point in first]
        scene.quad(
            "Building_JeddahPitCanopies",
            "White",
            first[0],
            first[1],
            first[2],
            first[3],
            up=True,
        )
        scene.quad(
            "Building_JeddahPitCanopies",
            "White",
            second[3],
            second[2],
            second[1],
            second[0],
            up=False,
        )
        for index in range(4):
            next_index = (index + 1) % 4
            scene.quad(
                "Building_JeddahPitCanopyEdges",
                "White",
                second[index],
                second[next_index],
                first[next_index],
                first[index],
            )
        for fraction in (0.0, 0.5, 1.0):
            sample = scene.at(PIT_START + (roof + fraction) * 28)
            scene.beam(
                "Building_JeddahPitCanopyFrame",
                "White",
                sample.point(-sample.half_width - 8, height - 0.35),
                sample.point(-sample.half_width - 39, height + 1.05),
                0.16,
            )
    for station in (PIT_START, PIT_START + 280):
        sample = scene.at(station)
        front, rear = (
            sample.point(-sample.half_width - 13),
            sample.point(-sample.half_width - 39),
        )
        scene.banner(front, rear, 18.4, "White", "Building_JeddahPitEnds")
    scene.landmarks.append(
        {
            "name": "Jeddah 280 m four-storey pit and team compound",
            "start_m": PIT_START,
            "end_m": PIT_END,
            "side": -1,
            "length_m": 280,
            "levels": 4,
            "garage_bays": 45,
            "body_height_estimate_m": 18.4,
            "source_note": "Primary F1/Tilke description gives 280 m and four storeys. FIA 2025 pit plan shows 45 numbered bays and a central service break. Direct forward 235/239/243 s puts the glazed garage/club building LEFT and open crowd stand RIGHT. Placement is opposite the actual 271 m main-stand footprint, with ±20 m longitudinal uncertainty. Depth, floor heights, canopy slopes and terrace details are reconstructed estimates. The prior 554 m/right-side generic compound is removed.",
        }
    )

    working_apron(scene)
    pit_workstations(scene)


def mapped_stands(scene: CircuitScene) -> None:
    stands = ((1154622779, 22), (1154622781, 16), (1154622780, 16), (1154622782, 19))
    for osm_id, _rows in stands:
        building = scene.footprint(osm_id)
        center, _axis, _side, _length, _width = frame(building)
        sample, _distance = scene.nearest(center[0], center[1])
        scene.ground_patches.append((Polygon(building.ring), sample.z, "Concrete"))
    for osm_id, rows in stands:
        footprint_stand(scene, osm_id, rows, "cantilever", seat_material="SeatBlue")


def pavilion_footprint(scene: CircuitScene) -> Polygon:
    center = scene.geo(21.6251343, 39.1069061)
    sample = scene.at(5500)
    axis = sample.tx, sample.ty
    normal = sample.ty, -sample.tx
    return Polygon(
        [
            (
                center[0] + axis[0] * u + normal[0] * v,
                center[1] + axis[1] * u + normal[1] * v,
            )
            for u, v in ((-42.5, -10), (42.5, -10), (42.5, 10), (-42.5, 10))
        ]
    )


def t27_pavilion(scene: CircuitScene) -> None:
    center = scene.geo(21.6251343, 39.1069061)
    sample = scene.at(5500)
    axis = sample.tx, sample.ty
    normal = sample.ty, -sample.tx
    base = scene.at(5390).z
    footprint = pavilion_footprint(scene)
    scene.ground_patches.append((footprint, base, "Concrete"))
    scene.terrain_cutouts.append(footprint)

    def point(u: float, v: float, z: float) -> Point:
        return (
            center[0] + axis[0] * u + normal[0] * v,
            center[1] + axis[1] * u + normal[1] * v,
            base + z,
        )

    for bay in range(10):
        u0, u1 = -42.5 + bay * 8.5, -42.5 + (bay + 1) * 8.5
        for level in (0.0, 4.4, 8.8):
            scene.quad(
                "Building_T27PavilionFloors",
                "Concrete",
                point(u0, -10, level),
                point(u1, -10, level),
                point(u1, 10, level),
                point(u0, 10, level),
                up=True,
            )
            scene.quad(
                "Building_T27PavilionSoffits",
                "Concrete",
                point(u0, -10, level - 0.24),
                point(u1, -10, level - 0.24),
                point(u1, 10, level - 0.24),
                point(u0, 10, level - 0.24),
                up=False,
            )
        for side in (-1, 1):
            for level in (0.0, 4.4):
                for pane in range(3):
                    left = u0 + 0.3 + pane * (8.5 - 0.6) / 3
                    right = u0 + 0.3 + (pane + 1) * (8.5 - 0.6) / 3
                    scene.banner(
                        point(left, side * 9.62, level + 0.55),
                        point(right, side * 9.62, level + 0.55),
                        3.5,
                        "Cream" if level == 0 and bay in (0, 1, 8, 9) else "Glass",
                        "Building_T27PavilionServicePanels"
                        if level == 0 and bay in (0, 1, 8, 9)
                        else "Building_T27PavilionGlazing",
                    )
                    scene.beam(
                        "Building_T27PavilionMullions",
                        "Steel",
                        point(left, side * 9.68, level + 0.5),
                        point(left, side * 9.68, level + 4.1),
                        0.07,
                    )
                scene.beam(
                    "Building_T27PavilionTransoms",
                    "Steel",
                    point(u0 + 0.3, side * 9.68, level + 3.2),
                    point(u1 - 0.3, side * 9.68, level + 3.2),
                    0.08,
                )
                scene.beam(
                    "Building_T27PavilionFrame",
                    "White",
                    point(u0, side * 10, level),
                    point(u0, side * 10, level + 4.4),
                    0.45,
                )
                scene.beam(
                    "Building_T27PavilionFrame",
                    "White",
                    point(u0, side * 10, level + 4.4),
                    point(u1, side * 10, level + 4.4),
                    0.38,
                    0.3,
                )
        for v0, v1 in ((-11.2, 0.0), (0.0, 11.2)):
            z0, z1 = 9.1 + (1.6 if v0 == 0 else 0), 9.1 + (1.6 if v1 == 0 else 0)
            roof = [
                point(u0, v0, z0),
                point(u0, v1, z1),
                point(u1, v1, z1),
                point(u1, v0, z0),
            ]
            scene.quad(
                "Building_T27PavilionCanopy",
                "White",
                roof[0],
                roof[1],
                roof[2],
                roof[3],
                up=True,
            )
            scene.quad(
                "Building_T27PavilionCanopy",
                "White",
                add(roof[3], (0, 0, -0.38)),
                add(roof[2], (0, 0, -0.38)),
                add(roof[1], (0, 0, -0.38)),
                add(roof[0], (0, 0, -0.38)),
                up=False,
            )
            for index in range(4):
                following = (index + 1) % 4
                scene.quad(
                    "Building_T27PavilionCanopyEdges",
                    "White",
                    roof[index],
                    add(roof[index], (0, 0, -0.38)),
                    add(roof[following], (0, 0, -0.38)),
                    roof[following],
                )
            scene.beam(
                "Building_T27PavilionCanopyFrame",
                "White",
                point(u0, v0, z0 - 0.22),
                point(u0, v1, z1 - 0.22),
                0.25,
            )
        scene.beam(
            "Building_T27PavilionRoofTruss",
            "White",
            point(u0, -10.8, 8.85),
            point(u0, 10.8, 8.85),
            0.22,
        )
        for side in (-1, 1):
            for fraction in (0.25, 0.5, 0.75):
                scene.beam(
                    "Building_T27PavilionRoofTruss",
                    "White",
                    point(u0, side * 10.8 * fraction, 8.85),
                    point(u0, side * 10.8 * (1 - fraction), 10.45 - 1.6 * (1 - fraction)),
                    0.16,
                )
    for u in (-42.5, 42.5):
        for level in (0.0, 4.4):
            scene.banner(
                point(u, -10, level + 0.5),
                point(u, 10, level + 0.5),
                3.5,
                "Cream" if level == 0 else "Glass",
                "Building_T27PavilionEnds",
            )
        for side in (-1, 1):
            scene.beam(
                "Building_T27PavilionEndPiers", "Cream",
                point(u, side * 9.4, 0), point(u, side * 9.4, 8.8),
                1.0, 1.2,
            )
    scene.landmarks.append(
        {
            "name": "FIA-photo registered T27 outfield pavilion",
            "center_latitude": 21.6251343,
            "center_longitude": 39.1069061,
            "length_estimate_m": 85,
            "depth_estimate_m": 20,
            "height_estimate_m": 10.7,
            "position_uncertainty_m": 20,
            "glazing": "Dark recessed upper panes, cream lower corner/service panels and solid pale end piers observed in supplied289–293s. Estimated lower opaque extent is limited to two corner bays at each end; rear symmetry and exact service-door arrangement remain uncertain. Deeper pale roof fascia and visible triangulated supports replace the thin repeated members. Pane rhythm, pier width, fascia thickness and truss dimensions are visual estimates, not measured section controls.",
            "source_note": "FIA 2025 event notes page 5 locates the T27 outfield staging area at 21°37′29.3″N, 39°06′23.7″E and photographs the actual two-level framed pavilion beside the race fence. Supplied 289–293 s shows the same pale/glazed corner context before the main-straight exit. The footprint is a reconstruction about 33 m east and 37 m north of that staging control, not an OSM building or survey. Dimensions and current glazing follow the direct visual baseline; the FIA preparation photo shows its exposed frame.",
        }
    )


def t27_tree_belt(scene: CircuitScene) -> None:
    from shapely.geometry import Point as ShapePoint

    pavilion = pavilion_footprint(scene).buffer(3)
    count = 0
    for index in range(11):
        sample = scene.at(5260 + index * 29)
        lane = sample.half_width + 0.95 + sample.left_shoulder + 27 + index % 3 * 2
        point = sample.point(lane)
        root = ShapePoint(point[:2])
        if pavilion.covers(root) or any(
            shape.covers(root) for shape in scene.water_shapes
        ):
            continue
        nearest, distance = scene.nearest(point[0], point[1])
        if distance < nearest.half_width + 6:
            continue
        scene.broadleaf(
            (point[0], point[1], scene.ground(point[0], point[1])),
            10 + index % 4 * 0.7,
            800 + index,
        )
        count += 1
    scene.vegetation.append(
        {
            "type": "T27 outfield broadleaf belt",
            "start_m": 5260,
            "end_m": 5550,
            "side": 1,
            "count": count,
            "placement": "Direct 289–292 s shows mature crowns behind the final-corner pavilion and outside wall. Individual positions are estimated; roots avoid the pavilion, all race arms and water.",
        }
    )
