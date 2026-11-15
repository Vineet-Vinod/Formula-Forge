"""Finite upper-bank terrain and its one existing mapped tree."""

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

from venues.monaco_ravine_dataclasses import RavineSource


@dataclass(frozen=True)
class UpperBankSource:
    terrain: RavineSource
    mapped_tree_id: int
    old_tree_base: Point
    tree_height_m: Annotated[FiniteFloat, Field(gt=0)]
    tree_seed: int
    tree_row_count: Annotated[int, Field(gt=0)]
    tree_burial_m: Annotated[FiniteFloat, Field(gt=0, le=0.2)]
    source_review: str
