"""Export fixed architectural lights separately from Jeddah's moving road pool."""

from __future__ import annotations

from circuit_mesh import world
from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.east_architecture import frame
from venues.jeddah_edition_lighting_dataclasses import (
    EditionLightingSource,
    EditionWash,
)


def fixtures(scene: CircuitScene) -> tuple[EditionWash, ...]:
    source = TypeAdapter(EditionLightingSource).validate_json(
        (scene.sources / "edition-lighting.json").read_bytes()
    )
    if scene.slug != "jeddah" or source.owner_osm_id != 1258744123:
        raise ValueError("EDITION lights require the mapped Jeddah hotel")
    foundations = [
        row["foundation_top_m"]
        for row in scene.landmarks
        if row.get("osm_id") == source.owner_osm_id and "foundation_top_m" in row
    ]
    if len(foundations) != 1 or not isinstance(foundations[0], (int, float)):
        raise ValueError("EDITION lighting requires its emitted foundation landmark")
    base = float(foundations[0])
    building = scene.footprint(source.owner_osm_id)
    center, axis, normal, length, width = frame(building)
    road, _distance = scene.nearest(center[0], center[1])
    facing = (
        1
        if (road.x - center[0]) * normal[0] + (road.y - center[1]) * normal[1] > 0
        else -1
    )
    lights = []
    for fraction in source.frontage_fractions:
        u = (fraction - 0.5) * length
        v = facing * (width / 2 + source.outward_offset_m)
        target_v = facing * (width / 2 - source.target_inset_m)
        position = (
            center[0] + axis[0] * u + normal[0] * v,
            center[1] + axis[1] * u + normal[1] * v,
            base + source.height_above_foundation_m,
        )
        target = (
            center[0] + axis[0] * u + normal[0] * target_v,
            center[1] + axis[1] * u + normal[1] * target_v,
            base + source.target_height_above_foundation_m,
        )
        lights.append(EditionWash(position, target, source.power))
    return tuple(lights)


def write_fixtures(scene: CircuitScene) -> None:
    rows = ["x,y,z,target_x,target_y,target_z,power"]
    for light in fixtures(scene):
        values = (*world(light.position), *world(light.target), light.power)
        rows.append(",".join(f"{value:.5f}" for value in values))
    scene.data.mkdir(parents=True, exist_ok=True)
    (scene.data / "edition_lights.csv").write_text("\n".join(rows) + "\n")
