"""Prepare one venue's native meshes outside Unreal, keeping imports bounded and serial."""

from __future__ import annotations

import importlib
import sys

from circuit_art import artwork
from circuit_dataclasses import PitLane
from circuit_scene import CircuitScene
from pydantic import TypeAdapter


def generate(slug: str) -> None:
    scene = CircuitScene(slug)
    print(f"{slug}: road surfaces", flush=True)
    base = (
        "Runoff"
        if slug in ("jeddah", "monaco", "baku", "singapore")
        else "Gravel"
        if slug == "bahrain"
        else "Grass"
    )
    scene.road_surfaces(base)
    pit_profile = scene.sources / "pit-lane.json"
    if pit_profile.exists():
        scene.pit_lane(TypeAdapter(PitLane).validate_json(pit_profile.read_bytes()))
    print(f"{slug}: registered architecture and landscape", flush=True)
    importlib.import_module("venues." + slug).build_venue(scene)
    print(f"{slug}: terrain", flush=True)
    scene.terrain(base)
    print(f"{slug}: barriers and furniture", flush=True)
    scene.barriers(
        slug in ("jeddah", "monaco", "baku", "singapore", "australia", "canada")
    )
    scene.markings()
    artwork(scene)
    scene.save()
    print(
        f"{slug}: {len(scene.tiles)} tiles, {sum(len(t.triangles) // 100 for t in scene.tiles.values())} triangles",
        flush=True,
    )


if __name__ == "__main__":
    generate(sys.argv[1])
