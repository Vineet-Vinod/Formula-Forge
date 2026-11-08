from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float, float]


@dataclass(frozen=True)
class BarrierPanel:
    start: float
    end: float
    side: int
    material: str


@dataclass(frozen=True)
class Building:
    osm_id: int
    name: str
    use: str
    height: float
    ring: list[tuple[float, float]]
    tags: dict[str, str]


@dataclass(frozen=True)
class OsmPoint:
    lat: float
    lon: float


@dataclass(frozen=True)
class OsmMember:
    type: str
    ref: int
    role: str = ""
    geometry: list[OsmPoint] = field(default_factory=list)


@dataclass(frozen=True)
class OsmElement:
    type: str
    id: int
    tags: dict[str, str] = field(default_factory=dict)
    geometry: list[OsmPoint] = field(default_factory=list)
    nodes: list[int] = field(default_factory=list)
    members: list[OsmMember] = field(default_factory=list)
    lat: float = 0
    lon: float = 0


@dataclass(frozen=True)
class OsmData:
    elements: list[OsmElement]


@dataclass(frozen=True)
class Catalogue:
    slug: str
    content_dir: str
    length_m: float
    start_station_m: float
    deck_separation: bool


@dataclass(frozen=True)
class Origin:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Route:
    uniform_scale: float


@dataclass(frozen=True)
class Provenance:
    origin: Origin
    route: Route
    circuit: str = ""


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
        return (
            self.x + self.ty * lane,
            self.y - self.tx * lane,
            self.z + self.bank * lane + lift,
        )


@dataclass
class MeshTile:
    triangles: bytearray = field(default_factory=bytearray)
    minimum: list[float] = field(default_factory=lambda: [float("inf")] * 3)
    maximum: list[float] = field(default_factory=lambda: [-float("inf")] * 3)
    materials: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TerrainGrid:
    x: float
    y: float
    step: float
    columns: int
    rows: int
    heights: tuple[float, ...]
