from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from circuit_dataclasses import Point
from pydantic import ConfigDict, Field, FiniteFloat

from venues.monaco_surfaces_dataclasses import NativeVertex


@dataclass(frozen=True)
class RavineGroundRow:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    tile: Annotated[str, Field(pattern=r"^Tile_Street_")]
    material: Literal["Grass", "Runoff", "MonacoIvyGround", "MonacoRockGround"]
    attributes_hex: Annotated[str, Field(pattern=r"^[0-9a-f]{192}$")]
    copies: Annotated[int, Field(gt=0)] = 1


@dataclass(frozen=True)
class RavineSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    circuit: Literal["monaco"]
    origin_lat_lon: tuple[FiniteFloat, FiniteFloat]
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    relative_datum_m: FiniteFloat
    outer_xy_m: Annotated[
        tuple[tuple[FiniteFloat, FiniteFloat], ...], Field(min_length=3)
    ]
    window_xy_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    mandatory_exclusions: tuple[tuple[tuple[FiniteFloat, FiniteFloat], ...], ...]
    collar_width_m: Annotated[FiniteFloat, Field(ge=1, le=5)]
    render_step_m: Annotated[FiniteFloat, Field(ge=0.1, le=0.5)]
    expected_domain_wkt: str
    grid_file: str
    grid_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    protected_source_sha256: dict[str, str]
    original_ground_rows: Annotated[tuple[RavineGroundRow, ...], Field(min_length=1)]
    source_note: str


@dataclass(frozen=True)
class RavineFace:
    offset: int
    intended_normal: Point
    original_vertices: tuple[NativeVertex, ...]
    packed_vertices: tuple[NativeVertex, ...]
    minimum_altitude_m: float
    xy_ulp_bound_m: float
    maximum_xy_error_m: float
    maximum_z_error_m: float
    inside: bool


@dataclass(frozen=True)
class RavinePrecisionFace:
    tile: str
    row: int
    area_m2: float
    minimum_altitude_m: float
    xy_ulp_bound_m: float
    maximum_xy_error_m: float
    maximum_z_error_m: float
    minimum_packed_normal_alignment: float
    minimum_intended_normal_alignment: float
    points: tuple[Point, ...]


@dataclass(frozen=True)
class RavineChange:
    tiles: tuple[str, ...]
    source_faces: int
    emitted_rows: int
    complete_unselected_rows: int
    domain_area_m2: float
    minimum_height_delta_m: float
    maximum_height_delta_m: float
    collapsed_area_m2: float
    collapsed_faces: int
    maximum_collapsed_width_m: float
    maximum_encoding_xy_error_m: float
    maximum_encoding_z_error_m: float
    minimum_normal_alignment: float
    minimum_resolved_normal_alignment: float
    unresolved_faces: tuple[RavinePrecisionFace, ...]
    reoriented_faces: int
    maximum_outside_plane_reprojection_m: float = 0.0
