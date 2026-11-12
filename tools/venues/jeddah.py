"""Floodlit Corniche, white framed hospitality and twisting coastal skyline."""

from __future__ import annotations

import math

from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.coastal_water import coastal_water
from venues.east_architecture import (
    facade,
    frame,
    mapped,
    roof_polygon,
    trees,
)
from venues.jeddah_facilities import (
    mapped_stands,
    pit_compound,
    t27_pavilion,
    t27_tree_belt,
)


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in (
        (260, 335, -1),
        (380, 450, 1),
        (515, 565, -1),
        (815, 875, -1),
        (940, 1000, 1),
        (1135, 1200, -1),
        (1305, 1365, 1),
        (1420, 1475, 1),
        (1545, 1605, -1),
        (1730, 1800, -1),
        (2180, 2350, -1),
        (2575, 2650, 1),
        (2660, 2720, 1),
        (2790, 2855, -1),
        (2895, 2965, 1),
        (3020, 3090, -1),
        (3390, 3460, 1),
        (3590, 3670, -1),
        (3790, 3860, 1),
        (3935, 4000, 1),
        (4100, 4170, -1),
        (4310, 4385, 1),
        (4590, 4700, -1),
        (5330, 5490, -1),
    ):
        scene.kerb(start, end, side, width=0.95)
    for start, end, side, width, material in (
        (245, 365, 1, 10, "RunoffGreen"),
        (2150, 2370, 1, 14, "RunoffGreen"),
        (2770, 2890, 1, 8, "RunoffGreen"),
        (3340, 3490, -1, 8, "RunoffGreen"),
        (4250, 4420, -1, 9, "RunoffGreen"),
        (5290, 5520, 1, 14, "RunoffGreen"),
    ):
        scene.runoff(start, end, side, width, material)

    for apex, side, distances in (
        (299, 1, (150, 100, 50)),
        (2277, 1, (150, 100, 50)),
        (5412, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5290, 6174, 1, "PanelGreen"),
        (0, 200, 1, "PanelGreen"),
        (5290, 5900, -1, "PanelGreen"),
        (5900, 6174, -1, "PanelStc"),
        (0, 200, -1, "PanelStc"),
        (250, 650, 1, "PanelYellow"),
        (370, 650, -1, "PanelYellow"),
        (2150, 2380, 1, "PanelGreen"),
    ):
        scene.branding(start, end, side, material)


def construction_tower(scene: CircuitScene) -> None:
    tower = mapped(scene, 1244131504)
    if tower is None:
        return
    center, axis, normal, length, width = frame(tower)
    road, _ = scene.nearest(center[0], center[1])
    base_z = road.z
    height = 300.0
    heading = math.atan2(axis[1], axis[0])
    footprint = Polygon(tower.ring)
    scene.box(
        "Building_DiamondConstructionCore",
        "Concrete",
        (center[0], center[1], base_z + (height + 5) / 2),
        13,
        12,
        height + 5,
        heading,
    )
    radius = min(length, width) * 0.42
    levels = 67
    for level in range(levels):
        fraction = level / (levels - 1)
        z = base_z + fraction * height
        angle = fraction * math.pi * 0.48
        taper = 1 - 0.32 * fraction * fraction
        corners = [
            (
                center[0]
                + radius * taper * math.cos(angle + face * math.pi / 2 + math.pi / 4),
                center[1]
                + radius * taper * math.sin(angle + face * math.pi / 2 + math.pi / 4),
            )
            for face in range(4)
        ]
        clipped = Polygon(corners).intersection(footprint)
        parts = [clipped] if isinstance(clipped, Polygon) else list(clipped.geoms)
        for part in parts:
            if not isinstance(part, Polygon) or part.area < 1:
                continue
            ring = list(part.exterior.coords)[:-1]
            roof_polygon(scene, ring, z, "Concrete")
            for a, b in zip(ring, ring[1:] + ring[:1]):
                pa, pb = (a[0], a[1], z), (b[0], b[1], z)
                scene.beam(
                    "Building_DiamondExposedFloorEdges", "Cream", pa, pb, 0.35, 0.27
                )
                if level < levels - 1:
                    for fraction_along in (0.1, 0.5, 0.9):
                        post = add(
                            pa, mul((pb[0] - pa[0], pb[1] - pa[1], 0.0), fraction_along)
                        )
                        scene.beam(
                            "Building_DiamondExposedColumns",
                            "Concrete",
                            post,
                            add(post, (0.0, 0.0, height / (levels - 1))),
                            0.55,
                        )
                if level >= levels - 3:
                    scene.banner(
                        pa, pb, 1.1, "Cream", "Building_DiamondTemporaryFormwork"
                    )
    crane_base = add((center[0], center[1], base_z), mul(axis, -8))
    crane_height = height + 23
    for side_a, side_b in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        foot = add(crane_base, (side_a * 0.8, side_b * 0.8, 0.0))
        scene.beam(
            "Building_DiamondCraneMast",
            "Yellow",
            foot,
            add(foot, (0.0, 0.0, crane_height)),
            0.18,
        )
    for rise in range(0, round(crane_height), 5):
        for side in (-1, 1):
            a = add(crane_base, (-0.8, side * 0.8, rise))
            b = add(crane_base, (0.8, side * 0.8, min(crane_height, rise + 5)))
            scene.beam("Building_DiamondCraneLattice", "Steel", a, b, 0.09)
            scene.beam(
                "Building_DiamondCraneLattice",
                "Steel",
                add(a, (0.0, 0.0, min(5.0, crane_height - rise))),
                add(b, (0.0, 0.0, -min(5.0, crane_height - rise))),
                0.09,
            )
    top = add(crane_base, (0.0, 0.0, crane_height))
    for beam_height in (0.0, 1.8):
        scene.beam(
            "Building_DiamondCraneJib",
            "Yellow",
            add(add(top, mul(normal, -12)), (0.0, 0.0, beam_height)),
            add(add(top, mul(normal, 36)), (0.0, 0.0, beam_height)),
            0.22,
        )
    for distance in range(-12, 36, 4):
        scene.beam(
            "Building_DiamondCraneJibBraces",
            "Steel",
            add(top, mul(normal, distance)),
            add(add(top, mul(normal, distance + 4)), (0.0, 0.0, 1.8)),
            0.1,
        )
    scene.box(
        "Building_DiamondCraneCounterweight",
        "Concrete",
        add(top, mul(normal, -10)),
        4.5,
        3,
        2.4,
        heading,
    )
    hook = add(top, mul(normal, 29))
    scene.beam(
        "Building_DiamondCraneCable", "Steel", hook, add(hook, (0.0, 0.0, -65)), 0.045
    )
    scene.modeled_buildings.add(tower.osm_id)
    scene.landmarks.append(
        {
            "name": "Diamond Tower construction state",
            "osm_id": tower.osm_id,
            "planned_height_m": tower.height,
            "rendered_construction_envelope_m": height,
            "visual_height_uncertainty_m": 80.0,
            "base_z_m": base_z,
            "adjacent_road_station_m": road.station,
            "state": "Exposed concrete core, open floorplates and columns, partial upper formwork and tower crane; no completed glazing.",
            "reference": "Jeddah165s wider silhouette and323s cropped close construction view.",
            "registration": "Mapped footprint retained.300m is a coarse scene estimate from the wider view, not a measured built height.432m/93levels in stale OSM describe the planned tower and are not asserted as its observed completed state. Footprint corner ground2.41–3.24m agrees with adjacent road3.24m; use road/site datum rather than adding height to a DSM roof.",
        }
    )


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    coastal_water(scene)
    mapped_stands(scene)
    pit_compound(scene)
    t27_pavilion(scene)
    t27_tree_belt(scene)
    construction_tower(scene)
    facade(scene, 1258744123, 25, "modern", "White")
    for building in scene.buildings:
        if building.osm_id in scene.modeled_buildings or building.use == "grandstand":
            continue
        center, _, _, _, _ = frame(building)
        _, distance = scene.nearest(center[0], center[1])
        if distance < 220:
            facade(
                scene,
                building.osm_id,
                max(10, min(60, building.height)),
                "modern",
                "White",
            )
    for start, end, side, setback in (
        (400, 1200, -1, 11),
        (1350, 2200, 1, 14),
        (2250, 2800, -1, 13),
        (3000, 3850, 1, 15),
        (3950, 4650, -1, 18),
        (4800, 5400, 1, 12),
    ):
        trees(scene, start, end, side, setback, 52, 9, palm=True)
