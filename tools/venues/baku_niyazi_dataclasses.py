from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class TreeRowSource:
    start_m: FiniteFloat
    end_m: FiniteFloat
    spacing_m: Annotated[FiniteFloat, Field(gt=5)]
    exterior_setback_m: Annotated[FiniteFloat, Field(ge=0.5, le=5)]
    height_m: Annotated[FiniteFloat, Field(ge=8, le=18)]
    crown_width_scale: Annotated[FiniteFloat, Field(ge=0.5, le=1)]
    minimum_over_road_m: Annotated[FiniteFloat, Field(ge=4)]
    source_note: str


@dataclass(frozen=True)
class TreePose:
    station_m: float
    base: Point
    height_m: float
    seed: int
    retained_wall_row: int
    wall_distance_m: float
    ground_tile: str
    ground_triangle: int


@dataclass(frozen=True)
class TreePlantingSource:
    source: TreeRowSource
    poses: Annotated[list[TreePose], Field(min_length=1)]
    protected_source_sha256: dict[str, str]
    ground_supports: Annotated[list[PackedPatchRow], Field(min_length=1)]
    minimum_native_root_embed_m: Annotated[FiniteFloat, Field(ge=0.05)]
