"""Pit route controls in source east/north metres, with explicit provenance."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from circuit_portals_dataclasses import Barrier, Portal
from pydantic import Field, FiniteFloat

XY = tuple[float, float]
GeoPoint = tuple[FiniteFloat, FiniteFloat]

@dataclass(frozen=True)
class OsmPoint:
    lat: float
    lon: float

@dataclass(frozen=True)
class OsmMember:
    type: str
    ref: int
    role: str = ''
    geometry: list[OsmPoint] = field(default_factory=list)

@dataclass(frozen=True)
class OsmElement:
    type: str
    id: int
    tags: dict[str,str] = field(default_factory=dict)
    geometry: list[OsmPoint] = field(default_factory=list)
    members: list[OsmMember] = field(default_factory=list)

@dataclass(frozen=True)
class OsmData:
    elements: list[OsmElement]

@dataclass(frozen=True)
class Origin:
    latitude: float
    longitude: float

@dataclass(frozen=True)
class RouteRegistration:
    chosen: str
    uniform_scale: float

@dataclass(frozen=True)
class Provenance:
    origin: Origin
    route: RouteRegistration

@dataclass(frozen=True)
class PitWay:
    osm_id: int
    points_lat_lon: list[GeoPoint]
    tags: dict[str,str]
    relation_role: str

@dataclass(frozen=True)
class PitCandidate:
    slug: str
    source_file: str
    source_sha256: str
    ways: list[PitWay]
    source_note: str

@dataclass(frozen=True)
class PitSection:
    x: float
    y: float
    z: float
    half_width: float
    track_station: float
    distance: float
    normal_x: float
    normal_y: float
    cross_slope: float = 0.0
    positive_extent: float = 0.0
    negative_extent: float = 0.0

@dataclass(frozen=True)
class PitRoute:
    slug: str
    source_urls: list[str]
    source_note: str
    sections: Annotated[list[PitSection], Field(min_length=2,max_length=10000)]
    limit_entry_m: Annotated[FiniteFloat, Field(ge=0)]
    limit_exit_m: Annotated[FiniteFloat, Field(gt=0)]
    speed_limit_kph: Annotated[FiniteFloat, Field(ge=20,le=100)]
    portals: list[Portal] = field(default_factory=list)
    barriers: list[Barrier] = field(default_factory=list)

@dataclass(frozen=True)
class PitRoadSample:
    station: float
    x: float
    y: float
    z: float
    tx: float
    ty: float
    half_width: float
    bank: float
    left_shoulder: float
    right_shoulder: float

@dataclass(frozen=True)
class PitCatalogue:
    slug: str
    content_dir: str
    length_m: float
    start_station_m: float
    samples: int
    barriers: int

@dataclass(frozen=True)
class PitRecipe:
    slug: str
    way_ids: list[int]
    half_width_m: Annotated[FiniteFloat, Field(ge=1.5,le=6)]
    speed_limit_kph: Annotated[FiniteFloat, Field(ge=20,le=100)]
    source_urls: list[str]
    source_note: str
    limit_entry_distance_m: FiniteFloat | None = None
    limit_exit_distance_m: FiniteFloat | None = None
    layer_height_controls: list[tuple[float,float]] = field(default_factory=list)
    native_xy_controls: list[XY] = field(default_factory=list)
    plan_adjustment_controls: list[tuple[float,float,float]] = field(default_factory=list)
    maximum_endpoint_join_m: Annotated[FiniteFloat,Field(ge=0,le=10)] = 3.0
    reconstruct_pit_floor_from_road: bool = False

XYZ = tuple[float,float,float]

@dataclass(frozen=True)
class PitFloorTriangle:
    a: XYZ
    b: XYZ
    c: XYZ

@dataclass(frozen=True)
class PitProtectionProof:
    original_barriers_near_pit: int
    original_barriers_intruding_paving: int
    retained_separator_samples: int
    replacement_barriers: int
    minimum_replacement_clearance_to_main_road_m: float
    minimum_replacement_clearance_to_pit_axis_m: float
    maximum_replacement_segment_m: float
    source_note: str

@dataclass(frozen=True)
class PitFloorTransition:
    start_distance_m: float
    end_distance_m: float
    start_height_m: float
    end_height_m: float
    original_maximum_grade: float
    replacement_grade: float
    maximum_height_change_m: float
    source_note: str

@dataclass(frozen=True)
class LegacyGeoControl:
    latitude: float
    longitude: float

@dataclass(frozen=True)
class LegacyPitControl:
    source_wgs84: LegacyGeoControl
    native_track_station_estimate_m: float
    source_signed_left_offset_estimate_m: float
    pit_distance_m: float

@dataclass(frozen=True)
class LegacyPitCircuit:
    controls: list[LegacyPitControl]

@dataclass(frozen=True)
class LegacyPitTraces:
    circuits: dict[str,LegacyPitCircuit]
