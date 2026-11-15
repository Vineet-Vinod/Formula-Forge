"""Literal garden controls and mapped-tree bindings for Villa de Rome."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from circuit_dataclasses import Point
from pydantic import ConfigDict, Field, FiniteFloat

from venues.monaco_terrace_dataclasses import TerraceAudit, TerraceSpec

XY = tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class RomeGardenTree:
    osm_id: Literal[5931906972, 5931906973]
    wgs84_lonlat: XY
    expected_old_base: Point
    height_m: Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class RomeGardenSource:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra='forbid', allow_inf_nan=False)

    origin_lat_lon: XY
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    relative_datum_m: FiniteFloat
    owner_osm_id: Literal[94400097]
    owner_wgs84_lonlat: tuple[XY, ...]
    garden_wgs84_lonlat: tuple[XY, ...]
    expected_garden_xy_m: tuple[XY, ...]
    apron_wgs84_lonlat: tuple[XY, ...]
    expected_apron_xy_m: tuple[XY, ...]
    front_wgs84_lonlat: tuple[XY, ...]
    expected_front_xy_m: tuple[XY, ...]
    expected_domain_wkt: str
    body_guard_m: Annotated[FiniteFloat, Field(gt=0)]
    mapped_trees: tuple[RomeGardenTree, RomeGardenTree]
    terrace: TerraceSpec
    protected_source_sha256: dict[str, str]


@dataclass(frozen=True)
class RomeGardenChange:
    geometry: TerraceAudit
    previous_tree_bases: tuple[Point, ...]
    new_tree_bases: tuple[Point, ...]
    unrelated_city_rows_preserved: int
    old_street_rows_preserved: int
    minimum_packed_normal_alignment: float
    minimum_actual_packed_tree_burial_m: float
    lawn_missing_area_m2: float
    lawn_extra_area_m2: float
