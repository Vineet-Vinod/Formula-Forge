"""Source controls for Villa Hermosa's measured envelope and estimated ridge."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, FiniteFloat
from pydantic.dataclasses import dataclass


@dataclass(frozen=True, config=ConfigDict(extra='forbid'))
class HermosaArchitecture:
    origin_lat_lon: tuple[FiniteFloat, FiniteFloat]
    uniform_scale: FiniteFloat
    relative_datum_m: FiniteFloat
    osm_id: Literal[94399624]
    source_id: Literal['BATIMENT0000000074074444']
    body_wgs84: Annotated[tuple[tuple[FiniteFloat, FiniteFloat], ...], Field(min_length=4)]
    eaves_wgs84: Annotated[tuple[tuple[FiniteFloat, FiniteFloat, FiniteFloat], ...], Field(min_length=4, max_length=4)]
    ridge_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]
    ridge_absolute_m: FiniteFloat
    ground_grid_file: str
    floor_base_absolute_m: FiniteFloat
    floor_height_m: Annotated[FiniteFloat, Field(gt=2, lt=5)]
    floors: Literal[6]
    roof_material: Literal['Roof', 'Steel']
