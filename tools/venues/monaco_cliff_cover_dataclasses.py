"""Source guards and material-only change receipt for the lower Monaco cliff."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from pydantic import ConfigDict, Field, FiniteFloat

XY = tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class CliffFormalGuard:
    name: str
    wgs84_lonlat: tuple[XY, ...]
    expected_native_xy_m: tuple[XY, ...]


@dataclass(frozen=True)
class CliffCoverSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid')

    origin_lat_lon: XY
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    wood_osm_id: Literal[967508764]
    wood_wgs84_lonlat: tuple[XY, ...]
    expected_wood_xy_m: tuple[XY, ...]
    formal_guards: tuple[CliffFormalGuard, ...]
    expected_domain_wkt: str
    expected_changed_faces: Annotated[int, Field(gt=0)]
    expected_face_area_sum_m2: Annotated[FiniteFloat, Field(gt=0)]
    protected_source_sha256: dict[str, str]


@dataclass(frozen=True)
class CliffCoverChange:
    changed_tiles: tuple[str, ...]
    changed_faces: int
    changed_face_area_sum_m2: float
    unchanged_rows_in_examined_tiles: int
    held_crossing_faces: int
    maximum_face_outside_domain_m2: float
