from __future__ import annotations

from dataclasses import dataclass

from pydantic import FiniteFloat


@dataclass(frozen=True)
class WoodlandPatch:
    source_id: str
    component: int
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
    leaf_type: str
    leaf_cycle: str
    name: str
    source_tags: dict[str, str]
