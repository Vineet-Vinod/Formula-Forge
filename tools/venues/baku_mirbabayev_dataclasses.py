from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from circuit_dataclasses import Point
from pydantic import Field, FiniteFloat

from venues.baku_ground_dataclasses import PackedPatchRow

XY = tuple[FiniteFloat, FiniteFloat]


@dataclass(frozen=True)
class PalaceGroundOpening:
    fraction: Annotated[FiniteFloat, Field(gt=0, lt=1)]
    width_m: Annotated[FiniteFloat, Field(gt=0, le=6)]
    round_head: bool = False


@dataclass(frozen=True)
class PalaceBands:
    ground_bottom_m: FiniteFloat = 0.20
    ground_head_m: FiniteFloat = 4.70
    first_belt_m: FiniteFloat = 7.10
    middle_bottom_m: FiniteFloat = 8.40
    middle_head_m: FiniteFloat = 12.10
    second_belt_m: FiniteFloat = 13.70
    upper_bottom_m: FiniteFloat = 15.80
    upper_head_m: FiniteFloat = 18.65


@dataclass(frozen=True)
class PalaceSource:
    ring_xy_m: Annotated[tuple[XY, ...], Field(min_length=3)]
    floor_relative_m: FiniteFloat = 2.6179030158204664
    cornice_m: Annotated[FiniteFloat, Field(gt=10, le=40)] = 20.5
    roof_rise_m: Annotated[FiniteFloat, Field(gt=0, le=8)] = 2.46
    pavilion_top_m: Annotated[FiniteFloat, Field(gt=10, le=45)] = 26.38
    height_uncertainty_m: Annotated[FiniteFloat, Field(gt=0, le=10)] = 5.0
    bands: PalaceBands = PalaceBands()
    main_fractions: Annotated[
        tuple[FiniteFloat, ...], Field(min_length=16, max_length=16)
    ] = (
        0.049,
        0.125,
        0.168,
        0.210,
        0.253,
        0.295,
        0.369,
        0.459,
        0.552,
        0.636,
        0.679,
        0.721,
        0.764,
        0.806,
        0.865,
        0.966,
    )
    main_ground: Annotated[
        tuple[PalaceGroundOpening, ...], Field(min_length=12, max_length=12)
    ] = (
        PalaceGroundOpening(0.049, 2.85),
        PalaceGroundOpening(0.125, 2.85),
        PalaceGroundOpening(0.198, 1.45),
        PalaceGroundOpening(0.271, 2.85),
        PalaceGroundOpening(0.369, 2.85),
        PalaceGroundOpening(0.459, 1.8, True),
        PalaceGroundOpening(0.552, 2.85),
        PalaceGroundOpening(0.636, 2.85),
        PalaceGroundOpening(0.724, 1.45),
        PalaceGroundOpening(0.802, 2.85),
        PalaceGroundOpening(0.865, 2.85),
        PalaceGroundOpening(0.966, 2.45),
    )

    def __post_init__(self) -> None:
        b = self.bands
        levels = (
            0.0,
            b.ground_bottom_m,
            b.ground_head_m,
            b.first_belt_m,
            b.middle_bottom_m,
            b.middle_head_m,
            b.second_belt_m,
            b.upper_bottom_m,
            b.upper_head_m,
            self.cornice_m,
            self.pavilion_top_m,
        )
        if levels != tuple(sorted(set(levels))):
            raise ValueError("Mirbabayev facade anchors must increase independently")
        if self.main_fractions != tuple(sorted(set(self.main_fractions))) or not all(
            0 < f < 1 for f in self.main_fractions
        ):
            raise ValueError("Mirbabayev projected upper groups must remain ordered")


@dataclass(frozen=True)
class PalacePavilion:
    center: Point
    radius_m: float
    front_normal: XY
    oval_facets: tuple[int, ...]


@dataclass(frozen=True)
class PalaceGeometry:
    cornice_m: float
    top_m: float
    pavilion_centers: tuple[Point, ...]
    main_stacks: tuple[float, ...]
    courtyard_open_m2: float
    rustication_max_curve_change_m: float


@dataclass(frozen=True)
class CapBand:
    center: Point
    normal: XY
    tangent: XY
    z0: float
    r0: float
    z1: float
    r1: float


@dataclass(frozen=True)
class PalaceRecipe:
    osm_id: Literal[133160749]
    origin_lat_lon: XY
    uniform_scale: FiniteFloat
    expected_legacy_height_m: FiniteFloat
    expected_legacy_rows: Annotated[int, Field(gt=0, le=400000)]
    legacy_counter_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    expected_candidate_rows: Annotated[int, Field(gt=0, le=400000)]
    candidate_counter_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    ground_supports: Annotated[list[PackedPatchRow], Field(min_length=1)]
    geometry: PalaceSource
    source_note: str


@dataclass(frozen=True)
class PalaceChange:
    removed_generic_rows: int
    emitted_rows: int
    preserved_parent_rows: int
    supporting_ground_rows: int
    parent: str
