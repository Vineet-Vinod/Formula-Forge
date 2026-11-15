from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

XY = tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class FoundationSource:
    ring_xy_m: tuple[XY, ...]
    floor_relative_m: FiniteFloat
    body_height_m: Annotated[FiniteFloat, Field(gt=20, le=40)] = 27.2
    corner_radius_m: Annotated[FiniteFloat, Field(gt=0, le=6)] = 3.6
    dome_radius_m: Annotated[FiniteFloat, Field(gt=0, le=4)] = 2.8
    body_height_uncertainty_m: Annotated[FiniteFloat, Field(gt=0, le=8)] = 4.0
    crown_height_uncertainty_m: Annotated[FiniteFloat, Field(gt=0, le=8)] = 4.0
    floor_bands_m: tuple[FiniteFloat, ...] = (0., 4.8, 9.05, 13.3, 17.55, 21.8, 25.3)


@dataclass(frozen=True)
class FoundationCorner:
    center: XY
    radius_m: float
    start_angle_rad: float
    sweep_rad: float
    floor_relative_m: FiniteFloat

    def point(self, u: float, z: float, depth: float = 0.) -> Point:
        import math

        angle = self.start_angle_rad + u / self.radius_m
        radius = self.radius_m + depth
        return (self.center[0] + radius * math.cos(angle),
                self.center[1] + radius * math.sin(angle), self.floor_relative_m + z)


@dataclass(frozen=True)
class FoundationRecipe:
    osm_id: int
    origin_lat_lon: XY
    uniform_scale: FiniteFloat
    expected_legacy_height_m: FiniteFloat
    expected_legacy_rows: Annotated[int, Field(gt=0, le=400000)]
    legacy_counter_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    expected_candidate_rows: Annotated[int, Field(gt=0, le=400000)]
    candidate_counter_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    geometry: FoundationSource


@dataclass(frozen=True)
class FoundationChange:
    removed_generic_rows: int
    emitted_rows: int
    preserved_parent_rows: int
    parent: str
