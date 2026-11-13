from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from pydantic import Field, FiniteFloat, JsonValue

Bounds = tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class CityPartitionRecipe:
    cell_m: Annotated[FiniteFloat, Field(ge=60, le=360)]


@dataclass(frozen=True)
class SceneTile:
    name: str
    file: str
    materials: list[str]
    bounds: Bounds
    triangles: Annotated[int, Field(gt=0, le=400_000)]
    sha256: str
    source_parent: str | None = None


@dataclass(frozen=True)
class PartitionParent:
    name: str
    source_sha256: str
    triangles: int
    children: list[str]
    triangle_multiset_equal: bool


@dataclass(frozen=True)
class CityPartitionProof:
    cell_m: float
    original_manifest_sha256: str
    parents: list[PartitionParent]
    superseded_assets: list[str]
    residency_bounds_preserved: bool = True


@dataclass(frozen=True)
class SceneManifest:
    slug: str
    content_dir: str
    tiles: list[SceneTile]
    landmarks: list[dict[str, JsonValue]] = field(default_factory=list)
    vegetation: list[dict[str, JsonValue]] = field(default_factory=list)
    surface_ranges: list[dict[str, JsonValue]] = field(default_factory=list)
    city_partition: CityPartitionProof | None = None
