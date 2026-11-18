"""Floodlit Corniche, white framed hospitality and twisting coastal skyline."""

from __future__ import annotations

from circuit_scene import CircuitScene

from venues.coastal_water import coastal_water
from venues.east_architecture import (
    facade,
    frame,
    trees,
)
from venues.jeddah_boundary import circuit_edges as boundary_edges
from venues.jeddah_construction import construction_tower
from venues.jeddah_context import corniche_context
from venues.jeddah_edition import edition_hotel
from venues.jeddah_facilities import (
    mapped_stands,
    pit_compound,
    t27_pavilion,
    t27_tree_belt,
)
from venues.jeddah_markers import distance_boards
from venues.jeddah_masarat import finish_terrain as finish_masarat_terrain
from venues.jeddah_pit_exit import pit_exit_building
from venues.jeddah_return_context import build as corniche_mosque
from venues.jeddah_skyline import skyline_residency


def circuit_edges(scene: CircuitScene) -> None:
    boundary_edges(scene)

    for apex, side, distances in (
        (299, 1, (150, 100, 50)),
        (2277, 1, (150, 100, 50)),
        (5412, 1, (150, 100, 50)),
    ):
        distance_boards(scene, apex, side)

    for start, end, material in (
        (0, 200, "PanelJeddahAramco"),
        (200, 650, "PanelYellow"),
        (650, 1100, "PanelPurple"),
        (1100, 1500, "PanelJeddahGlobant"),
        (1500, 1670, "PanelJeddahSaudiGP"),
        (1670, 2140, "PanelJeddahTag"),
        (2140, 2820, "PanelJeddahAramco"),
        (2820, 3400, "PanelJeddahLV"),
        (3400, 3750, "PanelNavy"),
        (3750, 4050, "PanelJeddahSalesforce"),
        (4050, 4450, "PanelJeddahLV"),
        (4450, 5210, "PanelJeddahCrypto"),
        (5210, 6009, "PanelJeddahAramco"),
        (6009, 6174, "PanelJeddahAramco"),
    ):
        for side in (-1, 1):
            panel = "PanelStc" if side == -1 and (start == 0 or start == 6009) else material
            if start == 1500 and side == 1:
                panel = "PanelJeddahTag"
            scene.branding(start, end, side, panel)


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    coastal_water(scene)
    mapped_stands(scene)
    pit_compound(scene)
    pit_exit_building(scene)
    t27_pavilion(scene)
    t27_tree_belt(scene)
    construction_tower(scene)
    edition_hotel(scene)
    corniche_mosque(scene)
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
    for start, end, side, setback, spacing, palm in (
        (400, 1200, -1, 11, 52, True),
        (1350, 1650, 1, 14, 52, True),
        (1650, 1850, 1, 8, 24, False),
        (1850, 2200, 1, 14, 52, True),
        (2250, 2800, -1, 13, 52, True),
        (3000, 3850, 1, 15, 52, True),
        (3950, 4650, -1, 18, 52, True),
        (4800, 5400, 1, 12, 52, True),
    ):
        trees(scene, start, end, side, setback, spacing, 9, palm=palm)
    skyline_residency(scene)
    corniche_context(scene)


def finish_terrain(scene: CircuitScene) -> None:
    finish_masarat_terrain(scene)
