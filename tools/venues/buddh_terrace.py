"""Source-qualified Buddh T3 terrace on the actual emitted Grass planes."""

from __future__ import annotations

import math
import struct
from collections.abc import Sequence
from typing import cast

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as GeoPoint
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.buddh_terrace_dataclasses import (
    FootWitness,
    GroundFace,
    PalmPlacement,
    TerraceGeometry,
    TerraceRecipe,
    TerraceSpec,
)


def coordinate(spec: TerraceSpec, u: float, v: float, rise: float) -> Point:
    return (
        spec.front_a[0]
        + u * (spec.front_b[0] - spec.front_a[0])
        + v * (spec.back_a[0] - spec.front_a[0]),
        spec.front_a[1]
        + u * (spec.front_b[1] - spec.front_a[1])
        + v * (spec.back_a[1] - spec.front_a[1]),
        spec.front_a_z_m + u * (spec.front_b_z_m - spec.front_a_z_m) + rise,
    )


def capture_ground(scene: MeshScene, domain: Polygon) -> tuple[GroundFace, ...]:
    faces = []
    for name, tile in scene.tiles.items():
        if not name.startswith("Tile_Street"):
            continue
        low, high = tile.minimum, tile.maximum
        if not box(
            -high[1] / 100, -high[0] / 100, -low[1] / 100, -low[0] / 100
        ).intersects(domain):
            continue
        for offset in range(0, len(tile.triangles), 100):
            if (
                tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
                != "Grass"
            ):
                continue
            values = struct.unpack_from("<24f", tile.triangles, offset + 4)
            if min(values[i + 5] for i in (0, 8, 16)) < 0.05:
                continue
            points = cast(
                tuple[Point, Point, Point],
                tuple(
                    (-values[i + 1] / 100, -values[i] / 100, values[i + 2] / 100)
                    for i in (0, 8, 16)
                ),
            )
            plan = Polygon([p[:2] for p in points])
            if plan.area > 1e-8 and plan.intersects(domain):
                faces.append(GroundFace(points, plan, name, offset))
    return tuple(faces)


def plane_height(face: GroundFace, x: float, y: float) -> float:
    a, b, c = face.points
    d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
    return u * a[2] + v * b[2] + (1 - u - v) * c[2]


def footing(
    ground: Sequence[GroundFace], index: STRtree, footprint: Polygon, column_top: float
) -> FootWitness:
    values: list[float] = []
    covered = []
    rows = []
    for i in index.query(footprint, predicate="intersects"):
        face = ground[int(i)]
        part = face.plan.intersection(footprint)
        if part.area <= 1e-10:
            continue
        if not isinstance(part, Polygon):
            raise TypeError(
                "A private support footprint needs an explicit polygon intersection"
            )
        covered.append(part)
        rows.append((face.source_tile, face.source_offset))
        values.extend(plane_height(face, x, y) for x, y in part.exterior.coords)
    missing = footprint.difference(unary_union(covered)).area
    if not values or missing > 1e-7:
        raise ValueError(
            f"An original Grass support footprint is incomplete: {missing} m²"
        )
    low, high = min(values), max(values)
    if column_top <= high + 0.17:
        raise ValueError("A raised terrace support intersects its existing ground")
    return FootWitness(
        footprint, low, high, low - 0.10, high + 0.15, column_top, missing, tuple(rows)
    )


def polygon_at(spec: TerraceSpec) -> Polygon:
    return Polygon(
        [coordinate(spec, u, v, 0)[:2] for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]
    )


def deck_clearance(
    spec: TerraceSpec, ground: Sequence[GroundFace], index: STRtree
) -> float:
    clearances: list[float] = []
    for row in range(spec.rows):
        a = coordinate(spec, 0, row / spec.rows, row * spec.riser_m - 0.12)
        b = coordinate(spec, 1, row / spec.rows, row * spec.riser_m - 0.12)
        c = coordinate(spec, 1, (row + 1) / spec.rows, row * spec.riser_m - 0.12)
        d = coordinate(spec, 0, (row + 1) / spec.rows, row * spec.riser_m - 0.12)
        plan = Polygon([a[:2], b[:2], c[:2], d[:2]])
        deck = GroundFace((a, b, c), plan, "terrace", row)
        for i in index.query(plan, predicate="intersects"):
            face = ground[int(i)]
            part = face.plan.intersection(plan)
            if isinstance(part, Polygon) and part.area > 1e-8:
                clearances.extend(
                    plane_height(deck, x, y) - plane_height(face, x, y)
                    for x, y in part.exterior.coords
                )
    if not clearances:
        raise ValueError("The terrace requires actual emitted Grass support")
    return min(clearances)


def quad(
    scene: MeshScene,
    material: str,
    points: Sequence[Point],
    kind: str,
    up: bool | None = None,
) -> None:
    scene.quad(kind, material, points[0], points[1], points[2], points[3], up=up)


def emit(
    scene: MeshScene, spec: TerraceSpec, ground: Sequence[GroundFace]
) -> TerraceGeometry:
    if (
        spec.front_a != (294.0, 884.0)
        or spec.front_b != (342.0, 708.0)
        or spec.back_a != (315.0, 890.0)
    ):
        raise ValueError(
            "Only the independently adjudicated east-exit footprint is released"
        )
    index = STRtree([g.plan for g in ground])
    feet = [
        footing(
            ground,
            index,
            box(point[0] - 0.275, point[1] - 0.275, point[0] + 0.275, point[1] + 0.275),
            point[2],
        )
        for support_index in range(spec.bays * 4 + 1)
        for v in (0.0, 0.5, 1.0)
        for point in (
            coordinate(
                spec,
                support_index / (spec.bays * 4),
                v,
                v * spec.rows * spec.riser_m - 0.16,
            ),
        )
    ]
    clearance = deck_clearance(spec, ground, index)
    if clearance < 0.1:
        raise ValueError("The terrace slab intersects or approaches the emitted Grass")
    length = math.dist(spec.front_a, spec.front_b)
    aisle = spec.aisle_width_m / length
    deck_triangles = 0
    before_crowd = sum(
        len(t.triangles) // 100
        for n, t in scene.tiles.items()
        if n.startswith("Building_Crowd")
    )
    for bay in range(spec.bays):
        u0 = bay / spec.bays + aisle / 2
        u1 = (bay + 1) / spec.bays - aisle / 2
        for row in range(spec.rows):
            v0, v1 = row / spec.rows, (row + 1) / spec.rows
            rise = row * spec.riser_m
            quad(
                scene,
                "Concrete",
                [
                    coordinate(spec, u, v, rise)
                    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
                ],
                "Building_BuddhTerraceDeck",
                True,
            )
            quad(
                scene,
                "Concrete",
                [
                    coordinate(spec, u, v, rise - 0.12)
                    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))
                ],
                "Building_BuddhTerraceSoffit",
                False,
            )
            deck_triangles += 2
            quad(
                scene,
                "Concrete",
                [
                    coordinate(spec, u0, v1, rise),
                    coordinate(spec, u1, v1, rise),
                    coordinate(spec, u1, v1, rise + spec.riser_m),
                    coordinate(spec, u0, v1, rise + spec.riser_m),
                ],
                "Building_BuddhTerraceRiser",
            )
            a, b = (
                coordinate(spec, u, (v0 + v1) / 2, rise + 0.42)
                for u in (u0 + 0.002, u1 - 0.002)
            )
            scene.beam("Building_BuddhTerraceBenches", "SeatYellow", a, b, 0.36, 0.12)
            scene.spectators(
                coordinate(spec, u0 + 0.003, (v0 + v1) / 2, rise + 0.30),
                coordinate(spec, u1 - 0.003, (v0 + v1) / 2, rise + 0.30),
                row + bay * spec.rows,
                "Building_Crowd_BuddhTerrace",
            )
    for aisle_index in range(spec.bays + 1):
        u = aisle_index / spec.bays
        left = max(0.0, u - aisle / 2)
        right = min(1.0, u + aisle / 2)
        for step in range(spec.rows * 2):
            v0, v1 = step / (spec.rows * 2), (step + 1) / (spec.rows * 2)
            rise = step * spec.riser_m / 2
            quad(
                scene,
                "Concrete",
                [
                    coordinate(spec, a, b, rise)
                    for a, b in ((left, v0), (right, v0), (right, v1), (left, v1))
                ],
                "Building_BuddhTerraceStairs",
                True,
            )
            quad(
                scene,
                "Concrete",
                [
                    coordinate(spec, left, v1, rise),
                    coordinate(spec, right, v1, rise),
                    coordinate(spec, right, v1, rise + spec.riser_m / 2),
                    coordinate(spec, left, v1, rise + spec.riser_m / 2),
                ],
                "Building_BuddhTerraceStairRisers",
            )
            for border in (left, right):
                near = max(left, border - 0.00025)
                far = min(right, border + 0.00025)
                quad(
                    scene,
                    "Yellow",
                    [
                        coordinate(spec, a, b, rise + 0.002)
                        for a, b in ((near, v0), (far, v0), (far, v1), (near, v1))
                    ],
                    "Building_BuddhTerraceAisleEdges",
                    True,
                )
    for support_index in range(spec.bays * 4 + 1):
        u = support_index / (spec.bays * 4)
        for v in (0.0, 0.5, 1.0):
            point = coordinate(spec, u, v, v * spec.rows * spec.riser_m - 0.16)
            support = feet[support_index * 3 + round(v * 2)]
            scene.box(
                "Building_BuddhTerraceFootings",
                "Concrete",
                (point[0], point[1], (support.base_z_m + support.plinth_top_z_m) / 2),
                0.55,
                0.55,
                support.plinth_top_z_m - support.base_z_m,
            )
            scene.beam(
                "Building_BuddhTerraceTrestles",
                "Steel",
                (point[0], point[1], support.plinth_top_z_m),
                point,
                0.17,
            )
        scene.beam(
            "Building_BuddhTerraceTrestles",
            "Steel",
            coordinate(spec, u, 0, -0.65),
            coordinate(spec, u, 1, spec.rows * spec.riser_m - 0.65),
            0.19,
        )
        if support_index < spec.bays * 4:
            next_u = (support_index + 1) / (spec.bays * 4)
            for v in (0.0, 1.0):
                a, b = (
                    coordinate(spec, u, v, v * spec.rows * spec.riser_m - 0.18),
                    coordinate(spec, next_u, v, v * spec.rows * spec.riser_m - 0.18),
                )
                scene.beam("Building_BuddhTerraceBeams", "Steel", a, b, 0.20)
    for i in range(spec.bays * 4):
        for offset in (0, 2):
            first, second = feet[i * 3 + offset], feet[(i + 1) * 3 + offset]
            if (
                min(
                    first.column_top_z_m - first.plinth_top_z_m,
                    second.column_top_z_m - second.plinth_top_z_m,
                )
                < 0.5
            ):
                continue
            ax, ay = first.footprint.centroid.coords[0]
            bx, by = second.footprint.centroid.coords[0]
            scene.beam(
                "Building_BuddhTerraceBracing",
                "Steel",
                (ax, ay, first.plinth_top_z_m + 0.1),
                (bx, by, second.column_top_z_m - 0.2),
                0.10,
            )
            scene.beam(
                "Building_BuddhTerraceBracing",
                "Steel",
                (bx, by, second.plinth_top_z_m + 0.1),
                (ax, ay, first.column_top_z_m - 0.2),
                0.10,
            )
    # A low source-visible balustrade is separate from the open support frame.
    for bay in range(spec.bays):
        front_u0, front_u1 = bay / spec.bays, (bay + 1) / spec.bays
        quad(
            scene,
            "White",
            [
                coordinate(spec, front_u0, 0, -0.10),
                coordinate(spec, front_u1, 0, -0.10),
                coordinate(spec, front_u1, 0, 0.8),
                coordinate(spec, front_u0, 0, 0.8),
            ],
            "Building_BuddhTerraceFront",
        )
        for v, rise in ((0.0, 1.0), (1.0, spec.rows * spec.riser_m + 1.05)):
            scene.beam(
                "Building_BuddhTerraceRails",
                "Steel",
                coordinate(spec, front_u0, v, rise),
                coordinate(spec, front_u1, v, rise),
                0.05,
            )
    after_crowd = sum(
        len(t.triangles) // 100
        for n, t in scene.tiles.items()
        if n.startswith("Building_Crowd")
    )
    return TerraceGeometry(
        tuple(feet),
        deck_triangles,
        after_crowd - before_crowd,
        polygon_at(spec),
        clearance,
    )


def load_recipe(scene: CircuitScene) -> TerraceRecipe:
    if scene.slug != "buddh":
        raise ValueError("The T3 terrace requires the qualified Buddh source frame")
    recipe = TypeAdapter(TerraceRecipe).validate_json(
        (scene.sources / "t3-terrace.json").read_bytes()
    )
    if (
        max(
            abs(scene.provenance.origin.latitude - recipe.expected_origin_latitude),
            abs(scene.provenance.origin.longitude - recipe.expected_origin_longitude),
            abs(scene.provenance.route.uniform_scale - recipe.expected_scene_scale),
        )
        > 1e-12
    ):
        raise ValueError("The T3 terrace requires the qualified Buddh source frame")
    if recipe.excluded_palm_indices != (0, 1):
        raise ValueError(
            "Only the two qualified root-inside procedural palms may be omitted"
        )
    return recipe


def palm_placements(
    scene: CircuitScene, recipe: TerraceRecipe
) -> tuple[PalmPlacement, ...]:
    plan = polygon_at(recipe.geometry)
    footprints = [Polygon(b.ring).buffer(2) for b in scene.buildings]
    placements = []
    for i in range(22):
        sample = scene.at(1500 + 950 * (i + 0.5) / 22)
        lane = -(sample.half_width + 0.95 + sample.right_shoulder + 28 + (i % 3) * 2.5)
        p = sample.point(lane)
        nearest, distance = scene.nearest(p[0], p[1])
        base = p[0], p[1], scene.ground(p[0], p[1])
        point = GeoPoint(base[:2])
        if (
            distance < nearest.half_width + 5
            or any(shape.covers(point) for shape in scene.water_shapes)
            or any(shape.contains(point) for shape in footprints)
        ):
            continue
        placements.append(PalmPlacement(i, base, 8 + (i % 3) * 0.8))
    if len(placements) != len(recipe.original_palms):
        raise ValueError("The qualified procedural palm row occupancy changed")
    for actual, expected in zip(placements, recipe.original_palms, strict=True):
        if (
            actual.index != expected.index
            or math.dist(actual.base, expected.base) > 1e-8
            or actual.height_m != expected.height_m
            or (actual.index in recipe.excluded_palm_indices)
            != plan.contains(GeoPoint(actual.base[:2]))
        ):
            raise ValueError(
                "The qualified procedural palm poses or terrace classification changed"
            )
    return tuple(placements)


def build_palms(scene: CircuitScene) -> None:
    recipe = load_recipe(scene)
    placements = palm_placements(scene, recipe)
    for placement in placements:
        if placement.index not in recipe.excluded_palm_indices:
            scene.palm(placement.base, placement.height_m)
    scene.vegetation.append(
        {
            "type": "palms",
            "start_m": 1500,
            "end_m": 2450,
            "side": -1,
            "count": len(placements) - len(recipe.excluded_palm_indices),
            "setback_m": 28,
            "excluded_procedural_indices": "0, 1",
            "placement": "Original source-index traversal and poses retained. Only the two estimated procedural roots inside the qualified east-exit terrace are omitted; mapped trees and all outside instances remain unchanged.",
        }
    )


def finish_terrain(scene: CircuitScene) -> TerraceGeometry:
    from venues.buddh_first_sector_rows import capture

    recipe = load_recipe(scene)
    reserve = polygon_at(recipe.geometry).buffer(0.5)
    if reserve.intersection(scene.road_mask).area > 1e-7 or any(
        reserve.intersection(Polygon(b.ring)).area > 1e-7 for b in scene.buildings
    ):
        raise ValueError(
            "The east terrace overlaps an existing road or mapped building"
        )
    if any(
        face.plan.intersection(reserve).area > 1e-7
        for face in capture(scene, reserve, {"Gravel"})
    ):
        raise ValueError("The east terrace overlaps the qualified first-sector gravel")
    ground = capture_ground(scene, reserve)
    geometry = emit(scene, recipe.geometry, ground)
    scene.landmarks.append(
        {
            "name": "Buddh T3 east-exit spectator terrace",
            "rows": recipe.geometry.rows,
            "rise_m": recipe.geometry.rows * recipe.geometry.riser_m,
            "footings": len(geometry.feet),
            "minimum_grass_soffit_clearance_m": geometry.minimum_deck_clearance_m,
            "registration": "Estimated east-exit footprint from supplied reference 132–135 s and the registered 2018 grass-bank envelope. Existing west approach stand retained; north cap held and omitted.",
            "construction": "Yellow seating, concrete aisles, low white front, open braced steel frame. Footings enclose actual emitted Grass planes; no terrain, road or native contact change.",
            "source_limits": recipe.source_limits,
        }
    )
    return geometry
