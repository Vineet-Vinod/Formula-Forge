"""Replace the mapped Foundation office-grid body with the qualified facade study."""
from __future__ import annotations

import hashlib
import struct
from collections import Counter
from copy import copy

from circuit_dataclasses import MeshTile
from circuit_scene import CircuitScene
from pydantic import TypeAdapter

from venues.baku_foundation_dataclasses import FoundationChange, FoundationRecipe
from venues.baku_foundation_geometry import build
from venues.east_architecture import facade

Row = tuple[str, bytes]


def rows(tile: MeshTile) -> Counter[Row]:
    return Counter((tile.materials[struct.unpack_from('<I', tile.triangles, i)[0]],
                    bytes(tile.triangles[i + 4:i + 100]))
                   for i in range(0, len(tile.triangles), 100))


def digest(counter: Counter[Row]) -> str:
    result = hashlib.sha256()
    for (material, payload), count in sorted(counter.items()):
        result.update(material.encode() + b'\0' + payload + struct.pack('<Q', count))
    return result.hexdigest()


def legacy(scene: CircuitScene, source: FoundationRecipe) -> tuple[str, Counter[Row]]:
    building = scene.footprint(source.osm_id)
    provenance = scene.provenance
    if (scene.slug != 'baku' or source.osm_id != 133160748
            or max(abs(provenance.origin.latitude - source.origin_lat_lon[0]),
                   abs(provenance.origin.longitude - source.origin_lat_lon[1]),
                   abs(provenance.route.uniform_scale - source.uniform_scale)) > 1e-10
            or len(building.ring) != len(source.geometry.ring_xy_m)
            or max(abs(a - b) for p, q in zip(building.ring, source.geometry.ring_xy_m)
                   for a, b in zip(p, q)) > 1e-8
            or abs(building.height - source.expected_legacy_height_m) > 1e-8
            or abs(building.height - source.geometry.body_height_m) > 1e-8
            or abs(min(scene.ground(x, y) for x, y in building.ring)
                   - source.geometry.floor_relative_m) > 1e-8):
        raise ValueError('The qualified Foundation owner, datum or legacy envelope changed')
    replay = copy(scene)
    replay.tiles = {}
    replay.landmarks = []
    replay.terrain_cutouts = []
    facade(replay, source.osm_id, building.height, 'classical', 'Cream')
    if len(replay.tiles) != 1:
        raise ValueError('The Foundation generic family escaped its qualified parent')
    parent, tile = next(iter(replay.tiles.items()))
    expected = rows(tile)
    if expected.total() != source.expected_legacy_rows or digest(expected) != source.legacy_counter_sha256:
        raise ValueError('The actual generic Foundation differs from its frozen source family')
    return parent, expected


def replacement(original: MeshTile, expected: Counter[Row], candidate: MeshTile) -> tuple[MeshTile, int]:
    missing = expected - rows(original)
    if missing:
        raise ValueError('The source Foundation rows are not an exact subset of the actual City tile')
    remaining = expected.copy()
    result = MeshTile(materials=original.materials.copy(), minimum=original.minimum.copy(),
                      maximum=original.maximum.copy())
    for offset in range(0, len(original.triangles), 100):
        raw = original.triangles[offset:offset + 100]
        key = original.materials[struct.unpack_from('<I', raw)[0]], bytes(raw[4:])
        if remaining[key]:
            remaining[key] -= 1
        else:
            result.triangles.extend(raw)
    kept = len(result.triangles) // 100
    for offset in range(0, len(candidate.triangles), 100):
        index = struct.unpack_from('<I', candidate.triangles, offset)[0]
        material = candidate.materials[index]
        if material not in result.materials:
            result.materials.append(material)
        result.triangles.extend(struct.pack('<I', result.materials.index(material)))
        result.triangles.extend(candidate.triangles[offset + 4:offset + 100])
    for axis in range(3):
        result.minimum[axis] = min(result.minimum[axis], candidate.minimum[axis])
        result.maximum[axis] = max(result.maximum[axis], candidate.maximum[axis])
    return result, kept


def finish(scene: CircuitScene) -> FoundationChange:
    path = scene.sources / 'foundation/reconstruction.json'
    source = TypeAdapter(FoundationRecipe).validate_json(path.read_bytes())
    parent, expected = legacy(scene, source)
    if parent not in scene.tiles or expected - rows(scene.tiles[parent]):
        raise ValueError('The Foundation requires its exact original prepartitioned City family')
    candidate = copy(scene)
    candidate.tiles = {}
    build(candidate, source.geometry)
    if set(candidate.tiles) != {parent}:
        raise ValueError('The qualified Foundation geometry escaped its one City parent')
    candidate_rows = rows(candidate.tiles[parent])
    if (candidate_rows.total() != source.expected_candidate_rows
            or digest(candidate_rows) != source.candidate_counter_sha256):
        raise ValueError("Foundation geometry differs from its independently qualified private source")
    result, kept = replacement(scene.tiles[parent], expected, candidate.tiles[parent])
    scene.tiles[parent] = result
    emitted = len(candidate.tiles[parent].triangles) // 100
    scene.landmarks.append({'osm_id': source.osm_id, 'name': 'Heydar Aliyev Foundation',
                           'structure': 'Six photographed principal facade bands, patterned entrance panel, rounded corner and blue cupola',
                           'source': 'foundation/reconstruction.json',
                           'body_height_m': source.geometry.body_height_m,
                           'body_height_uncertainty_m': source.geometry.body_height_uncertainty_m,
                           'scope': 'Mapped owner and legacy floor retained; rounded corner and facade/roof details are photographic estimates. '
                           'OSM8levels does not establish8principal facade rows. No native road/contact changes; cooked appearance pending.'})
    return FoundationChange(sum(expected.values()), emitted, kept, parent)
