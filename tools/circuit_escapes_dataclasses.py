"""Finite street escape reconstruction controls and source-space output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal

from circuit_dataclasses import Point
from circuit_portals_dataclasses import Barrier, Portal, PortalQuad
from pydantic import AliasChoices, Field, FiniteFloat


@dataclass(frozen=True)
class EscapeRoad:
    id: str
    name: str
    approach_station_m: FiniteFloat
    length_m: Annotated[FiniteFloat, Field(gt=5, le=180)]
    width_m: Annotated[FiniteFloat, Field(ge=4, le=30)]
    lateral_offset_m: Annotated[FiniteFloat, Field(ge=-15, le=15)]
    extent_uncertainty_m: Annotated[FiniteFloat, Field(gt=0)]
    source_urls: Annotated[list[str], Field(min_length=1)]
    reference_frames: Annotated[list[str], Field(min_length=1)]
    source_note: str


@dataclass(frozen=True)
class PaintStrip:
    id: str
    start_m: FiniteFloat
    end_m: FiniteFloat
    side: Literal[-1, 1]
    inner_offset_m: Annotated[FiniteFloat, Field(ge=0)]
    outer_offset_m: Annotated[FiniteFloat, Field(gt=0)]
    source_material: str
    target_material: str
    source_note: str


@dataclass(frozen=True)
class PaintDomain:
    id: str
    polygon_xy_m: PortalQuad
    bottom_m: FiniteFloat
    top_m: FiniteFloat
    source_material: str
    target_material: str
    source_note: str


@dataclass(frozen=True)
class EscapeRecipe:
    circuit: str
    event_year: int
    expected_scene_scale: Annotated[FiniteFloat, Field(gt=0)]
    escapes: list[EscapeRoad]
    source_status: str
    paint_strips: list[PaintStrip] = field(default_factory=list)
    paint_domains: list[PaintDomain] = field(default_factory=list)


@dataclass(frozen=True)
class PavingTriangle:
    a: Point
    b: Point
    c: Point
    material: str = "Runoff"


@dataclass(frozen=True)
class EscapeRegion:
    id: str
    name: str
    polygon_xy_m: tuple[tuple[float, float], ...]
    approach_station_m: float
    original_barrier_intersections: int
    paved_area_m2: float
    maximum_paving_grade: float
    maximum_road_join_error_m: float
    source_note: str


@dataclass(frozen=True)
class EscapeOverlay:
    circuit: str
    portals: tuple[Portal, ...]
    barriers: tuple[Barrier, ...]
    paving: tuple[PavingTriangle, ...]
    regions: Annotated[tuple[EscapeRegion, ...], Field(validation_alias=AliasChoices("regions", "audits"))]
    paint_domains: tuple[PaintDomain, ...] = ()
