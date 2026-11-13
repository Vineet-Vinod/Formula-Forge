"""Retained ground observations and estimated Sachs grandstand section."""

from dataclasses import dataclass


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
