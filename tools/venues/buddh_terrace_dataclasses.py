from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat
from shapely.geometry import Polygon

XY = tuple[float, float]


@dataclass(frozen=True)
class TerraceSpec:
    front_a: XY
    front_b: XY
    back_a: XY
    front_a_z_m: FiniteFloat
    front_b_z_m: FiniteFloat
    rows: Annotated[int, Field(ge=16, le=24)]
    riser_m: Annotated[FiniteFloat, Field(ge=0.32, le=0.45)]
    bays: Annotated[int, Field(ge=4, le=8)]
    aisle_width_m: Annotated[FiniteFloat, Field(ge=1.2, le=3)]
    source_note: str


@dataclass(frozen=True)
class GroundFace:
    points: tuple[Point, Point, Point]
    plan: Polygon
    source_tile: str
    source_offset: int


@dataclass(frozen=True)
class FootWitness:
    footprint: Polygon
    minimum_ground_m: float
    maximum_ground_m: float
    base_z_m: float
    plinth_top_z_m: float
    column_top_z_m: float
    missing_ground_m2: float
    actual_source_rows: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class TerraceGeometry:
    feet: tuple[FootWitness, ...]
    deck_top_triangles: int
    crowd_triangles: int
    occupied_plan: Polygon
    minimum_deck_clearance_m: float


@dataclass(frozen=True)
class PalmPlacement:
    index: Annotated[int, Field(ge=0, le=21)]
    base: Point
    height_m: Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class TerraceRecipe:
    expected_origin_latitude: FiniteFloat
    expected_origin_longitude: FiniteFloat
    expected_scene_scale: FiniteFloat
    geometry: TerraceSpec
    original_palms: Annotated[
        tuple[PalmPlacement, ...], Field(min_length=22, max_length=22)
    ]
    excluded_palm_indices: tuple[int, ...]
    source_limits: str


@dataclass(frozen=True)
class FrozenTerraceTile:
    name: str
    ordered_rows_sha256: str


@dataclass(frozen=True)
class FrozenTerraceProof:
    candidate_tiles: tuple[FrozenTerraceTile, ...]
