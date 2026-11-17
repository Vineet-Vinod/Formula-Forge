from dataclasses import replace
from pathlib import Path

import pytest
from circuit_dataclasses import RoadStation
from circuit_escapes import build_overlay, write_source_overlay
from circuit_escapes_dataclasses import (
    EscapeOverlay,
    EscapeRecipe,
    EscapeRoad,
    PaintDomain,
    PaintStrip,
)
from circuit_portals_dataclasses import Barrier
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box


def inputs() -> tuple[EscapeRecipe, list[RoadStation], list[Barrier]]:
    road = [RoadStation(float(s), 0 if s <= 50 else s-50, min(s, 50), .5,
                        0 if s <= 50 else 1, 1 if s <= 50 else 0, 3, 0)
            for s in range(101)]
    recipe = EscapeRecipe("test", 2025, 1, [EscapeRoad(
        "escape", "Estimated straight escape", 30, 50, 8, 0, 5,
        ["https://example.org/primary-map"], ["matched-reference.jpg"],
        "Synthetic invariant fixture; no venue source claim.")], "fixture")
    walls = [Barrier(-6, 53, 6, 53, .5, 1.45, .15)]
    return recipe, road, walls


def test_escape_opens_turn_without_replacing_unrelated_records() -> None:
    recipe, road, walls = inputs()
    original = list(walls)
    overlay = build_overlay(recipe, road, walls, 1, occupied=[])
    assert walls == original
    assert len(overlay.portals) == 1
    portal = overlay.portals[0]
    polygon = Polygon(portal.polygon_xy_m)
    assert polygon.is_valid and polygon.exterior.is_ccw
    assert len(portal.polygon_xy_m) == 4
    assert portal.bottom_m < .5 < portal.top_m
    assert overlay.regions[0].original_barrier_intersections == 1
    assert overlay.regions[0].maximum_paving_grade < 1e-10
    assert overlay.regions[0].maximum_road_join_error_m < .0001
    assert any(min(wall.ay, wall.by) >= 79.99 for wall in overlay.barriers)
    area = sum(Polygon([triangle.a[:2], triangle.b[:2], triangle.c[:2]]).area
               for triangle in overlay.paving)
    assert area == pytest.approx(overlay.regions[0].paved_area_m2, abs=1e-7)
    assert all((triangle.b[0]-triangle.a[0])*(triangle.c[1]-triangle.a[1])
               - (triangle.b[1]-triangle.a[1])*(triangle.c[0]-triangle.a[0]) > 0
               for triangle in overlay.paving)


def test_escape_rejects_wrong_frame_and_occupied_property() -> None:
    recipe, road, walls = inputs()
    with pytest.raises(ValueError, match="source frame"):
        build_overlay(recipe, road, walls, 1.01, occupied=[])
    with pytest.raises(ValueError, match="occupied property"):
        build_overlay(recipe, road, walls, 1, occupied=[box(-2, 65, 2, 70)])
    assert len(walls) == 1
    invalid = replace(recipe, escapes=[recipe.escapes[0], recipe.escapes[0]])
    with pytest.raises(ValueError, match="identifiers"):
        build_overlay(invalid, road, walls, 1, occupied=[])


def test_paint_reclassification_keeps_outer_border_and_kerb_materials() -> None:
    recipe, road, walls = inputs()
    strip = PaintStrip("paint", 60, 90, 1, .15, 5, "RunoffGreen", "Runoff", "Estimated narrow border retained.")
    overlay = build_overlay(replace(recipe, escapes=[], paint_strips=[strip]), road, walls, 1, occupied=[])
    assert not overlay.portals and not overlay.barriers and not overlay.paving
    assert len(overlay.paint_domains) == 15
    assert {domain.source_material for domain in overlay.paint_domains} == {"RunoffGreen"}
    assert {domain.target_material for domain in overlay.paint_domains} == {"Runoff"}
    assert all(domain.bottom_m == pytest.approx(.47) and domain.top_m == pytest.approx(.53)
               for domain in overlay.paint_domains)
    for domain in overlay.paint_domains:
        polygon = Polygon(domain.polygon_xy_m)
        assert polygon.is_valid and polygon.exterior.is_ccw
        assert polygon.bounds[1] == pytest.approx(42)
        assert polygon.bounds[3] == pytest.approx(46.85)


def test_source_serializer_refuses_an_input_as_its_destination(tmp_path: Path) -> None:
    recipe, road, walls = inputs()
    source = tmp_path/"recipe.json"
    original = TypeAdapter(EscapeRecipe).dump_json(recipe)
    source.write_bytes(original)
    overlay = build_overlay(recipe, road, walls, 1, occupied=[])
    with pytest.raises(ValueError, match="protected source input"):
        write_source_overlay(source, overlay, source, [])
    assert source.read_bytes() == original
    destination = tmp_path/"overlay.json"
    write_source_overlay(destination, overlay, source, [])
    assert TypeAdapter(EscapeOverlay).validate_json(destination.read_bytes()) == overlay


def test_registered_paint_domains_preserve_the_closed_road_seam() -> None:
    recipe, road, walls = inputs()
    domain = PaintDomain("seam", ((1.1, 101), (2.2, 101), (2.2, 102), (1.1, 102)),
                         .47, .53, "Yellow", "Runoff", "Exact retained footprint at the closed road seam.")
    qualified = replace(recipe, escapes=[], paint_domains=[domain])
    restored = TypeAdapter(EscapeRecipe).validate_json(TypeAdapter(EscapeRecipe).dump_json(qualified))
    overlay = build_overlay(restored, road, walls, 1, occupied=[])
    assert overlay.paint_domains == (domain,)
    assert not overlay.portals and not overlay.barriers and not overlay.paving
