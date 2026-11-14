from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PavementWidths:
    baseline_road_file: str
    baseline_road_sha256: str
