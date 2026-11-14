"""source dimensions and explicitly estimated component plans."""

from dataclasses import dataclass
from typing import Annotated

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat
from shapely.geometry import Polygon
from shapely.strtree import STRtree


@dataclass(frozen=True)
class SiteEnvelope:
    osm_id: int
    outer_wgs84: tuple[tuple[FiniteFloat, FiniteFloat], ...]


@dataclass(frozen=True)
class LocalFrame:
    center: tuple[float, float]
    axis: tuple[float, float]
    normal: tuple[float, float]


@dataclass(frozen=True)
class ContextGroundFace:
    points: tuple[Point, Point, Point]
    normals: tuple[Point, Point, Point]


@dataclass(frozen=True)
class ContextGroundLookup:
    faces: tuple[ContextGroundFace, ...]
    polygons: tuple[Polygon, ...]
    index: STRtree
    bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class SailArchitecture:
    site: SiteEnvelope
    center_wgs84: tuple[FiniteFloat, FiniteFloat]
    axis_source_vertices: tuple[int, int] = (1, 0)
    height_m: Annotated[FiniteFloat, Field(gt=250, lt=275)] = 264.7
    highest_occupied_m: Annotated[FiniteFloat, Field(gt=230, lt=250)] = 243.7
    floors: Annotated[int, Field(ge=60, le=70)] = 65
    length_m: FiniteFloat = 55.
    width_m: FiniteFloat = 22.
    base_relative_m: FiniteFloat = 3.
    foundation_bottom_relative_m: FiniteFloat = .5
    crown_height_m: FiniteFloat = 3.5
    balcony_depth_m: tuple[FiniteFloat, FiniteFloat] = (.85, 1.65)
    floor_slab_thickness_m: FiniteFloat = .28
    bay_width_m: FiniteFloat = 2.75
    podium_floors: int = 7
    podium_floor_pitch_m: FiniteFloat = 4.2
    ballroom_floors: int = 3
    ballroom_floor_pitch_m: FiniteFloat = 5.1
    podium_north_offset_m: FiniteFloat = 20.
    podium_projection_limit_m: FiniteFloat = 3.05


@dataclass(frozen=True)
class MallWing:
    name: str
    center_wgs84: tuple[FiniteFloat, FiniteFloat]
    length_m: FiniteFloat
    width_m: FiniteFloat
    floors: int
    floor_pitch_m: FiniteFloat


@dataclass(frozen=True)
class ContextServiceRoad:
    osm_id: int
    path_wgs84: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    estimated_width_m: Annotated[FiniteFloat, Field(gt=0, le=12)]
    facade_clearance_m: Annotated[FiniteFloat, Field(ge=0, le=3)]


@dataclass(frozen=True)
class MallArchitecture:
    site: SiteEnvelope
    axis_source_vertices: tuple[int, int]
    street_relative_m: FiniteFloat
    lower_ground_relative_m: FiniteFloat
    ground_to_first_m: FiniteFloat
    first_to_roof_m: FiniteFloat
    frontage_source_range: tuple[int, int]
    frontage_inset_m: FiniteFloat
    central_roof_center_wgs84: tuple[FiniteFloat, FiniteFloat]
    central_roof_length_m: FiniteFloat
    central_roof_width_m: FiniteFloat
    central_roof_rise_m: FiniteFloat
    cross_roof_center_wgs84: tuple[FiniteFloat, FiniteFloat]
    cross_roof_length_m: FiniteFloat
    cross_roof_width_m: FiniteFloat
    cross_roof_rise_m: FiniteFloat
    roof_plant_count: Annotated[int, Field(ge=0, le=150)]
    wings: tuple[MallWing, ...]
    service_roads: tuple[ContextServiceRoad, ...] = ()


@dataclass(frozen=True)
class ContextTileResidency:
    tile_name: str
    north_margin_m: Annotated[FiniteFloat, Field(gt=0, le=1500)]
    actual_baseline_bounds_ue_cm: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class ContextResidency:
    uniform_scale: Annotated[FiniteFloat, Field(gt=0)]
    tiles: Annotated[tuple[ContextTileResidency, ...], Field(min_length=2, max_length=2)]
