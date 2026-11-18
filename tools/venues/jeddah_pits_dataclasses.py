"""Dimensions estimated from the supplied Jeddah pit-stop sequence."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class PitWorkingLane:
    start_m: Positive
    length_m: Positive
    garage_front_offset_m: Positive
    bay_spacing_m: Positive
    service_gap_m: Positive
    support_taper_m: Positive
    working_strip_width_m: Positive
    stop_center_from_garage_m: Positive
    stop_half_width_m: Positive
    stop_half_length_m: Positive
    boom_height_m: Positive
    boom_reach_m: Positive
    stop_garage_centres: tuple[Positive, ...]
    source_note: str
