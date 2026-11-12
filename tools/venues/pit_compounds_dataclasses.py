"""Controls for the three footprint-registered pit reconstructions."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PitCompound:
    osm_id: int
    name: str
    body_height_m: float
    floors: int
    garage_height_m: float
    bay_spacing_m: float
    roof_form: Literal["folded", "terrace", "eaves"]
    garage_count: int | None = None
