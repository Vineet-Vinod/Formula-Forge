"""Visible T22 stand/arcade controls, independent of the pit-exit face."""

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class T22Frontage:
    osm_id: int
    origin_xy_m: tuple[FiniteFloat, FiniteFloat]
    outward_xy: tuple[FiniteFloat, FiniteFloat]
    outer_coordinate_m: FiniteFloat
    stand_depth_m: Positive
    bay_pitch_m: Positive
    pier_width_m: Positive
    arcade_depth_m: Positive
    arcade_height_m: Positive
    arch_spring_m: Positive
    seating_rows: Annotated[int, Field(ge=3, le=12)]
    row_depth_m: Positive
    row_rise_m: Positive
    source_note: str


@dataclass(frozen=True)
class ArcadeOpening:
    center: Point
    inward_xy: tuple[float, float]
