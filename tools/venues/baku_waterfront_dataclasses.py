from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from circuit_dataclasses import Point

from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class WaterfrontFront:
    osm_id: Literal[465003806, 152191301]
    ring_xy_m: tuple[tuple[float, float], ...]
    main_edge: int
    floor_relative_m: float
    cornice_m: float = 17.0
    roof_top_m: float = 21.0
    height_uncertainty_m: float = 4.0
    foundation_drop_m: float = 0.6


@dataclass(frozen=True)
class ParkTree:
    base: Point
    height_m: float
    crown_width_m: float
    seed: int
    form: Literal["evergreen", "deciduous"]
    parcel_id: int
    ground_tile: str
    ground_payload: str


@dataclass(frozen=True)
class FinalContextSource:
    fronts: tuple[WaterfrontFront, ...]
    trees: tuple[ParkTree, ...] = ()


@dataclass(frozen=True)
class GroundClipAudit:
    original_area_m2: float
    grass_area_m2: float
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


@dataclass(frozen=True)
class WaterfrontFamily:
    parent: str
    triangles: int
    counter_sha256: str


@dataclass(frozen=True)
class WaterfrontRecipe:
    version: Literal[1]
    origin_lat_lon: tuple[float, float]
    uniform_scale: float
    geometry: FinalContextSource
    legacy_families: tuple[WaterfrontFamily, ...]
    ground_domain_wkt: str
    ground_inputs: tuple[PackedPatchRow, ...]
    supporting_ground: tuple[PackedPatchRow, ...]
    post_tree_ground: tuple[PackedPatchRow, ...]
    expected_geometry_rows: int
    geometry_counter_sha256: str
    expected_ground_rows: int
    ground_counter_sha256: str
    source_note: str
    road_mask_sha256: str
    protected_inputs_sha256: dict[str, str]


@dataclass(frozen=True)
class WaterfrontChange:
    removed_owner_rows: int
    new_geometry_rows: int
    original_ground_rows: int
    segmented_ground_rows: int
    supporting_ground_rows: int
    preserved_rows: int
    changed_parents: tuple[str, ...]
