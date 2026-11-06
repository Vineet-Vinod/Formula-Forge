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
    left_shoulder: float = 2.2
    right_shoulder: float = 2.2

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


@dataclass(frozen=True)
class LandmarkProfile:
    name: str
    style: str
    height_m: float
    facade: str
    crown_m: float


@dataclass(frozen=True)
class LeaningTower:
    name: str
    height_m: float
    north_lean_deg: float


@dataclass(frozen=True)
class RoofShard:
    corners: list[tuple[float, float]]
    ridge: list[Point]


@dataclass(frozen=True)
class CurbRun:
    start_m: float
    end_m: float
    side: int


@dataclass(frozen=True)
class RouteSector:
    name: str
    start_m: float
    end_m: float
    tree_spacing_m: float
    palm_every: int
    wall_panels: list[str]


@dataclass(frozen=True)
class StreetDisplay:
    source_xy_m: tuple[float, float]
    width_m: float
    depth_m: float
    height_m: float
    base_height_m: float
    orientation_deg: float
    reference: str


@dataclass(frozen=True)
class EscapeRegion:
    name: str
    turn: int
    paint: str
    ring: list[tuple[float, float]]
    origin: Point
    direction: tuple[float, float]
    grade: float


@dataclass(frozen=True)
class TowerRoof:
    axis_x: float
    axis_y: float
    middle: float
    half_span: float
    sag: float

    def offset(self, x: float, y: float) -> float:
        t = max(-1.0, min(1.0, (x*self.axis_x + y*self.axis_y-self.middle)/self.half_span))
        return -self.sag * (1-t*t)
