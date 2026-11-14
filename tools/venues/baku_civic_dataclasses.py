from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat
from shapely.geometry import LineString, Polygon


@dataclass(frozen=True)
class CourtFrontageSource:
    osm_id: int
    height_m: Annotated[FiniteFloat, Field(gt=0)]
    floor_bands_m: Annotated[list[FiniteFloat], Field(min_length=5, max_length=5)]
    entrance_edge: int
    entrance_rise_m: Annotated[FiniteFloat, Field(ge=0, le=1)]
    height_uncertainty_m: Annotated[FiniteFloat, Field(gt=0)]
    track_front_edges: list[int]
    primary_photos: list[str]
    source_note: str

    def __post_init__(self) -> None:
        if self.floor_bands_m != sorted(set(self.floor_bands_m)):
            raise ValueError("Court floor bands must increase")
        if self.floor_bands_m[0] != 0 or self.floor_bands_m[-1] != self.height_m:
            raise ValueError("Court floor bands must span the retained envelope")


@dataclass(frozen=True)
class CourtFace:
    start: Point
    tangent: Point
    outward: Point
    length_m: float
    source_length_m: float


@dataclass(frozen=True)
class CourtOpening:
    shape: Polygon
    door: bool
    arch_spring_m: float | None


@dataclass(frozen=True)
class StreetGrade:
    line: LineString
    start_z_m: float
    end_z_m: float


@dataclass(frozen=True)
class NorthFrontageSource:
    osm_id: int
    street_edge: int
    main_threshold_m: FiniteFloat
    body_height_m: Annotated[FiniteFloat, Field(gt=0)]
    height_uncertainty_m: Annotated[FiniteFloat, Field(gt=0)]
    upper_bays: Annotated[int, Field(ge=1, le=20)]
    uncertainty_m: Annotated[FiniteFloat, Field(gt=0)]
    primary_photos: list[str]
    source_note: str
