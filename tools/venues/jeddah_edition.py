"""Mapped, occupied EDITION terraces outside Jeddah's northern banked hairpin."""

from __future__ import annotations

from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.affinity import affine_transform
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.east_architecture import frame
from venues.jeddah_edition_dataclasses import EditionDetail, EditionFrame
from venues.jeddah_edition_geometry import build


def edition_hotel(scene: CircuitScene) -> None:
    building = scene.footprint(1258744123)
    center, axis, normal, length, width = frame(building)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(3))
    if not isinstance(footprint, Polygon):
        raise TypeError("The EDITION footprint must remain one occupied property")
    local = affine_transform(
        footprint,
        [
            axis[0],
            axis[1],
            normal[0],
            normal[1],
            -center[0] * axis[0] - center[1] * axis[1],
            -center[0] * normal[0] - center[1] * normal[1],
        ],
    )
    road, distance = scene.nearest(center[0], center[1])
    facing = (
        1
        if (road.x - center[0]) * normal[0] + (road.y - center[1]) * normal[1] > 0
        else -1
    )
    base_z = max(scene.ground(x, y) for x, y in building.ring) + 0.15
    placement = EditionFrame(center[:2], axis[:2], normal[:2], base_z, facing, local)
    source = TypeAdapter(EditionDetail).validate_json(
        (scene.sources / "edition-detail.json").read_bytes()
    )
    owned = affine_transform(
        local,
        [axis[0], normal[0], axis[1], normal[1], center[0], center[1]],
    )
    scene.terrain_cutouts.append(orient(owned))
    scene.modeled_buildings.add(building.osm_id)
    for a, b in zip(building.ring, building.ring[1:] + building.ring[:1]):
        za, zb = scene.ground(*a) - 0.1, scene.ground(*b) - 0.1
        scene.quad(
            "Building_EditionFoundation",
            "Concrete",
            (a[0], a[1], za),
            (b[0], b[1], zb),
            (b[0], b[1], base_z + 0.2),
            (a[0], a[1], base_z + 0.2),
        )
    build(scene, placement, source)
    scene.landmarks.append(
        {
            "name": "The Jeddah EDITION terraced track frontage",
            "osm_id": building.osm_id,
            "mapped_length_m": length,
            "mapped_width_m": width,
            "adjacent_native_station_m": road.station,
            "distance_from_road_m": distance,
            "foundation_top_m": base_z,
            "roof_above_foundation_m": source.canopy_top_m,
            "roof_height_uncertainty_m": 4.0,
            "source": source.source_note,
        }
    )
