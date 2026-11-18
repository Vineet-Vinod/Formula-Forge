"""Estimated construction geometry qualified against the supplied Jeddah video."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class ConstructionRecipe:
    osm_id: int
    height_m: Positive
    height_uncertainty_m: Positive
    levels: Annotated[int, Field(ge=10, le=100)]
    slab_depth_m: Annotated[FiniteFloat, Field(ge=.3, le=.8)]
    column_width_m: Annotated[FiniteFloat, Field(ge=.6, le=1.4)]
    plate_radius_fraction: Annotated[FiniteFloat, Field(ge=.4, le=.7)]
    core_length_m: Positive
    core_width_m: Positive
    core_rib_depth_m: Annotated[FiniteFloat, Field(gt=0, le=.6)]
    core_rib_width_m: Positive
    formwork_levels: Annotated[int, Field(ge=1, le=5)]
    side_crane_height_m: Positive
    side_crane_offset_along_m: FiniteFloat
    side_crane_offset_across_m: FiniteFloat
    side_crane_jib_m: Positive
    side_crane_counter_jib_m: Positive
    side_crane_boom_angle_deg: Annotated[FiniteFloat, Field(ge=45, le=80)]
    source_note: str


@dataclass(frozen=True)
class ConstructionProof:
    osm_id: int
    height_m: float
    height_uncertainty_m: float
    floor_count: int
    base_z_m: float
    minimum_floor_area_m2: float
    maximum_floor_area_m2: float
    maximum_plate_outside_footprint_m2: float
    core_outside_footprint_m2: float
    side_crane_head_relative_m: float
    side_crane_tip_relative_m: float
    source_note: str
