from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import FiniteFloat


@dataclass(frozen=True)
class HillsideBuilding:
    source_id: str
    component: int
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
    roof_outline_m: list[FiniteFloat]
    holes_roof_m: list[list[FiniteFloat]]
    ground_m: FiniteFloat
    eaves_m: FiniteFloat
    roof_m: FiniteFloat
    floors: int | None
    roof_material: Literal['Terracotta', 'Roof', 'Concrete', 'Steel']
    height_precision_m: FiniteFloat | None


@dataclass(frozen=True)
class HillsideVegetation:
    source_id: str
    nature: str
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]


@dataclass(frozen=True)
class PropertyRoofStep:
    start_vertex: int
    end_vertex: int
    lower_endpoint_m: tuple[FiniteFloat, FiniteFloat]
    upper_endpoint_m: tuple[FiniteFloat, FiniteFloat]
    seam: list[tuple[FiniteFloat, FiniteFloat]]
    source_note: str


@dataclass(frozen=True)
class PropertyEnvelope:
    osm_id: int
    name: str
    style: Literal['ruscino', 'ermanno', 'rascasse', 'annex', 'roof_component']
    source_id: str
    component: int
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
    roof_outline_m: list[FiniteFloat]
    holes_roof_m: list[list[FiniteFloat]]
    ground_m: FiniteFloat
    roof_peak_m: FiniteFloat
    height_precision_m: FiniteFloat
    roof_step: PropertyRoofStep | None = None
    covered_osm_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class GardenFrontage:
    osm_id: int
    ring: list[tuple[FiniteFloat, FiniteFloat]]
    native_range_m: tuple[FiniteFloat, FiniteFloat]
    wall_height_m: FiniteFloat
    wall_inset_m: FiniteFloat
    source_note: str


@dataclass(frozen=True)
class RascasseFrontage:
    ground_body_osm_id: int
    roof_source_id: str
    roof_front_vertices: tuple[int, int]
    region_wgs84: list[tuple[FiniteFloat, FiniteFloat]]
    ground_grid_file: str
    uniform_scale: FiniteFloat
    podium_height_above_source_minimum_m: FiniteFloat
    body_search_width_m: FiniteFloat = 2.5
    street_threshold_sample_distance_m: FiniteFloat = 2.5
    forecourt_width_m: FiniteFloat = 6.0
