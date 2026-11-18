"""Reference-estimated Jeddah corridor and painted-apron records."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import FiniteFloat


@dataclass(frozen=True)
class ApronRange:
    start_m: FiniteFloat
    end_m: FiniteFloat
    side: Literal[-1, 1]
    maximum_width_m: FiniteFloat
    material: str
    source_frames: list[str]
    source_note: str


@dataclass(frozen=True)
class HighWall:
    start_m: FiniteFloat
    end_m: FiniteFloat
    side: Literal[-1, 1]
    height_m: FiniteFloat
    source_note: str


@dataclass(frozen=True)
class BoundaryRecipe:
    length_m: FiniteFloat
    ordinary_wall_gap_m: FiniteFloat
    kerbed_wall_gap_m: FiniteFloat
    kerb_width_m: FiniteFloat
    kerb_inner_offset_m: FiniteFloat
    kerb_outer_clearance_m: FiniteFloat
    kerbs: list[tuple[FiniteFloat, FiniteFloat, Literal[-1, 1]]]
    apron_ranges: list[ApronRange]
    high_walls: list[HighWall] = field(default_factory=list)
