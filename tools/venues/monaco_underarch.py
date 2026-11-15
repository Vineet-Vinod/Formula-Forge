"""Restore low woodland under the bridge without treating its deck as terrain."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
from copy import deepcopy
from typing import cast

import numpy as np
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_surfaces import append, face, fragment_rows, interpolate
from venues.monaco_surfaces_dataclasses import NativeVertex
from venues.monaco_underarch_dataclasses import (
    UnderarchChange,
    UnderarchFace,
    UnderarchSource,
)
from venues.monaco_underarch_plants import face_points, plant_underarch


def source_window(scene: CircuitScene, source: UnderarchSource) -> BaseGeometry:
    frame = scene.provenance
    if scene.slug != 'monaco' or max(
        abs(frame.origin.latitude - source.origin_lat_lon[0]),
        abs(frame.origin.longitude - source.origin_lat_lon[1]),
        abs(frame.route.uniform_scale - source.uniform_scale),
    ) > 1e-10:
        raise ValueError('Underarch source registration differs from Monaco')
    path = scene.sources / 'coastal-district.map.osm.gz'
    if hashlib.sha256(path.read_bytes()).hexdigest() != source.forest_source_sha256:
        raise ValueError('The literal mixed-forest source changed')
    projected = tuple(scene.geo(lat, lon) for lon, lat in source.forest_wgs84_lonlat)
    if len(projected) != len(source.expected_forest_xy_m) or max(
        math.dist(a, b) for a, b in zip(projected, source.expected_forest_xy_m)
    ) > 1e-8:
        raise ValueError('The literal forest no longer matches its qualified plan')
    bridge_path = scene.sources / 'architecture/larvotto-bridge.json'
    if hashlib.sha256(bridge_path.read_bytes()).hexdigest() != source.bridge_source_sha256:
        raise ValueError('The source-qualified bridge plan changed')
    bridge = json.loads(bridge_path.read_text())
    outline = Polygon([scene.geo(lat, lon) for lon, lat in bridge['outline_wgs84']])
    return Polygon(projected).intersection(outline)


def actual_faces(scene: MeshScene, window: BaseGeometry) -> tuple[
    tuple[UnderarchFace, ...], tuple[UnderarchFace, ...]
]:
    floors: list[UnderarchFace] = []
    ceilings: list[UnderarchFace] = []
    xmin, ymin, xmax, ymax = window.bounds
    for name, tile in scene.tiles.items():
        if not name.startswith(('Tile_Street_', 'Building_City_')) or not tile.triangles:
            continue
        if (-tile.minimum[1] / 100 < xmin or -tile.maximum[1] / 100 > xmax
                or -tile.minimum[0] / 100 < ymin or -tile.maximum[0] / 100 > ymax):
            continue
        points = face_points(tile)
        low = points[:, :, :2].min(axis=1)
        high = points[:, :, :2].max(axis=1)
        eligible = ((high[:, 0] >= xmin) & (low[:, 0] <= xmax)
                    & (high[:, 1] >= ymin) & (low[:, 1] <= ymax))
        normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
        for index in np.flatnonzero(eligible):
            offset = int(index) * 100
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            floor = name.startswith('Tile_Street_') and material == 'Runoff' and normals[index, 2] > 1e-8
            ceiling = name.startswith('Building_City_') and material == 'Concrete' and normals[index, 2] < -1e-8
            if not (floor or ceiling):
                continue
            plan = Polygon(points[index, :, :2])
            if plan.intersection(window).area <= 1e-9:
                continue
            a, b, c = points[index]
            item = UnderarchFace(name, int(index), material,
                (tuple(a), tuple(b), tuple(c)), plan,
                bytes(tile.triangles[offset:offset + 100]))
            (floors if floor else ceilings).append(item)
    return tuple(floors), tuple(ceilings)


def excluded(scene: CircuitScene, window: BaseGeometry) -> BaseGeometry:
    roads = []
    for a, b in zip(scene.road, (*scene.road[1:], scene.road[0])):
        if LineString(((a.x, a.y), (b.x, b.y))).distance(window) > 40:
            continue
        edges = []
        for s in (a, b):
            left = s.half_width + scene.kerb_margin(s.station) + s.left_shoulder
            right = s.half_width + scene.kerb_margin(s.station) + s.right_shoulder
            edges.append(((s.x + s.ty * left, s.y - s.tx * left),
                          (s.x - s.ty * right, s.y + s.tx * right)))
        roads.append(Polygon((edges[0][0], edges[1][0], edges[1][1], edges[0][1])))
    barriers = []
    with (scene.scratch / 'barriers.csv').open() as handle:
        for row in csv.DictReader(handle):
            line = LineString(((float(row['ax']), float(row['ay'])),
                               (float(row['bx']), float(row['by']))))
            if line.distance(window) < 20:
                barriers.append(line.buffer(float(row['radius']) + 0.25))
    paths = []
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.tags.get('highway') in ('footway', 'path', 'steps', 'pedestrian') and len(element.geometry) > 1:
                paths.append(LineString([scene.geo(p.lat, p.lon) for p in element.geometry]).buffer(1.25))
    bodies = [Polygon(b.ring).buffer(0.5) for b in scene.buildings if b.use != 'bridge']
    return unary_union([unary_union(roads).buffer(0.25), *barriers, *paths, *bodies])


def clip_ground(scene: MeshScene, mask: BaseGeometry) -> tuple[dict[str, MeshTile], int, int, int, float, float]:
    candidates: dict[str, MeshTile] = {}
    selected = kept = fragments = 0
    area = maximum_reprojection = 0.0
    for name, old in scene.tiles.items():
        if not name.startswith('Tile_Street_'):
            continue
        tile = deepcopy(old)
        data = bytearray()
        local = 0
        for offset in range(0, len(old.triangles), 100):
            raw = bytes(old.triangles[offset:offset + 100])
            material = old.materials[struct.unpack_from('<I', raw)[0]]
            if material != 'Runoff':
                data.extend(raw)
                kept += 1
                continue
            parent = face(old, offset)
            inside = parent.plan.intersection(mask)
            if parent.plan.area <= 1e-10 or inside.area <= 1e-9 or min(v[5] for v in parent.vertices) < 0.05:
                data.extend(raw)
                kept += 1
                continue
            selected += 1
            local += 1
            area += inside.area
            for is_inside, region in ((False, parent.plan.difference(mask)), (True, inside)):
                material = 'MonacoIvyGround' if is_inside else 'Runoff'
                for vertices in fragment_rows(parent, region, material):
                    projected = []
                    for vertex in vertices:
                        encoded = struct.unpack('<8f', struct.pack('<8f', *vertex))
                        corrected = interpolate(parent, -encoded[1] / 100, -encoded[0] / 100)
                        if is_inside:
                            corrected = (*corrected[:6], -encoded[1] / 800, -encoded[0] / 800)
                        packed = struct.unpack('<8f', struct.pack('<8f', *corrected))
                        if packed[:2] != encoded[:2]:
                            raise ValueError('Underarch parent projection moved encoded XY')
                        maximum_reprojection = max(maximum_reprojection, abs(packed[2] - encoded[2]) / 100)
                        projected.append(cast(NativeVertex, corrected))
                    values = np.asarray(projected, dtype=np.float32).astype(float)
                    points = values[:, [1, 0, 2]] * np.array((-1, -1, 1)) / 100
                    normal = np.cross(points[1] - points[0], points[2] - points[0])
                    length = float(np.linalg.norm(normal))
                    stored = values[:, 3:6][:, [1, 0, 2]] * np.array((-1, -1, 1))
                    if length < 1e-10 or normal[2] <= 0 or float((stored @ (normal / length)).min()) < 0.9:
                        raise ValueError('An underarch clipped face needs precision classification')
                    append(data, tile, material, tuple(projected))
                    fragments += 1
        if local:
            tile.triangles = data
            candidates[name] = tile
    return candidates, selected, kept, fragments, area, maximum_reprojection


def apply(scene: MeshScene, mask: BaseGeometry, floors: tuple[UnderarchFace, ...],
          ceilings: tuple[UnderarchFace, ...], source: UnderarchSource) -> UnderarchChange:
    candidate, selected, kept, fragments, area, reprojection = clip_ground(scene, mask)
    if not selected or not ceilings:
        raise ValueError('Underarch needs actual lower Ground and actual overhead bridge soffits')
    plants = MeshScene()
    audit = plant_underarch(plants, mask, floors, ceilings, source.planting)
    # All source, packed-floor and full wind-envelope checks precede scene mutation.
    for name, added in plants.tiles.items():
        tile = deepcopy(scene.tiles[name]) if name in scene.tiles else MeshTile()
        for offset in range(0, len(added.triangles), 100):
            material = added.materials[struct.unpack_from('<I', added.triangles, offset)[0]]
            if material not in tile.materials:
                tile.materials.append(material)
            tile.triangles.extend(struct.pack('<I', tile.materials.index(material)))
            tile.triangles.extend(added.triangles[offset + 4:offset + 100])
        for axis in range(3):
            tile.minimum[axis] = min(tile.minimum[axis], added.minimum[axis])
            tile.maximum[axis] = max(tile.maximum[axis], added.maximum[axis])
        candidate[name] = tile
    scene.tiles.update(candidate)
    return UnderarchChange(tuple(name for name in candidate if name.startswith('Tile_Street_')),
        selected, kept, area, fragments, reprojection, audit)


def finish_terrain(scene: CircuitScene) -> UnderarchChange:
    source = TypeAdapter(UnderarchSource).validate_json(
        (scene.sources / 'architecture/underarch/reconstruction.json').read_bytes())
    window = source_window(scene, source)
    floors, ceilings = actual_faces(scene, window)
    mask = window.intersection(unary_union([f.plan for f in floors])).difference(excluded(scene, window))
    if not mask.is_valid or abs(mask.area - source.expected_mask_area_m2) > 1e-6 or mask.symmetric_difference(from_wkt(source.expected_mask_wkt)).area > 1e-6:
        raise ValueError('The finite source-qualified underarch domain changed')
    result = apply(scene, mask, floors, ceilings, source)
    scene.landmarks.append({'name': 'Larvotto bridge lower woodland', 'source':
        'Literal mixed-forest 941749869 below actual bridge soffits; local lower Runoff only; estimated low planting, full wind clearance checked'})
    return result
