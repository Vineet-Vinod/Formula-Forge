from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from circuit_dataclasses import Point
from pydantic import ConfigDict, Field, FiniteFloat
from shapely.geometry import Polygon


@dataclass(frozen=True)
class UnderarchFace:
    tile: str
    row: int
    material: str
    points: tuple[Point, Point, Point]
    plan: Polygon
    raw: bytes


@dataclass(frozen=True)
class UnderarchSpec:
    seed: int = 941749869
    spacing_m: float = 2.25
    jitter_m: float = 0.35
    minimum_primitive_height_m: float = 3.8
    maximum_primitive_height_m: float = 5.5
    root_burial_fraction: float = 0.46
    wind_envelope_m: float = 0.25
    minimum_soffit_clearance_m: float = 1.0


@dataclass(frozen=True)
class UnderarchPlant:
    index: int
    xy_m: tuple[float, float]
    actual_ground_relative_m: float
    ground_owner: tuple[str, int]
    primitive_height_m: float
    crown_maximum_relative_m: float
    minimum_soffit_relative_m: float
    conservative_wind_clearance_m: float
    projected_wind_area_m2: float
    seed: int


@dataclass(frozen=True)
class UnderarchAudit:
    plants: tuple[UnderarchPlant, ...]
    attempted: int
    boundary_rejected: int
    ceiling_rejected: int
    minimum_clearance_m: float
    source_floor_faces: int
    actual_ceiling_faces: int


@dataclass(frozen=True)
class UnderarchSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    forest_osm_id: Literal[941749869]
    forest_source_sha256: str
    forest_wgs84_lonlat: Annotated[tuple[tuple[FiniteFloat, FiniteFloat], ...], Field(min_length=3)]
    expected_forest_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    origin_lat_lon: tuple[FiniteFloat, FiniteFloat]
    uniform_scale: FiniteFloat
    bridge_source_sha256: str
    expected_mask_area_m2: Annotated[FiniteFloat, Field(gt=0)]
    expected_mask_wkt: str
    planting: UnderarchSpec


@dataclass(frozen=True)
class UnderarchChange:
    changed_street_tiles: tuple[str, ...]
    original_faces_split: int
    complete_outside_rows: int
    classified_area_m2: float
    emitted_fragments: int
    maximum_encoded_plane_reprojection_m: float
    foliage: UnderarchAudit
