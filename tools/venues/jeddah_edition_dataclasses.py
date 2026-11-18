"""Source controls and local placement for the Jeddah EDITION exterior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat
from shapely.geometry import Polygon

Positive = Annotated[FiniteFloat, Field(gt=0)]
Fraction = Annotated[FiniteFloat, Field(ge=0, le=1)]


@dataclass(frozen=True)
class EditionTier:
    floor_m: FiniteFloat
    ceiling_m: Positive
    front_recess_m: Positive
    end_inset_m: Positive


@dataclass(frozen=True)
class EditionDetail:
    tiers: tuple[EditionTier, ...]
    canopy_top_m: Positive
    canopy_thickness_m: Positive
    slab_thickness_m: Positive
    facade_bay_m: Positive
    opaque_pier_m: Positive
    glazing_recess_m: Positive
    room_back_depth_m: Positive
    window_sill_m: Positive
    window_head_m: Positive
    fascia_recess_m: Positive
    fascia_lip_m: Positive
    balustrade_height_m: Positive
    canopy_span_fraction: tuple[Fraction, Fraction]
    upper_room_span_fraction: tuple[Fraction, Fraction]
    fin_span_fraction: tuple[Fraction, Fraction]
    fin_peak_m: Positive
    fin_thickness_m: Positive
    brace_bottom_m: Positive
    brace_top_m: Positive
    source_note: str


@dataclass(frozen=True)
class EditionFrame:
    center: tuple[float, float]
    axis: tuple[float, float]
    normal: tuple[float, float]
    base_z: float
    facing: int
    footprint: Polygon
