"""Registered controls and geometry records for Sainte-Dévote."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from circuit_dataclasses import Point
from pydantic import ConfigDict, Field, FiniteFloat

from venues.monaco_ravine_dataclasses import RavineChange, RavineSource

XY = tuple[FiniteFloat, FiniteFloat]
Positive = Annotated[FiniteFloat, Field(gt=0)]

@dataclass(frozen=True)
class ChapelFrame:
    origin: Point
    axis: tuple[float, float]
    inward: tuple[float, float]
    width_m: float
    floor_absolute_m: float
    datum_m: float
    base_absolute_m: float = 6.85

    def point(self, u: float, depth: float, z: float) -> Point:
        return (self.origin[0] + self.axis[0] * u + self.inward[0] * depth,
                self.origin[1] + self.axis[1] * u + self.inward[1] * depth,
                self.floor_absolute_m - self.datum_m + z)


@dataclass(frozen=True)
class TowerSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    center_u_m: FiniteFloat = 10.7
    center_depth_m: FiniteFloat = 4.3
    width_m: FiniteFloat = 2.3
    depth_m: FiniteFloat = 2.3
    bell_stage_bottom_absolute_m: FiniteFloat = 17.4
    bell_stage_top_absolute_m: FiniteFloat = 22.0
    crown_top_absolute_m: FiniteFloat = 24.0
    opening_width_m: FiniteFloat = 1.1
    opening_bottom_absolute_m: FiniteFloat = 18.25
    opening_top_absolute_m: FiniteFloat = 21.3


@dataclass(frozen=True)
class NaveSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    owner_uv_m: tuple[tuple[float, float], ...]
    foundation_absolute_m: FiniteFloat = 6.85
    eaves_absolute_m: FiniteFloat = 14.1
    ridge_absolute_m: FiniteFloat = 17.5
    estimated_ridge_u_m: FiniteFloat = 7.133327357328756
    ridge_position_uncertainty_m: FiniteFloat = 2.5
    ridge_height_uncertainty_m: FiniteFloat = 2.5
    hip_start_depth_m: FiniteFloat = 25.0
    front_depth_m: FiniteFloat = 0.65
    roof_thickness_m: FiniteFloat = 0.14
    tower: TowerSource = TowerSource()


@dataclass(frozen=True)
class WallFrame:
    frame: ChapelFrame
    origin: tuple[float, float]
    axis: tuple[float, float]
    inward: tuple[float, float]

    def point(self, x: float, z: float, inset: float) -> Point:
        return self.frame.point(
            self.origin[0] + self.axis[0] * x + self.inward[0] * inset,
            self.origin[1] + self.axis[1] * x + self.inward[1] * inset,
            z - self.frame.floor_absolute_m,
        )


@dataclass(frozen=True)
class ChapelSite:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    apron_absolute_m: FiniteFloat
    ground_grid_xy_m: XY
    ground_grid_step_m: Positive
    ground_grid_columns: Annotated[int, Field(gt=1)]
    ground_grid_rows: Annotated[int, Field(gt=1)]
    step_count: Literal[5]
    stair_rise_m: Positive
    stair_tread_m: Positive
    landing_depth_m: Positive
    foot_burial_m: Positive
    minimum_step_clearance_m: Positive
    ground: RavineSource


@dataclass(frozen=True)
class ChapelSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    osm_id: Literal[94399398]
    origin_lat_lon: XY
    uniform_scale: Positive
    relative_datum_m: FiniteFloat
    owner_wgs84_lonlat: Annotated[tuple[XY, ...], Field(min_length=3)]
    expected_owner_xy_m: Annotated[tuple[XY, ...], Field(min_length=3)]
    front_origin_vertex: Literal[1]
    front_end_vertex: Literal[3]
    floor_absolute_m: FiniteFloat
    floor_uncertainty_m: Positive
    base_absolute_m: FiniteFloat
    nave: NaveSource
    site: ChapelSite
    primary_source_sha256: dict[str, str]
    source_limits: tuple[str, ...]


@dataclass(frozen=True)
class ChapelStep:
    step: int
    minimum_top_clearance_m: float
    minimum_foot_burial_m: float
    probes: int


@dataclass(frozen=True)
class ChapelStairShell:
    original_box_rows: int
    emitted_rows: int
    profile_depth_z_m: tuple[XY, ...]
    volume_m3: float
    original_duplicate_side_area_m2: float
    minimum_packed_normal_alignment: float
    closed_edge_count: int


@dataclass(frozen=True)
class ChapelChange:
    city_tile: str
    removed_generic_rows: int
    emitted_architecture_rows: int
    complete_unselected_city_rows: int
    ground: RavineChange
    stairs: tuple[ChapelStep, ...]
    stair_shell: ChapelStairShell
