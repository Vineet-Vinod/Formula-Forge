"""Finite photographed natural sites and explicit architecture/path exclusions."""

from dataclasses import dataclass

from pydantic import FiniteFloat


@dataclass(frozen=True)
class NaturalRegion:
    name: str
    vertices: tuple[tuple[FiniteFloat, FiniteFloat], ...]


@dataclass(frozen=True)
class NaturalExclusion:
    source_id: str
    vertices: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    linear: bool
    buffer_m: FiniteFloat


@dataclass(frozen=True)
class NaturalSites:
    origin_latitude: FiniteFloat
    origin_longitude: FiniteFloat
    uniform_scale: FiniteFloat
    regions: tuple[NaturalRegion, ...]
    exclusions: tuple[NaturalExclusion, ...]
    road_and_protection_margin_m: FiniteFloat
    building_margin_m: FiniteFloat
    source_input_sha256: dict[str, str]
