"""Qatar panels only on the retained near pit-entry face before the walkway."""

from __future__ import annotations

import math
from pathlib import Path

from circuit_mesh import MeshScene
from pit_routes_dataclasses import PitRoute
from pydantic import TypeAdapter

from venues.jeddah_pit_entry_panels_dataclasses import (
    EntryPanel,
    EntryPanelRecipe,
)
from venues.jeddah_pit_protection import sample, sections_hash

SOURCE = Path(__file__).resolve().parents[2] / "Attribution/Sources/jeddah/pit-entry-panels.json"


def load_recipe() -> EntryPanelRecipe:
    return TypeAdapter(EntryPanelRecipe).validate_json(SOURCE.read_bytes())


def selected_panels(route: PitRoute, recipe: EntryPanelRecipe) -> list[EntryPanel]:
    if route.slug != "jeddah" or sections_hash(route) != recipe.source_sections_sha256:
        raise ValueError("Pit-entry facing requires the unchanged Jeddah source route")
    actual = set(route.barriers)
    phase = 0.0
    output = []
    for record in recipe.walls:
        wall = record.barrier
        if wall not in actual or record.start_fraction >= record.end_fraction:
            raise ValueError("The qualified pit-entry wall is missing or has invalid panel bounds")
        if recipe.bottom_offset_m + recipe.height_m >= wall.top - wall.bottom:
            raise ValueError("Pit-entry panels must fit below the retained wall cap")
        dx, dy = wall.bx - wall.ax, wall.by - wall.ay
        length = math.hypot(dx, dy)
        if length < 0.1:
            raise ValueError("The qualified pit-entry face must have a finite wall span")
        nx, ny = -dy / length, dx / length
        section = sample(route, (record.route_start_distance_m + record.route_end_distance_m) / 2)
        center_x, center_y = (wall.ax + wall.bx) / 2, (wall.ay + wall.by) / 2
        if nx * (section.x - center_x) + ny * (section.y - center_y) <= 0:
            raise ValueError("The qualified pit-entry face must point into the fast lane")
        shift = wall.radius + recipe.inward_offset_m
        first = (wall.ax + dx * record.start_fraction + nx * shift,
                 wall.ay + dy * record.start_fraction + ny * shift,
                 wall.bottom + recipe.bottom_offset_m)
        last = (wall.ax + dx * record.end_fraction + nx * shift,
                wall.ay + dy * record.end_fraction + ny * shift,
                wall.bottom + recipe.bottom_offset_m)
        span = length * (record.end_fraction - record.start_fraction)
        output.append(EntryPanel(record.source_barrier_index, first, last, (nx, ny, 0.0),
                                 -(phase + span) / recipe.repeat_m, span / recipe.repeat_m))
        phase += span
    return output


def emit_entry_panels(scene: MeshScene, route: PitRoute) -> None:
    recipe = load_recipe()
    for panel in selected_panels(route, recipe):
        # The right wall is read from the lane; reverse its texture axis continuously.
        scene.banner(panel.last, panel.first, recipe.height_m, recipe.material,
                     "Tile_Route", panel.u0, panel.repeat)
