from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field

from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class HotelDimensions:
    cornice_m: float = 34.0
    mansard_m: float = 5.2
    corner_radius_m: float = 5.0
    body_floor_bands_m: tuple[float, ...] = (
        0.0,
        8.6,
        12.8,
        17.0,
        20.4,
        23.8,
        27.2,
        30.6,
        34.0,
    )
    roof_material: str = "BakuHotelCopper"


@dataclass(frozen=True)
class HotelLayout:
    rear_start: Point
    rear_end: Point
    southwest_return_end: Point
    datum_m: float
    rear_stack_along_m: tuple[float, ...]
    blind_mass_along_m: tuple[float, float]


@dataclass(frozen=True)
class HotelWall:
    edge_name: str
    start: Point
    end: Point
    stack_along_m: tuple[float, ...]
    feet_along_height_m: tuple[tuple[float, float], ...]
    source_status: str


@dataclass(frozen=True)
class HotelCupola:
    center: Point
    radius_m: float
    heading_rad: float
    source_status: str


@dataclass(frozen=True)
class HotelSource:
    osm_id: Literal[152190583]
    outer_xy: tuple[tuple[float, float], ...]
    literal_outer_xy: tuple[tuple[float, float], ...]
    datum_m: float
    walls: tuple[HotelWall, ...]
    cupolas: tuple[HotelCupola, ...]
    rear_layout: HotelLayout
    dimensions: HotelDimensions
    source_note: str


@dataclass(frozen=True)
class HotelGroundSource:
    version: Literal[1]
    recipe_sha256: str
    protected_source_sha256: dict[str, str]
    ground_supports: Annotated[list[PackedPatchRow], Field(min_length=1)]
    source_note: str
