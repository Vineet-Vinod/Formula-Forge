"""Keep photographed planting separate from roofs, paths and existing surface roles."""

import struct

from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from venues.monaco_natural_ground import lower_regions
from venues.monaco_natural_ground_dataclasses import NaturalSites
from venues.monaco_ravine_dataclasses import RavineSource
from venues.monaco_surfaces import face, replace_surfaces
from venues.monaco_surfaces_dataclasses import SurfaceRegion


def test_lower_natural_sites_exclude_actual_buildings_and_ambiguous_eave() -> None:
    scene = CircuitScene("monaco")
    scene.road_surfaces("Runoff")
    source = TypeAdapter(NaturalSites).validate_json(
        (scene.sources / "architecture/lower-natural-sites.json").read_bytes())
    ravine = TypeAdapter(RavineSource).validate_json(
        (scene.sources / "architecture/ravine-source.json").read_bytes())
    cover = unary_union([
        region.plan for region in lower_regions(scene, source, from_wkt(ravine.expected_domain_wkt))
    ])
    assert 1 < cover.area < 80
    assert not cover.intersects(Point(15.820995, 323.78632).buffer(.25))
    assert cover.covers(Point(-10.960111, 348.851092))
    assert not cover.covers(Point(-4.702761, 347.598537))
    assert not cover.intersects(scene.corridor_mask.buffer(2))
    for building in scene.buildings:
        assert cover.intersection(Polygon(building.ring).buffer(1.5)).area < 1e-8


def test_natural_cover_preserves_other_roles_and_original_height_plane() -> None:
    scene = MeshScene()
    scene.triangle("Tile_Street", "Runoff", (0., 0., 2.), (4., 0., 3.), (0., 4., 4.))
    scene.triangle("Tile_Street", "MonacoIvyGround", (0., 0., 5.), (4., 0., 6.), (0., 4., 7.))
    tile = next(iter(scene.tiles.values()))
    original_ivy = bytes(tile.triangles[100:])
    result = replace_surfaces(scene, [SurfaceRegion(
        "qualified planting", Polygon(((0, 0), (2, 0), (0, 2))), "natural"
    )], allowed_materials=frozenset({"Runoff"}))
    assert result.classified_area_m2 == 2
    assert bytes(tile.triangles[-100:]) == original_ivy
    for offset in range(0, len(tile.triangles), 100):
        material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
        if material == "MonacoIvyGround":
            continue
        source = face(tile, offset)
        for vertex, (x, y) in zip(source.vertices, source.xy, strict=True):
            assert abs(vertex[2] / 100 - (2 + x / 4 + y / 2)) < 1e-6
