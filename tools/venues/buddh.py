"""Buddh's layered roof slabs, long open straights and bowl grandstands."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import add, cross, mul, sub
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.east_architecture import (
    facade,
    footprint_stand,
    trees,
)
from venues.east_paint import apron_hatching
from venues.west_architecture import apron_band


def mapped_garage_front(scene: CircuitScene) -> None:
    building = scene.footprint(188019421)
    for index in range(9, 15):
        start, end = building.ring[index], building.ring[index + 1]
        length = math.dist(start, end)
        axis = (end[0] - start[0]) / length, (end[1] - start[1]) / length, 0.0
        normal = -axis[1], axis[0], 0.0
        midpoint = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        road, _ = scene.nearest(*midpoint)
        if (road.x - midpoint[0]) * normal[0] + (road.y - midpoint[1]) * normal[1] < 0:
            normal = mul(normal, -1)
        bays = max(1, round(length / 8))
        for bay in range(bays):
            pa = add((start[0], start[1], 0.0), mul(axis, length * bay / bays))
            pb = add((start[0], start[1], 0.0), mul(axis, length * (bay + 1) / bays))
            pa = pa[0], pa[1], scene.nearest(*pa[:2])[0].z + 0.05
            pb = pb[0], pb[1], scene.nearest(*pb[:2])[0].z + 0.05
            pa, pb = add(pa, mul(normal, 0.15)), add(pb, mul(normal, 0.15))
            scene.banner(pa, pb, 4.4, "Black", "Building_BuddhGaragePortals")
            for point in (pa, pb):
                scene.beam(
                    "Building_BuddhGaragePiers",
                    "White",
                    point,
                    add(point, (0.0, 0.0, 4.7)),
                    0.45,
                )
            scene.beam(
                "Building_BuddhGarageHeaders",
                "White",
                add(pa, (0.0, 0.0, 4.55)),
                add(pb, (0.0, 0.0, 4.55)),
                0.6,
                0.3,
            )
            for height in (4.1, 4.24, 4.38):
                scene.beam(
                    "Building_BuddhGarageRollerBoxes",
                    "Steel",
                    add(pa, (0.0, 0.0, height)),
                    add(pb, (0.0, 0.0, height)),
                    0.12,
                    0.06,
                )
    scene.landmarks.append(
        {
            "name": "Buddh registered garage portals",
            "osm_id": 188019421,
            "start_m": 470,
            "end_m": 870,
            "registration": "Road-facing retained ring edges9–15; dark full-width ground-floor portals, white structural piers and overhead roller boxes replace office-window appearance. Garage threshold elevations follow the adjacent road/pit apron; heights and bay spacing estimated from reference113–125s.",
        }
    )


def mapped_pit_roofs(scene: CircuitScene) -> None:
    pit = scene.footprint(188019421)
    footprint = Polygon(pit.ring)
    scene.terrain_cutouts.append(footprint)
    foundation = min(scene.ground(x, y) for x, y in pit.ring)
    for station, roof_height in ((804., 24.), (528., 20.)):
        sample = scene.at(station)
        axis = sample.tx, sample.ty, 0.
        outward = sample.ty, -sample.tx, 0.
        for level in range(4):
            half = 35+level*1.2
            corners = [add(sample.point(lane), mul(axis, along))
                       for along, lane in ((-half, 12), (half, 12), (half, 70), (-half, 70))]
            wing = footprint.intersection(Polygon([p[:2] for p in corners]))
            extension = 6-level*.9
            roof = unary_union([wing, translate(wing, xoff=-outward[0]*extension,
                                               yoff=-outward[1]*extension)])
            parts = [roof] if isinstance(roof, Polygon) else [p for p in roof.geoms if isinstance(p, Polygon)]
            coordinates = [p for part in parts for p in part.exterior.coords]
            lanes = [(x-sample.x)*outward[0]+(y-sample.y)*outward[1] for x, y in coordinates]
            near, far = min(lanes), max(lanes)
            slab = max(11.8, roof_height-level*3.2)

            def height(x: float, y: float, front: float = near, rear: float = far,
                       z: float = slab, origin: Point = (sample.x, sample.y, 0),
                       direction: Point = outward) -> float:
                lane = (x-origin[0])*direction[0]+(y-origin[1])*direction[1]
                return foundation+z+1.3*(lane-front)/max(.1, rear-front)

            for triangle in constrained_delaunay_triangles(roof).geoms:
                points: list[Point] = [(x, y, height(x, y)) for x, y in list(triangle.exterior.coords)[:3]]
                if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                    points.reverse()
                a, b, c = points
                scene.triangle('Building_BuddhPitRoof', 'Roof', a, b, c)
                scene.triangle('Building_BuddhPitSoffit', 'Concrete',
                               add(c, (0, 0, -.3)), add(b, (0, 0, -.3)), add(a, (0, 0, -.3)))
            for part in parts:
                for pa, pb in pairwise(list(orient(part).exterior.coords)):
                    a, b = (*pa, height(*pa)), (*pb, height(*pb))
                    scene.quad('Building_BuddhPitFascia', 'White',
                               add(a, (0, 0, -.3)), add(b, (0, 0, -.3)), b, a)
        for along in (-28., 0., 28.):
            location = add((sample.x, sample.y, 0), mul(axis, along))
            line = LineString([add(location, mul(outward, 12))[:2],
                               add(location, mul(outward, 70))[:2]])
            intersection = footprint.intersection(line)
            paths = [intersection] if isinstance(intersection, LineString) else [p for p in intersection.geoms if isinstance(p, LineString)]
            if not paths:
                continue
            path = max(paths, key=lambda p: p.length)
            foot = path.interpolate(path.length*.75)
            scene.beam('Building_BuddhPitColumns', 'White',
                       (foot.x, foot.y, foundation),
                       (foot.x, foot.y, foundation+roof_height-.5), .6)
    scene.landmarks.append({'name': 'Buddh mapped pit roof wings', 'osm_id': 188019421,
                            'roof_group_stations_m': '528 and 804',
                            'maximum_front_overhang_m': 6,
                            'foundation_m': foundation,
                            'source': 'Four-layer side canopies observed in reference 113, 117 and 121 seconds. Each group follows its actual mapped garage wing instead of the empty courtyard in the compound bounding rectangle. Layer spacing, overhang and heights remain visual estimates. The lowest fin clears the existing 11 m office roof.'})


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in (
        (260, 345, -1),
        (1000, 1080, 1),
        (1125, 1200, -1),
        (1370, 1475, 1),
        (2650, 2780, 1),
        (3230, 3320, -1),
        (3335, 3410, -1),
        (3450, 3530, 1),
        (3570, 3650, 1),
        (3675, 3750, -1),
        (3950, 4130, 1),
        (4170, 4320, 1),
        (4360, 4450, -1),
        (4595, 4680, -1),
        (4710, 4790, 1),
        (5005, 5100, 1),
    ):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in (
        (230, 370, 1, 13, "RunoffGreen"),
        (1330, 1505, -1, 18, "Runoff"),
        (2600, 2820, -1, 18, "RunoffGreen"),
        (3190, 3430, 1, 15, "RunoffRed"),
        (3500, 3770, -1, 12, "RunoffGreen"),
        (3900, 4340, -1, 18, "RunoffRed"),
        (4550, 4700, 1, 13, "Gravel"),
        (4970, 5130, -1, 17, "RunoffGreen"),
    ):
        scene.runoff(start, end, side, width, material)

    for start, end, side in (
        (260, 345, -1),
        (1370, 1475, 1),
        (2650, 2780, 1),
        (3230, 3410, -1),
        (3450, 3650, 1),
        (3675, 3750, -1),
        (3950, 4320, 1),
        (4360, 4450, -1),
    ):
        scene.runoff(start, end, side, 2.6, "RunoffGreen")

    for apex, side, distances in (
        (1041, -1, (150, 100, 50)),
        (1429, -1, (150, 100, 50)),
        (2719, -1, (150, 100, 50)),
        (3279, 1, (150, 100, 50)),
        (304, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (400, 1000, -1, "PanelAirtel"),
        (400, 1000, 1, "PanelAirtel"),
        (3110, 3310, -1, "PanelAirtel"),
        (3950, 4320, -1, "PanelAirtel"),
    ):
        scene.branding(start, end, side, material)

    apron_band(scene, 1335, 1500, -1, 15.0, 15.7, "RunoffBlue")
    apron_hatching(scene, 3210, 3410, 1, 2.8, 14.7, "Yellow")
    apron_band(scene, 3950, 4320, -1, 0.15, 2.6, "RunoffGreen")
    apron_band(scene, 3950, 4320, -1, 2.6, 2.8, "White")


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    footprint_stand(
        scene, 169886092, rows=30, roof="cantilever", seat_material="SeatBlue"
    )
    facade(scene, 188019421, 11, "modern", "White")
    mapped_garage_front(scene)
    mapped_pit_roofs(scene)
    facade(scene, 188028655, 8, "modern", "White")
    facade(scene, 496650379, 8, "modern", "Cream")
    scene.stand(
        1260, 1400, -1, rows=24, setback=12, roofed=False, seat_material="SeatBlue"
    )
    scene.stand(
        2640, 2800, -1, rows=20, setback=20, roofed=False, seat_material="SeatBlue"
    )
    scene.stand(
        3950, 4390, -1, rows=24, setback=22, roofed=True, seat_material="SeatBlue"
    )
    scene.stand(
        4550, 4700, -1, rows=19, setback=12, roofed=True, seat_material="SeatBlue"
    )
    p = scene.at(3080)
    c = p.point(-(p.half_width + p.left_shoulder + 23))
    base = c[0], c[1], scene.ground(c[0], c[1])
    scene.box("Building_BuddhTimingPylon", "White", add(base, (0, 0, 13)), 3.6, 3.6, 26)
    scene.box("Building_BuddhTimingPanel", "Black", add(base, (0, 0, 19)), 3.8, 3.8, 11)
    for level in range(10):
        scene.box(
            "Building_BuddhTimingPanel",
            "White",
            add(base, (0, 0, 14 + level)),
            3.9,
            3.9,
            0.09,
        )
    scene.landmarks.append(
        {
            "name": "Buddh timing pylon",
            "station_m": 3080,
            "height_m": 26,
            "dimensions": "White timing pylon and dark position panel observed near the infield braking approach; placement estimated.",
        }
    )
    for start, end, side, setback, spacing in (
        (700, 1250, 1, 35, 42),
        (1500, 2450, -1, 28, 45),
        (1550, 2450, 1, 40, 48),
        (2800, 3250, -1, 55, 55),
        (3450, 3800, 1, 60, 50),
        (4400, 4660, 1, 45, 45),
    ):
        trees(scene, start, end, side, setback, spacing, 8, palm=True)
    for start, end, side, setback in (
        (1000, 1300, -1, 90),
        (2000, 2600, 1, 95),
        (3100, 3600, -1, 95),
        (3700, 3900, 1, 100),
    ):
        trees(scene, start, end, side, setback, 45, 9)
