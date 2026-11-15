from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class No85Source:
    ring_xy_m: tuple[tuple[float, float], ...]
    floor_relative_m: float
    main_edge: int = 9
    return_edge: int = 10
    cornice_m: float = 28.0
    wing_cornice_m: float = 24.0
    middle_return_m: float = 20.4
    back_return_m: float = 16.5
    height_uncertainty_m: float = 5.0
    foundation_drop_m: float = 0.6
    main_core_interval_m: tuple[float, float] = (5.4, 31.4)
    lower_floor_m: tuple[float, ...] = (4.3, 8.0, 11.7, 15.4)
    upper_floor_m: tuple[float, ...] = (19.6, 23.3)


@dataclass(frozen=True)
class No85Model:
    main_length_m: float
    owner_area_m2: float
    roof_area_m2: float
    source_group_types: int
    estimated_lower_balcony_floors: int
    estimated_oriel_pane_rows: int


@dataclass(frozen=True)
class No85Recipe:
    osm_id: Literal[279589354]
    origin_lat_lon: tuple[float, float]
    uniform_scale: float
    expected_tag_height_m: float
    expected_legacy_height_m: float
    expected_legacy_rows: int
    legacy_counter_sha256: str
    expected_candidate_rows: int
    candidate_counter_sha256: str
    ground_supports: tuple[PackedPatchRow, ...]
    geometry: No85Source
    road_mask_sha256: str
    protected_inputs_sha256: dict[str, str]
    source_note: str


@dataclass(frozen=True)
class No85Change:
    removed_rows: int
    emitted_rows: int
    preserved_rows: int
    supporting_ground_rows: int
    parent: str
