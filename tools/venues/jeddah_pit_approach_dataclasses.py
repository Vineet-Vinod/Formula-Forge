"""Source-reconstructed Qatar approach walls around the unchanged Jeddah pit axis."""

from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from circuit_portals_dataclasses import Barrier
from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class ApproachChain:
    side: Literal[-1, 1]
    start_m: FiniteFloat
    end_m: FiniteFloat
    start_xy_m: tuple[FiniteFloat, FiniteFloat] | None = None
    end_xy_m: tuple[FiniteFloat, FiniteFloat] | None = None
    start_transition_m: FiniteFloat = 16
    end_transition_m: FiniteFloat = 12


@dataclass(frozen=True)
class ApproachGantry:
    distance_m: FiniteFloat
    width_m: FiniteFloat
    height_m: FiniteFloat
    clearance_m: FiniteFloat
    post_offset_m: FiniteFloat
    material: str


@dataclass(frozen=True)
class ApproachRecipe:
    source_sections_sha256: str
    source_encoded_pit_lane_sha256: str
    joins: list[Barrier]
    chains: list[ApproachChain]
    axis_offset_m: Annotated[FiniteFloat, Field(gt=2)]
    radius_m: Annotated[FiniteFloat, Field(gt=0)]
    wall_height_m: Annotated[FiniteFloat, Field(gt=0)]
    footing_embed_m: Annotated[FiniteFloat, Field(gt=0)]
    segment_m: Annotated[FiniteFloat, Field(gt=0, le=1)]
    panel_material: str
    panel_height_m: FiniteFloat
    panel_repeat_m: FiniteFloat
    gantry: ApproachGantry


@dataclass(frozen=True)
class ApproachWall:
    side: Literal[-1, 1]
    start_m: float
    end_m: float
    barrier: Barrier
    first_floor: float
    last_floor: float


@dataclass(frozen=True)
class ApproachPoint:
    distance_m: float
    point: Point
