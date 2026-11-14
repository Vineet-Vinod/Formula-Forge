"""Source roles and original packed surface attributes for the west ravine."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat
from shapely.geometry import Polygon

XY = tuple[float, float]
NativeVertex = tuple[float, float, float, float, float, float, float, float]
SurfaceClass = Literal["lawn", "ivy", "rock", "paved", "natural"]
SourceCover = Literal[
    "Ivy/Garden cover candidate",
    "Ivy candidate",
    "Ivy/Rock mixed candidate",
    "Rock candidate",
    "Paved ground candidate",
]


@dataclass(frozen=True)
class SurfaceRegion:
    name: str
    plan: Polygon
    surface: SurfaceClass


@dataclass(frozen=True)
class SurfaceFace:
    vertices: tuple[NativeVertex, NativeVertex, NativeVertex]
    xy: tuple[XY, XY, XY]
    plan: Polygon
    material: str


@dataclass(frozen=True)
class SurfaceChange:
    tiles: tuple[str, ...]
    original_faces_split: int
    complete_outside_rows: int
    classified_area_m2: float
    emitted_fragments: int


@dataclass(frozen=True)
class SourceVertex:
    native_xy_m: tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class SourceRegion:
    id: str
    class_name: Annotated[SourceCover, Field(alias="class")]
    vertices: Annotated[tuple[SourceVertex, ...], Field(min_length=3)]


@dataclass(frozen=True)
class SourceExclusion:
    vertices: tuple[SourceVertex, ...] = ()


@dataclass(frozen=True)
class SurfaceFrame:
    scene_origin_latitude: FiniteFloat
    scene_origin_longitude: FiniteFloat
    scene_scale: FiniteFloat


@dataclass(frozen=True)
class SourceDocument:
    transform: SurfaceFrame
    candidate_regions: tuple[SourceRegion, ...]
    explicit_exclusions: tuple[SourceExclusion, ...]
