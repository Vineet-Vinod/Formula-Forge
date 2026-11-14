"""Costa material classification must preserve the rendered hillside geometry."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from venues.monaco_dataclasses import CostaGroundFace, CostaLandCover
from venues.monaco_landcover import (
    cell_indices,
    classified_masks,
    costa_landcover,
    interpolate,
    original_faces,
    touched_cells,
)


@pytest.fixture(scope='module')
def hillside() -> tuple[CircuitScene, CostaLandCover]:
    scene = CircuitScene('monaco')
    scene.road_surfaces('Runoff')
    scene.tiles.clear()
    scene.terrain_cutouts.extend(Polygon(b.ring) for b in scene.buildings)
    config = TypeAdapter(CostaLandCover).validate_json(
        (scene.sources / 'architecture/costa-landcover.json').read_bytes()
    )
    return scene, config


def test_costa_classifies_separate_natural_regions_without_covering_property_or_access(
    hillside: tuple[CircuitScene, CostaLandCover],
) -> None:
    scene, config = hillside
    masks = classified_masks(scene, config)
    cover = unary_union(list(masks.values()))
    assert 300 < masks['Grass'].area < 600
    assert 50 < masks['Limestone'].area < 200
    assert masks['Grass'].intersection(masks['Limestone']).area < 1e-9
    assert masks['Grass'].covers(ShapePoint(*scene.geo(43.73748525089175, 7.421373219526269)))
    assert cover.covers(ShapePoint(*scene.geo(43.73756243225085, 7.42124465995261)))
    annex = Polygon([scene.geo(lat, lon) for lon, lat in config.annex_outer])
    assert cover.intersection(annex.buffer(2.5)).area < 1e-9
    assert cover.intersection(scene.corridor_mask).area < 1e-9
    assert cover.intersection(unary_union(scene.terrain_cutouts)).area < 1e-9
    for tags in [{'highway': 'pedestrian'}, {'natural': 'wood'}]:
        for ring in scene.area_polygons(tags):
            assert cover.intersection(Polygon(ring)).area < 1e-9


def test_costa_clipping_preserves_every_original_plane_normal_and_outer_vertex(
    hillside: tuple[CircuitScene, CostaLandCover], monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene, config = hillside
    masks = classified_masks(scene, config)
    cover = unary_union(list(masks.values()))
    cells = touched_cells(scene, cover)
    faces = original_faces(scene, cells)
    assert cells and faces
    before_road, before_grid = list(scene.road), scene.grid
    before_cutouts = list(scene.terrain_cutouts)
    before_cells = set(scene.emitted_terrain_cells)
    emitted: list[CostaGroundFace] = []

    def capture(
        kind: str, material: str, a: Point, b: Point, c: Point,
        uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
        normals: tuple[Point, ...] | None = None,
    ) -> None:
        if kind != 'Tile_CostaLandcover':
            return
        assert normals is not None
        face = CostaGroundFace((a, b, c), (normals[0], normals[1], normals[2]))
        shape = Polygon([p[:2] for p in face.points])
        if material == 'Runoff':
            assert shape.intersection(cover).area < 1e-8
        else:
            assert shape.difference(masks[material]).area < 1e-8
        for p, texcoord in zip(face.points, uv, strict=True):
            assert texcoord == pytest.approx((p[0] / 8, p[1] / 8), abs=1e-10)
        emitted.append(face)

    monkeypatch.setattr(scene, 'triangle', capture)
    try:
        costa_landcover(scene)
        assert scene.terrain_cutouts == before_cutouts
        assert scene.emitted_terrain_cells - before_cells == cell_indices(scene, cells)
    finally:
        scene.terrain_cutouts[:] = before_cutouts
        scene.emitted_terrain_cells.clear()
        scene.emitted_terrain_cells.update(before_cells)
    shapes = [Polygon([p[:2] for p in face.points]) for face in emitted]
    index = STRtree(shapes)
    for face in faces:
        footprint = Polygon([p[:2] for p in face.points])
        parts = [emitted[int(i)] for i in index.query(footprint, predicate='intersects')
                 if footprint.intersection(shapes[int(i)]).area > 1e-9]
        triangles = [Polygon([p[:2] for p in part.points]) for part in parts]
        assert sum(p.area for p in triangles) == pytest.approx(footprint.area, abs=1e-8)
        assert unary_union(triangles).symmetric_difference(footprint).area < 1e-8
        vertices = {tuple(round(v, 8) for v in p) for part in parts for p in part.points}
        for original, original_normal in zip(face.points, face.normals, strict=True):
            assert tuple(round(v, 8) for v in original) in vertices
            original_height, normal = interpolate(face, original[0], original[1])
            assert original_height == pytest.approx(original[2], abs=1e-10)
            assert normal == pytest.approx(original_normal, abs=1e-10)
        for part in parts:
            for p, normal in zip(part.points, part.normals, strict=True):
                expected_height, expected_normal = interpolate(face, p[0], p[1])
                assert p[2] == pytest.approx(expected_height, abs=1e-10)
                assert normal == pytest.approx(expected_normal, abs=1e-10)
            center = tuple(sum(p[axis] for p in part.points) / 3 for axis in range(3))
            height, normal = interpolate(face, center[0], center[1])
            assert center[2] == pytest.approx(height, abs=1e-10)
            assert tuple(sum(n[axis] for n in part.normals) / 3 for axis in range(3)) == pytest.approx(normal, abs=1e-10)
    assert scene.road == before_road and scene.grid == before_grid


@pytest.mark.parametrize('layer', ['verge', 'ground'])
def test_costa_refuses_cells_that_would_remove_a_deferred_surface(
    hillside: tuple[CircuitScene, CostaLandCover], layer: str,
) -> None:
    scene, config = hillside
    cover = unary_union(list(classified_masks(scene, config).values()))
    sample = cover.representative_point()
    patch = box(sample.x - .1, sample.y - .1, sample.x + .1, sample.y + .1)
    old_cutouts = list(scene.terrain_cutouts)
    old_cells = set(scene.emitted_terrain_cells)
    if layer == 'verge':
        scene.verge_patches.append((patch, 'Concrete', None))
    else:
        scene.ground_patches.append((patch, 12., 'Concrete'))
    try:
        with pytest.raises(ValueError, match='deferred verge or ground patch'):
            touched_cells(scene, cover)
        assert scene.terrain_cutouts == old_cutouts
        assert scene.emitted_terrain_cells == old_cells
    finally:
        if layer == 'verge':
            scene.verge_patches.pop()
        else:
            scene.ground_patches.pop()
