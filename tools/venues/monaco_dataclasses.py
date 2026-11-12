from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import FiniteFloat


@dataclass(frozen=True)
class HillsideBuilding:
    source_id: str
    component: int
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
    roof_outline_m: list[FiniteFloat]
    holes_roof_m: list[list[FiniteFloat]]
    ground_m: FiniteFloat
    eaves_m: FiniteFloat
    roof_m: FiniteFloat
    floors: int | None
    roof_material: Literal['Terracotta', 'Roof', 'Concrete', 'Steel']
    height_precision_m: FiniteFloat | None


@dataclass(frozen=True)
class HillsideVegetation:
    source_id: str
    nature: str
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
