from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class ForecourtSource:
    service_geo: Annotated[list[tuple[FiniteFloat, FiniteFloat]], Field(min_length=2)]
    park_geo: Annotated[list[tuple[FiniteFloat, FiniteFloat]], Field(min_length=4)]
    park_paths_geo: list[list[tuple[FiniteFloat, FiniteFloat]]] = field(default_factory=list)
    core_half_width_m: Annotated[FiniteFloat, Field(gt=0)] = 2
    blend_extent_m: Annotated[FiniteFloat, Field(gt=2)] = 42
    park_transition_m: Annotated[FiniteFloat, Field(gt=0)] = 16
