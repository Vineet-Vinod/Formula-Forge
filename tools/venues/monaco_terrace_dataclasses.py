from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal, TypeAlias

from circuit_dataclasses import Point
from pydantic import ConfigDict, Field, FiniteFloat
from shapely.geometry import Polygon

from venues.monaco_underarch_dataclasses import UnderarchFace

TerraceFloor: TypeAlias = UnderarchFace


@dataclass(frozen=True)
class TerraceSpec:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid", allow_inf_nan=False)

    relative_datum_m: float = 1.5128994113
    reference_northing_m: float = 372.4
    reference_lawn_absolute_m: float = 59.5
    lawn_north_grade: float = 0.085
    minimum_soil_cover_m: float = 0.02
    retaining_burial_m: float = 0.12
    upper_stone_band_height_m: float = 6.0
    upper_stone_band_uncertainty_m: float = 2.5
    face_step_m: float = 0.7
    rock_inset_m: float = 0.18
    balustrade_height_m: float = 1.02
    source_level_uncertainty_m: float = 1.5
    mortar_joint_m: float = 0.018
    maximum_stone_relief_m: float = 0.035


@dataclass(frozen=True)
class TerraceAudit:
    area_m2: float
    lawn_faces: int
    rock_faces: int
    masonry_faces: int
    support_segments: int
    maximum_support_extrapolation_m: float
    minimum_soil_cover_m: float
    minimum_foundation_burial_m: float
    maximum_visible_masonry_band_m: float
    maximum_lower_rock_face_m: float
    balusters: int
    hedges: int
    minimum_top_absolute_m: float
    maximum_top_absolute_m: float
    encoding_missing_area_m2: float
    encoding_extra_area_m2: float
    encoding_area_bound_m2: float
    omitted_subformat_stone_faces: int
    omitted_subformat_stone_area_m2: float
    distinct_stones: int
    stone_facing_faces: int
    maximum_stone_relief_m: float


@dataclass(frozen=True)
class StoneCell:
    plan: Polygon
    material: str
    relief_m: float


@dataclass(frozen=True)
class TerraceSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid", allow_inf_nan=False)

    origin_lat_lon: tuple[FiniteFloat, FiniteFloat]
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    relative_datum_m: FiniteFloat
    garden_wgs84_lonlat: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    expected_garden_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    apron_wgs84_lonlat: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    expected_apron_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    pool_wgs84_lonlat: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    expected_pool_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    front_wgs84_lonlat: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    expected_front_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    expected_domain_wkt: str
    body_guard_m: Annotated[FiniteFloat, Field(gt=0)]
    mapped_tree_id: Literal[5931906971]
    mapped_tree_wgs84_lonlat: tuple[FiniteFloat, FiniteFloat]
    expected_previous_tree_base: Point
    tree_height_m: Annotated[FiniteFloat, Field(gt=0)]
    tree_seed: Literal[239]
    protected_source_sha256: dict[str, str]
    terrace: TerraceSpec


@dataclass(frozen=True)
class TerraceChange:
    geometry: TerraceAudit
    old_tree_base: Point
    new_tree_base: Point
    unrelated_city_rows_preserved: int
    old_street_rows_preserved: int
    minimum_packed_normal_alignment: float
    maximum_lawn_missing_area_m2: float
    maximum_lawn_extra_area_m2: float
