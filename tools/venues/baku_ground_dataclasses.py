from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Base64Bytes, Field, FiniteFloat


@dataclass(frozen=True)
class BarrierSupportSource:
    retained_box_id: int
    top: tuple[Point, Point, Point]
    bottom: tuple[Point, Point, Point]


@dataclass(frozen=True)
class ControlFieldSource:
    version: Literal[1]
    points: list[Point]
    faces: list[tuple[int, int, int]]
    maximum_projection_m: Annotated[FiniteFloat, Field(gt=0, le=0.00025)]
    source_note: str
    patch_domain_wkt: str
    body_cutouts_wkt: str
    concrete_core_wkt: str
    rebuild_window_xy_m: tuple[float, float, float, float]
    protected_source_paths: list[str]
    barrier_supports: list[BarrierSupportSource] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.points or not self.faces:
            raise ValueError("The Baku public field must contain points and faces")
        if any(i < 0 or i >= len(self.points) for face in self.faces for i in face):
            raise ValueError("The Baku public field contains an invalid vertex index")


@dataclass(frozen=True)
class PackedPatchRow:
    tile: str
    material: str
    payload: Annotated[Base64Bytes, Field(min_length=96, max_length=96)]
    copies: Annotated[int, Field(gt=0)]


@dataclass(frozen=True)
class GroundPatchSource:
    version: Literal[1]
    protected_source_sha256: dict[str, str]
    removals: list[PackedPatchRow]
    additions: list[PackedPatchRow]
    source_note: str


@dataclass(frozen=True)
class PackedTriangle:
    tile: str
    material: str
    payload: bytes
    points: tuple[Point, Point, Point]
    attributes: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]
