from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import FiniteFloat


@dataclass(frozen=True)
class WaterPolygon:
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]] = field(default_factory=list)


@dataclass(frozen=True)
class PierDeck:
    osm_id: int
    ring: list[tuple[FiniteFloat, FiniteFloat]]
    level_m: FiniteFloat


@dataclass(frozen=True)
class WaterWitness:
    name: str
    longitude: FiniteFloat
    latitude: FiniteFloat
    water: bool


@dataclass(frozen=True)
class CoastalWater:
    water_level_m: FiniteFloat
    polygons: list[WaterPolygon]
    piers: list[PierDeck]
    witnesses: list[WaterWitness]
