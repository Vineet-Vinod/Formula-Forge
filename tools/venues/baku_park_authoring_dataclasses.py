from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat

from venues.baku_ground_dataclasses import PackedPatchRow

Index = Annotated[int, Field(ge=0)]


@dataclass(frozen=True)
class ParkControlVertex:
    position_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    source_normal: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    uv: tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class ParkControlFace:
    tile: str
    material: str
    vertices: tuple[Index, Index, Index]
    copies: Annotated[int, Field(gt=0)]


@dataclass(frozen=True)
class ParkAuthoredGround:
    version: Literal[1]
    protected_source_sha256: dict[str, str]
    removals: tuple[PackedPatchRow, ...]
    vertices: tuple[ParkControlVertex, ...]
    faces: tuple[ParkControlFace, ...]
    source_note: str
    expected_output_sha256: str
    coordinate_frame: str
    source_constraints: str
