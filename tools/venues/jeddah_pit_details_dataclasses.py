"""Estimated dimensions for the observed pit frontage and workshop fittings."""
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class PitFacadeDetail:
    upper_glazing_recess_m: Positive
    balcony_depth_m: Positive
    balcony_slab_m: Positive
    upper_mullion_m: Positive
    garage_back_depth_m: Positive
    garage_ceiling_m: Positive
    interior_light_depth_m: Positive
    interior_light_power: Annotated[FiniteFloat, Field(gt=0, le=4)]
    source_note: str
