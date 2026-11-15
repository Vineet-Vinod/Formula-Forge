"""Replace the generic chapel and its finite photograph-qualified front apron."""
from __future__ import annotations

import hashlib
import math
import struct
from collections import Counter
from copy import copy
from dataclasses import replace
from itertools import pairwise

from circuit_dataclasses import MeshTile, Point, RetainedTerrainSource, TerrainGrid
from circuit_mesh import MeshScene, cross, norm, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles, from_wkt
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.monaco_chapel_dataclasses import (
    ChapelChange,
    ChapelFrame,
    ChapelSource,
    ChapelStairShell,
    ChapelStep,
    NaveSource,
)
from venues.monaco_chapel_facade import build
from venues.monaco_chapel_roof import emit
from venues.monaco_groves import ground_height
from venues.monaco_ravine import replace_ground
from venues.monaco_ravine_dataclasses import RavineChange
from venues.monaco_upper_ground import supporting_ground

OWNER = 94399398
CITY = 'Building_City_m1_00'
STREET = 'Tile_Street_m1_01'
Row = tuple[str, bytes]


def bindings(scene: CircuitScene, source: ChapelSource) -> tuple[ChapelFrame, NaveSource]:
    provenance = scene.provenance
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()).relative_datum_m
    if scene.slug != 'monaco' or max(
        abs(provenance.origin.latitude - source.origin_lat_lon[0]),
        abs(provenance.origin.longitude - source.origin_lat_lon[1]),
        abs(provenance.route.uniform_scale - source.uniform_scale),
        abs(datum - source.relative_datum_m),
    ) > 1e-10:
        raise ValueError('The chapel source frame or retained datum changed')
    owner = tuple(scene.geo(lat, lon) for lon, lat in source.owner_wgs84_lonlat)
    actual = scene.footprint(OWNER).ring
    if (len(owner) != len(actual) or len(owner) != len(source.expected_owner_xy_m)
            or max(math.dist(a, b) for a, b in zip(owner, actual)) > 1e-8
            or max(math.dist(a, b) for a, b in zip(owner, source.expected_owner_xy_m)) > 1e-8):
        raise ValueError('The chapel literal WGS84 owner changed')
    origin = owner[source.front_origin_vertex]
    end = owner[source.front_end_vertex]
    width = math.dist(origin, end)
    axis = (end[0] - origin[0]) / width, (end[1] - origin[1]) / width
    inward = -axis[1], axis[0]
    frame = ChapelFrame((*origin, 0.), axis, inward, width, source.floor_absolute_m,
                        source.relative_datum_m, source.base_absolute_m)
    uv = tuple(((p[0] - origin[0]) * axis[0] + (p[1] - origin[1]) * axis[1],
                (p[0] - origin[0]) * inward[0] + (p[1] - origin[1]) * inward[1]) for p in owner)
    if (len(uv) != len(source.nave.owner_uv_m)
            or max(math.dist(a, b) for a, b in zip(uv, source.nave.owner_uv_m)) > 1e-8):
        raise ValueError('The literal chapel owner differs from the qualified local roof plan')
    ground = source.site.ground
    if (ground.origin_lat_lon != source.origin_lat_lon
            or ground.uniform_scale != source.uniform_scale
            or ground.relative_datum_m != source.relative_datum_m
            or ground.collar_width_m != 1 or ground.render_step_m != .1):
        raise ValueError('The chapel architecture and finite ground recipe disagree')
    if (source.base_absolute_m != source.nave.foundation_absolute_m
            or source.base_absolute_m >= source.site.apron_absolute_m
            or abs(source.floor_absolute_m - source.site.apron_absolute_m
                   - source.site.stair_rise_m) > 1e-10):
        raise ValueError('The chapel foundation or stairs no longer meet the qualified apron')
    return frame, replace(source.nave, owner_uv_m=uv)


def legacy_rows(scene: CircuitScene) -> Counter[Row]:
    from venues.monaco import frontage

    replay = copy(scene)
    replay.tiles = {}
    replay.modeled_buildings = set()
    replay.landmarks = []
    replay.terrain_cutouts = []
    frontage(replay, scene.footprint(OWNER))
    if set(replay.tiles) != {CITY}:
        raise ValueError('The old generic chapel escaped its one qualified City tile')
    tile = replay.tiles[CITY]
    result: Counter[Row] = Counter()
    for offset in range(0, len(tile.triangles), 100):
        material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
        result[material, bytes(tile.triangles[offset + 4:offset + 100])] += 1
    if sum(result.values()) != 607:
        raise ValueError('The retained generic chapel recipe changed')
    return result


def replacement(old: MeshTile, needed: Counter[Row], new: MeshTile) -> tuple[MeshTile, int]:
    found: Counter[Row] = Counter()
    for offset in range(0, len(old.triangles), 100):
        material = old.materials[struct.unpack_from('<I', old.triangles, offset)[0]]
        found[material, bytes(old.triangles[offset + 4:offset + 100])] += 1
    if any(found[key] < count for key, count in needed.items()):
        raise ValueError('Exact old chapel rows were not found before replacement')
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
        row = struct.unpack_from('<24f', data, offset + 4)
        for vertex in (0, 8, 16):
            for axis in range(3):
                minimum[axis] = min(minimum[axis], row[vertex + axis])
                maximum[axis] = max(maximum[axis], row[vertex + axis])
    return MeshTile(data, minimum, maximum, materials), kept


def front_ground(scene: MeshScene, source: ChapelSource) -> RavineChange:
    site = source.site
    domain = from_wkt(site.ground.expected_domain_wkt)
    if (not isinstance(domain, Polygon) or not domain.is_valid
            or abs(domain.area - 139.21986637639202) > 1e-8
            or {row.tile for row in site.ground.original_ground_rows} != {STREET}):
        raise ValueError('The chapel ground escaped its qualified finite domain')
    level = site.apron_absolute_m - source.relative_datum_m
    grid = TerrainGrid(*site.ground_grid_xy_m, site.ground_grid_step_m,
                       site.ground_grid_columns, site.ground_grid_rows,
                       tuple(level for _ in range(site.ground_grid_columns * site.ground_grid_rows)))
    change = replace_ground(scene, grid, domain, site.ground, reproject_outside=True)
    if (change.tiles != (STREET,) or change.source_faces != 20 or change.unresolved_faces
            or change.minimum_normal_alignment <= 0 or change.minimum_resolved_normal_alignment <= 0):
        raise ValueError('The chapel front failed its strict source and packed-normal gates')
    return change


def stair_shell(architecture: MeshScene, frame: ChapelFrame,
                profiles: tuple[Polygon, ...]) -> ChapelStairShell:
    profile = unary_union(profiles)
    if not isinstance(profile, Polygon) or profile.interiors or not profile.is_valid:
        raise ValueError('The chapel stairs require one closed stepped profile')
    profile = orient(profile, sign=1)
    before = len(architecture.tiles.get(CITY, MeshTile()).triangles)
    floor = frame.floor_absolute_m - frame.datum_m

    def point(u: float, depth: float, z: float) -> Point:
        return frame.point(u, depth, z - floor)

    for triangle in constrained_delaunay_triangles(profile).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coordinates.reverse()
        for u in (0., frame.width_m):
            a, b, c = [point(u, d, z) for d, z in coordinates]
            if u == 0:
                b, c = c, b
            architecture.triangle('Building_ChapelStairs', 'MonacoChapelStone', a, b, c)
    for a, b in pairwise(profile.exterior.coords):
        architecture.quad('Building_ChapelStairs', 'MonacoChapelStone',
                          point(0, *a), point(0, *b),
                          point(frame.width_m, *b), point(frame.width_m, *a))
    tile = architecture.tiles[CITY]
    payload = tile.triangles[before:]
    edges: Counter[tuple[Point, Point]] = Counter()
    directions: Counter[tuple[Point, Point]] = Counter()
    minimum_alignment = 1.
    volume = 0.
    for offset in range(0, len(payload), 100):
        row = struct.unpack_from('<24f', payload, offset + 4)
        vertices = [(-row[i + 1] / 100, -row[i] / 100, row[i + 2] / 100) for i in (0, 8, 16)]
        normal = norm(cross(sub(vertices[1], vertices[0]), sub(vertices[2], vertices[0])))
        minimum_alignment = min(minimum_alignment, *(sum(a * b for a, b in zip(normal,
            (-row[i + 4], -row[i + 3], row[i + 5]))) for i in (0, 8, 16)))
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edge = (a, b) if a < b else (b, a)
            edges[edge] += 1
            directions[edge] += 1 if a < b else -1
        volume += sum(a * b for a, b in zip(vertices[0], cross(vertices[1], vertices[2]))) / 6
    if (any(count != 2 for count in edges.values()) or any(directions.values())
            or minimum_alignment < .999):
        raise ValueError('The packed chapel stair shell is open or faces inward')
    expected_volume = profile.area * frame.width_m
    if abs(volume - expected_volume) > .0005:
        raise ValueError('The packed chapel stair shell changed the original occupied volume')
    duplicate_area = 2 * (sum(p.area for p in profiles) - profile.area)
    return ChapelStairShell(len(profiles) * 12, len(payload) // 100,
                            tuple(profile.exterior.coords)[:-1], expected_volume,
                            duplicate_area, minimum_alignment, len(edges))


def stairs(scene: MeshScene, architecture: MeshScene, frame: ChapelFrame,
           source: ChapelSource) -> tuple[tuple[ChapelStep, ...], ChapelStairShell]:
    site = source.site
    domain = from_wkt(site.ground.expected_domain_wkt)
    supports = supporting_ground(scene, domain)
    checks = []
    profiles = []
    for index in range(site.step_count):
        front = -site.landing_depth_m - (site.step_count - index) * site.stair_tread_m
        rear = 0.
        top = -site.stair_rise_m + (index + 1) * site.stair_rise_m / site.step_count
        probes = [frame.point(u, d, 0) for u in (0, frame.width_m / 4, frame.width_m / 2,
                  frame.width_m * .75, frame.width_m) for d in (front, (front + rear) / 2, rear)]
        ground = [ground_height(supports, p[0], p[1]) for p in probes]
        absolute_top = frame.point(0, 0, top)[2]
        clearance = absolute_top - max(ground)
        if clearance <= site.minimum_step_clearance_m:
            raise ValueError('A chapel stair top is buried in the actual emitted front ground')
        base = min(ground) - site.foot_burial_m
        profiles.append(box(front, base, rear, absolute_top))
        checks.append(ChapelStep(index, clearance, site.foot_burial_m, len(probes)))
    shell = stair_shell(architecture, frame, tuple(profiles))
    return tuple(checks), shell


def finish_terrain(scene: CircuitScene) -> ChapelChange:
    directory = scene.sources / 'architecture/chapel'
    source = TypeAdapter(ChapelSource).validate_json((directory / 'reconstruction.json').read_bytes())
    frame, nave = bindings(scene, source)
    for relative, source_hash in source.primary_source_sha256.items():
        path = directory / relative
        if path.parent != directory or hashlib.sha256(path.read_bytes()).hexdigest() != source_hash:
            raise ValueError('A qualified chapel primary source record changed')
    if Polygon(scene.footprint(OWNER).ring).intersection(scene.corridor_mask.buffer(.2)).area > 1e-8:
        raise ValueError('The chapel owner intersects actual racing protection')
    expected = legacy_rows(scene)
    if CITY not in scene.tiles:
        raise ValueError('The chapel requires its original post-terrain City tile')
    replacement(scene.tiles[CITY], expected, MeshTile())
    staged = MeshScene()
    staged.tiles = dict(scene.tiles)
    ground = front_ground(staged, source)
    architecture = MeshScene()
    build(architecture, frame)
    emit(architecture, frame, nave)
    steps, shell = stairs(staged, architecture, frame, source)
    if set(architecture.tiles) != {CITY}:
        raise ValueError('The chapel architecture escaped its one qualified City tile')
    tile, kept = replacement(scene.tiles[CITY], expected, architecture.tiles[CITY])
    staged.tiles[CITY] = tile
    scene.tiles = staged.tiles
    for landmark in scene.landmarks:
        if landmark.get('osm_id') != OWNER:
            continue
        old_height = landmark.pop('height_m', None)
        old_levels = landmark.pop('levels', None)
        if old_height is not None:
            landmark['legacy_default_height_m'] = old_height
        if old_levels is not None:
            landmark['legacy_default_levels'] = old_levels
        landmark['height_status'] = 'Superseded generic body; source-estimated church silhouette and thresholds are recorded separately.'
        landmark['structure'] = 'Three-part ornamented church front, pitched nave and open bell tower'
    scene.landmarks.append({
        'osm_id': OWNER, 'name': 'Source-registered Chapelle Sainte-Dévote',
        'source': 'architecture/chapel/reconstruction.json',
        'floor_absolute_m': source.floor_absolute_m,
        'floor_uncertainty_m': source.floor_uncertainty_m,
        'preserved_unrelated_city_rows': kept,
        'dimensions_status': 'Literal OSM owner, operator facade and registered 2019/2024 obliques. '
        'Nave ridge, tower crown and stair dimensions remain bounded architectural estimates. '
        'The local 6.97 m absolute photo apron is not a measured DEM. Existing separate rear annex, '
        'outside ground planes, native terrain/contact and racing road are preserved. '
        'Paving classification and cooked visual acceptance remain separate.',
    })
    return ChapelChange(CITY, sum(expected.values()), len(architecture.tiles[CITY].triangles) // 100,
                        kept, ground, steps, shell)
