"""Private source-qualified visibility controls for Corniche landmarks."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class SkylineResidency:
    osm_id: int
    tile_name: str
    south_margin_m: Annotated[FiniteFloat, Field(gt=0, le=1000)]
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    actual_baseline_bounds_ue_cm: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
