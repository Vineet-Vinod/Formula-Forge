"""Retained ground observations and estimated Sachs grandstand section."""

from dataclasses import dataclass

from circuit_dataclasses import Point


@dataclass(frozen=True)
class SachsGroundAnchor:
    ring_index: int
    longitude: float
    latitude: float
    height_nhn_m: float
    url: str
    response_sha256: str


@dataclass(frozen=True)
class SachsStandSource:
    ground_anchors: list[SachsGroundAnchor]
    front_ring_indices: tuple[int, int] = (3, 17)
    row_count: int = 27
    row_pitch_m: float = 1.0
    row_rise_m: float = 0.41
    first_floor_m: float = 0.75
    canopy_above_front_m: float = 15.1
    section_uncertainty_m: float = 2.0


@dataclass(frozen=True)
class SachsGroundTriangle:
    material: str
    points: tuple[Point, Point, Point]
    uv: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    normals: tuple[Point, Point, Point]


@dataclass(frozen=True)
class SachsForecourtSource:
    uniform_scale: float
    ground_datum_nhn_m: float
    grid_x_m: float
    grid_y_m: float
    grid_step_m: float
    cells: list[tuple[int, int]]
    triangles: list[SachsGroundTriangle]
    width_m: float = 4.5
    full_front_length_m: float = 9.0
    taper_end_m: float = 14.0
