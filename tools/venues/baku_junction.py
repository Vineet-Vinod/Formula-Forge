"""The source-registered Azneft traffic island and connected public paving."""

from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.baku_ground import finish_terrain
from venues.baku_ground_dataclasses import GroundPatchSource
from venues.baku_junction_dataclasses import JunctionChange, JunctionRecipe


def finish(scene: CircuitScene, source_path: Path | None = None) -> JunctionChange:
    path = source_path or scene.sources / "junction/reconstruction.json"
    source = TypeAdapter(JunctionRecipe).validate_json(path.read_bytes())
    provenance = scene.provenance
    if scene.slug != "baku" or max(
        abs(provenance.origin.latitude - source.origin_lat_lon[0]),
        abs(provenance.origin.longitude - source.origin_lat_lon[1]),
        abs(provenance.route.uniform_scale - source.uniform_scale),
    ) > 1e-10:
        raise ValueError("Baku ordinary-island source frame changed")
    island = Polygon([scene.geo(lat, lon) for lat, lon in source.island_ring_lat_lon])
    if not island.is_valid or abs(island.area - source.island_area_m2) > 1e-6:
        raise ValueError("Baku literal traffic-island registration changed")
    patch_path = path.with_name(source.ground_delta_file)
    raw = patch_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.ground_delta_sha256:
        raise ValueError("Baku ordinary-island geometry differs from reviewed source")
    patch = TypeAdapter(GroundPatchSource).validate_json(gzip.decompress(raw))
    removed = sum(row.copies for row in patch.removals)
    added = sum(row.copies for row in patch.additions)
    if (removed, added) != (source.removed_rows, source.new_rows):
        raise ValueError("Baku ordinary-island reviewed row counts changed")
    finish_terrain(scene, patch_path)
    scene.landmarks.append(
        {
            "name": "Azneft ordinary traffic island and connected paving",
            "source": "junction/reconstruction.json",
            "scope": source.source_note,
            "held": "The incoming Niyazi carriageway and fountain terrace remain separate.",
        }
    )
    return JunctionChange(removed, added, source.curb_faces)
