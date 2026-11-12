"""Raffles City building parts and the temporary Stamford spectator terrace."""

from __future__ import annotations

import gzip
import math
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import OsmData, OsmElement, Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

SOURCES = Path(__file__).resolve().parents[2] / "Attribution/Sources/singapore"


@lru_cache(maxsize=1)
def features() -> dict[int, OsmElement]:
    data = gzip.decompress((SOURCES / "stamford-context.osm.json.gz").read_bytes())
    return {element.id: element for element in TypeAdapter(OsmData).validate_json(data).elements}


def tower_shape(scene: CircuitScene, element: OsmElement) -> Polygon:
    ring = [scene.geo(point.lat, point.lon) for point in element.geometry]
    if element.id == 172364975:
        # Resample the mapped curved front; retain the flat service-side edges.
        center = scene.geo(1.293309160, 103.853417623)
        curved = []
        for a, b in pairwise(ring[:12]):
            aa, ab = math.atan2(a[1] - center[1], a[0] - center[0]), math.atan2(b[1] - center[1], b[0] - center[0])
            delta = (ab - aa + math.pi) % math.tau - math.pi
            ra, rb = math.dist(a, center), math.dist(b, center)
            steps = max(1, math.ceil(math.dist(a, b) / 2))
            for step in range(steps):
                t = step / steps
                radius, angle = ra + (rb - ra) * t, aa + delta * t
                curved.append((center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle)))
        ring = [*curved, *ring[11:]]
    return orient(Polygon(ring))


def horizontal_shell(scene: CircuitScene, shape: Polygon, z: float, thickness: float, kind: str, material: str) -> None:
    for triangle in constrained_delaunay_triangles(shape).geoms:
        ring = list(orient(triangle).exterior.coords)[:3]
        a, b, c = [(x, y, z) for x, y in ring]
        scene.triangle(kind, material, a, b, c)
        scene.triangle(kind, material, add(c, (0, 0, -thickness)), add(b, (0, 0, -thickness)), add(a, (0, 0, -thickness)))
    for boundary in (shape.exterior, *shape.interiors):
        for a, b in pairwise(boundary.coords):
            pa, pb = (a[0], a[1], z), (b[0], b[1], z)
            scene.quad(kind, material, pa, add(pa, (0, 0, -thickness)), add(pb, (0, 0, -thickness)), pb)


def city_tower(scene: CircuitScene, element: OsmElement, datum: float) -> None:
    shape = tower_shape(scene, element)
    height = float(element.tags["height"])
    minimum = float(element.tags["min_height"])
    levels = int(element.tags["building:levels"]) - int(element.tags["building:min_level"])
    swiss = element.id == 172364975
    office = element.id == 172364974
    kind = "Building_" + {172364975: "SwissotelStamford", 172364973: "FairmontSingapore", 172364974: "RafflesCityTower"}[element.id]
    crown_height = 12.0 if swiss else 3.0
    room_levels = levels - 4 if swiss else levels - 1
    room_top = datum + height - crown_height
    bottom = datum + minimum
    inset = .9 if not office else .28
    inner = orient(shape.buffer(-inset))
    floor_band = shape.difference(inner)
    assert isinstance(floor_band, Polygon)
    shell_ring = list(inner.exterior.coords)
    for a, b in pairwise(shell_ring):
        scene.banner((a[0], a[1], bottom), (b[0], b[1], bottom), room_top - bottom,
                     "Glass", kind + "RecessedRooms")
    for level in range(room_levels + 1):
        z = bottom + (room_top - bottom) * level / room_levels
        horizontal_shell(scene, floor_band, z, .18 if not office else .24,
                         kind + "Balconies", "White" if not office else "Concrete")
    for edge_index, (a, b) in enumerate(pairwise(shape.exterior.coords)):
        span = math.dist(a, b)
        if span < .1:
            continue
        tangent = (b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.
        inward = -tangent[1], tangent[0], 0.
        bays = max(1, round(span / (3.1 if not office else 4.0)))
        for bay in range(bays):
            t = (bay + .5) / bays
            point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, bottom)
            center = add(add(point, mul(inward, inset * .5)), (0, 0, (room_top - bottom) / 2))
            scene.box(kind + "Piers", "White" if not office else "Concrete", center,
                      .22, inset, room_top - bottom, math.atan2(tangent[1], tangent[0]))
            for floor in range(room_levels):
                if (bay * 7 + floor * 11 + edge_index * 3) % 17 > 3:
                    continue
                first = add(add(point, mul(tangent, -span / bays * .31)), mul(inward, inset - .035))
                last = add(add(point, mul(tangent, span / bays * .31)), mul(inward, inset - .035))
                z = (room_top - bottom) * (floor + .2) / room_levels
                scene.banner(add(first, (0, 0, z)), add(last, (0, 0, z)),
                             (room_top - bottom) / room_levels * .65, "WarmGlass", kind + "LitRooms")
    crown = orient(shape.buffer(-.22))
    for a, b in pairwise(crown.exterior.coords):
        scene.banner((a[0], a[1], room_top), (b[0], b[1], room_top), crown_height - .6,
                     "WarmGlass" if swiss else "Glass", kind + "Crown")
        span = math.dist(a, b)
        count = max(1, math.ceil(span / 3.0))
        for index in range(count):
            t = (index + .5) / count
            point = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, room_top
            scene.beam(kind + "CrownMullions", "White" if not office else "Concrete",
                       point, add(point, (0, 0, crown_height - .6)), .12)
    for level in range(4 if swiss else 2):
        z = room_top + (crown_height - .6) * level / (3 if swiss else 1)
        horizontal_shell(scene, shape.difference(crown), z, .22, kind + "CrownBands", "White" if not office else "Concrete")
    horizontal_shell(scene, shape, datum + height, .6, kind + "Roof", "White" if not office else "Concrete")
    scene.modeled_buildings.add(element.id)
    scene.landmarks.append({"name": element.tags["name"], "osm_id": element.id,
                            "height_m": height, "minimum_height_m": minimum,
                            "foundation_datum_m": datum, "mapped_levels": int(element.tags["building:levels"]),
                            "source_note": "Retained OSM building-part ring and height/min_height tags share the existing 30 m mall podium. Height is total above ground, not additional to the podium. Owner exterior supports recessed balcony grids, the Swissôtel glazed crown and the contrasting rectangular office tower. Floor-band, bay and crown details are reconstructed estimates; no source pixels are used."})


def stamford_stand(scene: CircuitScene) -> Polygon:
    sample = scene.at(1818)
    axis, outward = (sample.tx, sample.ty, 0.), (sample.ty, -sample.tx, 0.)
    front = sample.point(sample.half_width + 10.0)
    base_z = (scene.at(1765).z + scene.at(1870).z) / 2 + .12
    rows, length, depth = 18, 105., 16.2

    def point(along: float, reach: float, z: float) -> Point:
        return add(add((front[0], front[1], z), mul(axis, along)), mul(outward, reach))

    footprint = Polygon([point(u, v, 0)[:2] for u, v in ((-length / 2, 0), (length / 2, 0), (length / 2, depth), (-length / 2, depth))])
    scene.ground_patches.append((footprint, base_z, "Runoff"))
    for bay in range(15):
        a, b = -length / 2 + length * bay / 15, -length / 2 + length * (bay + 1) / 15
        for row in range(rows):
            reach, top = row * .9, base_z + .8 + row * .45
            pa, pb, pc, pd = point(a, reach, top), point(b, reach, top), point(b, reach + .9, top), point(a, reach + .9, top)
            scene.quad("Building_StamfordStandTerraces", "Concrete", pa, pb, pc, pd, up=True)
            scene.quad("Building_StamfordStandRisers", "Concrete", add(pa, (0, 0, -.45)), add(pb, (0, 0, -.45)), pb, pa)
            scene.beam("Building_StamfordStandSeats", "SeatRed", point(a, reach + .38, top + .16), point(b, reach + .38, top + .16), .38, .18)
            scene.spectators(point(a, reach + .36, top + .25), point(b, reach + .36, top + .25), row, "Building_Crowd_Stamford")
        for u in (a, b):
            for reach in (0., depth):
                height = base_z + .8 + (rows - 1) * .45 * reach / depth
                scene.beam("Building_StamfordStandScaffold", "Steel", point(u, reach, base_z), point(u, reach, height), .14)
            scene.beam("Building_StamfordStandScaffold", "Steel", point(u, 0, base_z + .8), point(u, depth, base_z + .8 + (rows - 1) * .45), .14)
            scene.beam("Building_StamfordStandScaffold", "Steel", point(u, depth, base_z), point(u, 0, base_z + .8), .12)
    scene.landmarks.append({"name": "Temporary Stamford Grandstand", "start_m": 1765,
                            "end_m": 1870, "side": 1, "rows_estimate": rows,
                            "length_estimate_m": length, "depth_estimate_m": depth,
                            "source_note": "Operator 2025 event map and ticket page place Stamford Grandstand on the RIGHT between T7 and T8, beside War Memorial Park. Continuous supplied 634/636/638 s shows the open scaffold-backed seating. Length 105 ±25 m, depth 16.2 ±4 m and 18 rows are visual estimates, not an OSM stand survey. Only its temporary footprint receives adjacent-road-level ground reconstruction; the rest of the park remains unchanged."})
    return footprint


def build_stamford(scene: CircuitScene) -> Polygon:
    podium = scene.footprint(39487263)
    datum = min(scene.ground(x, y) for x, y in podium.ring)
    for osm_id in (172364973, 172364974, 172364975):
        city_tower(scene, features()[osm_id], datum)
    return stamford_stand(scene)


def stamford_tree_band(scene: CircuitScene, stand: Polygon) -> None:
    start, end, spacing = 1390.380744, 1948.274616, 18.
    footprints = [Polygon(building.ring).buffer(2) for building in scene.buildings]
    footprints.append(stand.buffer(2))
    count, placed = math.ceil((end - start) / spacing), 0
    for index in range(count):
        sample = scene.at(start + (end - start) * (index + .5) / count)
        lane = sample.half_width + .95 + sample.left_shoulder + 5 + index % 3 * 2.5
        point = sample.point(lane)
        nearest, distance = scene.nearest(*point[:2])
        shape_point = ShapePoint(point[:2])
        if distance < nearest.half_width + 5:
            continue
        if any(shape.covers(shape_point) for shape in scene.water_shapes):
            continue
        if any(shape.contains(shape_point) for shape in footprints):
            continue
        scene.broadleaf((point[0], point[1], scene.ground(*point[:2])), 13 + index % 4 * .6, index + round(start))
        placed += 1
    scene.vegetation.append({"type": "broadleaf", "start_m": start, "end_m": end,
                             "side": 1, "count": placed, "setback_m": 5,
                             "placement": "Original tree lattice, heights and seeds retained. Roots within 2 m of the source-backed temporary Stamford stand are excluded."})
