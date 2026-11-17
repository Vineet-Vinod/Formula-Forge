"""Height-qualified openings and replacement protection in source metres."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat

PlanPoint = tuple[FiniteFloat, FiniteFloat]
PortalQuad = Annotated[tuple[PlanPoint, ...], Field(min_length=4, max_length=4)]


@dataclass(frozen=True)
class Portal:
    id: str
    polygon_xy_m: PortalQuad
    bottom_m: FiniteFloat
    top_m: FiniteFloat
    source_note: str


@dataclass(frozen=True)
class Barrier:
    ax: FiniteFloat
    ay: FiniteFloat
    bx: FiniteFloat
    by: FiniteFloat
    bottom: FiniteFloat
    top: FiniteFloat
    radius: Annotated[FiniteFloat, Field(gt=0)]
