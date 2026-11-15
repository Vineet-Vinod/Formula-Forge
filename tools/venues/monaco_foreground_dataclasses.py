"""Source controls and geometry records for two registered Monaco foreground houses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

from venues.monaco_bamboo_dataclasses import BambooAudit, BambooSpec, CanePose

XY = tuple[FiniteFloat, FiniteFloat]
XYZ = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Positive = Annotated[FiniteFloat, Field(gt=0)]
GardenPrecisionAction = Literal['collapsed', 'reoriented', 'normal_aligned']

class MissingForegroundFloor(ValueError):
    pass


@dataclass(frozen=True)
class BruyeresSpec:
    osm_id: Literal[94400108]
    owner_xy_m: tuple[XY, ...]
    roof_xy_m: tuple[XY, ...]
    front_endpoints_xy_m: tuple[XY, XY]
    datum_m: FiniteFloat
    core_base_relative_m: FiniteFloat
    main_roof_relative_m: FiniteFloat
    core_base_uncertainty_m: Positive = 1.5
    floor_count: Literal[4] = 4
    recess_m: Annotated[FiniteFloat, Field(ge=.12, le=.30)] = .20
    curved_balcony_depth_m: Positive = 1.45
    curved_balcony_width_m: Positive = 5.60
    side_balcony_depth_m: Positive = 1.05
    side_balcony_width_m: Positive = 3.20


@dataclass(frozen=True)
class BruyeresFrame:
    origin: XY
    tangent: XY
    outward: XY
    span_m: float


@dataclass(frozen=True)
class BruyeresAudit:
    osm_id: int
    owner_area_m2: float
    core_area_m2: float
    lower_estate_area_m2: float
    core_base_relative_m: float
    core_base_uncertainty_m: float
    main_roof_relative_m: float
    main_roof_absolute_m: float
    floor_count: int
    openings: int
    curved_balconies: int
    side_balconies: int
    core_ring_xyz_m: tuple[Point, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class BruyeresGardenAudit:
    area_m2: float
    ground_triangles: int
    retaining_segments: int
    source_boundary_points: int
    max_core_base_join_error_m: float
    minimum_retaining_burial_m: float
    palms_xy_m: tuple[XY, ...]
    precision_faces: tuple[GardenPrecisionFace, ...]
    original_primitive_degenerate_rejections: int
    shared_body_edges: tuple[GardenSharedEdge, ...]
    limitations: tuple[str, ...]
    bamboo: BambooAudit | None = None
    retained_canes: tuple[CanePose, ...] = ()


@dataclass(frozen=True)
class GardenPrecisionFace:
    action: GardenPrecisionAction
    source_points: tuple[Point, Point, Point]
    packed_points: tuple[Point, Point, Point]
    source_minimum_altitude_m: float
    xy_ulp_bound_m: float
    maximum_xy_error_m: float
    maximum_z_error_m: float
    source_projected_area_m2: float
    packed_three_dimensional_area_m2: float


@dataclass(frozen=True)
class GardenSharedEdge:
    endpoints_xy_m: tuple[XY, XY]
    maximum_body_distance_m: float
    xy_ulp_bound_m: float
    new_precision_reconciliation: bool


@dataclass(frozen=True)
class MontjoieSpec:
    osm_id: Literal[94399506]
    owner_xy_m: Annotated[tuple[XY, ...], Field(min_length=7, max_length=7)]
    front_vertex_indices: tuple[Literal[6], Literal[5]]
    relative_datum_m: FiniteFloat
    base_relative_m: FiniteFloat
    main_top_relative_m: FiniteFloat
    floor_bottom_offsets_m: Annotated[tuple[FiniteFloat, ...], Field(min_length=5, max_length=5)]
    opening_height_m: Positive
    left_bay_center_m: Positive
    right_bay_center_m: Positive
    left_opening_width_m: Positive
    right_opening_width_m: Positive
    recess_m: Annotated[FiniteFloat, Field(ge=.12, le=.30)]
    balcony_halfwidth_m: Positive
    balcony_depth_m: Positive
    top_balcony_halfwidth_m: Positive
    top_balcony_depth_m: Positive
    parapet_height_m: Positive
    pavilion_center_uv_m: XY
    pavilion_width_m: Positive
    pavilion_depth_m: Positive
    pavilion_height_m: Positive
    pavilion_uncertainty_m: Positive


@dataclass(frozen=True)
class MontjoieFrame:
    origin: XY
    tangent: XY
    outward: XY
    width_m: float


@dataclass(frozen=True)
class MontjoieOpening:
    floor: int
    bay: int
    contour_uz_m: tuple[XY, ...]


@dataclass(frozen=True)
class MontjoieAudit:
    osm_id: int
    owner_area_m2: float
    front_width_m: float
    base_relative_m: float
    main_top_relative_m: float
    main_top_absolute_m: float
    opening_count: int
    arched_opening_count: int
    projecting_balcony_count: int
    juliet_rail_count: int
    recess_m: float
    front_wall_area_m2: float
    aperture_area_m2: float
    roof_parapet_top_relative_m: float
    pavilion_peak_relative_m: float
    pavilion_peak_absolute_m: float
    pavilion_plan_xyz_m: tuple[XYZ, ...]
    openings: tuple[MontjoieOpening, ...]


@dataclass(frozen=True)
class ForegroundPhoto:
    url: str
    sha256: str
    identity: str
    date_status: str
    actual_or_proposed: Literal['actual_photo']


@dataclass(frozen=True)
class ForegroundSource:
    schema: Literal[1]
    origin_latitude: FiniteFloat
    origin_longitude: FiniteFloat
    scene_scale: Positive
    relative_datum_m: FiniteFloat
    bruyeres: BruyeresSpec
    bruyeres_bamboo: BambooSpec
    montjoie: MontjoieSpec
    bruyeres_owner_wgs84_lonlat: tuple[XY, ...]
    montjoie_owner_wgs84_lonlat: tuple[XY, ...]
    bruyeres_roof_wgs84_xyz: tuple[XYZ, ...]
    montjoie_roof_wgs84_xyz: tuple[XYZ, ...]
    estimated_open_frontage_bounds_xy_m: tuple[float, float, float, float]
    portal_source_note: str
    photos: tuple[ForegroundPhoto, ...]
    source_limits: tuple[str, ...]


@dataclass(frozen=True)
class ForegroundFloor:
    tile: str
    offset: int
    material: str
    points: tuple[Point, Point, Point]


@dataclass(frozen=True)
class ForegroundChange:
    changed_tiles: tuple[str, ...]
    old_rows_removed: int
    new_rows_appended: int
    preserved_old_rows: int
    source_boundary_points: int
    bruyeres: BruyeresAudit
    montjoie: MontjoieAudit
    garden: BruyeresGardenAudit
