"""Replace only Villa de Rome's exact generic family with its reviewed roof/body."""
from __future__ import annotations

import hashlib
import math
import struct
from collections import Counter
from copy import copy

import numpy as np
from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.monaco_foreground import replacement
from venues.monaco_rome_dataclasses import RomeChange, RomeSource, RomeSpec
from venues.monaco_rome_geometry import (
    ROOF_KIND,
    SOFFIT_KIND,
    emit,
    roof_envelope,
    source_object_point,
)

CITY = 'Building_City_m1_01'
Row = tuple[str, bytes]


class RoofCapture(MeshScene):
    def __init__(self) -> None:
        super().__init__()
        self.parts: dict[str, list[tuple[Point, Point, Point]]] = {ROOF_KIND: [], SOFFIT_KIND: []}
        self.top_plans: list[Polygon] = []

    def triangle(self, kind: str, material: str, a: Point, b: Point, c: Point,
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                 normals: tuple[Point, ...] | None = None) -> None:
        center = ((a[0]+b[0]+c[0])/3, (a[1]+b[1]+c[1])/3, (a[2]+b[2]+c[2])/3)
        tile = self.tile(kind, center)
        before = len(tile.triangles)
        super().triangle(kind, material, a, b, c, uv, normals)
        if kind not in self.parts or len(tile.triangles) == before:
            return
        row = struct.unpack_from('<24f', tile.triangles, before+4)
        points = [(-row[i+1]/100, -row[i]/100, row[i+2]/100) for i in (0, 8, 16)]
        self.parts[kind].append((points[0], points[1], points[2]))
        if kind == ROOF_KIND and min(row[i+5] for i in (0, 8, 16)) > .01:
            self.top_plans.append(Polygon([p[:2] for p in points]))


def bindings(scene: CircuitScene, source: RomeSource) -> RomeSpec:
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources/'scenery-ground.json').read_bytes()).relative_datum_m
    if scene.slug != 'monaco' or max(
        abs(scene.provenance.origin.latitude-source.origin_lat_lon[0]),
        abs(scene.provenance.origin.longitude-source.origin_lat_lon[1]),
        abs(scene.provenance.route.uniform_scale-source.uniform_scale),
        abs(datum-source.relative_datum_m), abs(datum-source.spec.frame.datum_m),
    ) > 1e-9:
        raise ValueError('Villa de Rome requires its reviewed source frame and datum')
    for relative, expected in source.protected_source_sha256.items():
        if hashlib.sha256((scene.sources/relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Villa de Rome source changed: {relative}')
    owner = tuple(scene.geo(lat, lon) for lon, lat in source.owner_wgs84_lonlat)
    actual = tuple(scene.footprint(source.osm_id).ring)
    if (len(owner) != len(actual) or len(owner) != len(source.spec.owner_xy_m)
            or max(math.dist(p, q) for p, q in zip(owner, actual)) > 1e-8
            or max(math.dist(p, q) for p, q in zip(owner, source.spec.owner_xy_m)) > 1e-8):
        raise ValueError('Villa de Rome literal owner differs from the reviewed source')
    roof = tuple((*scene.geo(lat, lon), z) for lon, lat, z in source.original_ign_wgs84_xyz)
    if (len(roof) != len(source.spec.roof_xy_absolute_z_m)
            or max(math.dist(p, q) for p, q in zip(roof, source.spec.roof_xy_absolute_z_m)) > 1e-8):
        raise ValueError('Original Villa de Rome IGN XYZ observations changed')
    if Polygon(roof_envelope(source.spec)).intersection(scene.corridor_mask.buffer(.2)).area > 1e-8:
        raise ValueError('Villa de Rome roof enters current racing protection')
    return source.spec


def legacy_rows(scene: CircuitScene) -> Counter[Row]:
    from venues.monaco import frontage

    replay = copy(scene)
    replay.tiles = {}
    replay.modeled_buildings = set()
    replay.landmarks = []
    replay.terrain_cutouts = []
    frontage(replay, scene.footprint(94400097))
    if set(replay.tiles) != {CITY}:
        raise ValueError('Villa de Rome legacy family escaped its one City tile')
    tile = replay.tiles[CITY]
    wanted: Counter[Row] = Counter()
    for offset in range(0, len(tile.triangles), 100):
        material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
        wanted[material, bytes(tile.triangles[offset+4:offset+100])] += 1
    if wanted.total() != 1822:
        raise ValueError('Villa de Rome generic family no longer has its reviewed1822 rows')
    return wanted


def apply(scene: MeshScene, source: RomeSource, wanted: Counter[Row]) -> RomeChange:
    if CITY not in scene.tiles or wanted.total() != source.expected_legacy_rows:
        raise ValueError('Villa de Rome requires its exact generic City family')
    new = RoofCapture()
    body_ends = emit(new, source.spec)
    if set(new.tiles) != {CITY} or body_ends != {CITY: source.body_south_prefix_bytes}:
        raise ValueError('Villa de Rome geometry escaped its reviewed family/body prefix')
    tile = new.tiles[CITY]
    geometry_sha = hashlib.sha256(tile.triangles).hexdigest()
    body_sha = hashlib.sha256(tile.triangles[:source.body_south_prefix_bytes]).hexdigest()
    if (geometry_sha != source.frozen_v3_rows_sha256 or tuple(tile.materials) != source.frozen_v3_materials
            or body_sha != source.body_south_prefix_sha256
            or len(tile.triangles)//100 != source.expected_new_triangles):
        raise ValueError('Villa de Rome differs from immutable reviewed V3 geometry')
    values = np.frombuffer(tile.triangles, dtype=np.dtype([('mat', '<u4'), ('v', '<f4', (3, 8))]))['v'].astype(float)
    points = values[:, :, [1, 0, 2]]*np.array((-1, -1, 1))/100
    normals = np.cross(points[:, 1]-points[:, 0], points[:, 2]-points[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    if lengths.min() < 1e-10:
        raise ValueError('A Villa de Rome face collapsed during native encoding')
    stored = values[:, :, 3:6][:, :, [1, 0, 2]]*np.array((-1, -1, 1))
    alignment = float(np.einsum('ij,ikj->ik', normals/lengths[:, None], stored).min())
    if alignment < .99:
        raise ValueError('A Villa de Rome face lost its packed normal')
    for kind, faces in new.parts.items():
        edges: Counter[tuple[Point, Point]] = Counter()
        directed: Counter[tuple[Point, Point]] = Counter()
        for a, b, c in faces:
            for p, q in ((a, b), (b, c), (c, a)):
                edge = (p, q) if p < q else (q, p)
                edges[edge] += 1
                directed[p, q] += 1
        if any(count != 2 or directed[p, q] != directed[q, p] for (p, q), count in edges.items()):
            raise ValueError(f'Villa de Rome {kind} is not a consistently closed packed skin')
    roof = Polygon(roof_envelope(source.spec))
    union = unary_union(new.top_plans)
    coverage, overlap = union.symmetric_difference(roof).area, sum(p.area for p in new.top_plans)-union.area
    if len(new.top_plans) != 14 or coverage > .002 or overlap > .002:
        raise ValueError('Villa de Rome roof has an uncovered or overlapping plan')
    offset = max(math.dist(source_object_point(source.spec, obj, .5, .5, 0)[:2], obj.nominal_xy_m)
                 for obj in source.spec.source_objects)
    if len(source.spec.source_objects) != 3 or offset > 1e-7:
        raise ValueError('Villa de Rome roof objects left their reviewed direct source centres')
    candidate, kept = replacement(scene.tiles[CITY], wanted, tile)
    if candidate.materials[:len(scene.tiles[CITY].materials)] != scene.tiles[CITY].materials:
        raise ValueError('Villa de Rome changed the original material prefix')
    scene.tiles[CITY] = candidate
    return RomeChange(wanted.total(), len(tile.triangles)//100, kept, geometry_sha, body_sha,
                      alignment, len(new.top_plans), coverage, overlap,
                      len(new.parts[ROOF_KIND]), len(new.parts[SOFFIT_KIND]), offset)


def finish_terrain(scene: CircuitScene, source: RomeSource | None = None) -> RomeChange:
    if source is None:
        source = TypeAdapter(RomeSource).validate_json(
            (scene.sources/'architecture/villa-de-rome/reconstruction.json').read_bytes())
    bindings(scene, source)
    result = apply(scene, source, legacy_rows(scene))
    for landmark in scene.landmarks:
        if landmark.get('osm_id') != source.osm_id:
            continue
        for key in ('height_m', 'levels'):
            value = landmark.pop(key, None)
            if value is not None:
                landmark['legacy_default_'+key] = value
        landmark.update({'building_identity_storeys': 9,
                         'height_status': 'Nine-storey developer identity; estimated8 strata plus occupied mansard, not9 exposed floors on every face',
                         'roof_height_status': 'Architectural82.7/86.6/88.0m absolute estimates; original north IGN XYZ/part association unresolved;89.1m maximum unused',
                         'source': source.source_qualification,
                         'structure': 'South marble colonnade/loggias, balconies and central pediment; four-face hip, continuous mansard and source-registered roof services; secondary elevations/support estimated'})
    return result
