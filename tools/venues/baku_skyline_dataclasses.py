from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class SkylineBuilding:
    osm_id: int
    name: str
    height_m: Annotated[FiniteFloat, Field(gt=0)]
    floors: Annotated[int, Field(gt=0)]
    style: Literal["torch", "crescent", "residence", "hotel", "podium", "context"]


@dataclass(frozen=True)
class SkylineRecipe:
    source_file: str
    buildings: list[SkylineBuilding]
