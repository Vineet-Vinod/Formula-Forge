from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class GroundInterval:
    along_m: tuple[float, float]
    points: tuple[Point, Point]
    ground_file: str
    ground_row: int
    ground_material: str


@dataclass(frozen=True)
class MuseumEdge:
    ring: Literal["outer_xy", "courtyard_xy"]
    edge: int
    role: Literal[
        "connector_side",
        "northwest_side",
        "front_west",
        "front_center",
        "front_east",
        "return",
        "held",
    ]
    length_m: float
    segments: list[GroundInterval]
    missing_length_m: float


@dataclass(frozen=True)
class MuseumFooting:
    paths: list[MuseumEdge]
    total_boundary_m: float
    total_missing_m: float


@dataclass(frozen=True)
class MuseumLayout:
    outer_xy: list[tuple[float, float]]
    courtyard_xy: list[tuple[float, float]]


@dataclass(frozen=True)
class MuseumClipProof:
    changed_rows: int
    removed_area_m2: float
    original_outside_vertices: int
    missing_original_outside_vertices: int
    maximum_new_plane_error_m: float
    maximum_encoding_area_difference_m2: float
    minimum_new_triangle_area_m2: float
    parent_addition_sha256: dict[str, list[str]]


@dataclass(frozen=True)
class DebourDimensions:
    cornice_m: float = 14.4
    cornice_uncertainty_m: float = 3.0
    ground_opening_m: tuple[float, float] = (1.0, 6.0)
    upper_opening_m: tuple[float, float] = (8.0, 12.5)
    portico_top_m: float = 7.1
    portico_depth_m: float = 2.6
    gallery_depth_m: float = 1.1
    crown_rise_m: float = 4.0


@dataclass(frozen=True)
class MuseumRecord:
    name: Literal["gymnasium", "debour"]
    osm_id: int
    layout: MuseumLayout
    footing: MuseumFooting
    datum_m: FiniteFloat
    datum_uncertainty_m: Annotated[FiniteFloat, Field(gt=0)]
    source_note: str


@dataclass(frozen=True)
class MuseumSource:
    version: Literal[1]
    protected_source_sha256: dict[str, str]
    ground_supports: Annotated[list[PackedPatchRow], Field(min_length=1)]
    records: Annotated[list[MuseumRecord], Field(min_length=2, max_length=2)]
    debour_dimensions: DebourDimensions
    source_note: str

    def __post_init__(self) -> None:
        if {record.name for record in self.records} != {"gymnasium", "debour"}:
            raise ValueError(
                "Baku museum source must contain both registered properties"
            )
        if any(record.footing.total_missing_m > 1e-6 for record in self.records):
            raise ValueError("Baku museum source lacks a complete wall-foot profile")
