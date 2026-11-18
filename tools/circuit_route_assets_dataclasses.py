from __future__ import annotations

from dataclasses import dataclass, field

from circuit_escapes_dataclasses import PaintDomain
from circuit_portals_dataclasses import Portal


@dataclass(frozen=True)
class RouteMesh:
    name: str
    file: str
    materials: list[str]
    bounds: list[float]
    triangles: int
    sha256: str


@dataclass(frozen=True)
class RouteAssets:
    circuit: str
    version: int
    frame: str
    tiles: list[RouteMesh]
    portals: list[Portal]
    paint_domains: list[PaintDomain]
    source_sha256: dict[str, str]
    pit_lane_file: str | None
    protection_file: str
    source_note: str
    escape_surface_file: str | None = None
    cosmetic_portals: list[Portal] = field(default_factory=list)


@dataclass(frozen=True)
class RoutePlanEntry:
    circuit: str
    manifest: str
    content_dir: str
    index: str


@dataclass(frozen=True)
class RoutePlan:
    circuits: list[RoutePlanEntry]
    receipt: str
    state: str
