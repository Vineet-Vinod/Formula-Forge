"""Terminate the generic service body beside the filmed open-sky exit."""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import replace
from pathlib import Path

from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.east_architecture import facade
from venues.jeddah_pit_exit_dataclasses import PitExitReconstruction
from venues.jeddah_pits import pit_route_source, route_section

SOURCE = Path(__file__).resolve().parents[2] / "Attribution/Sources/jeddah/pit-exit-reconstruction.json"


def source_record() -> PitExitReconstruction:
    result = TypeAdapter(PitExitReconstruction).validate_json(SOURCE.read_bytes())
    if result.osm_id != 1257884698 or result.mode != "open_sky_reference_variant":
        raise ValueError("Jeddah pit-exit ownership or selected source variant changed")
    return result


def exit_tip_mask(source: PitExitReconstruction) -> Polygon:
    route = pit_route_source()
    distances = [section.distance for section in route.sections]
    centers = []
    for distance in (source.start_distance_m, source.end_distance_m):
        index = max(0, min(len(distances) - 2, bisect.bisect_right(distances, distance) - 1))
        a, b = route.sections[index:index + 2]
        t = (distance - a.distance) / (b.distance - a.distance)
        centers.append(route_section(route, a.track_station * (1 - t) + b.track_station * t))
    first, last = centers
    samples = [first, *[section for section in route.sections
                       if source.start_distance_m < section.distance < source.end_distance_m], last]
    return Polygon([
        (section.x + section.normal_x * lateral, section.y + section.normal_y * lateral)
        for lateral, points in ((-source.garage_side_clearance_m, samples),
                                (source.track_side_mask_extent_m, list(reversed(samples))))
        for section in points
    ])


def pit_exit_building(scene: CircuitScene) -> None:
    source = source_record()
    index = next(i for i, building in enumerate(scene.buildings) if building.osm_id == source.osm_id)
    original = scene.buildings[index]
    footprint = Polygon(original.ring)
    mask = exit_tip_mask(source)
    retained = footprint.difference(mask)
    if not isinstance(retained, Polygon) or not retained.is_valid or retained.area < footprint.area * .75:
        raise ValueError("Jeddah open-exit correction exceeds the qualified eastern tip")
    if footprint.area - retained.area < 1:
        raise ValueError("Jeddah open-exit recipe did not remove the conflicting roof tip")
    ring = [(float(x), float(y)) for x, y in list(retained.exterior.coords)[:-1]]
    scene.buildings[index] = replace(original, ring=ring)
    try:
        facade(scene, source.osm_id, source.retained_height_m, "modern", "White")
    finally:
        scene.buildings[index] = original
    scene.landmarks.append({
        "name": "Jeddah pit exit open-sky reference variant",
        "osm_id": source.osm_id,
        "exit_roof_state": source.mode,
        "source_open_exit_recipe_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_open_exit_module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_footprint_m2": footprint.area,
        "retained_footprint_m2": retained.area,
        "removed_eastern_tip_m2": footprint.area - retained.area,
        "garage_side_termination_m": source.garage_side_clearance_m,
        "source_note": source.source_note,
    })
