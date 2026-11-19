"""Paint controls registered to the accepted Jeddah pit and racing surfaces."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class PaintLine:
    name: str
    frame: Literal['pit', 'entry_fork', 'exit_outer']
    controls: Annotated[list[tuple[FiniteFloat, FiniteFloat]], Field(min_length=2)]
    width_m: Annotated[FiniteFloat, Field(gt=0, le=.3)]
    dash_m: Annotated[FiniteFloat, Field(ge=0)] = 0
    gap_m: Annotated[FiniteFloat, Field(ge=0)] = 0


@dataclass(frozen=True)
class PitMarkings:
    source_sections_sha256: str
    source_road_sha256: str
    source_note: str
    lines: list[PaintLine]
    road_edge_replacements_m: list[tuple[FiniteFloat, FiniteFloat]]
