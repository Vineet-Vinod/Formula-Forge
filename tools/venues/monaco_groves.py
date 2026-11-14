"""Add source-observed canopy clumps without repainting or reshaping their substrate."""

from __future__ import annotations

import struct

from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.ops import unary_union

from venues.monaco_groves_dataclasses import WestBankGroves
from venues.monaco_west_dataclasses import BelvedereArchitecture

LANDMARK = 'Source-observed west-bank canopy clumps'
GroundTriangle = tuple[Point, Point, Point]


def packed_point(point: Point) -> Point:
    y, x, z = struct.unpack('<3f', struct.pack('<3f', -point[1] * 100, -point[0] * 100, point[2] * 100))
    return -x / 100, -y / 100, z / 100


def ground_support(scene: CircuitScene, source: WestBankGroves) -> tuple[GroundTriangle, ...]:
    wanted = {(row.tile, row.material, bytes.fromhex(row.attributes_hex)) for row in source.supports}
    if len(wanted) != len(source.supports):
        raise ValueError('Canopy ground witnesses must be distinct')
    found = set()
    for name in {row.tile for row in source.supports}:
        tile = scene.tiles.get(name)
        if tile is None:
            raise ValueError('Canopies require the actual post-terrain Street tiles')
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            key = name, material, bytes(tile.triangles[offset + 4:offset + 100])
            if key in wanted:
                found.add(key)
    if found != wanted:
        raise ValueError('The qualified emitted canopy support planes changed')
    faces = []
    for row in source.supports:
        values = struct.unpack('<24f', bytes.fromhex(row.attributes_hex))
        points = tuple((-values[i + 1] / 100, -values[i] / 100, values[i + 2] / 100) for i in (0, 8, 16))
        faces.append((points[0], points[1], points[2]))
    return tuple(faces)


def ground_height(faces: tuple[GroundTriangle, ...], x: float, y: float) -> float:
    heights = []
    for a, b, c in faces:
        if not Polygon((a[:2], b[:2], c[:2])).buffer(1e-5).covers(ShapePoint(x, y)):
            continue
        determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(determinant) < 1e-10:
            raise ValueError('Canopy ground witness has no horizontal support area')
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
        heights.append(u * a[2] + v * b[2] + (1 - u - v) * c[2])
    if not heights:
        raise ValueError('A canopy trunk corner has no qualified ground support')
    return max(heights)


def add_groves(scene: CircuitScene) -> None:
    if scene.slug != 'monaco' or any(row.get('name') == LANDMARK for row in scene.landmarks):
        raise ValueError('West-bank canopies require one Monaco post-terrain invocation')
    source = TypeAdapter(WestBankGroves).validate_json(
        (scene.sources / 'architecture/west-bank-groves.json').read_bytes())
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()).relative_datum_m
    if max(abs(source.origin_lat_lon[0] - scene.provenance.origin.latitude),
           abs(source.origin_lat_lon[1] - scene.provenance.origin.longitude),
           abs(source.uniform_scale - scene.provenance.route.uniform_scale),
           abs(source.relative_datum_m - datum)) > 1e-9:
        raise ValueError('The qualified canopy frame or vertical datum changed')
    faces = ground_support(scene, source)
    belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / 'architecture/west-belvedere.json').read_bytes())
    monument = ShapePoint(belvedere.center_xy_m).buffer(belvedere.radius_m + .3)
    paths = []
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.tags.get('highway') in {'footway', 'path', 'steps', 'pedestrian'} and len(element.geometry) >= 2:
                paths.append(LineString([scene.geo(p.lat, p.lon) for p in element.geometry]).buffer(1))
    blocked = unary_union([monument, Polygon(source.held_roof_ring_xy_m).buffer(.8),
                           scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes, *paths,
                           *[Polygon(b.ring).buffer(.5) for b in scene.buildings]])
    burial = []
    for pose in source.canopies:
        center = ShapePoint(pose.base[:2])
        if blocked.intersects(center.buffer(.2)):
            raise ValueError('A qualified canopy trunk overlaps architecture, paving or a path')
        crown = center.buffer(.41 * pose.height_m)
        if crown.intersects(monument) or crown.intersects(scene.corridor_mask.buffer(.5)):
            raise ValueError('An estimated crown overhangs the belvedere or race protection')
        for dx in (-.125, .125):
            for dy in (-.125, .125):
                x, y, z = packed_point((pose.base[0] + dx, pose.base[1] + dy, pose.base[2]))
                burial.append(ground_height(faces, x, y) - z)
        low, high = pose.crown_diameter_range_m
        if not 0 < low <= .82 * pose.height_m <= high:
            raise ValueError('A canopy exceeds the source-estimated crown-size range')
    if not burial or min(burial) < .08:
        raise ValueError('A packed canopy trunk foot floats above its actual ground')
    for pose in source.canopies:
        scene.broadleaf(pose.base, pose.height_m, pose.seed)
    scene.landmarks.append({'name': LANDMARK, 'canopy_clumps': len(source.canopies),
                            'minimum_packed_trunk_embed_m': min(burial),
                            'source': 'architecture/west-bank-groves.json',
                            'dimensions_status': 'Original canopy estimates from the government 2019 orthophoto and 2012/2014 oblique views, not individual tree identities. Heights/crowns and inferred stems retain broad uncertainty. Two uncertain belvedere-overhang crowns and the unresolved roadside species are omitted. Existing ground, building/roof layers, road, contact and native field are unchanged.'})
