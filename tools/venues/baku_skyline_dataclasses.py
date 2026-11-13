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


@dataclass(frozen=True)
class FlameTower:
    osm_id: int
    name: str
    height_m: Annotated[FiniteFloat, Field(gt=0)]
    floors: Annotated[int, Field(gt=0)]
    base_relative_m: FiniteFloat
    ground_uncertainty_m: Annotated[FiniteFloat, Field(gt=0)]
    crown_tip_fraction: Annotated[FiniteFloat, Field(gt=0, lt=1)]
    service_bands: list[Annotated[FiniteFloat, Field(gt=0, lt=1)]]


@dataclass(frozen=True)
class FlameTowerRecipe:
    source_file: str
    source_sha256: str
    towers: list[FlameTower]
