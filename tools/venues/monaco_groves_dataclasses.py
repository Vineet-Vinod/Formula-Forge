"""Bounded canopy estimates and exact rendered-ground witnesses for the west bank."""

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from pydantic import ConfigDict, Field, FiniteFloat


@dataclass(frozen=True)
class BankCanopy:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    base: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    height_m: Annotated[FiniteFloat, Field(ge=8, le=17)]
    seed: int
    source_pixel_xy: tuple[FiniteFloat, FiniteFloat]
    crown_diameter_range_m: tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class GroveSupport:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    tile: Annotated[str, Field(pattern=r'^Tile_Street_')]
    material: Literal['Grass', 'Runoff', 'MonacoIvyGround', 'MonacoRockGround']
    attributes_hex: Annotated[str, Field(pattern=r'^[0-9a-f]{192}$')]


@dataclass(frozen=True)
class WestBankGroves:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    circuit: Literal['monaco']
    origin_lat_lon: tuple[FiniteFloat, FiniteFloat]
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    relative_datum_m: FiniteFloat
    held_roof_ring_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    canopies: Annotated[tuple[BankCanopy, ...], Field(min_length=1, max_length=12)]
    supports: Annotated[tuple[GroveSupport, ...], Field(min_length=1, max_length=64)]
    source_notes: tuple[str, ...]
