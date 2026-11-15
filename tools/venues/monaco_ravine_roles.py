"""Finite natural-role material partitions on the original Monaco ground planes."""
from __future__ import annotations

import csv
import hashlib
import math
import struct
from copy import deepcopy

from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_chapel_dataclasses import ChapelSource
from venues.monaco_dataclasses import LarvottoBridge
from venues.monaco_ravine_roles_dataclasses import (
    GroundRow,
    RavineRoleBoundary,
    RavineRolesChange,
    RavineRolesSource,
)
from venues.monaco_ravine_roles_ground import recolor
from venues.monaco_surfaces import face
from venues.monaco_surfaces_dataclasses import SurfaceFace
from venues.monaco_west_dataclasses import BelvedereArchitecture


def boundary(scene: CircuitScene, source: RavineRoleBoundary) -> BaseGeometry:
    points = tuple(scene.geo(lat, lon) for lon, lat in source.wgs84_lonlat)
    if len(points) != len(source.expected_native_xy_m) or max(
        math.dist(a, b) for a, b in zip(points, source.expected_native_xy_m)
    ) > 1e-8:
        raise ValueError('A registered ravine-role boundary changed its source frame')
    return Polygon(points).buffer(source.margin_m) if source.margin_m else Polygon(points)


def domain(scene: CircuitScene, source: RavineRolesSource) -> BaseGeometry:
    frame = scene.provenance
    if scene.slug != 'monaco' or max(
        abs(frame.origin.latitude - source.origin_lat_lon[0]),
        abs(frame.origin.longitude - source.origin_lat_lon[1]),
        abs(frame.route.uniform_scale - source.uniform_scale),
    ) > 1e-10:
        raise ValueError('Ravine roles require the retained Monaco source frame')
    for path, expected in source.protected_source_sha256.items():
        if hashlib.sha256((scene.sources / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f'A protected ravine-role source changed: {path}')
    barriers = scene.scratch / 'barriers.csv'
    if hashlib.sha256(barriers.read_bytes()).hexdigest() != source.barriers_csv_sha256:
        raise ValueError('Ravine-role protection controls changed')
    blocked = [boundary(scene, item) for item in source.explicit_guards]
    blocked.extend(Polygon(b.ring).buffer(.15) for b in scene.buildings)
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.tags.get('highway') in ('footway', 'path', 'steps', 'pedestrian') and len(element.geometry) > 1:
                blocked.append(LineString([scene.geo(p.lat, p.lon) for p in element.geometry]).buffer(.8))
    blocked.extend([scene.corridor_mask.buffer(1), *scene.extra_corridors, *scene.water_shapes])
    bridge = TypeAdapter(LarvottoBridge).validate_json(
        (scene.sources / 'architecture/larvotto-bridge.json').read_bytes())
    blocked.append(Polygon([scene.geo(lat, lon) for lon, lat in bridge.outline_wgs84]).buffer(.15))
    belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / 'architecture/west-belvedere.json').read_bytes())
    blocked.append(Point(belvedere.center_xy_m).buffer(belvedere.radius_m + .6))
    chapel = TypeAdapter(ChapelSource).validate_json(
        (scene.sources / 'architecture/chapel/reconstruction.json').read_bytes())
    blocked.append(from_wkt(chapel.site.ground.expected_domain_wkt))
    with barriers.open() as handle:
        for row in csv.DictReader(handle):
            line = LineString(((float(row['ax']), float(row['ay'])),
                               (float(row['bx']), float(row['by']))))
            blocked.append(line.buffer(float(row['radius']) + .5))
    actual = unary_union([boundary(scene, item) for item in source.natural_roles]).difference(unary_union(blocked))
    expected = from_wkt(source.expected_domain_wkt)
    if not actual.is_valid or actual.symmetric_difference(expected).area > 1e-6:
        raise ValueError('The source-qualified ravine-role domain changed')
    return expected


def partition(scene: MeshScene, plan: BaseGeometry, expected_faces: int,
              expected_area_m2: float, expected_parent_sha256: str) -> RavineRolesChange:
    owners: list[tuple[str, int, bytes, SurfaceFace]] = []
    area = 0.0
    for name, tile in sorted(scene.tiles.items()):
        if not name.startswith('Tile_Street_') or not tile.triangles:
            continue
        bounds = box(-tile.maximum[1] / 100, -tile.maximum[0] / 100,
                     -tile.minimum[1] / 100, -tile.minimum[0] / 100)
        if not bounds.intersects(plan):
            continue
        for offset in range(0, len(tile.triangles), 100):
            if tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]] != 'Runoff':
                continue
            parent = face(tile, offset)
            if parent.plan.area < 1e-10 or min(v[5] for v in parent.vertices) < .05:
                continue
            inside = parent.plan.intersection(plan).area
            if inside <= 1e-9:
                continue
            owners.append((name, offset, bytes(tile.triangles[offset:offset + 100]), parent))
            area += inside
    digest = hashlib.sha256()
    for name, offset, raw, _ in owners:
        digest.update(name.encode() + b'\0' + struct.pack('<Q', offset // 100) + raw[4:])
    if len(owners) != expected_faces or abs(area - expected_area_m2) > 1e-6 or digest.hexdigest() != expected_parent_sha256:
        raise ValueError('Actual ravine-role parent ownership differs from its frozen proof')
    # Validate every partition before changing any original mesh or material table.
    prepared = {}
    stats = []
    whole = held = emitted = kept = 0
    for name in sorted({owner[0] for owner in owners}):
        tile = deepcopy(scene.tiles[name])
        local = {offset: (raw, parent) for owner, offset, raw, parent in owners if owner == name}
        output = bytearray()
        for offset in range(0, len(tile.triangles), 100):
            if offset not in local:
                output.extend(tile.triangles[offset:offset + 100])
                kept += 1
                continue
            raw, _ = local[offset]
            fragments, audit = recolor(GroundRow('Runoff', raw[4:]), plan)
            if audit is None or (not audit.held_unrepresentable_natural_area_m2 and audit.normal_min_alignment <= 0):
                raise ValueError('A new ravine-role partition is unresolved in native encoding')
            stats.append(audit)
            held += int(audit.held_unrepresentable_natural_area_m2 > 0)
            whole += int(audit.outside_area_m2 < 1e-10)
            for row in fragments:
                if row.material not in tile.materials:
                    tile.materials.append(row.material)
                output.extend(struct.pack('<I', tile.materials.index(row.material)))
                output.extend(row.payload)
            emitted += len(fragments)
        tile.triangles = output
        prepared[name] = tile
    scene.tiles.update(prepared)
    new_stats = [s for s in stats if not s.held_unrepresentable_natural_area_m2]
    return RavineRolesChange(
        changed_tiles=tuple(prepared), selected_parent_faces=len(owners),
        whole_material_only_faces=whole, split_faces=len(owners) - whole - held,
        held_parent_faces=held,
        held_natural_area_m2=sum(s.held_unrepresentable_natural_area_m2 for s in stats),
        arithmetic_ghost_area_m2=sum(s.dropped_f32_area_m2 for s in stats),
        emitted_fragment_faces=emitted, complete_unchanged_rows=kept + held,
        natural_area_m2=sum(s.natural_area_m2 for s in stats),
        maximum_plane_error_m=max(s.maximum_plane_error_m for s in new_stats),
        maximum_plane_error_bound_m=max(s.maximum_plane_error_bound_m for s in new_stats),
        minimum_normal_alignment=min(s.normal_min_alignment for s in new_stats),
    )


def finish_terrain(scene: CircuitScene) -> RavineRolesChange:
    source = TypeAdapter(RavineRolesSource).validate_json(
        (scene.sources / 'architecture/ravine-roles/reconstruction.json').read_bytes())
    change = partition(scene, domain(scene, source), source.expected_parent_faces,
        source.expected_natural_area_m2, source.expected_parent_sha256)
    scene.landmarks.append({'name': 'Source-registered mixed natural ravine roles',
        'source': 'architecture/ravine-roles/source-qualification.json',
        'original_runoff_faces': change.selected_parent_faces,
        'natural_area_m2': change.natural_area_m2,
        'held_sub_float32_natural_area_m2': change.held_natural_area_m2,
        'limits': 'Material partitions on literal old planes only. Original normal and UV interpolation retained. No height, plant, roof, road or native contact change. Marie/Rome engineered junction remains held.'})
    return change
