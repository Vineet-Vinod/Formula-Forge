"""The separate planted slope and exposed rock beside the Costa villas."""

from __future__ import annotations

import math
import random

from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_dataclasses import CostaArchitecture, CostaGroundFace, CostaLandCover


def classified_masks(scene: CircuitScene, config: CostaLandCover) -> dict[str, BaseGeometry]:
    if abs(scene.provenance.route.uniform_scale - config.uniform_scale) > 1e-9:
        raise ValueError('Costa land cover requires its retained geographic registration')
    paths: list[BaseGeometry] = []
    for dataset in scene.osm:
        for element in dataset.elements:
            if element.tags.get('highway') not in {'footway', 'pedestrian', 'path', 'steps'} or len(element.geometry) < 2:
                continue
            points = [scene.geo(p.lat, p.lon) for p in element.geometry]
            if element.tags.get('area') == 'yes':
                paths.append(Polygon(points))
            else:
                try:
                    width = float(element.tags.get('width', '2').removesuffix(' m'))
                except ValueError:
                    width = 2
                paths.append(LineString(points).buffer(max(.5, min(8, width)) / 2 + .25))
    annex = Polygon([scene.geo(lat, lon) for lon, lat in config.annex_outer])
    properties = TypeAdapter(CostaArchitecture).validate_json(
        (scene.sources / 'architecture/costa-properties.json').read_bytes()
    )
    roofs = [Polygon([scene.geo(lat, lon) for lon, lat in record.outer]).buffer(.4)
             for record in properties.components]
    blocked = unary_union([
        scene.corridor_mask.buffer(1), *scene.extra_corridors, *scene.water_shapes,
        *scene.terrain_cutouts, *paths, *roofs, annex.buffer(2.5),
        *[Polygon(b.ring).buffer(.4) for b in scene.buildings],
    ])
    regions = {r.cover: Polygon([scene.geo(lat, lon) for lon, lat in r.outer]).difference(blocked)
               for r in config.regions}
    planted = regions['planted']
    rocky = regions['rocky'].difference(planted)
    outcrops = unary_union([
        Polygon([scene.geo(lat, lon) for lon, lat in ring]).buffer(.55)
        for ring in config.rock_outcrops
    ]).intersection(rocky)
    return {'Grass': unary_union([planted, rocky.difference(outcrops)]), 'Limestone': outcrops}


def touched_cells(scene: CircuitScene, mask: BaseGeometry) -> list[Polygon]:
    grid = scene.grid
    xmin, ymin, xmax, ymax = mask.bounds
    cells = []
    for row in range(max(0, math.floor((ymin - grid.y) / grid.step)),
                     min(grid.rows - 1, math.ceil((ymax - grid.y) / grid.step))):
        for column in range(max(0, math.floor((xmin - grid.x) / grid.step)),
                            min(grid.columns - 1, math.ceil((xmax - grid.x) / grid.step))):
            x, y = grid.x + column * grid.step, grid.y + row * grid.step
            cell = box(x, y, x + grid.step, y + grid.step)
            if cell.intersection(mask).area > 1e-8:
                cells.append(cell)
    later_surfaces = unary_union([
        *[shape for shape, _material, _sample in scene.verge_patches],
        *[shape for shape, _height, _material in scene.ground_patches],
    ])
    if unary_union(cells).intersection(later_surfaces).area > 1e-8:
        raise ValueError('Costa cells overlap a deferred verge or ground patch; preserve that surface first')
    if cell_indices(scene, cells) & scene.emitted_terrain_cells:
        raise ValueError('Costa terrain cells have already been emitted')
    return cells


def cell_indices(scene: CircuitScene, cells: list[Polygon]) -> set[tuple[int, int]]:
    return {(round((cell.bounds[1] - scene.grid.y) / scene.grid.step),
             round((cell.bounds[0] - scene.grid.x) / scene.grid.step)) for cell in cells}


def original_faces(scene: CircuitScene, cells: list[Polygon]) -> list[CostaGroundFace]:
    corridor = unary_union([scene.corridor_mask, *scene.extra_corridors])
    voids = unary_union([
        corridor, *scene.extra_corridors, *scene.water_shapes, *scene.terrain_cutouts,
    ])
    voids = unary_union([voids, *[shape for shape, _height, _material in scene.ground_patches]])
    faces = []
    for cell in cells:
        for triangle in constrained_delaunay_triangles(cell.difference(voids)).geoms:
            points = [(x, y, scene.ground(x, y)) for x, y in list(triangle.exterior.coords)[:3]]
            if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                points.reverse()
            normals = [scene._ground_normal(x, y) for x, y, _z in points]
            faces.append(CostaGroundFace((points[0], points[1], points[2]),
                                         (normals[0], normals[1], normals[2])))
    return faces


def interpolate(face: CostaGroundFace, x: float, y: float) -> tuple[float, tuple[float, float, float]]:
    a, b, c = face.points
    determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
    second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
    weights = first, second, 1 - first - second
    height = sum(w * p[2] for w, p in zip(weights, face.points, strict=True))
    normals = [sum(w * n[axis] for w, n in zip(weights, face.normals, strict=True)) for axis in range(3)]
    return height, (normals[0], normals[1], normals[2])


def split_face(face: CostaGroundFace, mask: BaseGeometry) -> list[CostaGroundFace]:
    shape = Polygon([p[:2] for p in face.points]).intersection(mask)
    parts = []
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points, normals = [], []
        coordinates = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            coordinates.reverse()
        for x, y in coordinates:
            height, normal = interpolate(face, x, y)
            points.append((x, y, height))
            normals.append(normal)
        parts.append(CostaGroundFace((points[0], points[1], points[2]),
                                    (normals[0], normals[1], normals[2])))
    return parts


def costa_landcover(scene: CircuitScene) -> None:
    if scene.slug != 'monaco' or scene.catalogue.deck_separation:
        raise ValueError('The Costa material repair requires the Monaco ground-layer recipe')
    config = TypeAdapter(CostaLandCover).validate_json(
        (scene.sources / 'architecture/costa-landcover.json').read_bytes()
    )
    masks = classified_masks(scene, config)
    cover = unary_union(list(masks.values()))
    if cover.is_empty or any(mask.is_empty for mask in masks.values()):
        raise ValueError('Costa requires separate planted and exposed-rock surfaces')
    cells = touched_cells(scene, cover)
    faces = original_faces(scene, cells)
    original = unary_union([Polygon([p[:2] for p in face.points]) for face in faces])
    if cover.difference(original).area > 1e-7:
        raise ValueError('Costa classifications must remain inside existing emitted terrain')
    for face in faces:
        footprint = Polygon([p[:2] for p in face.points])
        materials = [('Runoff', footprint.difference(cover)),
                     *[(material, footprint.intersection(mask)) for material, mask in masks.items()]]
        for material, mask in materials:
            for part in split_face(face, mask):
                a, b, c = part.points
                scene.triangle('Tile_CostaLandcover', material, a, b, c,
                               tuple((p[0] / 8, p[1] / 8) for p in part.points), part.normals)
    scene.emitted_terrain_cells.update(cell_indices(scene, cells))
    shrubs = vegetation(scene, masks['Grass'], faces)
    scene.landmarks.append({
        'name': 'Costa planted slope and rocky ravine margin',
        'planted_area_m2': masks['Grass'].area, 'exposed_rock_area_m2': masks['Limestone'].area,
        'reconstructed_shrubs': shrubs, 'replaced_terrain_cells': len(cells),
        'source': 'architecture/costa-landcover.json and costa-landcover-provenance.json',
        'dimensions_status': 'Separate bounded original land-cover reconstruction from primary2019 orthophoto '
                             'and2019/2024 ravine photographs. No new terrain heights. Existing emitted cell '
                             'triangle planes, outer vertices and interpolated normals retained. Paths, plaza, '
                             'road/property bodies, existing venue surfaces and unqualified annex4420 excluded. '
                             'Rock/ivy boundaries and individual shrubs are estimates, not surveyed objects.',
    })


def vegetation(scene: CircuitScene, grass: BaseGeometry, faces: list[CostaGroundFace]) -> int:
    rng = random.Random(74384420)
    area = grass.buffer(-.9)
    xmin, ymin, xmax, ymax = grass.bounds
    count = 0
    y = ymin + 1.2
    while y < ymax:
        x = xmin + 1.2
        while x < xmax:
            px, py = x + rng.uniform(-.65, .65), y + rng.uniform(-.65, .65)
            point = ShapePoint(px, py)
            if area.covers(point):
                face = next((f for f in faces if Polygon([p[:2] for p in f.points]).covers(point)), None)
                if face is not None:
                    height, _normal = interpolate(face, px, py)
                    scene.broadleaf((px, py, height), rng.uniform(1.8, 3.1), 4420 + count)
                    count += 1
            x += 3.8
        y += 3.8
    return count
