from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from circuit_dataclasses import Point
from pydantic import ConfigDict

XY = tuple[float, float]


@dataclass(frozen=True)
class RoofObjectSource:
    kind: Literal['rooflight', 'fans', 'plant']
    source_pixel: XY
    nominal_xy_m: XY
    footprint_xy_m: tuple[XY, XY, XY, XY]


@dataclass(frozen=True)
class RomeFrame:
    origin: XY
    axis: XY
    inward: XY
    width_m: float
    depth_m: float
    datum_m: float = 1.5128994113

    def point(self, u: float, depth: float, absolute_z: float) -> Point:
        return (self.origin[0] + self.axis[0]*u + self.inward[0]*depth,
                self.origin[1] + self.axis[1]*u + self.inward[1]*depth,
                absolute_z - self.datum_m)


@dataclass(frozen=True)
class RomeSpec:
    frame: RomeFrame
    owner_xy_m: tuple[XY, ...]
    roof_xy_absolute_z_m: tuple[Point, ...]
    base_absolute_m: float = 56.304901364425
    floor_height_m: float = 3.25
    normal_levels: int = 8
    terrace_depth_fraction: float = .245
    terrace_absolute_m: float = 82.7
    shoulder_absolute_m: float = 86.6
    hip_apex_absolute_m: float = 88.0
    hip_apex_uv: XY = (.5, .62)
    mansard_inner_u_fraction: float = .075
    mansard_inner_front_v_fraction: float = .285
    mansard_inner_rear_v_fraction: float = .925
    loggia_depth_m: float = 2.4
    column_radius_m: float = .18
    column_capital_width_m: float = .58
    main_bays: int = 3
    north_upper_uv: tuple[XY, XY] | None = None
    north_eave_uv: tuple[XY, XY] | None = None
    source_objects: tuple[RoofObjectSource, ...] = ()


@dataclass(frozen=True)
class RomeSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    osm_id: Literal[94400097]
    origin_lat_lon: XY
    uniform_scale: float
    relative_datum_m: float
    owner_wgs84_lonlat: tuple[XY, ...]
    original_ign_wgs84_xyz: tuple[Point, ...]
    protected_source_sha256: dict[str, str]
    spec: RomeSpec
    expected_legacy_rows: Literal[1822]
    frozen_v3_rows_sha256: str
    frozen_v3_materials: tuple[str, ...]
    expected_new_triangles: Literal[70612]
    body_south_prefix_bytes: Literal[6362000]
    body_south_prefix_sha256: str
    original_north_z_association_accepted: Literal[False]
    native_visual_acceptance: Literal[False]
    source_qualification: str


@dataclass(frozen=True)
class RomeChange:
    old_rows_removed: int
    new_triangles: int
    unrelated_city_rows_preserved: int
    new_geometry_sha256: str
    body_south_prefix_sha256: str
    minimum_packed_normal_alignment: float
    main_roof_top_triangles: int
    roof_coverage_error_m2: float
    roof_overlap_area_m2: float
    closed_roof_triangles: int
    closed_soffit_triangles: int
    maximum_object_center_offset_m: float
