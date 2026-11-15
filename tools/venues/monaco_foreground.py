"""Replace two ordinary frontages after terrain, preserving every unrelated mesh row."""

from __future__ import annotations

import math
import struct
from collections import Counter
from copy import copy
from dataclasses import replace

from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box

from venues.monaco_bamboo import emit_bamboo
from venues.monaco_bruyeres import core_plan, emit_bruyeres, emit_garden
from venues.monaco_foreground_dataclasses import (
    XY,
    BruyeresSpec,
    ForegroundChange,
    ForegroundFloor,
    ForegroundSource,
    MissingForegroundFloor,
    MontjoieSpec,
)
from venues.monaco_montjoie import emit_montjoie

OWNERS = (94400108, 94399506)
TILE = 'Building_City_00_00'
FLOORS = frozenset(('Runoff', 'Grass', 'Concrete', 'Limestone', 'Gravel', 'Road', 'RunoffGreen'))
Row = tuple[str, bytes]


def bindings(scene: CircuitScene, source: ForegroundSource) -> tuple[BruyeresSpec, MontjoieSpec]:
    frame = scene.provenance
    if scene.slug != 'monaco' or max(
            abs(source.origin_latitude - frame.origin.latitude),
            abs(source.origin_longitude - frame.origin.longitude),
            abs(source.scene_scale - frame.route.uniform_scale)) > 1e-10:
        raise ValueError('Foreground primary-source registration differs from the Monaco frame')
    projected = []
    for osm_id, controls, expected in (
            (OWNERS[0], source.bruyeres_owner_wgs84_lonlat, source.bruyeres.owner_xy_m),
            (OWNERS[1], source.montjoie_owner_wgs84_lonlat, source.montjoie.owner_xy_m)):
        owner = tuple(scene.geo(lat, lon) for lon, lat in controls)
        actual = scene.footprint(osm_id).ring
        if (len(owner) != len(expected) or len(actual) != len(owner)
                or max(math.dist(a, b) for a, b in zip(owner, expected)) > 1e-8
                or max(math.dist(a, b) for a, b in zip(owner, actual)) > 1e-8):
            raise ValueError('A foreground literal WGS84 owner differs from the retained mapped property')
        projected.append(owner)
    roof = tuple((
        (lon - source.origin_longitude) * math.pi / 180 * 6378137.0
        * math.cos(math.radians(source.origin_latitude)) * source.scene_scale,
        (lat - source.origin_latitude) * math.pi / 180 * 6378137.0 * source.scene_scale,
    ) for lon, lat, _z in source.bruyeres_roof_wgs84_xyz)
    if (len(roof) != len(source.bruyeres.roof_xy_m)
            or max(math.dist(a, b) for a, b in zip(roof, source.bruyeres.roof_xy_m)) > 1e-8):
        raise ValueError('The literal IGN upper roof no longer matches its qualified component')
    if (source.bruyeres.osm_id, source.montjoie.osm_id) != OWNERS:
        raise ValueError('Foreground adapter is limited to its two qualified owners')
    if (abs(source.relative_datum_m - source.montjoie.relative_datum_m) > 1e-10
            or abs(source.relative_datum_m - source.bruyeres.datum_m) > 1e-10
            or abs(source.relative_datum_m - source.bruyeres_bamboo.relative_datum_m) > 1e-10):
        raise ValueError('Foreground roof and ground datums disagree')
    return (replace(source.bruyeres, owner_xy_m=projected[0], roof_xy_m=roof,
                    front_endpoints_xy_m=(roof[1], roof[2])),
            replace(source.montjoie, owner_xy_m=projected[1]))


def nearby_floors(scene: MeshScene, estate: Polygon) -> tuple[ForegroundFloor, ...]:
    cover = estate.buffer(.01)
    xmin, ymin, xmax, ymax = cover.bounds
    result = []
    for name, tile in scene.tiles.items():
        if not name.startswith('Tile_Street_') or not tile.triangles:
            continue
        if (-tile.minimum[1] / 100 < xmin or -tile.maximum[1] / 100 > xmax
                or -tile.minimum[0] / 100 < ymin or -tile.maximum[0] / 100 > ymax):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            if material not in FLOORS:
                continue
            row = struct.unpack_from('<24f', tile.triangles, offset + 4)
            if min(row[i + 5] for i in (0, 8, 16)) < .05:
                continue
            vertices = tuple((-row[i + 1] / 100, -row[i] / 100, row[i + 2] / 100)
                             for i in (0, 8, 16))
            if (max(p[0] for p in vertices) < xmin or min(p[0] for p in vertices) > xmax
                    or max(p[1] for p in vertices) < ymin or min(p[1] for p in vertices) > ymax):
                continue
            plan = Polygon([p[:2] for p in vertices])
            if plan.area > 1e-9 and plan.intersects(cover):
                result.append(ForegroundFloor(name, offset, material,
                                              (vertices[0], vertices[1], vertices[2])))
    return tuple(result)


def surface(floors: tuple[ForegroundFloor, ...], x: float, y: float) -> float:
    candidates = []
    for face in floors:
        a, b, c = face.points
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / den
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / den
        if min(u, v, 1 - u - v) >= -2e-5:
            candidates.append(sum(point[2] * weight for point, weight in zip(face.points, (u, v, 1 - u - v))))
    if not candidates:
        raise MissingForegroundFloor(f'No actual retained floor plane at ({x:.8f}, {y:.8f})')
    if max(candidates) - min(candidates) > .003:
        raise ValueError('Foreground support has materially different competing planes')
    return sum(candidates) / len(candidates)


def packed_boundary(estate: Polygon, floors: tuple[ForegroundFloor, ...]) -> tuple[XY, ...]:
    points: list[XY] = []
    for face in floors:
        for p in face.points:
            xy = p[0], p[1]
            if estate.boundary.distance(ShapePoint(xy)) < .00015 and not any(math.dist(xy, q) < 1e-7 for q in points):
                points.append(xy)
    points.sort(key=lambda xy: estate.boundary.project(ShapePoint(xy)))
    if len(points) < len(estate.exterior.coords) - 1:
        raise ValueError('Actual foreground floor did not expose every owner boundary corner')
    plan = Polygon(points)
    if not plan.is_valid or plan.symmetric_difference(estate).area > .005:
        raise ValueError('Actual packed foreground boundary differs from the retained owner void')
    for x, y in points:
        surface(floors, x, y)
    return tuple(points)


def legacy_rows(scene: CircuitScene) -> dict[str, Counter[Row]]:
    from venues.monaco import frontage

    replay = copy(scene)
    replay.tiles = {}
    replay.modeled_buildings = set()
    replay.landmarks = []
    replay.terrain_cutouts = []
    for osm_id in OWNERS:
        frontage(replay, scene.footprint(osm_id))
    result = {}
    for name, tile in replay.tiles.items():
        counter: Counter[Row] = Counter()
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            counter[(material, bytes(tile.triangles[offset + 4:offset + 100]))] += 1
        result[name] = counter
    return result


def replacement(old: MeshTile, needed: Counter[Row], new: MeshTile) -> tuple[MeshTile, int]:
    found: Counter[Row] = Counter()
    for offset in range(0, len(old.triangles), 100):
        material = old.materials[struct.unpack_from('<I', old.triangles, offset)[0]]
        key = material, bytes(old.triangles[offset + 4:offset + 100])
        if key in needed:
            found[key] += 1
    if any(found[key] < count for key, count in needed.items()):
        raise ValueError('Exact old foreground rows were not found before replacement')
    remaining = needed.copy()
    data = bytearray()
    kept = 0
    for offset in range(0, len(old.triangles), 100):
        material = old.materials[struct.unpack_from('<I', old.triangles, offset)[0]]
        key = material, bytes(old.triangles[offset + 4:offset + 100])
        if remaining[key]:
            remaining[key] -= 1
        else:
            data.extend(old.triangles[offset:offset + 100])
            kept += 1
    materials = old.materials.copy()
    for material in new.materials:
        if material not in materials:
            materials.append(material)
    for offset in range(0, len(new.triangles), 100):
        material = new.materials[struct.unpack_from('<I', new.triangles, offset)[0]]
        data.extend(struct.pack('<I', materials.index(material)))
        data.extend(new.triangles[offset + 4:offset + 100])
    minimum = [math.inf] * 3
    maximum = [-math.inf] * 3
    for offset in range(0, len(data), 100):
        values = struct.unpack_from('<24f', data, offset + 4)
        for start in (0, 8, 16):
            for axis in range(3):
                minimum[axis] = min(minimum[axis], values[start + axis])
                maximum[axis] = max(maximum[axis], values[start + axis])
    return MeshTile(data, minimum, maximum, materials), kept


def finish_terrain(scene: CircuitScene) -> ForegroundChange:
    source = TypeAdapter(ForegroundSource).validate_json(
        (scene.sources / 'architecture/foreground-properties.json').read_bytes())
    bruyeres, montjoie = bindings(scene, source)
    estate = Polygon(bruyeres.owner_xy_m)
    if estate.difference(core_plan(bruyeres)).intersection(box(*source.estimated_open_frontage_bounds_xy_m)).area > 1e-8:
        raise ValueError('The lower planted estate entered the source-observed open portal frontage')
    if any(Polygon(spec.owner_xy_m).intersection(scene.corridor_mask.buffer(.2)).area > 1e-8
           for spec in (bruyeres, montjoie)):
        raise ValueError('A foreground property intersects current racing protection')
    floors = nearby_floors(scene, estate)
    boundary = packed_boundary(estate, floors)

    def outside(x: float, y: float) -> float:
        return surface(floors, x, y)

    def foundation(x: float, y: float) -> float:
        try:
            return outside(x, y)
        except MissingForegroundFloor:
            if not estate.buffer(.0001).covers(ShapePoint(x, y)):
                raise
            return scene.ground(x, y)

    new = MeshScene()
    house = emit_bruyeres(new, bruyeres, foundation)
    garden = emit_garden(new, bruyeres, boundary, outside)
    villa = emit_montjoie(new, montjoie)
    planted = Polygon(boundary).difference(core_plan(bruyeres)).intersection(box(24, 283, 35, 292.8))
    if not isinstance(planted, Polygon):
        raise TypeError('The qualified bamboo bed must remain connected')
    planting = emit_bamboo(new, garden.retained_canes, source.bruyeres_bamboo, planted)
    garden = replace(garden, bamboo=planting)
    expected = legacy_rows(scene)
    if set(new.tiles) != {TILE} or set(expected) != {TILE} or TILE not in scene.tiles:
        raise ValueError('Foreground source geometry escaped its one qualified City tile')
    candidate, kept = replacement(scene.tiles[TILE], expected[TILE], new.tiles[TILE])
    if candidate.materials[:len(scene.tiles[TILE].materials)] != scene.tiles[TILE].materials:
        raise ValueError('Foreground replacement changed the original material table')
    if abs(core_plan(bruyeres).area - house.core_area_m2) > 1e-8:
        raise ValueError('Foreground upper-core partition changed during authoring')
    scene.tiles[TILE] = candidate
    for landmark in scene.landmarks:
        osm_id = landmark.get('osm_id')
        if osm_id not in OWNERS:
            continue
        old_height = landmark.pop('height_m', None)
        old_levels = landmark.pop('levels', None)
        if old_height is not None:
            landmark['legacy_default_height_m'] = old_height
        if old_levels is not None:
            landmark['retained_osm_levels'] = old_levels
        landmark['front_bands'] = 4 if osm_id == bruyeres.osm_id else 5
        landmark['height_status'] = 'Actual-photo front bands and compatible IGN component; exact thresholds and projections remain estimated. Original OSM/default values are retained as source metadata, not a complete rendered-floor survey.'
        landmark['structure'] = ('Separate red upper core, rounded balustraded balconies, side balconies and lower planted/retaining estate'
                                 if osm_id == bruyeres.osm_id else
                                 'Light cream facade, individual curved iron balconies/corbels, two upper arches and small estimated blue roof pavilion')
    scene.landmarks.append({
        'name': 'Source-registered Les Bruyères and Villa Montjoie',
        'bruyeres_osm_id': bruyeres.osm_id, 'montjoie_osm_id': montjoie.osm_id,
        'upper_core_area_m2': house.core_area_m2, 'lower_estate_area_m2': garden.area_m2,
        'preserved_old_city_rows': kept,
        'dimensions_status': 'Literal WGS84 owners and IGN roof components; actual dated exterior photographs establish distinct facade rhythms. Les Bruyères four front bands and nominal 11.3 m absolute core base (±1.5 m) are bounded reconstructions. Montjoie lowest openings clear actual packed frontage ground. Exact garage/forecourt, rear details and a new enclosed roof belvedere remain held. Existing field, roads, terrain cutouts, Street rows and unrelated City rows are unchanged.',
    })
    scene.vegetation.append({
        'name': 'Photographed Les Bruyères lower planted estate',
        'osm_id': bruyeres.osm_id, 'palms': len(garden.palms_xy_m),
        'placement_status': 'CCA actual exterior and dated 2025 own-work photograph support dense lower planting and palms. Original accepted leaf-cluster/palm recipes are reused; exact individual positions and heights are estimated. No existing outside vegetation is removed or reseeded.',
    })
    return ForegroundChange((TILE,), sum(expected[TILE].values()),
                            len(new.tiles[TILE].triangles) // 100, kept, len(boundary),
                            house, villa, garden)
