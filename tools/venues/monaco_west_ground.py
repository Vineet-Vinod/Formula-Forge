"""Exact existing woodland planes support the separately modeled belvedere."""

from __future__ import annotations

import struct

from circuit_mesh import world
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.monaco_dataclasses import ApproachGround, CostaGroundFace
from venues.monaco_west_dataclasses import BelvedereArchitecture, ExistingWoodGround


def existing_wood_ground(scene: CircuitScene, config: BelvedereArchitecture,
                         region: Polygon) -> tuple[Polygon, list[CostaGroundFace]]:
    source = TypeAdapter(ExistingWoodGround).validate_json(
        (scene.sources/config.existing_wood_ground_file).read_bytes()
    )
    found = False
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.id != source.osm_id:
                continue
            ring = tuple((p.lon, p.lat) for p in element.geometry)
            if element.tags.get('natural') != 'wood' or ring != source.outer_wgs84:
                raise ValueError('The registered belvedere woodland source changed')
            found = True
    if not found:
        raise ValueError('The registered belvedere woodland source is missing')
    plan = Polygon([scene.geo(lat, lon) for lon, lat in source.outer_wgs84])
    if sum(shape.equals(plan) for shape in scene.terrain_cutouts) != 1:
        raise ValueError('The belvedere requires exactly its existing natural woodland cutout')
    faces = []
    for name, tile in scene.tiles.items():
        if not name.startswith('Tile_Street_') or 'Grass' not in tile.materials:
            continue
        material = tile.materials.index('Grass')
        for offset in range(0, len(tile.triangles), 100):
            if struct.unpack_from('<I', tile.triangles, offset)[0] != material:
                continue
            points, normals = [], []
            for corner in range(3):
                x, y, z, nx, ny, nz = struct.unpack_from('<6f', tile.triangles, offset+4+corner*32)
                points.append((-y/100, -x/100, z/100))
                normals.append((-ny, -nx, nz))
            shape = Polygon([p[:2] for p in points])
            if shape.area < 1e-10 or not shape.intersects(region):
                continue
            if not plan.buffer(.0001).covers(shape):
                continue
            faces.append(CostaGroundFace((points[0], points[1], points[2]),
                                          (normals[0], normals[1], normals[2])))
    cover = unary_union([Polygon([p[:2] for p in face.points]) for face in faces])
    if plan.intersection(region).difference(cover.buffer(.0001)).area > 1e-8:
        raise ValueError('Existing emitted Grass planes do not cover the registered support ground')
    return plan, faces


def belvedere_ground(raw: list[CostaGroundFace], grass: list[CostaGroundFace]) -> ApproachGround:
    faces = []
    for face in raw:
        points, normals = [], []
        for point, normal in zip(face.points, face.normals, strict=True):
            x, y, z = struct.unpack('<3f', struct.pack('<3f', *world(point)))
            nx, ny, nz = struct.unpack('<3f', struct.pack('<3f', -normal[1], -normal[0], normal[2]))
            points.append((-y/100, -x/100, z/100))
            normals.append((-ny, -nx, nz))
        faces.append(CostaGroundFace((points[0], points[1], points[2]),
                                     (normals[0], normals[1], normals[2])))
    faces.extend(grass)
    plans = tuple(Polygon([p[:2] for p in face.points]) for face in faces)
    return ApproachGround(tuple(faces), plans, STRtree(plans))
