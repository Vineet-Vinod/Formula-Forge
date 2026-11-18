"""Source controls for the named Corniche Mosque at the T22 shoreline."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class CornicheMosqueSource:
    osm_node_id: int
    latitude: Annotated[FiniteFloat, Field(ge=-90, le=90)]
    longitude: Annotated[FiniteFloat, Field(ge=-180, le=180)]
    floor_relative_m: FiniteFloat
    published_floor_m2: Positive
    hall_side_m: Positive
    hall_wall_m: Positive
    dome_radius_m: Positive
    dome_height_m: Positive
    loggia_depth_m: Positive
    porch_depth_m: Positive
    minaret_side_m: Positive
    minaret_shaft_m: Positive
    minaret_crown_m: Positive
    source_note: str


@dataclass(frozen=True)
class MosqueOpening:
    center_m: float
    width_m: float
    bottom_m: float
    spring_m: float
    crown_m: float
