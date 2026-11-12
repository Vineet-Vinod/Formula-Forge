"""Close each venue's road/escape envelope before exporting physical and visible walls."""

from __future__ import annotations

import importlib
import json
import math
import sys
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import BarrierSegment
from circuit_protection import filter_barriers, load_openings
from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]


def generate(slug: str) -> None:
    scene = CircuitScene(slug)
    if scene.catalogue.deck_separation:
        raise ValueError("Grade-separated circuits require independent deck boundaries")
    scene.road_surfaces()
    importlib.import_module("venues." + slug).build_venue(scene)
    shape = unary_union([scene.corridor_mask, *scene.extra_corridors])
    elevated = {
        landmark["osm_id"] for landmark in scene.landmarks
        if landmark.get("road_clearance_exception", "none") != "none" and "osm_id" in landmark
    }
    occupied = []
    for building in scene.buildings:
        if (building.osm_id not in scene.modeled_buildings or building.osm_id in elevated
                or building.use in ("roof", "bridge") or building.tags.get("location") == "overhead"):
            continue
        footprint = Polygon(building.ring).buffer(0.5).difference(scene.road_mask.buffer(0.6))
        if footprint.intersects(shape):
            occupied.append(footprint)
    shape = shape.difference(unary_union(occupied)).simplify(0.02, preserve_topology=True)
    polygons = [shape] if isinstance(shape, Polygon) else list(shape.geoms)
    prefix = scene.catalogue.content_dir.split("/")[0]
    if prefix == "COTA":
        prefix = "Cota"
    walls: list[BarrierSegment] = []
    for polygon in polygons:
        for ring in (polygon.exterior, *polygon.interiors):
            points = list(ring.coords)
            for a, b in pairwise(points):
                count = max(1, math.ceil(math.dist(a, b) / 2))
                for i in range(count):
                    pa = (
                        a[0] + (b[0] - a[0]) * i / count,
                        a[1] + (b[1] - a[1]) * i / count,
                    )
                    pb = (
                        a[0] + (b[0] - a[0]) * (i + 1) / count,
                        a[1] + (b[1] - a[1]) * (i + 1) / count,
                    )
                    sample, _ = scene.nearest((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
                    lane = ((pa[0] + pb[0]) / 2 - sample.x) * sample.ty - (
                        (pa[1] + pb[1]) / 2 - sample.y
                    ) * sample.tx
                    bottom = sample.z + sample.bank * lane
                    walls.append((*pa, *pb, bottom, bottom + 0.95, 0.15))
    openings = load_openings(scene.sources, scene.length)
    walls = filter_barriers(walls, openings, scene.nearest)
    header = f"constexpr TrackBarrier k{prefix}SceneWalls[] = {{\n"
    header += (
        "".join(
            "    {" + ", ".join(f"{value:.4f}f" for value in wall) + "},\n"
            for wall in walls
        )
        + "};\n"
    )
    ranges = [r for r in scene.surface_ranges if r["type"] == "runoff"]
    header += f"constexpr TrackRunoffZone k{prefix}SceneRunoff[] = {{\n"
    for surface in ranges:
        material = "Gravel" if surface["material"] == "Gravel" else "Asphalt"
        header += f"    {{{float(surface['start_m']):.3f}f, {float(surface['end_m']):.3f}f, {int(surface['side'])}, TrackRunoffSurface::{material}, {float(surface['requested_width_m']):.3f}f}},\n"
    if not ranges:
        header += "    {0.f, 0.f, 0, TrackRunoffSurface::Asphalt, 0.f},\n"
    header += "};\n"
    directory = ROOT / "Source/FormulaForge/Native/track_data"
    (directory / (slug + "_boundaries.inc")).write_text(header)
    includes = directory / "generated_surveys.inc"
    text = includes.read_text()
    line = f'#include "track_data/{slug}_boundaries.inc"'
    if line not in text:
        includes.write_text(text + line + "\n")
    catalogue = directory / "generated_catalog.inc"
    text = catalogue.read_text()
    start = text.index("    {TrackLayoutId::" + prefix + ",")
    end = text.find("\n    {TrackLayoutId::", start + 5)
    if end < 0:
        end = len(text)
    block = text[start:end].rstrip()
    block = block.replace("k" + prefix + "Runoff", "k" + prefix + "SceneRunoff")
    if "k" + prefix + "SceneWalls" not in block:
        block = block[:-2] + ",\n     k" + prefix + "SceneWalls},"
    catalogue.write_text(text[:start] + block + "\n" + text[end:].lstrip("\n"))
    record = {
        "source": "Registered native road and reference-authored escape ranges",
        "method": "Exact planar polygon union, preserving interior islands; simplification tolerance2cm, wallsegments atmost2m. One closed boundary supplies physical and visible protection.",
        "wall_count": len(walls),
        "occupied_footprints": len(occupied),
        "structure_clearance_m": 0.5,
        "runoff_ranges": ranges,
        "road_unchanged": True,
        "limitations": "Escape depths and station endpoints are reference estimates, not surveyed race-event barrier positions. Pit access remains a closed game boundary.",
    }
    (scene.sources / "boundaries.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{slug}: closed envelope, {len(walls)} walls", flush=True)


if __name__ == "__main__":
    for venue in sys.argv[1:]:
        generate(venue)
