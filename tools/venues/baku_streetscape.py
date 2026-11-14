"""Source-fitted Philharmonic and historic university; terrain stays unchanged."""

from __future__ import annotations

import gzip
import hashlib
import struct
from collections import Counter

from circuit_mesh import MeshScene
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.baku_philharmonic_geometry import roof_forms
from venues.baku_philharmonic_model import hall_body
from venues.baku_streetscape_dataclasses import (
    StreetscapeGroundSource,
    StreetscapeSource,
)
from venues.baku_university import historic_facade


def _occupied(scene: CircuitScene, source: StreetscapeSource) -> Polygon:
    shape = Polygon(source.hall_literal_xy).difference(scene.road_mask.buffer(1.2))
    if not isinstance(shape, Polygon) or not shape.is_valid:
        raise ValueError("Baku Philharmonic occupied outline changed")
    if hashlib.sha256(shape.wkb).hexdigest() != source.hall_cutout_wkb_sha256:
        raise ValueError("Baku Philharmonic road clearance/cutout changed")
    return shape


def _load(scene: CircuitScene) -> tuple[StreetscapeSource, StreetscapeGroundSource]:
    folder = scene.sources / "streetscape"
    recipe = gzip.decompress((folder / "recipe.json.gz").read_bytes())
    guard = TypeAdapter(StreetscapeGroundSource).validate_json(
        gzip.decompress((folder / "ground-supports.json.gz").read_bytes())
    )
    if hashlib.sha256(recipe).hexdigest() != guard.recipe_sha256:
        raise ValueError("Baku streetscape recipe changed; requalify its source")
    for relative, expected in guard.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Baku streetscape source frame changed: {relative}")
    source = TypeAdapter(StreetscapeSource).validate_json(recipe)
    hall = scene.footprint(152190848)
    university = scene.footprint(source.university.osm_id)
    if (
        tuple(hall.ring) != source.hall_literal_xy
        or tuple(university.ring) != source.university.ring
    ):
        raise ValueError("Baku streetscape literal footprint/source frame changed")
    if (
        min(scene.ground(*p) for p in hall.ring) != source.hall.base_m
        or min(scene.ground(*p) for p in university.ring) != source.university.datum_m
    ):
        raise ValueError("Baku streetscape inherited source datum changed")
    return source, guard


def validate_ground(scene: MeshScene, source: StreetscapeGroundSource) -> None:
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
            raise ValueError(
                f"Baku streetscape supporting Ground tile is missing: {name}"
            )
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[
                struct.unpack_from("<I", tile.triangles, offset)[0]
            ]
            key = name, material, bytes(tile.triangles[offset + 4 : offset + 100])
            if key in expected:
                found[key] += 1
    if found != expected:
        raise ValueError("Baku streetscape actual supporting Ground changed")


def prepare(scene: CircuitScene) -> None:
    """Replace the two old bodies and retain the hall's exact existing cutout."""
    source, _ = _load(scene)
    footprint = _occupied(scene, source)
    if {152190848, 196291852} & scene.modeled_buildings:
        raise ValueError("Baku streetscape owners were already emitted")
    scene.modeled_buildings.update((152190848, 196291852))
    scene.terrain_cutouts.append(footprint)


def finish(scene: CircuitScene) -> None:
    source, guard = _load(scene)
    footprint = _occupied(scene, source)
    if not {152190848, 196291852} <= scene.modeled_buildings or not any(
        p.equals_exact(footprint, 0) for p in scene.terrain_cutouts
    ):
        raise ValueError("Baku streetscape must be reserved before terrain generation")
    validate_ground(scene, guard)
    hall_body(scene, source.hall, footprint)
    roof_forms(scene, source.hall)
    historic_facade(scene, source.university)
    scene.landmarks.extend(
        (
            {
                "name": "Azerbaijan State Philharmonic",
                "osm_id": 152190848,
                "body_height_estimate_m": source.hall.body_top_m,
                "tower_peak_estimate_m": source.hall.towers[0].peak_m,
                "source": "streetscape/reconstruction.json; mapped roof parts and primary exterior rhythm; base/heights estimated, native review pending",
            },
            {
                "name": "Historic Western University building, heritage 3289",
                "osm_id": source.university.osm_id,
                "cornice_estimate_m": source.university.cornice_m,
                "mansard_estimate_m": source.university.mansard_m,
                "source": "streetscape/reconstruction.json; primary frontage, current operator not assumed; height/base estimated, native review pending",
            },
        )
    )
