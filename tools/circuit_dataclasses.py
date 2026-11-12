from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, FiniteFloat, StrictBool

Point = tuple[float, float, float]


@dataclass(frozen=True)
class ElevationControls:
    controls: Annotated[list[tuple[FiniteFloat, FiniteFloat]], Field(min_length=2)]


@dataclass(frozen=True)
class WidthControls:
    controls_m: Annotated[list[tuple[FiniteFloat, FiniteFloat]], Field(min_length=2)]


@dataclass(frozen=True)
class RacingRecipe:
    width_profile: WidthControls | None = None


@dataclass(frozen=True)
class RetainedTerrainSource:
    grid_file: Path
    grid_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    provider: str = "Retained ground data"
    dataset: str = "Retained TerrainGrid"
    relative_datum_m: FiniteFloat = 0
    road_join_distance_m: Annotated[FiniteFloat, Field(gt=0, le=20)] = 20


@dataclass(frozen=True)
class CircuitLight:
    position: Point
    ground_z: float
    pool_radius_m: float
    power: float


@dataclass(frozen=True)
class PitLane:
    start_m: float
    end_m: float
    side: Literal[-1, 1]
    outer_offset_m: float
    source_note: str
    shoulder_m: float = 0.10
    transition_m: float = 25.0


@dataclass(frozen=True)
class ShoulderCorrection:
    start_m: float
    end_m: float
    side: Literal[-1, 1]
    shoulder_m: float
    source_note: str
    transition_m: float = 25.0


@dataclass(frozen=True)
class ShoulderCorrections:
    sections: list[ShoulderCorrection] = field(default_factory=list)


@dataclass(frozen=True)
class EdgeCorrection:
    start_m: float
    end_m: float
    side: Literal[-1, 1]
    source_note: str


@dataclass(frozen=True)
class SurfaceProjection:
    origin: Point
    axis: Point
    length_m: float
    depth_m: float


@dataclass(frozen=True)
class BarrierPanel:
    start: float
    end: float
    side: int
    material: str


@dataclass(frozen=True)
class RunoffRange:
    start_m: float
    end_m: float
    side: int
    width_m: float
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


RecordingCount = Annotated[int, Field(ge=0, strict=True)]
RecordingMeasure = Annotated[FiniteFloat, Field(ge=0)]


@dataclass(frozen=True)
class RecordingReviewRequest:
    recording_directory: Path
    output_directory: Path
    circuit_slug: str


@dataclass(frozen=True)
class RecordingState:
    station_m: FiniteFloat
    speed_kph: FiniteFloat
    barrier_contact: StrictBool
    on_track: StrictBool
    grounded: StrictBool
    lap_invalid: StrictBool
    completed_laps: RecordingCount
    last_lap_valid: StrictBool
    last_lap_s: RecordingMeasure
    visual_penetration_m: RecordingMeasure
    loaded_visual_tiles: RecordingCount
    primary_screen_percentage_approx: RecordingMeasure


@dataclass(frozen=True)
class RecordingFrame(RecordingState):
    frame: RecordingCount
    time_s: RecordingMeasure
    simulation_s: RecordingMeasure
    image: str
    width: Annotated[int, Field(gt=0, strict=True)]
    height: Annotated[int, Field(gt=0, strict=True)]


@dataclass(frozen=True)
class RecordingSession:
    schema_version: Literal[1]
    state: Literal["recording", "stopped"]
    stop_reason: str
    circuit: str
    frames: RecordingCount
    rendered_frames: RecordingCount
    all_drawn_frames_saved: StrictBool
    duration_s: RecordingMeasure
    presentation_only_replay: StrictBool
    final_state: RecordingState


@dataclass(frozen=True)
class RecordingApex:
    name: Annotated[
        str, Field(validation_alias=AliasChoices("corner", "official_corner"))
    ]
    apex_station_m: FiniteFloat


@dataclass(frozen=True)
class RecordingApexList:
    approaches: list[RecordingApex] = field(default_factory=list)


@dataclass(frozen=True)
class RecordingRecipe:
    braking_markers: RecordingApexList = field(default_factory=RecordingApexList)


@dataclass(frozen=True)
class RecordingTarget:
    station_m: float
    reason: str


@dataclass(frozen=True)
class RecordingSelection:
    target_station_m: float
    reason: str
    frame: int
    journal_line: int
    station_m: float
    station_error_m: float
    time_s: float
    source_image: str
    copied_image: str | None


@dataclass(frozen=True)
class RecordingGap:
    start_station_m: float
    end_station_m: float
    length_m: float


@dataclass(frozen=True)
class RecordingReview:
    circuit_slug: str
    recording_directory: str
    native_catalogue: str
    circuit_length_m: float
    native_start_station_m: float
    session_state: str
    stop_reason: str
    presentation_only_replay: bool
    completed_laps_during_recording: int
    valid_last_completed_live_lap: bool
    clean_live_recording: bool
    frame_count: int
    manifest_saved_frames: int
    rendered_frames: int
    all_drawn_frames_saved: bool
    contact_frames: int
    offtrack_frames: int
    airborne_frames: int
    invalid_lap_frames: int
    maximum_visual_penetration_m: float
    minimum_loaded_tiles: int
    minimum_moving_loaded_tiles: int | None
    dimensions: list[tuple[int, int]]
    primary_screen_percentage_range: tuple[float, float]
    frame_interval_median_ms: float | None
    frame_interval_p95_ms: float | None
    interval_caveat: str
    station_bin_count: int
    visited_station_bins: list[int]
    station_bin_coverage_fraction: float
    maximum_circular_frame_gap_m: float
    station_gaps: list[RecordingGap]
    gap_reporting_threshold_m: float
    selected_image_count: int
    selected_target_count: int
    missing_image_files: int
    archived_journals: list[str]
    warnings: list[str]
