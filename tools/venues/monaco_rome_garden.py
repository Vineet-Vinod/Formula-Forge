"""Add the separate Rome lawn and retaining edge without moving the house or native field."""
from __future__ import annotations

import hashlib
import math
from collections import Counter

import numpy as np
from circuit_dataclasses import MeshTile, Point, RetainedTerrainSource
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.monaco_foreground import replacement
from venues.monaco_hermosa_terrace import CITY, STREET, nearby_ground, project
from venues.monaco_rome_garden_dataclasses import (
    RomeGardenChange,
    RomeGardenSource,
    RomeGardenTree,
)
from venues.monaco_terrace import Support, emit, encoded, top_height
from venues.monaco_terrace_dataclasses import TerraceFloor, TerraceSpec
from venues.monaco_underarch_plants import face_points
from venues.monaco_upper_ground import tree_rows


def bindings(scene: CircuitScene, source: RomeGardenSource) -> tuple[Polygon, LineString, tuple[Point, ...]]:
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()).relative_datum_m
    if scene.slug != 'monaco' or max(
        abs(scene.provenance.origin.latitude - source.origin_lat_lon[0]),
        abs(scene.provenance.origin.longitude - source.origin_lat_lon[1]),
        abs(scene.provenance.route.uniform_scale - source.uniform_scale),
        abs(datum - source.relative_datum_m),
        abs(datum - source.terrace.relative_datum_m),
    ) > 1e-9:
        raise ValueError('Rome garden requires its retained source frame and datum')
    for relative, expected in source.protected_source_sha256.items():
        if hashlib.sha256((scene.sources / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Rome garden protected source changed: {relative}')
    owner = Polygon([scene.geo(lat, lon) for lon, lat in source.owner_wgs84_lonlat])
    if owner.symmetric_difference(Polygon(scene.footprint(source.owner_osm_id).ring)).area > 1e-8:
        raise ValueError('The Rome garden owner footprint changed')
    garden = Polygon(project(scene, source.garden_wgs84_lonlat, source.expected_garden_xy_m))
    apron = Polygon(project(scene, source.apron_wgs84_lonlat, source.expected_apron_xy_m))
    bodies = unary_union([Polygon(b.ring).buffer(source.body_guard_m) for b in scene.buildings if b.use != 'bridge'])
    actual = garden.difference(unary_union([apron, bodies]))
    expected = from_wkt(source.expected_domain_wkt)
    if (not isinstance(actual, Polygon) or not actual.is_valid
            or not isinstance(expected, Polygon) or not expected.is_valid
            or actual.symmetric_difference(expected).area > 1e-6):
        raise ValueError('The finite source-qualified Rome garden domain changed')
    protection = unary_union([scene.corridor_mask.buffer(.25), *[p.buffer(.25) for p in scene.extra_corridors],
        *[Polygon(b.ring).buffer(.15) for b in scene.buildings if b.use == 'bridge']])
    if expected.buffer(.12).intersection(protection).area > 1e-8:
        raise ValueError('The Rome garden overlaps racing pavement/protection')
    front = LineString(project(scene, source.front_wgs84_lonlat, source.expected_front_xy_m)[:4])
    if tuple(tree.osm_id for tree in source.mapped_trees) != (5931906972, 5931906973):
        raise ValueError('Rome garden is limited to its two qualified mapped trees')
    old = []
    for tree in source.mapped_trees:
        mapped = [e for ds in scene.osm for e in ds.elements if e.type == 'node' and e.id == tree.osm_id]
        if not mapped or any(e.tags.get('natural') != 'tree' for e in mapped):
            raise ValueError('A qualified Rome mapped tree is missing')
        x, y = scene.geo(tree.wgs84_lonlat[1], tree.wgs84_lonlat[0])
        if any(math.dist(scene.geo(e.lat, e.lon), (x, y)) > 1e-8 for e in mapped):
            raise ValueError('The actual Rome mapped-tree coordinates changed')
        base = (x, y, scene.ground(x, y))
        if math.dist(base, tree.expected_old_base) > 1e-9:
            raise ValueError('The actual retained mapped-tree producer base changed')
        old.append(base)
    # Qualified ring order keeps original perimeter UVs, stone rhythm and planting stable.
    return orient(expected), front, tuple(old)


def apply(scene: MeshScene, domain: Polygon, front: LineString,
          floors: tuple[TerraceFloor, ...], source: TerraceSpec,
          trees: tuple[RomeGardenTree, ...], previous: tuple[Point, ...]) -> RomeGardenChange:
    if (source.reference_lawn_absolute_m != 59.15 or source.lawn_north_grade != 0
            or source.minimum_soil_cover_m < .02 or source.retaining_burial_m < .1
            or not 0 < source.upper_stone_band_height_m <= 6
            or not 0 < source.face_step_m <= .7 or not .01 <= source.mortar_joint_m <= .03
            or not 0 < source.maximum_stone_relief_m <= .035):
        raise ValueError('Rome garden exceeds its bounded separate source profile')
    if CITY not in scene.tiles or STREET not in scene.tiles or len(trees) != len(previous):
        raise ValueError('Rome garden requires actual complete source tiles and tree bindings')
    wanted: Counter[tuple[str, bytes]] = Counter()
    for tree, old in zip(trees, previous):
        replay = MeshScene()
        replay.broadleaf(old, tree.height_m, tree.osm_id % 997)
        wanted.update(tree_rows(replay))
    if sum(wanted.values()) != len(trees) * 102:
        raise ValueError('The retained Rome tree shape recipe changed')
    # Validate and remove exact old tree rows only in temporary buffers.
    city_base, kept = replacement(scene.tiles[CITY], wanted, MeshTile())
    new = MeshScene()
    geometry = emit(new, domain, front, floors, source)
    alignment = 1.0
    for tile in new.tiles.values():
        v = np.frombuffer(tile.triangles, dtype=np.dtype([('m', '<u4'), ('v', '<f4', (3, 8))]))['v'].astype(float)
        p = v[:, :, :3][:, :, [1, 0, 2]] * np.array((-1, -1, 1)) / 100
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        length = np.linalg.norm(n, axis=1)
        if np.any(length < 1e-10):
            raise ValueError('A new Rome garden face collapsed during native encoding')
        stored = v[:, :, 3:6][:, :, [1, 0, 2]] * np.array((-1, -1, 1))
        alignment = min(alignment, float(np.einsum('ij,ikj->ik', n / length[:, None], stored).min()))
    if alignment < .9:
        raise ValueError('A new Rome garden face lost its packed normal alignment')
    lawn_tile = new.tiles[STREET]
    points = face_points(lawn_tile)
    lawn_faces = tuple(TerraceFloor(STREET, i, 'MonacoGardenLawn',
        ((float(a[0]), float(a[1]), float(a[2])), (float(b[0]), float(b[1]), float(b[2])), (float(c[0]), float(c[1]), float(c[2]))),
        Polygon((a[:2], b[:2], c[:2])), bytes(lawn_tile.triangles[i * 100:(i + 1) * 100]))
        for i, (a, b, c) in enumerate(points))
    cover = unary_union([face.plan for face in lawn_faces])
    missing, extra = domain.difference(cover).area, cover.difference(domain).area
    if missing + extra > geometry.encoding_area_bound_m2:
        raise ValueError('The Rome garden native encoding exceeded its bounded coverage')
    support, actual_lawn = Support(floors), Support(lawn_faces)
    minimum_burial = math.inf
    updated = []
    for tree, old in zip(trees, previous):
        x, y, _z = old
        new_z = min(top_height(source, support, x + dx, y + dy)
                    for dx in (-.125, .125) for dy in (-.125, .125)) - .1
        for dx in (-.125, .125):
            for dy in (-.125, .125):
                minimum_burial = min(minimum_burial,
                    actual_lawn.height(encoded(x + dx), encoded(y + dy)) - encoded(new_z))
        updated.append((x, y, new_z))
        new.broadleaf((x, y, new_z), tree.height_m, tree.osm_id % 997)
    if minimum_burial < .0999:
        raise ValueError('An actual packed Rome tree foot is unsupported')
    city, _unused = replacement(city_base, Counter(), new.tiles[CITY])
    street, old_street = replacement(scene.tiles[STREET], Counter(), new.tiles[STREET])
    if street.triangles[:len(scene.tiles[STREET].triangles)] != scene.tiles[STREET].triangles:
        raise ValueError('Rome garden changed an original Ground row')
    scene.tiles.update({CITY: city, STREET: street})
    return RomeGardenChange(geometry, previous, tuple(updated), kept, old_street,
        alignment, minimum_burial, missing, extra)


def finish_terrain(scene: CircuitScene) -> RomeGardenChange:
    source = TypeAdapter(RomeGardenSource).validate_json(
        (scene.sources / 'architecture/rome-garden/reconstruction.json').read_bytes())
    domain, front, previous = bindings(scene, source)
    result = apply(scene, domain, front, nearby_ground(scene, domain), source.terrace,
        source.mapped_trees, previous)
    scene.landmarks.append({'name': 'Villa de Rome formal lawn and retaining edge',
        'source': 'architecture/rome-garden/source-qualification.json',
        'garden_area_m2': result.geometry.area_m2,
        'limits': 'Separate estimated 59.15 m lawn plateau; southern source rim/stepping pads/opening held. Native field, house body, road, bridge and camera remain unchanged.'})
    return result
