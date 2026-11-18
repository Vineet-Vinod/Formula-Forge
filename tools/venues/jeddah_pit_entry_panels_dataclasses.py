"""Finite Qatar facing on actual retained pit-entry wall segments."""

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from circuit_portals_dataclasses import Barrier
from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class EntryPanelWall:
    source_barrier_index: int
    barrier: Barrier
    start_fraction: Annotated[FiniteFloat, Field(ge=0, le=1)]
    end_fraction: Annotated[FiniteFloat, Field(ge=0, le=1)]
    route_start_distance_m: FiniteFloat
    route_end_distance_m: FiniteFloat


@dataclass(frozen=True)
class EntryPanelRecipe:
    source_sections_sha256: str
    source_encoded_pit_lane_sha256: str
    material: str
    bottom_offset_m: Annotated[FiniteFloat, Field(gt=0)]
    height_m: Annotated[FiniteFloat, Field(gt=0)]
    inward_offset_m: Annotated[FiniteFloat, Field(gt=0, lt=0.05)]
    repeat_m: Annotated[FiniteFloat, Field(gt=0)]
    walls: list[EntryPanelWall]


@dataclass(frozen=True)
class EntryPanel:
    source_barrier_index: int
    first: Point
    last: Point
    inward_normal: Point
    u0: float
    repeat: float
