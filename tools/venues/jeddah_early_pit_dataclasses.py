"""Finite controls for the source-observed STC pit approach."""

from dataclasses import dataclass
from typing import Annotated

from circuit_portals_dataclasses import Barrier, Portal
from pit_routes_dataclasses import PitFloorTriangle
from pydantic import Field, FiniteFloat


@dataclass(frozen=True)
class EntryWall:
    start_distance_m: FiniteFloat
    end_distance_m: FiniteFloat
    barrier: Barrier
    material: str
    privacy: bool
    first_floor_m: FiniteFloat
    last_floor_m: FiniteFloat


@dataclass(frozen=True)
class EntryBridge:
    left: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    right: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    underside_m: Annotated[FiniteFloat, Field(gt=0)]
    panel_height_m: Annotated[FiniteFloat, Field(gt=0)]


@dataclass(frozen=True)
class EarlyPit:
    walls: tuple[EntryWall, ...]
    portals: tuple[Portal, ...]
    bridge: EntryBridge
    source_note: str
    floors: tuple[PitFloorTriangle, ...]
    floor_portals: tuple[Portal, ...]
    source_road_sha256: str
    source_sections_sha256: str
    separator_portals: tuple[Portal, ...]
    separator_paint: tuple[PitFloorTriangle, ...]
