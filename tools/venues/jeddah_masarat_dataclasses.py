"""Source estimates, registered placement and actual packed-ground records for Masarat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from circuit_dataclasses import Point
from pydantic import ConfigDict, Field, FiniteFloat
from shapely.geometry import Polygon
from shapely.strtree import STRtree

XY = tuple[float, float]


@dataclass(frozen=True)
class Wing:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    name: str
    center: FiniteFloat
    width: Annotated[FiniteFloat, Field(gt=10, lt=25)]
    depth: Annotated[FiniteFloat, Field(gt=30, lt=55)]
    front: Annotated[FiniteFloat, Field(gt=5, lt=20)]
    floors: Annotated[int, Field(ge=20, le=28)]
    height: Annotated[FiniteFloat, Field(gt=65, lt=100)]
    material: Literal['White', 'Cream']
    entry_relative_m: Annotated[FiniteFloat, Field(ge=0, le=15)]


@dataclass(frozen=True)
class MasaratDimensions:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    entrance_relative_m: Annotated[FiniteFloat, Field(ge=0, le=15)]
    entrance_uncertainty_m: Annotated[FiniteFloat, Field(ge=2, le=5)]
    high_height_m: Annotated[FiniteFloat, Field(gt=130, lt=160)]
    high_height_uncertainty_m: Annotated[FiniteFloat, Field(ge=12, le=20)]
    return_height_m: Annotated[FiniteFloat, Field(gt=80, lt=100)]
    high_floors: Annotated[int, Field(ge=40, le=44)]
    return_floors: Annotated[int, Field(ge=25, le=30)]
    wings: Annotated[tuple[Wing, ...], Field(min_length=4, max_length=4)]


@dataclass(frozen=True)
class MasaratStreet:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    osm_id: int
    path_wgs84_lon_lat: Annotated[tuple[tuple[FiniteFloat, FiniteFloat], ...], Field(min_length=2)]
    estimated_width_m: Annotated[FiniteFloat, Field(gt=0, le=20)]
    clearance_m: Annotated[FiniteFloat, Field(ge=1, le=3)]


@dataclass(frozen=True)
class MasaratSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    frontage_controls_wgs84_lon_lat: tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]
    expected_route_uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    dimensions: MasaratDimensions
    streets: tuple[MasaratStreet, ...]


@dataclass(frozen=True, kw_only=True)
class MasaratArchitecture(MasaratDimensions):
    origin: XY
    axis: XY
    normal: XY


@dataclass(frozen=True)
class GroundFace:
    points: tuple[Point, Point, Point]
    normals: tuple[Point, Point, Point]
    uv: tuple[XY, XY, XY]
    plan: Polygon
    tile_name: str
    index: int
    raw: bytes


@dataclass(frozen=True)
class GroundLookup:
    faces: tuple[GroundFace, ...]
    index: STRtree


@dataclass(frozen=True)
class GroundEdit:
    tile_name: str
    index: int
    raw: bytes
    replacement: bytes
    removed_area_m2: float


@dataclass(frozen=True)
class FoundationQuad:
    name: str
    points: tuple[Point, Point, Point, Point]


@dataclass(frozen=True)
class MasaratSupport:
    quads: tuple[FoundationQuad, ...]
    minimum_toe_burial_m: float
    maximum_exposed_basement_m: float
    maximum_ground_above_entry_m: float
    fence_minimum_burial_m: float
    entrance_step_m: float
    retained_entrance_grade_percent: float
