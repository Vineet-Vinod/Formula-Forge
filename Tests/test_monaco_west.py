"""Source-datum, exact support crossings and local vegetation preservation."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from circuit_dataclasses import Point, TerrainGrid
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.strtree import STRtree
from venues.monaco_approaches import ground_sample
from venues.monaco_belvedere import belvedere, boundary_sections
from venues.monaco_cliff import cliff_preflight, source_height
from venues.monaco_dataclasses import ApproachGround, CasaGardenSetting, CostaGroundFace
from venues.monaco_setting import leaf_banks
from venues.monaco_west_dataclasses import BelvedereArchitecture, CliffPatch

SOURCES = Path('Attribution/Sources/monaco/architecture')


def ground() -> ApproachGround:
    normals = ((0., 0., 1.),)*3
    faces = (CostaGroundFace(((-40., 320., 0.), (0., 320., 0.), (0., 370., 10.)), normals),
             CostaGroundFace(((-40., 320., 0.), (0., 370., 10.), (-40., 370., 0.)), normals))
    plans = tuple(Polygon([p[:2] for p in f.points]) for f in faces)
    return ApproachGround(faces, plans, STRtree(plans))


def test_source_nodes_preserve_the_registered_vertical_datum() -> None:
    grid = TypeAdapter(TerrainGrid).validate_json((SOURCES/'costa-ground-grid.json').read_bytes())
    config = TypeAdapter(CliffPatch).validate_json((SOURCES/'west-cliff.json').read_bytes())
    for x, y, absolute in ((-6., 342., 29.86), (-4., 342., 32.04), (-6., 344., 34.08), (-4., 344., 36.53),
                           (-4., 338., 32.04), (-2., 338., 34.27)):
        assert source_height(grid, x, y)+config.relative_datum_m == pytest.approx(absolute, abs=1e-10)


def test_support_segments_follow_both_original_planes() -> None:
    original = ground()
    sections = boundary_sections(original, (-35., 350.), (-5., 330.))
    assert len(sections) == 2
    for first, last in sections:
        for fraction in (0., .25, .5, .75, 1.):
            point = tuple(a+fraction*(b-a) for a, b in zip(first, last, strict=True))
            z, _ = ground_sample(original, (point[0], point[1]))
            assert point[2] == pytest.approx(z, abs=1e-10)


def test_unsupported_belvedere_is_rejected_before_emission() -> None:
    config = TypeAdapter(BelvedereArchitecture).validate_json((SOURCES/'west-belvedere.json').read_bytes())
    scene = MeshScene()
    with pytest.raises(ValueError, match='intersects unqualified old terrain'):
        belvedere(scene, replace(config, paving_absolute_m=1., cap_absolute_m=2.1), ground())
    assert not scene.tiles


def test_unqualified_ivy_cannot_escape_the_cliff_domain() -> None:
    config = TypeAdapter(CliffPatch).validate_json((SOURCES/'west-cliff.json').read_bytes())
    grid = TypeAdapter(TerrainGrid).validate_json((SOURCES/'costa-ground-grid.json').read_bytes())
    escaped = replace(config, ivy_rings_xy_m=(((-20., 340.), (-18., 340.), (-18., 342.)),))
    with pytest.raises(ValueError, match='ivy masks must remain inside'):
        cliff_preflight(ground(), grid, escaped)


class RecordedPlants(MeshScene):
    def __init__(self) -> None:
        super().__init__()
        self.plants: list[tuple[Point, float, int]] = []

    def broadleaf(self, base: Point, height: float, seed: int) -> None:
        self.plants.append((base, height, seed))
        super().broadleaf(base, height, seed)


def test_excluding_new_structure_preserves_every_outside_canopy_seed_and_row() -> None:
    planted = box(-35., 325., -5., 365.)
    excluded = box(-32., 327., -20., 345.)
    original = ground()
    config = CasaGardenSetting()
    before, after = RecordedPlants(), RecordedPlants()
    leaf_banks(before, planted, list(original.faces), config)
    emitted = leaf_banks(after, planted, list(original.faces), config, excluded)
    expected = [plant for plant in before.plants if not excluded.covers(ShapePoint(plant[0][:2]))]
    assert 0 < len(expected) < len(before.plants)
    assert after.plants == expected
    assert emitted == len(expected)
    expected_scene = MeshScene()
    for base, size, seed in expected:
        expected_scene.broadleaf(base, size, seed)
    def rows(scene: MeshScene) -> Counter[tuple[str, bytes]]:
        return Counter((tile.materials[int.from_bytes(tile.triangles[i:i+4], 'little')],
                        bytes(tile.triangles[i+4:i+100]))
                       for tile in scene.tiles.values() for i in range(0, len(tile.triangles), 100))

    assert rows(after) == rows(expected_scene)
