"""Reserve and emit the source-fitted Four Seasons without changing terrain."""

from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter

from circuit_mesh import MeshScene
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.baku_hotel_dataclasses import HotelGroundSource, HotelSource
from venues.baku_hotel_model import full_hotel


def _load(scene: CircuitScene) -> tuple[HotelSource, HotelGroundSource]:
    recipe = gzip.decompress((scene.sources / "hotel-recipe.json.gz").read_bytes())
    guard = TypeAdapter(HotelGroundSource).validate_json(
        gzip.decompress((scene.sources / "hotel-ground-supports.json.gz").read_bytes())
    )
    if hashlib.sha256(recipe).hexdigest() != guard.recipe_sha256:
        raise ValueError("Baku hotel geometry recipe changed; requalify its source")
    for relative, expected in guard.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Baku hotel source frame changed: {relative}")
    source = TypeAdapter(HotelSource).validate_json(recipe)
    _validate_frame(scene, source)
    return source, guard


def _validate_frame(scene: CircuitScene, source: HotelSource) -> None:
    building = scene.footprint(152190583)
    if (
        source.osm_id != building.osm_id
        or tuple(building.ring) != source.literal_outer_xy
    ):
        raise ValueError("Baku hotel literal footprint/source frame changed")
    occupied, literal = Polygon(source.outer_xy), Polygon(building.ring)
    if not occupied.is_valid or occupied.difference(literal).area > 1e-8:
        raise ValueError("Baku hotel body escaped its qualified occupied outline")
    if source.dimensions.body_floor_bands_m[-1] != source.dimensions.cornice_m:
        raise ValueError("Baku hotel level storeys no longer meet its cornice")


def validate_ground(scene: MeshScene, source: HotelGroundSource) -> None:
    expected = Counter(
        {
            (row.tile, row.material, row.payload): row.copies
            for row in source.ground_supports
        }
    )
    found: Counter[tuple[str, str, bytes]] = Counter()
    for name in {row.tile for row in source.ground_supports}:
        tile = scene.tiles.get(name)
        if tile is None:
            raise ValueError(f"Baku hotel supporting Ground tile is missing: {name}")
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            key = name, material, bytes(tile.triangles[offset + 4 : offset + 100])
            if key in expected:
                found[key] += 1
    if found != expected:
        raise ValueError(
            "Baku hotel actual supporting Ground changed; requalify its profiles"
        )


def prepare(scene: CircuitScene) -> None:
    """Reserve the existing literal property before protection export."""
    source, _ = _load(scene)
    scene.modeled_buildings.add(source.osm_id)


def finish(scene: CircuitScene) -> None:
    source, guard = _load(scene)
    if source.osm_id not in scene.modeled_buildings:
        raise ValueError("Baku hotel must be reserved before terrain generation")
    validate_ground(scene, guard)
    full_hotel(scene, source)
    scene.landmarks.append(
        {
            "name": "Four Seasons Hotel Baku",
            "osm_id": source.osm_id,
            "cornice_estimate_m": source.dimensions.cornice_m,
            "mansard_estimate_m": source.dimensions.mansard_m,
            "source": "hotel-reconstruction.json; primary rear/photographed returns, explicit unseen-return/height/datum estimates; native review pending",
        }
    )
