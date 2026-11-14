"""Rebuild Baku's bounded Ground delta from its authored field and ordinary scene."""

from __future__ import annotations

from circuit_dataclasses import PitLane
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from venues.baku import build_venue
from venues.baku_ground_authoring import rebuild


def main() -> None:
    scene = CircuitScene("baku")
    scene.road_surfaces("Runoff")
    pit = scene.sources / "pit-lane.json"
    if pit.exists():
        scene.pit_lane(TypeAdapter(PitLane).validate_json(pit.read_bytes()))
    build_venue(scene)
    scene.terrain("Runoff")
    patch = rebuild(
        scene,
        scene.sources / "oldcity-control-field.json.gz",
        scene.sources / "oldcity-ground-delta.json.gz",
    )
    print(
        f"Baku Ground: {sum(row.copies for row in patch.removals)} original rows replaced; "
        f"{sum(row.copies for row in patch.additions)} authored rows written."
    )


if __name__ == "__main__":
    main()
