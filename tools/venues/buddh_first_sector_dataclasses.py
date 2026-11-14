from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from circuit_dataclasses import Point, RoadStation
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class WidthTarget:
    station_m: float
    width_m: float
    manual_allowance_m: float
    source_note: str


@dataclass(frozen=True)
class RaisedCurb:
    name: str
    start_m: float
    end_m: float
    side: Literal[-1, 1]
    width_m: float
    height_m: float
    source_note: str


@dataclass(frozen=True)
class FirstSectorProposal:
    baseline_road_sha256: str
    start_m: float
    end_m: float
    targets: list[WidthTarget]
    raised_curbs: list[RaisedCurb]
    t1_outer_reaches_m: list[tuple[float, float]]
    t3_blue_widths_m: list[tuple[float, float]]
    t3_gravel_outer_reaches_m: list[tuple[float, float]]
    source_interpretation: str


@dataclass(frozen=True)
class BaselineFace:
    points: tuple[Point, Point, Point]
    plan: Polygon
    material: str
    source_file: str
    row_index: int
    raw: bytes


@dataclass(frozen=True)
class RetainedRunoff:
    start_m: float
    end_m: float
    side: int
    width_m: float


@dataclass(frozen=True)
class RetainedBaseline:
    native_source_sha256: str
    runtime_source_sha256: str
    road_source_sha256: str
    length_m: float
    sample_count: int
    expected_scene_scale: float
    expected_origin_latitude: float
    expected_origin_longitude: float
    spatial_rows_sha256: str
    width_controls: list[tuple[float, float]]
    shoulder_controls: list[tuple[float, float, float]]
    runtime_minima: list[RetainedRunoff]
    scalar_rows_sha256: str
    source_note: str


@dataclass(frozen=True)
class NativeCurve:
    positions: tuple[float, ...]
    values: tuple[float, ...]


NativeVertex = tuple[float, float, float, float, float, float, float, float]


@dataclass(frozen=True)
class SurfaceFace:
    vertices: tuple[NativeVertex, NativeVertex, NativeVertex]
    points: tuple[Point, Point, Point]
    plan: Polygon
    material: str
    tile_name: str
    offset: int
    raw: bytes


@dataclass(frozen=True)
class SurfaceRole:
    name: str
    material: str
    plan: BaseGeometry
    contact: Literal["paved", "gravel", "grass"]
    rebuild: bool = True


@dataclass(frozen=True)
class ContactTriangle:
    points: tuple[Point, Point, Point]
    surface: Literal["paved", "gravel", "grass"]
    support: tuple[Point, Point, Point] | None = None
    height_only: bool = False
    source_plan: tuple[Point, Point, Point] | None = None


@dataclass(frozen=True)
class RetainedSplitOwner:
    tile_name: str
    old_offset: int
    old_raw: bytes
    fragments: tuple[bytes, ...]


@dataclass(frozen=True)
class ClassificationTriangle:
    points: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    surface: Literal["paved", "gravel"]


@dataclass(frozen=True)
class FirstSectorState:
    proposal: FirstSectorProposal
    baseline: RetainedBaseline
    retained_road: tuple[RoadStation, ...]
    candidate_road: tuple[RoadStation, ...]
    changed_cells: tuple[int, ...]


@dataclass(frozen=True)
class FirstSectorResult:
    contact: tuple[ContactTriangle, ...]
    changed_tiles: tuple[str, ...]
    preserved_raw_rows: int
    split_rows: int
    removed_road_rows: int
    removed_curb_rows: int
    emitted_floor_triangles: int
    inferred_under_curb_ground_m2: float
    role_areas_m2: dict[str, float]
    replacement_domain: BaseGeometry
    low_apron_closure_max_height_m: float
    low_apron_closure_missing_m: float
    retained_splits: tuple[RetainedSplitOwner, ...] = ()
