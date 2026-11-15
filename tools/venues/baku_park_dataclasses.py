from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from venues.baku_ground_dataclasses import PackedPatchRow
from venues.baku_waterfront_dataclasses import ParkTree


@dataclass(frozen=True)
class ParkOffice:
    osm_id: Literal[279935608]
    old_base_m: float
    new_base_m: float
    rows: int
    old_counter_sha256: str
    new_counter_sha256: str
    height_m: float = 6.8
    datum_uncertainty_m: float = 2.0


@dataclass(frozen=True)
class ParkRecipe:
    version: Literal[1]
    origin_lat_lon: tuple[float, float]
    uniform_scale: float
    ground_delta_path: str
    ground_delta_sha256: str
    original_trees: tuple[ParkTree, ...]
    trees: tuple[ParkTree, ...]
    foreground_seed_ids: tuple[int, ...]
    original_tree_rows: int
    original_tree_counter_sha256: str
    tree_rows: int
    tree_counter_sha256: str
    office: ParkOffice
    supporting_ground: tuple[PackedPatchRow, ...]
    source_note: str


@dataclass(frozen=True)
class ParkChange:
    ground_removed_rows: int
    ground_added_rows: int
    old_tree_rows: int
    new_tree_rows: int
    translated_office_rows: int
    supporting_ground_rows: int
    preserved_city_rows: int
    changed_parents: tuple[str, ...]
