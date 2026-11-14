"""Source-frame dimensions for Anderson Bridge's two roadway openings."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class AndersonBridge:
    axis_wgs84: tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    station_m: Annotated[FiniteFloat, Field(gt=0)]
    steel_span_m: Annotated[FiniteFloat, Field(gt=0)]
    overall_length_m: Annotated[FiniteFloat, Field(gt=0)]
    girder_pitch_m: Annotated[FiniteFloat, Field(gt=0)]
    girder_width_m: Annotated[FiniteFloat, Field(gt=0)]
    main_truss_top_m: Annotated[FiniteFloat, Field(gt=0)]
    cross_tie_rise_m: Annotated[FiniteFloat, Field(gt=0)]
