"""Estimated fixed façade-wash positions for the Jeddah EDITION."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]
Fraction = Annotated[FiniteFloat, Field(gt=0, lt=1)]


@dataclass(frozen=True)
class EditionLightingSource:
    owner_osm_id: int
    frontage_fractions: tuple[Fraction, Fraction, Fraction, Fraction]
    outward_offset_m: Positive
    height_above_foundation_m: Positive
    target_inset_m: Positive
    target_height_above_foundation_m: Positive
    power: Positive
    source_note: str


@dataclass(frozen=True)
class EditionWash:
    position: Point
    target: Point
    power: float
