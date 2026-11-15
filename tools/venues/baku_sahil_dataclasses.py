from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CrownNormalField:
    origin_height_fraction: float = 0.30
    vertical_radius_fraction: float = 0.70


@dataclass(frozen=True)
class SahilShadingSource:
    version: Literal[1]
    normal_field: CrownNormalField
    material_recipe_sha256: str


@dataclass(frozen=True)
class SahilMaterialSource:
    version: Literal[1]
    accepted_parent_asset: str
    parent_sha256: str
    accepted_instance_asset: str
    instance_sha256: str
    actual_instance_asset: str
    accepted_atlas_asset: str
    atlas_sha256: str
    neutral_normal_asset: str
    normal_sha256: str
    target_parent_name: Literal["BakuSahilCanopySurface"]
    target_instance_name: Literal["BakuSahilCanopy"]
