from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field

from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class PhilharmonicTower:
    osm_part: int
    center: Point
    axis: Point
    width_m: float = 7.2
    shaft_top_m: float = 17.5
    loggia_top_m: float = 23.0
    lantern_top_m: float = 28.2
    peak_m: float = 32.0
    height_uncertainty_m: float = 6.0


@dataclass(frozen=True)
class PhilharmonicSource:
    base_m: float
    body_top_m: float
    dome_center: Point
    dome_radius_m: float
    towers: tuple[PhilharmonicTower, ...]
    oriel_center: Point = (-1872.839724187898, -920.781576849459, 0.0)
    oriel_radius_m: float = 5.6
    oriel_roof_rise_m: float = 1.3
    oriel_roof_rise_uncertainty_m: float = 0.5


@dataclass(frozen=True)
class UniversityWall:
    edge: int
    start: Point
    end: Point
    feet_along_height_m: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class UniversitySource:
    osm_id: Literal[196291852]
    ring: tuple[tuple[float, float], ...]
    datum_m: float
    walls: tuple[UniversityWall, ...]
    cornice_m: float = 15.0
    mansard_m: float = 2.3
    cornice_uncertainty_m: float = 3.0
    mansard_uncertainty_m: float = 1.0


@dataclass(frozen=True)
class StreetscapeSource:
    version: Literal[1]
    hall_literal_xy: tuple[tuple[float, float], ...]
    hall_cutout_wkb_sha256: str
    hall: PhilharmonicSource
    university: UniversitySource
    source_note: str


@dataclass(frozen=True)
class StreetscapeGroundSource:
    version: Literal[1]
    recipe_sha256: str
    protected_source_sha256: dict[str, str]
    ground_supports: Annotated[list[PackedPatchRow], Field(min_length=1)]
    source_note: str
