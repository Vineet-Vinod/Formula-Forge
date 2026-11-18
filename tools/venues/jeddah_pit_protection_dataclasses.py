"""Qualified exit protection around the unchanged four-metre Jeddah fast lane."""

from dataclasses import dataclass
from typing import Literal

from circuit_portals_dataclasses import Barrier
from pydantic import FiniteFloat


@dataclass(frozen=True)
class ExitJoin:
    side: Literal[-1, 1]
    distance_m: FiniteFloat
    point_xy_m: tuple[FiniteFloat, FiniteFloat]
    source_wall_index: int


@dataclass(frozen=True)
class ExitProtectionRecipe:
    source_sections_sha256: str
    cancellation_distance_m: FiniteFloat
    left_start_after_cancellation_m: FiniteFloat
    wall_axis_offset_m: FiniteFloat
    wall_radius_m: FiniteFloat
    height_above_lane_m: FiniteFloat
    foundation_embed_m: FiniteFloat
    leading_transition_m: FiniteFloat
    right_start_xy_m: tuple[FiniteFloat, FiniteFloat]
    joins: list[ExitJoin]
    panel_material: str
    panel_height_m: FiniteFloat
    panel_repeat_m: FiniteFloat


@dataclass(frozen=True)
class ExitWall:
    side: Literal[-1, 1]
    start_distance_m: float
    end_distance_m: float
    barrier: Barrier


@dataclass(frozen=True)
class ExitProtection:
    walls: list[ExitWall]
    retained: list[Barrier]
    replaced_old_count: int
