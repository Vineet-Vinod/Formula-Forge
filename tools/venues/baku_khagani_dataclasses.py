from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from circuit_dataclasses import Point

from venues.baku_civic_dataclasses import CourtFace
from venues.baku_ground_dataclasses import PackedPatchRow


@dataclass(frozen=True)
class FrontWall:
    osm_id: int
    edge: int
    face: CourtFace
    feet_m: tuple[tuple[float, float], ...]
    original_along_m: tuple[float, float]


@dataclass(frozen=True)
class LibrarySource:
    front: FrontWall
    wing_height_m: float = 15.6
    wing_uncertainty_m: float = 3.0
    gallery_depth_m: float = 3.2
    gallery_depth_uncertainty_m: float = 1.0
    bays: int = 22
    bay_count_uncertainty: int = 3


@dataclass(frozen=True)
class HistoricFront:
    address: Literal[23, 25, 27]
    wall: FrontWall
    cornice_m: float
    roof_rise_m: float
    cornice_uncertainty_m: float = 3.0
    roof_uncertainty_m: float = 1.0
    return_wall: FrontWall | None = None


@dataclass(frozen=True)
class StreetTree:
    base: Point
    height_m: float
    crown_width_m: float
    seed: int
    parcel: Literal["sahil", "sidewalk"]
    source_note: str


@dataclass(frozen=True)
class KhaganiSource:
    version: Literal[1]
    library: LibrarySource
    historic_fronts: tuple[HistoricFront, ...]
    trees: tuple[StreetTree, ...] = ()


@dataclass(frozen=True)
class LegacyRow:
    tile: str
    kind: str
    material: str
    payload: bytes
    edge: int


@dataclass(frozen=True)
class LegacyFamily:
    osm_id: Literal[177428532, 286020256]
    ring: tuple[tuple[float, float], ...]
    height_m: float
    datum_m: float
    emission_sha256: str
    replaced_edges: tuple[int, ...]


@dataclass(frozen=True)
class KhaganiGroundSource:
    version: Literal[1]
    recipe_sha256: str
    canopy_sha256: str
    protected_source_sha256: dict[str, str]
    barriers_csv_sha256: str
    legacy_families: tuple[LegacyFamily, ...]
    ground_supports: list[PackedPatchRow]
    minimum_native_root_embed_m: float
    source_note: str


@dataclass(frozen=True)
class AtlasCrop:
    column: int
    row: int
    left_px: int
    top_px: int
    right_px: int
    bottom_px: int


@dataclass(frozen=True)
class CanopyStyle:
    park_width_multiplier: float = 1.12
    sidewalk_cross_scale: float = 0.62
    trunk_fork_fraction: float = 0.30
    crown_width_uncertainty_m: float = 2.0
    lower_crown_height_uncertainty_m: float = 1.5
