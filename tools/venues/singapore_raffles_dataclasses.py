"""Retained source controls for the Raffles Avenue scenery."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SingaporeGroundParcel:
    name: str
    source_way_id: int
    ring_lonlat: list[tuple[float, float]]
    anchor_native_station_m: float
    height_offset_m: float
    height_uncertainty_m: float
    material: str
    source_note: str
