from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

Positive = Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class CanePose:
    index: int
    root: Point
    original_height_m: float


@dataclass(frozen=True)
class BambooSpec:
    seed: Literal[94400108] = 94400108
    relative_datum_m: FiniteFloat = 1.5128994113001681
    minimum_canopy_top_absolute_m: FiniteFloat = 14.7
    maximum_canopy_top_absolute_m: FiniteFloat = 16.4
    height_uncertainty_m: Positive = 2.0
    branches_per_cane: Annotated[int, Field(ge=2, le=32)] = 14
    leaves_per_branch: Annotated[int, Field(ge=4, le=64)] = 24
    minimum_leaf_length_m: Positive = .17
    maximum_leaf_length_m: Positive = .29
    minimum_leaf_width_m: Positive = .025
    maximum_leaf_width_m: Positive = .043
    maximum_branch_reach_m: Positive = 1.05
    cane_radius_m: Positive = .012
    boundary_margin_m: Positive = .10


@dataclass(frozen=True)
class BambooAudit:
    root_count: int
    branch_count: int
    blade_count: int
    skipped_boundary_blades: int
    minimum_height_m: float
    maximum_height_m: float
    source_height_uncertainty_m: float
    minimum_bed_clearance_m: float


@dataclass(frozen=True)
class CaneCurve:
    root: Point
    direction: tuple[float, float]
    lean: float
    height: float

    def point(self, t: float) -> Point:
        return (self.root[0] + self.direction[0] * self.lean * t * t,
                self.root[1] + self.direction[1] * self.lean * t * t,
                self.root[2] + self.height * t)


@dataclass(frozen=True)
class TwigArc:
    root: Point
    horizontal: Point
    reach: float
    lift: float
    droop: float

    def point(self, t: float) -> Point:
        return (self.root[0] + self.horizontal[0] * self.reach * t,
                self.root[1] + self.horizontal[1] * self.reach * t,
                self.root[2] + self.lift * math.sin(t * math.pi) - self.droop * t * t)
