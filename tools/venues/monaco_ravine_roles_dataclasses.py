"""Packed material-partition rows and measured encoding audit."""
from dataclasses import dataclass
from typing import Annotated, ClassVar

from pydantic import ConfigDict, Field, FiniteFloat

XY = tuple[FiniteFloat, FiniteFloat]

@dataclass(frozen=True)
class GroundRow:
    material: str
    payload: bytes

@dataclass(frozen=True)
class GroundClipAudit:
    original_area_m2: float
    natural_area_m2: float
    outside_area_m2: float
    emitted_area_m2: float
    dropped_f32_area_m2: float
    maximum_plane_error_m: float
    maximum_plane_error_bound_m: float
    maximum_normal_interpolation_error: float
    maximum_uv_interpolation_error: float
    coverage_error_outside_encoding_bound_m2: float
    overlap_area_m2: float
    normal_min_alignment: float
    minimum_emitted_area_m2: float
    held_unrepresentable_natural_area_m2: float = 0.0
    reassigned_zero_width_outside_area_m2: float = 0.0
    maximum_dropped_width_m: float = 0.0

@dataclass(frozen=True)
class RavineRoleBoundary:
    name: str
    wgs84_lonlat: Annotated[tuple[XY, ...], Field(min_length=3)]
    expected_native_xy_m: Annotated[tuple[XY, ...], Field(min_length=3)]
    margin_m: Annotated[FiniteFloat, Field(ge=0)] = 0

@dataclass(frozen=True)
class RavineRolesSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    origin_lat_lon: XY
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    natural_roles: tuple[RavineRoleBoundary, ...]
    explicit_guards: tuple[RavineRoleBoundary, ...]
    expected_domain_wkt: str
    expected_parent_faces: Annotated[int, Field(gt=0)]
    expected_natural_area_m2: Annotated[FiniteFloat, Field(gt=0)]
    expected_parent_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    protected_source_sha256: dict[str, str]
    barriers_csv_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]

@dataclass(frozen=True)
class RavineRolesChange:
    changed_tiles: tuple[str, ...]
    selected_parent_faces: int
    whole_material_only_faces: int
    split_faces: int
    held_parent_faces: int
    held_natural_area_m2: float
    arithmetic_ghost_area_m2: float
    emitted_fragment_faces: int
    complete_unchanged_rows: int
    natural_area_m2: float
    maximum_plane_error_m: float
    maximum_plane_error_bound_m: float
    minimum_normal_alignment: float
