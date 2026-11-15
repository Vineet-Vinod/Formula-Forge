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


def generate(slug: str, write_native_contact: bool = False) -> None:
    if write_native_contact and slug != "buddh":
        raise ValueError("Explicit first-sector contact export requires Buddh")
    if (ROOT / "Attribution/Sources" / slug / "scenery-ground.json").exists():
        acquire(slug)
    scene = CircuitScene(slug)
    first_sector = None
    if slug == "buddh":
        from venues.buddh_first_sector import prepare_scene

        first_sector = prepare_scene(scene)
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
    if first_sector is not None:
        from venues.buddh_first_sector import finish_terrain as finish_first_sector

        result = finish_first_sector(scene, first_sector)
        if write_native_contact:
            from venues.buddh_first_sector_contact import write_contact

            write_contact(result, ROOT / "Source/FormulaForge/Native/track_data/buddh_first_sector_contact.inc")
        from venues.buddh_terrace import finish_terrain as finish_t3_terrace

        finish_t3_terrace(scene)
    if slug == "baku":
        from venues.baku import finish_terrain

        finish_terrain(scene)
    if slug == "monaco":
        from venues.monaco_surfaces import finish_terrain as finish_monaco_surfaces

        finish_monaco_surfaces(scene)
        from venues.monaco_hermosa import finish as finish_villa_hermosa

        finish_villa_hermosa(scene)
        from venues.monaco_ravine import finish_terrain as finish_monaco_ravine

        finish_monaco_ravine(scene)
        from venues.monaco_groves import add_groves

        add_groves(scene)
        from venues.monaco_natural_ground import finish as finish_natural_ground

        finish_natural_ground(scene)
        from venues.monaco_upper_ground import finish as finish_upper_ground

        finish_upper_ground(scene)
    if slug == "jeddah":
        from venues.jeddah import finish_terrain as finish_jeddah_terrain

        finish_jeddah_terrain(scene)
    print(f"{slug}: barriers and furniture", flush=True)
    scene.barriers(
        slug in ("jeddah", "monaco", "baku", "singapore", "australia", "canada")
    )
    scene.markings()
    if slug == "monaco":
        from venues.monaco_foreground import finish_terrain as finish_monaco_foreground

        finish_monaco_foreground(scene)
        from venues.monaco_chapel import finish_terrain as finish_monaco_chapel

        finish_monaco_chapel(scene)
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
