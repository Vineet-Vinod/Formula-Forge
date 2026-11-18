"""Finite source choice for the filmed open Jeddah pit exit."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class PitExitReconstruction:
    osm_id: int
    mode: str
    start_distance_m: Annotated[FiniteFloat, Field(gt=0)]
    end_distance_m: Annotated[FiniteFloat, Field(gt=0)]
    garage_side_clearance_m: Annotated[FiniteFloat, Field(gt=2)]
    track_side_mask_extent_m: Annotated[FiniteFloat, Field(gt=0)]
    retained_height_m: Annotated[FiniteFloat, Field(gt=0)]
    source_note: str


@dataclass(frozen=True)
class PitExitFrontage:
    floor_levels_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    roof_height_m: Annotated[FiniteFloat, Field(gt=0)]
    slab_thickness_m: Annotated[FiniteFloat, Field(gt=0)]
    room_setback_m: Annotated[FiniteFloat, Field(gt=0)]
    glazing_setback_m: Annotated[FiniteFloat, Field(gt=0)]
    bay_pitch_m: Annotated[FiniteFloat, Field(gt=0)]
    guard_height_m: Annotated[FiniteFloat, Field(gt=0)]
    source_note: str
