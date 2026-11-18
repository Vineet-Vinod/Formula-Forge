"""Jeddah fixture feet and the complete paved-area clearance witness."""

from dataclasses import dataclass, field

from circuit_dataclasses import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import PreparedGeometry


@dataclass(frozen=True)
class FixtureFoot:
    station_m: float
    side: int
    preferred: Point
    placed: Point
    relocation_m: float
    paving_clearance_m: float


@dataclass
class FixtureSite:
    paving: BaseGeometry
    forbidden: PreparedGeometry
    feet: list[FixtureFoot] = field(default_factory=list)
