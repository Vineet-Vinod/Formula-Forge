"""Classify qualified natural cliff cover after its original support consumers."""
from __future__ import annotations

import csv
import hashlib
import math
import struct

from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_cliff_cover_dataclasses import CliffCoverChange, CliffCoverSource
from venues.monaco_ravine_dataclasses import RavineSource
from venues.monaco_surfaces import face
from venues.monaco_west_dataclasses import BelvedereArchitecture

MATERIAL = 'MonacoNaturalGround'


def domain(scene: CircuitScene, source: CliffCoverSource) -> BaseGeometry:
    frame = scene.provenance
    if scene.slug != 'monaco' or max(
        abs(frame.origin.latitude - source.origin_lat_lon[0]),
        abs(frame.origin.longitude - source.origin_lat_lon[1]),
        abs(frame.route.uniform_scale - source.uniform_scale),
    ) > 1e-10:
        raise ValueError('Cliff cover requires its retained Monaco source frame')
    for relative, expected in source.protected_source_sha256.items():
        if hashlib.sha256((scene.sources / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Cliff cover protected source changed: {relative}')
    mapped = [e for dataset in scene.osm for e in dataset.elements
              if e.type == 'way' and e.id == source.wood_osm_id]
    if not mapped or any(e.tags.get('natural') != 'wood' for e in mapped):
        raise ValueError('The actual mapped natural-wood owner is missing or changed')
    projected = tuple(scene.geo(lat, lon) for lon, lat in source.wood_wgs84_lonlat)
    if len(projected) != len(source.expected_wood_xy_m) or max(
        math.dist(a, b) for a, b in zip(projected, source.expected_wood_xy_m)
    ) > 1e-8:
        raise ValueError('Literal cliff woodland controls differ from their qualified frame')
    for owner in mapped:
        actual = tuple(scene.geo(p.lat, p.lon) for p in owner.geometry)
        if len(actual) != len(projected) or max(math.dist(a, b) for a, b in zip(actual, projected)) > 1e-8:
            raise ValueError('The retained actual woodland ring differs from its literal source')
    ravine = TypeAdapter(RavineSource).validate_json(
        (scene.sources / 'architecture/ravine-source.json').read_bytes())
    old = from_wkt(ravine.expected_domain_wkt)
    wood = Polygon(projected)
    blocked: list[BaseGeometry] = [Polygon(b.ring).buffer(.5) for b in scene.buildings]
    blocked.extend(Polygon(r) for r in ravine.mandatory_exclusions)
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.tags.get('highway') in ('footway', 'path', 'steps', 'pedestrian') and len(element.geometry) > 1:
                blocked.append(LineString([scene.geo(p.lat, p.lon) for p in element.geometry]).buffer(.8))
    belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / 'architecture/west-belvedere.json').read_bytes())
    blocked.append(Point(belvedere.center_xy_m).buffer(belvedere.radius_m + .6))
    blocked.extend([scene.corridor_mask.buffer(1), *scene.extra_corridors, *scene.water_shapes])
    for guard in source.formal_guards:
        coordinates = tuple(scene.geo(lat, lon) for lon, lat in guard.wgs84_lonlat)
        if len(coordinates) != len(guard.expected_native_xy_m) or max(
            math.dist(a, b) for a, b in zip(coordinates, guard.expected_native_xy_m)
        ) > 1e-8:
            raise ValueError('A source-qualified formal garden exclusion changed')
        blocked.append(Polygon(coordinates).buffer(.15))
    with (scene.scratch / 'barriers.csv').open() as handle:
        for row in csv.DictReader(handle):
            line = LineString(((float(row['ax']), float(row['ay'])),
                               (float(row['bx']), float(row['by']))))
            if line.distance(wood) < 3:
                blocked.append(line.buffer(float(row['radius']) + .5))
    result = unary_union([old, wood.difference(unary_union(blocked)).difference(old)])
    if not result.is_valid or result.symmetric_difference(from_wkt(source.expected_domain_wkt)).area > 1e-6:
        raise ValueError('The bounded contiguous natural-cliff source domain changed')
    return result


def reclassify(scene: MeshScene, plan: BaseGeometry,
               expected_faces: int, expected_area_m2: float) -> CliffCoverChange:
    changes: dict[str, list[int]] = {}
    held = examined = 0
    area = outside_max = 0.0
    for name, tile in scene.tiles.items():
        if not name.startswith('Tile_Street_') or not tile.triangles:
            continue
        bounds = box(-tile.maximum[1] / 100, -tile.maximum[0] / 100,
                     -tile.minimum[1] / 100, -tile.minimum[0] / 100)
        if not bounds.intersects(plan):
            continue
        examined += len(tile.triangles) // 100
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            if material != 'Grass':
                continue
            parent = face(tile, offset)
            inside = parent.plan.intersection(plan).area
            if parent.plan.area < 1e-10 or inside < 1e-9:
                continue
            outside = parent.plan.difference(plan).area
            if outside > max(1e-7, parent.plan.length * .000025):
                held += 1
                continue
            if min(v[5] for v in parent.vertices) < .05:
                continue
            changes.setdefault(name, []).append(offset)
            area += parent.plan.area
            outside_max = max(outside_max, outside)
    count = sum(len(offsets) for offsets in changes.values())
    if count != expected_faces or abs(area - expected_area_m2) > 1e-6:
        raise ValueError(f'Actual old Grass ownership differs from the qualified cliff receipt: actual {count} faces / {area:.12f} m²; expected {expected_faces} / {expected_area_m2:.12f}')
    # Every owner, mask and count check passes before any material or mesh mutation.
    for name, offsets in changes.items():
        tile = scene.tiles[name]
        if MATERIAL not in tile.materials:
            tile.materials.append(MATERIAL)
        index = tile.materials.index(MATERIAL)
        for offset in offsets:
            struct.pack_into('<I', tile.triangles, offset, index)
    return CliffCoverChange(tuple(changes), count, area, examined - count, held, outside_max)


def finish_terrain(scene: CircuitScene) -> CliffCoverChange:
    source = TypeAdapter(CliffCoverSource).validate_json(
        (scene.sources / 'architecture/cliff-cover/reconstruction.json').read_bytes())
    plan = domain(scene, source)
    change = reclassify(scene, plan, source.expected_changed_faces, source.expected_face_area_sum_m2)
    scene.landmarks.append({'name': 'Contiguous mixed natural cliff cover',
        'source': 'architecture/cliff-cover/source-qualification.json',
        'material_only_faces': change.changed_faces,
        'mixed_cover_face_area_sum_m2': change.changed_face_area_sum_m2,
        'limits': 'Existing whole Grass faces only; every XYZ, normal, UV, plant and native driving record remains unchanged. Mixed source role, not exact rock/ivy pixels or canopy geometry.'})
    return change
