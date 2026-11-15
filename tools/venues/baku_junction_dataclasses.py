from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class JunctionRecipe:
    version: Literal[1]
    origin_lat_lon: tuple[float, float]
    uniform_scale: FiniteFloat
    island_osm_id: Literal[270087949]
    island_ring_lat_lon: tuple[tuple[float, float], ...]
    island_area_m2: Annotated[FiniteFloat, Field(gt=0)]
    estimated_curb_rise_m: Annotated[FiniteFloat, Field(gt=0, le=0.3)]
    estimated_outward_crossfall: Annotated[FiniteFloat, Field(ge=0, le=0.03)]
    ground_delta_file: str
    ground_delta_sha256: str
    removed_rows: Annotated[int, Field(gt=0)]
    new_rows: Annotated[int, Field(gt=0)]
    curb_faces: Annotated[int, Field(gt=0)]
    source_note: str


@dataclass(frozen=True)
class JunctionChange:
    removed_rows: int
    new_rows: int
    curb_faces: int
