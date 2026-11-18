"""Close Corniche walls and distinct first-sequence painted pavement."""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter
from shapely.geometry import LinearRing, Polygon
from shapely.geometry.base import BaseGeometry

from venues.jeddah_boundary_dataclasses import BoundaryRecipe, HighWall

if TYPE_CHECKING:
    from circuit_scene import CircuitScene

ROOT = Path(__file__).resolve().parents[2]


def load_recipe() -> BoundaryRecipe:
    return TypeAdapter(BoundaryRecipe).validate_json(
        (ROOT / "Attribution/Sources/jeddah/boundary-reconstruction.json").read_bytes()
    )


def wall_height(station: float, side: int, sections: list[HighWall]) -> float:
    for section in sections:
        if section.side == side and section.start_m <= station <= section.end_m:
            return section.height_m
    return 0.95


def usable_ring(ring: LinearRing) -> bool:
    # GEOS can retain zero-area out-and-back chains after a corridor union.
    return Polygon(ring).area > 1e-4


def paint_aprons(scene: CircuitScene) -> None:
    def band(start: float, end: float, side: int, inner: float, outer: float,
             wave: float = 0.0) -> BaseGeometry:
        inside = []
        outside = []
        for i in range(66):
            station = start + (end - start) * i / 65
            sample = scene.at(station)
            bend = wave * math.sin(math.pi * i / 65) ** 2
            inside.append(sample.point(side * (sample.half_width + inner + bend))[:2])
            outside.append(sample.point(side * (sample.half_width + outer + bend))[:2])
        shape = Polygon(inside + outside[::-1])
        if not shape.is_valid:
            shape = shape.buffer(0)
        return shape.intersection(scene.corridor_mask).difference(scene.road_mask.buffer(0.96))

    # Reconstructed abstract curves, not reference pixels or an asserted exact artwork trace.
    base = band(315, 445, 1, 1.12, 6.65)
    pink = band(315, 445, 1, 1.5, 3.15, 1.15).intersection(base)
    cyan = band(315, 445, 1, 4.55, 5.5, -1.5).intersection(base).difference(pink)
    left = band(1535, 1620, -1, 1.12, 5.65)
    green = band(1535, 1620, -1, 2.3, 3.8, 1.15).intersection(left)
    right = band(1690, 1815, 1, 1.12, 6.65)
    right_pink = band(1690, 1815, 1, 1.6, 3.8, 1.25).intersection(right)
    paint = ((pink, "JeddahApronPink"), (cyan, "JeddahApronCyan"),
             (base.difference(pink.union(cyan)), "White"),
             (green, "Green"), (left.difference(green), "JeddahApronOrange"),
             (right_pink, "JeddahApronPink"),
             (right.difference(right_pink), "JeddahApronYellow"))
    patches = []
    for shape, material, sample in scene.verge_patches:
        remaining = shape
        for mask, color in paint:
            piece = remaining.intersection(mask)
            if not piece.is_empty:
                patches.append((piece, color, sample))
                remaining = remaining.difference(mask)
        if not remaining.is_empty:
            patches.append((remaining, material, sample))
    scene.verge_patches = patches


def circuit_edges(scene: CircuitScene) -> None:
    recipe = load_recipe()
    if abs(scene.length - recipe.length_m) > 0.001:
        raise ValueError("Jeddah boundary source does not match the native lap")
    for start, end, side in recipe.kerbs:
        scene.kerb(start, end, side, width=recipe.kerb_width_m, material="Green")
    for apron in recipe.apron_ranges:
        scene.surface_ranges.append({
            "type": "runoff", "start_m": apron.start_m, "end_m": apron.end_m,
            "side": apron.side, "requested_width_m": apron.maximum_width_m,
            "material": apron.material,
        })
    paint_aprons(scene)
