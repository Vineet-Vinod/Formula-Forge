"""Keep only the named Sail tiles resident through their measured approach views."""

from __future__ import annotations

from circuit_scene import CircuitScene

from venues.jeddah_context_dataclasses import ContextResidency


def context_residency(scene: CircuitScene, source: ContextResidency) -> None:
    expected = {'Building_City_00_m3', 'Building_City_01_m3'}
    if {entry.tile_name for entry in source.tiles} != expected:
        raise ValueError('Corniche context residency must name exactly the two Sail tiles')
    for entry in source.tiles:
        tile = scene.tiles[entry.tile_name]
        actual = (*tile.minimum, *tile.maximum)
        if any(abs(a - b) > .1 for a, b in zip(actual, entry.actual_baseline_bounds_ue_cm, strict=True)):
            raise ValueError(f'The Sail residency baseline bounds changed; redo the route proof: {entry.tile_name}')
    for entry in source.tiles:
        tile = scene.tiles[entry.tile_name]
        # Only CSV residency expands north (negative UE X); mesh vertices and native render bounds do not.
        tile.minimum[0] = min(tile.minimum[0], entry.actual_baseline_bounds_ue_cm[0] - entry.north_margin_m * 100)
    scene.landmarks.append({
        'name': 'Sail named approach residency',
        'tiles': ', '.join(entry.tile_name for entry in source.tiles),
        'source': 'context-residency.json',
        'qualification': 'Only the two named CSV envelopes extend toward the northern approach. '
                         'The versioned recipe records zero potentially visible unloaded policy frames for the current pose packet under '
                         'unchanged 1,800 m load / 2,050 m release hysteresis. Potential frustum overlap is '
                         'not proof of rendered visibility or absence of occlusion. Existing Diamond rule, '
                         'actual mesh bounds, geometry, location and global streaming radii remain fixed.',
    })
