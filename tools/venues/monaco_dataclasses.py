from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat
from shapely.geometry import Polygon
from shapely.strtree import STRtree


@dataclass(frozen=True)
class HillsideBuilding:
    source_id: str
    component: int
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
    roof_outline_m: list[FiniteFloat]
    holes_roof_m: list[list[FiniteFloat]]
    ground_m: FiniteFloat
    eaves_m: FiniteFloat
    roof_m: FiniteFloat
    floors: int | None
    roof_material: Literal['Terracotta', 'Roof', 'Concrete', 'Steel']
    height_precision_m: FiniteFloat | None


@dataclass(frozen=True)
class HillsideVegetation:
    source_id: str
    nature: str
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]


@dataclass(frozen=True)
class PropertyRoofStep:
    start_vertex: int
    end_vertex: int
    lower_endpoint_m: tuple[FiniteFloat, FiniteFloat]
    upper_endpoint_m: tuple[FiniteFloat, FiniteFloat]
    seam: list[tuple[FiniteFloat, FiniteFloat]]
    source_note: str


@dataclass(frozen=True)
class PropertyEnvelope:
    osm_id: int
    name: str
    style: Literal['ruscino', 'ermanno', 'rascasse', 'annex', 'roof_component']
    source_id: str
    component: int
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    holes: list[list[tuple[FiniteFloat, FiniteFloat]]]
    roof_outline_m: list[FiniteFloat]
    holes_roof_m: list[list[FiniteFloat]]
    ground_m: FiniteFloat
    roof_peak_m: FiniteFloat
    height_precision_m: FiniteFloat
    roof_step: PropertyRoofStep | None = None
    covered_osm_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class GardenFrontage:
    osm_id: int
    ring: list[tuple[FiniteFloat, FiniteFloat]]
    native_range_m: tuple[FiniteFloat, FiniteFloat]
    wall_height_m: FiniteFloat
    wall_inset_m: FiniteFloat
    source_note: str


@dataclass(frozen=True)
class RascasseFrontage:
    ground_body_osm_id: int
    roof_source_id: str
    roof_front_vertices: tuple[int, int]
    region_wgs84: list[tuple[FiniteFloat, FiniteFloat]]
    ground_grid_file: str
    uniform_scale: FiniteFloat
    podium_height_above_source_minimum_m: FiniteFloat
    body_search_width_m: FiniteFloat = 2.5
    street_threshold_sample_distance_m: FiniteFloat = 2.5
    forecourt_width_m: FiniteFloat = 6.0


@dataclass(frozen=True)
class CostaComponent:
    osm_id: int
    name: str
    source_id: str
    style: Literal['casa_core', 'casa_west', 'casa_east', 'antoinette']
    outer: list[tuple[FiniteFloat, FiniteFloat]]
    roof_outline_m: list[FiniteFloat]
    ground_m: FiniteFloat
    roof_peak_m: FiniteFloat
    roof_inset_m: FiniteFloat
    upper_floor_base_m: FiniteFloat
    upper_floor_height_m: FiniteFloat
    upper_floors: int
    plan_precision_m: FiniteFloat
    height_precision_m: FiniteFloat
    roof_step: PropertyRoofStep | None = None


@dataclass(frozen=True)
class CostaArchitecture:
    uniform_scale: FiniteFloat
    ground_grid_file: str
    components: list[CostaComponent]


@dataclass(frozen=True)
class CostaLandRegion:
    name: str
    cover: Literal['planted', 'rocky']
    outer: list[tuple[FiniteFloat, FiniteFloat]]


@dataclass(frozen=True)
class CostaLandCover:
    uniform_scale: FiniteFloat
    regions: list[CostaLandRegion]
    rock_outcrops: list[list[tuple[FiniteFloat, FiniteFloat]]]
    annex_outer: list[tuple[FiniteFloat, FiniteFloat]]


@dataclass(frozen=True)
class CostaGroundFace:
    points: tuple[Point, Point, Point]
    normals: tuple[Point, Point, Point]


@dataclass(frozen=True)
class ApproachGround:
    faces: tuple[CostaGroundFace, ...]
    polygons: tuple[Polygon, ...]
    index: STRtree


@dataclass(frozen=True)
class BridgeApproach:
    end: Literal['east', 'west']
    bridge_cap_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]
    outer_tie_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]
    plan_xy_m: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    transition_length_m: FiniteFloat


@dataclass(frozen=True)
class LarvottoBridge:
    outline_wgs84: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    centerline_wgs84: tuple[tuple[FiniteFloat, FiniteFloat], ...]
    east_deck_absolute_m: FiniteFloat
    west_deck_absolute_m: FiniteFloat
    crown_thickness_m: Annotated[FiniteFloat, Field(gt=.5, lt=2)]
    arch_rise_m: Annotated[FiniteFloat, Field(ge=4, le=15)]
    parapet_height_m: Annotated[FiniteFloat, Field(ge=.4, le=1.5)]
    parapet_thickness_m: Annotated[FiniteFloat, Field(ge=.1, le=.5)]
    approach_transition_m: Annotated[FiniteFloat, Field(ge=4, le=15)]
    sample_interval_m: Annotated[FiniteFloat, Field(gt=.1, le=1)]


@dataclass(frozen=True)
class BridgeFrame:
    origin: tuple[FiniteFloat, FiniteFloat]
    axis: tuple[FiniteFloat, FiniteFloat]
    span: FiniteFloat


@dataclass(frozen=True)
class BridgeProfile:
    frame: BridgeFrame
    east_relative_m: FiniteFloat
    west_relative_m: FiniteFloat
    crown_thickness_m: FiniteFloat
    arch_rise_m: FiniteFloat


@dataclass(frozen=True)
class SettingCypress:
    xy_m: tuple[FiniteFloat, FiniteFloat]
    height_m: Annotated[FiniteFloat, Field(ge=3, le=20)]
    seed: int


@dataclass(frozen=True)
class CasaGardenSetting:
    origin_xy_m: tuple[FiniteFloat, FiniteFloat] = (25.98656456603288, 342.79334028423057)
    u_axis: tuple[FiniteFloat, FiniteFloat] = (.9834340951564259, .18126604890012293)
    v_axis: tuple[FiniteFloat, FiniteFloat] = (.18126604890012293, -.9834340951564259)
    garden_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((-5.8, .8), (18.5, .8), (19., 19.5), (-5.8, 20.))
    patio_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((-5.8, .8), (18.5, .8), (18.6, 5.2), (-5.8, 5.2))
    central_stair_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((6.7, 5.2), (8.8, 5.2), (8.8, 11.4), (6.7, 11.4))
    lower_stair_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((11.8, 15.8), (14.8, 15.8), (14.8, 19.75), (11.8, 19.75))
    central_landing_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((6.7, 11.4), (8.8, 11.4), (8.8, 12.4), (6.7, 12.4))
    lower_top_landing_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((11.8, 15.1), (14.8, 15.1), (14.8, 15.8), (11.8, 15.8))
    lower_bottom_landing_uv_m: tuple[tuple[FiniteFloat, FiniteFloat], ...] = ((11.8, 19.75), (14.8, 19.75), (14.8, 20.35), (11.8, 20.35))
    patio_anchor_absolute_m: FiniteFloat = 28.34
    central_stair_bottom_absolute_m: FiniteFloat = 24.737007139230315
    lower_stair_top_absolute_m: FiniteFloat = 23.17
    lower_stair_bottom_absolute_m: FiniteFloat = 21.19635246118234
    plant_spacing_m: Annotated[FiniteFloat, Field(ge=.5, le=8)] = 2.3
    leaf_bank_height_m: tuple[FiniteFloat, FiniteFloat] = (4.2, 6.0)
    cypresses: tuple[SettingCypress, ...] = (SettingCypress((-14., 318.), 11.5, 93137606),
                                           SettingCypress((-10.5, 319.), 12.5, 93137607))


@dataclass(frozen=True)
class RetailTerrace:
    osm_id: int = 508221117
    roof_absolute_m: FiniteFloat = 9.95
    lower_storeys: int = 2
    roof_coping_height_m: FiniteFloat = .12
    retaining_ground_overlap_m: FiniteFloat = .002
