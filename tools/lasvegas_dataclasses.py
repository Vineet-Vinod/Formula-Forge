from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float, float]


@dataclass(frozen=True)
class RoadStation:
    station: float
    x: float
    y: float
    z: float
    tx: float
    ty: float
    half_width: float
    bank: float

    def point(self, lane: float, lift: float = 0.0) -> Point:
        return self.x + self.ty * lane, self.y - self.tx * lane, self.z + self.bank * lane + lift


@dataclass
class MeshTile:
    triangles: bytearray = field(default_factory=bytearray)
    minimum: list[float] = field(default_factory=lambda: [float('inf')] * 3)
    maximum: list[float] = field(default_factory=lambda: [-float('inf')] * 3)
    materials: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TerrainGrid:
    x: float
    y: float
    step: float
    columns: int
    rows: int
    heights: tuple[float, ...]
