"""Retain the actual Diamond construction skyline through the final turn."""

from __future__ import annotations

from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.jeddah_dataclasses import SkylineResidency


def skyline_residency(scene: CircuitScene) -> None:
    source = TypeAdapter(SkylineResidency).validate_json(
        (scene.sources / 'skyline-residency.json').read_bytes()
    )
    if abs(scene.provenance.route.uniform_scale - source.uniform_scale) > 1e-9:
        raise ValueError('The named skyline bounds require the retained Jeddah frame')
    scene.footprint(source.osm_id)
    tile = scene.tiles[source.tile_name]
    # Source south is positive UE X. Only CSV residency uses these authoring bounds;
    # The current construction geometry still supplies the real native render bounds.
    tile.maximum[0] = max(tile.maximum[0], source.actual_baseline_bounds_ue_cm[3] + source.south_margin_m * 100)
    scene.landmarks.append({
        'name': 'Diamond Tower named skyline residency',
        'osm_id': source.osm_id, 'tile': source.tile_name,
        'south_residency_margin_m': source.south_margin_m,
        'source': 'skyline-residency.json',
        'dimensions_status': 'This rule only extends the named tile CSV load/unload envelope toward the southern hairpin; global streaming radii remain unchanged. Current exposed-concrete/luffing-crane geometry is qualified separately in construction-reconstruction.json. Historical baseline bounds and whole-lap range witnesses remain in the residency source record.',
    })
