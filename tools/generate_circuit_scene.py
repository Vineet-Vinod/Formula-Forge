"""Prepare one venue's native meshes outside Unreal, keeping imports bounded and serial."""

from __future__ import annotations

import importlib
import sys

from circuit_art import artwork
from circuit_dataclasses import PitLane
from circuit_partition import partition_city
from circuit_partition_dataclasses import CityPartitionRecipe
from circuit_scene import CircuitScene
from circuit_terrain import ROOT, acquire
from pydantic import TypeAdapter


def generate(slug: str) -> None:
    if (ROOT / "Attribution/Sources" / slug / "scenery-ground.json").exists():
        acquire(slug)
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
    if slug == "baku":
        from venues.baku import finish_terrain

        finish_terrain(scene)
    if slug == "monaco":
        from venues.monaco_surfaces import finish_terrain as finish_monaco_surfaces

        finish_monaco_surfaces(scene)
        from venues.monaco_groves import add_groves

        add_groves(scene)
    if slug == "jeddah":
        from venues.jeddah import finish_terrain as finish_jeddah_terrain

        finish_jeddah_terrain(scene)
    print(f"{slug}: barriers and furniture", flush=True)
    scene.barriers(
        slug in ("jeddah", "monaco", "baku", "singapore", "australia", "canada")
    )
    scene.markings()
    artwork(scene)
    triangle_count = sum(len(tile.triangles) // 100 for tile in scene.tiles.values())
    tile_count = scene.save()
    partition = scene.sources / "scene-partition.json"
    if partition.exists():
        scene.tiles.clear()
        tile_count = partition_city(
            scene.scratch, TypeAdapter(CityPartitionRecipe).validate_json(partition.read_bytes())
        )
    print(
        f"{slug}: {tile_count} tiles, {triangle_count} triangles",
        flush=True,
    )


if __name__ == "__main__":
    generate(sys.argv[1])
