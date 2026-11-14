"""Bounded west-ravine architecture and rendered cliff source settings."""

from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class BelvedereArchitecture:
    center_xy_m: tuple[FiniteFloat, FiniteFloat]
    east_axis: tuple[FiniteFloat, FiniteFloat]
    south_axis: tuple[FiniteFloat, FiniteFloat]
    radius_m: Annotated[FiniteFloat, Field(gt=4, lt=6)]
    paving_absolute_m: FiniteFloat
    cap_absolute_m: FiniteFloat
    relative_datum_m: FiniteFloat
    existing_wood_ground_file: str
    wall_thickness_m: FiniteFloat = .3
    rim_walk_width_m: FiniteFloat = .8
    arc_segments: Annotated[int, Field(ge=96, le=192)] = 128
    arch_bays: Annotated[int, Field(ge=8, le=16)] = 12
    arch_width_m: FiniteFloat = .65
    arch_height_m: FiniteFloat = .82
    arch_recess_m: FiniteFloat = .10
    course_height_m: FiniteFloat = .42
    stone_joint_m: FiniteFloat = .025
    base_overlap_m: FiniteFloat = .12


@dataclass(frozen=True)
class CliffPatch:
    ground_grid_file: str
    uniform_scale: FiniteFloat
    relative_datum_m: FiniteFloat
    outer_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    ivy_rings_xy_m: tuple[tuple[tuple[FiniteFloat, FiniteFloat], ...], ...] = ()
    collar_width_m: Annotated[FiniteFloat, Field(ge=1.5, le=3.)] = 2.
    render_step_m: Annotated[FiniteFloat, Field(ge=.5, le=1.)] = .75


@dataclass(frozen=True)
class ExistingWoodGround:
    osm_id: int
    outer_wgs84: tuple[tuple[FiniteFloat, FiniteFloat], ...]
