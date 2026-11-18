"""Source recipe and bounded overlay result for Jeddah pit personnel access."""
from dataclasses import dataclass
from typing import Annotated

from circuit_portals_dataclasses import Barrier, Portal
from pit_routes_dataclasses import PitSection
from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class WalkwayRecipe:
    start_distance_m: Positive
    end_distance_m: Positive
    segment_m: Annotated[FiniteFloat, Field(gt=0, le=4)]
    platform_height_m: Annotated[FiniteFloat, Field(gt=0, le=.25)]
    lane_edge_gap_m: Positive
    wall_gap_m: Positive
    rail_edge_gap_m: Positive
    rail_radius_m: Annotated[FiniteFloat, Field(gt=0, le=.05)]
    lower_rail_m: Positive
    upper_rail_m: Positive
    post_spacing_m: Annotated[FiniteFloat, Field(gt=0, le=3)]
    end_ramp_m: Positive
    minimum_width_m: Positive
    source_note: str


@dataclass(frozen=True)
class WalkwayStation:
    section: PitSection
    wall_face_m: float
    wall_bottom_m: float
    wall_top_m: float
    outer_edge_m: float
    lift_m: float
    inner_edge_m: float
    rail_center_m: float


@dataclass(frozen=True)
class WalkwayProof:
    start_distance_m: float
    end_distance_m: float
    platform_area_m2: float
    minimum_width_m: float
    maximum_width_m: float
    fastlane_overlap_m2: float
    wall_overlap_m2: float
    minimum_rail_inner_edge_m: float
    reference_wall_count: int
    rail_barrier_count: int
    floor_portal_count: int
    source_note: str


@dataclass(frozen=True)
class WalkwayResult:
    extra_barriers: tuple[Barrier, ...]
    floor_portals: tuple[Portal, ...]
    proof: WalkwayProof
