"""Estimated sections for the source-visible glazed pit-entry end elevation."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class PitEntryDetail:
    station_m: Positive
    width_m: Positive
    height_m: Positive
    floor_height_m: Positive
    levels: Annotated[int, Field(gt=0)]
    band_height_m: Positive
    glazing_depth_m: Positive
    backing_depth_m: Positive
    bay_width_m: Positive
    pier_width_m: Positive
    lobby_light_power: Annotated[FiniteFloat, Field(gt=0, le=4)]
    source_note: str
