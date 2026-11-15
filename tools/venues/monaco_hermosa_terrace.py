"""Fit the registered Hermosa lawn and retaining face to actual emitted ground."""
from __future__ import annotations

import csv
import hashlib
import math
import struct
from collections import Counter

import numpy as np
from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.monaco_foreground import replacement
from venues.monaco_terrace import Support, emit, top_height
from venues.monaco_terrace_dataclasses import (
    TerraceChange,
    TerraceFloor,
    TerraceSource,
    TerraceSpec,
)
from venues.monaco_underarch_plants import face_points
from venues.monaco_upper_ground import tree_rows
from venues.monaco_upper_ground_dataclasses import UpperBankSource

CITY = 'Building_City_m1_01'
STREET = 'Tile_Street_m1_01'
FLOORS = frozenset(('Runoff', 'Grass', 'MonacoIvyGround', 'MonacoRockGround',
    'MonacoNaturalGround', 'Concrete', 'Road', 'Limestone', 'Gravel'))


def project(scene: CircuitScene, controls: tuple[tuple[float, float], ...],
            expected: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    points = tuple(scene.geo(lat, lon) for lon, lat in controls)
    if len(points) < 3 or len(points) != len(expected) or max(
        math.dist(a, b) for a, b in zip(points, expected)
    ) > 1e-8:
        raise ValueError('A literal garden source plan differs from the qualified frame')
    return points


def bindings(scene: CircuitScene, source: TerraceSource) -> tuple[Polygon, LineString, Point]:
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()).relative_datum_m
    if scene.slug != 'monaco' or max(
        abs(scene.provenance.origin.latitude - source.origin_lat_lon[0]),
        abs(scene.provenance.origin.longitude - source.origin_lat_lon[1]),
        abs(scene.provenance.route.uniform_scale - source.uniform_scale),
        abs(datum - source.relative_datum_m),
        abs(datum - source.terrace.relative_datum_m),
    ) > 1e-9:
        raise ValueError('Hermosa terrace requires its retained source frame and datum')
    for relative, expected in source.protected_source_sha256.items():
        if hashlib.sha256((scene.sources / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Hermosa terrace source changed: {relative}')
    ring = project(scene, source.garden_wgs84_lonlat, source.expected_garden_xy_m)
    corner = ring[3]
    start = tuple(ring[2][i] * 0.12 + corner[i] * 0.88 for i in (0, 1))
    end = tuple(corner[i] * 0.5 + ring[4][i] * 0.5 for i in (0, 1))
    curve = [tuple((1 - t) ** 2 * start[i] + 2 * (1 - t) * t * corner[i] + t * t * end[i]
             for i in (0, 1)) for t in (j / 12 for j in range(13))]
    outer = Polygon([*ring[:3], *curve, *ring[4:]])
    apron = Polygon(project(scene, source.apron_wgs84_lonlat, source.expected_apron_xy_m))
    mapped_pool = Polygon(project(scene, source.pool_wgs84_lonlat, source.expected_pool_xy_m))
    bodies = unary_union([Polygon(b.ring).buffer(source.body_guard_m) for b in scene.buildings if b.use != 'bridge'])
    domain = outer.difference(unary_union([apron, mapped_pool, bodies]))
    expected = from_wkt(source.expected_domain_wkt)
    if (not isinstance(domain, Polygon) or not domain.is_valid
            or not isinstance(expected, Polygon) or not expected.is_valid
            or domain.symmetric_difference(expected).area > 1e-6):
        raise ValueError('The finite Hermosa terrace domain changed')
    protected = [scene.corridor_mask.buffer(0.25),
        *[area.buffer(0.25) for area in scene.extra_corridors],
        *[Polygon(b.ring).buffer(0.15) for b in scene.buildings if b.use == 'bridge']]
    with (scene.scratch / 'barriers.csv').open() as handle:
        for row in csv.DictReader(handle):
            line = LineString(((float(row['ax']), float(row['ay'])), (float(row['bx']), float(row['by']))))
            if line.distance(domain) < 2:
                protected.append(line.buffer(float(row['radius']) + 0.25))
    if domain.buffer(0.12).intersection(unary_union(protected)).area > 1e-8:
        raise ValueError('The Hermosa garden overlaps actual racing protection or bridge structure')
    front = LineString(project(scene, source.front_wgs84_lonlat, source.expected_front_xy_m)[:4])
    upper = TypeAdapter(UpperBankSource).validate_json(
        (scene.sources / 'architecture/upper-bank-source.json').read_bytes())
    candidates = [row for row in scene.landmarks if row.get('mapped_tree_id') == source.mapped_tree_id]
    if len(candidates) != 1 or 'tree_base_delta_m' not in candidates[0]:
        raise ValueError('Hermosa terrace requires the actual upper-bank mapped-tree producer')
    x, y = scene.geo(source.mapped_tree_wgs84_lonlat[1], source.mapped_tree_wgs84_lonlat[0])
    previous = (x, y, upper.old_tree_base[2] + float(candidates[0]['tree_base_delta_m']))
    if math.dist(previous, source.expected_previous_tree_base) > 1e-9:
        raise ValueError('The actual retained mapped-tree source base changed')
    # Keep qualified ring order: GEOS union ordering must not shift perimeter UVs.
    return orient(expected), front, previous


def nearby_ground(scene: MeshScene, domain: Polygon) -> tuple[TerraceFloor, ...]:
    floors = []
    xmin, ymin, xmax, ymax = domain.bounds
    for name, tile in scene.tiles.items():
        if not name.startswith('Tile_Street_') or not tile.triangles:
            continue
        if (-tile.minimum[1] / 100 < xmin - 0.1 or -tile.maximum[1] / 100 > xmax + 0.1
                or -tile.minimum[0] / 100 < ymin - 0.1 or -tile.maximum[0] / 100 > ymax + 0.1):
            continue
        points = face_points(tile)
        low, high = points[:, :, :2].min(axis=1), points[:, :, :2].max(axis=1)
        eligible = ((high[:, 0] >= xmin) & (low[:, 0] <= xmax)
                    & (high[:, 1] >= ymin) & (low[:, 1] <= ymax))
        cross = ((points[:, 1, 0] - points[:, 0, 0]) * (points[:, 2, 1] - points[:, 0, 1])
               - (points[:, 1, 1] - points[:, 0, 1]) * (points[:, 2, 0] - points[:, 0, 0]))
        for index in np.flatnonzero(eligible & (cross > 1e-9)):
            offset = int(index) * 100
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            if material not in FLOORS:
                continue
            plan = Polygon(points[index, :, :2])
            if not plan.intersects(domain.buffer(0.00003)):
                continue
            a, b, c = points[index]
            floors.append(TerraceFloor(name, int(index), material, (tuple(a), tuple(b), tuple(c)),
                plan, bytes(tile.triangles[offset:offset + 100])))
    return tuple(floors)


def apply(scene: MeshScene, domain: Polygon, front: LineString,
          floors: tuple[TerraceFloor, ...], source: TerraceSpec,
          previous_tree: Point, tree_height_m: float, tree_seed: int) -> TerraceChange:
    if CITY not in scene.tiles or STREET not in scene.tiles:
        raise ValueError('Hermosa terrace requires the actual retained City and Street tiles')
    if (source.minimum_soil_cover_m < 0.02 or source.retaining_burial_m < 0.1
            or not 0 < source.face_step_m <= 0.7 or not 0 < source.upper_stone_band_height_m <= 6
            or not 0.01 <= source.mortar_joint_m <= 0.03
            or not 0 < source.maximum_stone_relief_m <= 0.035):
        raise ValueError('Hermosa reconstruction exceeds its bounded source recipe')
    new = MeshScene()
    geometry = emit(new, domain, front, floors, source)
    old_tree = MeshScene()
    old_tree.broadleaf(previous_tree, tree_height_m, tree_seed)
    wanted = tree_rows(old_tree)
    if sum(wanted.values()) != 102:
        raise ValueError('The mapped tree recipe changed')
    x, y, _old_z = previous_tree
    support = Support(floors)
    new_z = min(top_height(source, support, x + dx, y + dy)
                for dx in (-0.125, 0.125) for dy in (-0.125, 0.125)) - 0.1
    new_tree = x, y, new_z
    minimum_alignment = 1.0
    plans: list[Polygon] = []
    for name, tile in new.tiles.items():
        values = np.frombuffer(tile.triangles,
            dtype=np.dtype([('mat', '<u4'), ('v', '<f4', (3, 8))]))['v'].astype(float)
        points = values[:, :, [1, 0, 2]] * np.array((-1, -1, 1)) / 100
        normal = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        length = np.linalg.norm(normal, axis=1)
        if np.any(length < 1e-10):
            raise ValueError('A new Hermosa face collapsed during native encoding')
        stored = values[:, :, 3:6][:, :, [1, 0, 2]] * np.array((-1, -1, 1))
        alignment = np.einsum('ij,ikj->ik', normal / length[:, None], stored)
        minimum_alignment = min(minimum_alignment, float(alignment.min()))
        if name == STREET:
            if np.any(normal[:, 2] <= 0):
                raise ValueError('A newly encoded Hermosa lawn face points down')
            plans.extend(Polygon(p[:, :2]) for p in points)
    if minimum_alignment < 0.9:
        raise ValueError('A new Hermosa face lost its packed normal alignment')
    cover = unary_union(plans)
    missing, extra = domain.difference(cover).area, cover.difference(domain).area
    if missing + extra > geometry.encoding_area_bound_m2:
        raise ValueError('Hermosa lawn coverage exceeds its native XY encoding bound')
    new.broadleaf(new_tree, tree_height_m, tree_seed)
    city, kept = replacement(scene.tiles[CITY], wanted, new.tiles[CITY])
    street, old_street = replacement(scene.tiles[STREET], Counter(), new.tiles[STREET])
    if street.triangles[:len(scene.tiles[STREET].triangles)] != scene.tiles[STREET].triangles:
        raise ValueError('Hermosa terrace changed an actual old Ground row')
    # Original house/bridge/terrain rows and all other mapped trees remain in place.
    scene.tiles.update({CITY: city, STREET: street})
    return TerraceChange(geometry, previous_tree, new_tree, kept, old_street,
        minimum_alignment, missing, extra)


def finish_terrain(scene: CircuitScene) -> TerraceChange:
    source = TypeAdapter(TerraceSource).validate_json(
        (scene.sources / 'architecture/hermosa-terrace/reconstruction.json').read_bytes())
    domain, front, previous = bindings(scene, source)
    result = apply(scene, domain, front, nearby_ground(scene, domain), source.terrace,
        previous, source.tree_height_m, source.tree_seed)
    scene.landmarks.append({'name': 'Villa Hermosa formal garden and stone retaining band',
        'source': 'architecture/hermosa-terrace/source-qualification.json',
        'garden_area_m2': result.geometry.area_m2,
        'source_limits': 'Photo-estimated stone wall cap6 m +/-2.5 m; separate lower natural rock, two conflicting pool outlines held rather than two pools claimed; native terrain and driving data unchanged'})
    return result
