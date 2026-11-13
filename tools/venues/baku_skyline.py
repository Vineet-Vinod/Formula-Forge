"""Mapped eastern waterfront buildings visible beyond Baku's first corner."""

from __future__ import annotations

import gzip
import math
from itertools import pairwise

from circuit_dataclasses import Building, OsmData, Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon

from venues.baku_skyline_dataclasses import SkylineBuilding, SkylineRecipe
from venues.east_architecture import frame, roof_polygon


def waterfront_skyline(scene: CircuitScene) -> None:
    recipe = TypeAdapter(SkylineRecipe).validate_json(
        (scene.sources / "skyline-buildings.json").read_bytes()
    )
    data = TypeAdapter(OsmData).validate_json(
        gzip.decompress((scene.sources / recipe.source_file).read_bytes())
    )
    rings = scene._rings(data)
    elements = {element.id: element for element in data.elements}
    existing = {building.osm_id for building in scene.buildings}
    for record in recipe.buildings:
        if record.osm_id in existing:
            raise ValueError(f"Skyline must not replace an existing Baku property: {record.osm_id}")
        element = elements[record.osm_id]
        ring = max(rings[record.osm_id], key=lambda points: Polygon(points).area)
        building = Building(record.osm_id, record.name, "yes", record.height_m, ring, element.tags)
        footprint = Polygon(ring)
        if footprint.intersects(scene.corridor_mask.buffer(1.2)):
            raise ValueError(f"Eastern skyline overlaps the protected track: {record.osm_id}")
        scene.buildings.append(building)
        scene.modeled_buildings.add(record.osm_id)
        scene.terrain_cutouts.append(footprint)
        if record.style == "torch":
            city_tower(scene, building)
        elif record.style == "crescent":
            crescent_hotel(scene, building)
        else:
            street_block(scene, building, record)
        scene.landmarks.append({
            "name": record.name, "osm_id": record.osm_id,
            "height_m": record.height_m, "facade": record.style,
            "source": "skyline-buildings.json; actual additional OSM footprint. Heights and section uncertainty are recorded per property. No source photograph pixels are shipped.",
        })


def city_tower(scene: CircuitScene, building: Building) -> None:
    center, axis, side, length, width = frame(building)
    base = min(scene.ground(x, y) for x, y in building.ring)
    segments, levels = 64, 84
    kind = "Building_CrescentCity"

    def point(angle: float, fraction: float, outset: float = 0.0) -> Point:
        crown = max(0.0, (fraction - .73) / .27)
        radius = 1.0 + .23 * math.sin(math.pi * fraction) - .91 * crown * crown
        shift = -.13 * length * crown * crown
        along = (length / 2 * radius + outset) * math.cos(angle) + shift
        across = (width / 2 * radius + outset) * math.sin(angle)
        return add(add((center[0], center[1], base + building.height * fraction),
                       mul(axis, along)), mul(side, across))

    for level in range(levels):
        low, high = level / levels, (level + 1) / levels
        for segment in range(segments):
            a, b = segment * math.tau / segments, (segment + 1) * math.tau / segments
            material = "BakuSkyGlassLight" if segment % 16 < 3 else "BakuSkyGlass"
            scene.quad(kind, material, point(a, low), point(b, low),
                       point(b, high), point(a, high))
    for floor in range(1, 44):
        f = floor / 44
        for segment in range(segments):
            a, b = segment * math.tau / segments, (segment + 1) * math.tau / segments
            scene.beam(kind, "Steel", point(a, f, .035), point(b, f, .035), .13)
    for segment in range(0, segments, 4):
        angle = segment * math.tau / segments
        for level in range(16):
            low, high = level / 16, (level + 1) / 16
            for sign in (-1, 1):
                first = angle + sign * math.tau * low * .55
                second = angle + sign * math.tau * high * .55
                scene.beam(kind, "Steel", point(first, low, .10),
                           point(second, high, .10), .24)
    cap = (center[0] - axis[0] * length * .13,
           center[1] - axis[1] * length * .13, base + building.height)
    for segment in range(segments):
        a, b = segment * math.tau / segments, (segment + 1) * math.tau / segments
        scene.triangle(kind, "BakuSkyGlass", point(a, 1), point(b, 1), cap)


def crescent_hotel(scene: CircuitScene, building: Building) -> None:
    center, axis, side, length, depth = frame(building)
    base = min(scene.ground(x, y) for x, y in building.ring)
    kind = "Building_CrescentHotel"
    span = length * .48

    def section(u: float) -> tuple[float, float]:
        outer = building.height * math.sqrt(max(0.0, 1 - (u / span) ** 2))
        inner = building.height * .64 * math.sqrt(max(0.0, 1 - (u / (span * .68)) ** 2))
        return outer, inner

    def point(u: float, z: float, lane: float) -> Point:
        return add(add((center[0], center[1], base + z), mul(axis, u)), mul(side, lane))

    for index in range(96):
        a, b = -span + 2 * span * index / 96, -span + 2 * span * (index + 1) / 96
        top_a, bottom_a = section(a)
        top_b, bottom_b = section(b)
        front = -depth * .40
        back = depth * .40
        pa, pb = point(a, bottom_a, front), point(b, bottom_b, front)
        qa, qb = point(a, top_a, front), point(b, top_b, front)
        scene.quad(kind, "BakuSkyGlass", pa, pb, qb, qa)
        scene.quad(kind, "BakuSkyGlassLight", point(b, bottom_b, back), point(a, bottom_a, back),
                   point(a, top_a, back), point(b, top_b, back))
        scene.quad(kind, "Steel", qa, qb, point(b, top_b, back), point(a, top_a, back))
        scene.quad(kind, "Concrete", pb, pa, point(a, bottom_a, back), point(b, bottom_b, back))
        scene.beam(kind, "White", qa, qb, .23)
        for floor in range(1, 37):
            z = floor * building.height / 37
            if bottom_a + .2 < z < top_a - .2 and bottom_b + .2 < z < top_b - .2:
                scene.beam(kind, "Steel", point(a, z, front - .04), point(b, z, front - .04), .14)


def street_block(scene: CircuitScene, building: Building, record: SkylineBuilding) -> None:
    footprint = Polygon(building.ring)
    ring = list(footprint.exterior.coords)
    if not footprint.exterior.is_ccw:
        ring.reverse()
    base = min(scene.ground(x, y) for x, y in building.ring)
    kind = "Building_EasternWaterfront"
    modern = record.style in ("hotel", "residence")
    podium = record.style == "podium"
    for a, b in pairwise(ring):
        span = math.dist(a, b)
        if span < .2:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        pa, pb = (*a, base), (*b, base)
        scene.banner(pa, pb, building.height, "Cream" if not modern else "Concrete", kind)
        bays = max(1, round(span / (4.4 if modern else 3.6)))
        for floor in range(record.floors):
            low = base + (floor + .17) * building.height / record.floors
            high = building.height / record.floors * .66
            if modern:
                scene.beam(kind, "White", (*a, low - .20), (*b, low - .20), .2, .4)
            for bay in range(bays):
                offset = (bay + .5) * span / bays
                width = min(span / bays * (.8 if modern else .55), 3.6)
                start = (a[0] + tx * (offset - width / 2) + nx * .06,
                         a[1] + ty * (offset - width / 2) + ny * .06, low)
                end = add(start, (tx * width, ty * width, 0))
                scene.banner(start, end, high, "BakuSkyGlassLight" if modern else "Glass", kind)
                if record.style == "residence":
                    outer_a = add(start, (nx * .75, ny * .75, -.15))
                    outer_b = add(end, (nx * .75, ny * .75, -.15))
                    scene.quad(kind, "White", add(start, (0, 0, -.15)),
                               add(end, (0, 0, -.15)), outer_b, outer_a, up=True)
                    scene.beam(kind, "Steel", add(outer_a, (0, 0, .9)),
                               add(outer_b, (0, 0, .9)), .06)
        scene.beam(kind, "White", (*a, base + building.height), (*b, base + building.height),
                   .5 if podium else .3)
    roof_polygon(scene, building.ring, base + building.height)
