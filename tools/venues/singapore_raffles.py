"""Mapped Raffles Avenue construction frontage and the Ritz-Carlton complex."""

from __future__ import annotations

import gzip
import itertools
import math
from functools import lru_cache
from pathlib import Path

from circuit_dataclasses import OsmData, OsmElement, Point
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint

from venues.east_architecture import frame
from venues.singapore_raffles_dataclasses import SingaporeGroundParcel

SOURCES = Path(__file__).resolve().parents[2] / 'Attribution/Sources/singapore'


@lru_cache(maxsize=1)
def features() -> dict[int, OsmElement]:
    payload = gzip.decompress((SOURCES / 'raffles-context.osm.json.gz').read_bytes())
    return {element.id: element for element in TypeAdapter(OsmData).validate_json(payload).elements}


def path(scene: CircuitScene, osm_id: int) -> list[tuple[float, float]]:
    return [scene.geo(point.lat, point.lon) for point in features()[osm_id].geometry]


def ground_parcels(scene: CircuitScene) -> None:
    parcels = TypeAdapter(list[SingaporeGroundParcel]).validate_json((SOURCES / 'ground-parcels.json').read_bytes())
    for parcel in parcels:
        polygon = Polygon([scene.geo(latitude, longitude) for longitude, latitude in parcel.ring_lonlat])
        height = scene.at(parcel.anchor_native_station_m).z + parcel.height_offset_m
        scene.ground_patches.append((polygon, height, parcel.material))
        scene.landmarks.append({'name': parcel.name + ' ground reconstruction', 'osm_id': parcel.source_way_id,
                                'height_m': height, 'uncertainty_m': parcel.height_uncertainty_m,
                                'source_note': parcel.source_note})


def construction_frontage(scene: CircuitScene) -> None:
    site = Polygon(path(scene, 1221351351))
    level = scene.at(4000).z + .12
    scene.modeled_buildings.add(1492514975)
    for a, b in itertools.pairwise(site.exterior.coords):
        midpoint = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        sample, distance = scene.nearest(*midpoint)
        if not 3750 < sample.station < 4250 or distance > 35:
            continue
        count = max(1, math.ceil(math.dist(a, b) / 4))
        for index in range(count):
            first = a[0] + (b[0] - a[0]) * index / count, a[1] + (b[1] - a[1]) * index / count, level
            last = a[0] + (b[0] - a[0]) * (index + 1) / count, a[1] + (b[1] - a[1]) * (index + 1) / count, level
            scene.banner(first, last, 4.0, 'White', 'Building_NSConstructionHoarding')
            scene.beam('Building_NSConstructionHoarding', 'Steel', first, add(first, (0, 0, 4.8)), .10)
            scene.beam('Building_NSConstructionHoarding', 'Steel', add(first, (0, 0, 4.0)), add(last, (0, 0, 4.0)), .08)
    scene.landmarks.append({'name': 'NS Square construction frontage', 'osm_id': 1221351351,
                            'height_estimate_m': 4.0,
                            'source_note': 'Actual mapped construction parcel and street-facing boundary. Supplied 1250.81 s shows pale construction frontage behind race fencing. PUB confirms demolition and redevelopment during 2023–2027. Hoarding height and support spacing are estimates; no finished future stadium is invented.'})


def podium(scene: CircuitScene) -> None:
    building = scene.footprint(46594815)
    shape = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    center, axis, side, length, _width = frame(building)
    base = scene.at(4100).z + .15
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(shape)
    ring = list(shape.exterior.coords)
    for a, b in itertools.pairwise(ring):
        span = math.dist(a, b)
        if span < .2:
            continue
        pa, pb = (a[0], a[1], base), (b[0], b[1], base)
        scene.banner(pa, pb, 12.2, 'White', 'Building_RitzPodium')
        tangent = (b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.
        winding = 1 if shape.exterior.is_ccw else -1
        outward = tangent[1] * winding * .035, -tangent[0] * winding * .035, 0.
        bays = max(1, round(span / 4))
        for floor in range(3):
            for bay in range(bays):
                left = add(add(pa, outward), mul(tangent, span * (bay + .12) / bays))
                right = add(add(pa, outward), mul(tangent, span * (bay + .88) / bays))
                scene.banner(add(left, (0, 0, floor * 4.0 + 1.0)), add(right, (0, 0, floor * 4.0 + 1.0)),
                             2.5, 'WarmGlass' if (bay + floor) % 5 else 'Glass', 'Building_RitzPodiumWindows')
            scene.beam('Building_RitzPodium', 'White', add(pa, (0, 0, floor * 4.0 + 3.9)),
                       add(pb, (0, 0, floor * 4.0 + 3.9)), .22, .18)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        points = [(x, y, base + 12.2) for x, y in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            points[1], points[2] = points[2], points[1]
        scene.triangle('Building_RitzPodium', 'White', points[0], points[1], points[2])

    def vault(u: float, angle: float) -> Point:
        return (center[0] + axis[0] * u + side[0] * 8 * math.cos(angle),
                center[1] + axis[1] * u + side[1] * 8 * math.cos(angle),
                base + 12.2 + 3.8 * math.sin(angle))

    for along in range(12):
        u0, u1 = length * (-.4 + .8 * along / 12), length * (-.4 + .8 * (along + 1) / 12)
        for across in range(20):
            angle0, angle1 = math.pi * across / 20, math.pi * (across + 1) / 20
            a, b, c, d = vault(u0, angle0), vault(u1, angle0), vault(u1, angle1), vault(u0, angle1)
            if shape.covers(Polygon([a[:2], b[:2], c[:2], d[:2]])):
                scene.quad('Building_RitzEntryVault', 'WarmGlass', a, b, c, d, up=True)
                scene.quad('Building_RitzEntryVault', 'Glass', add(d, (0, 0, -.10)), add(c, (0, 0, -.10)),
                           add(b, (0, 0, -.10)), add(a, (0, 0, -.10)), up=False)
                scene.beam('Building_RitzEntryVaultFrame', 'White', add(a, (0, 0, .025)), add(d, (0, 0, .025)), .10)
        for across in range(21):
            angle = math.pi * across / 20
            a, b = vault(u0, angle), vault(u1, angle)
            if shape.covers(LineString([a[:2], b[:2]]).buffer(.035)):
                scene.beam('Building_RitzEntryVaultFrame', 'White', a, b, .07)
    for u in (-length * .4, length * .4):
        middle = center[0] + axis[0] * u, center[1] + axis[1] * u, base + 12.2
        for across in range(20):
            first, last = vault(u, math.pi * across / 20), vault(u, math.pi * (across + 1) / 20)
            if shape.covers(LineString([first[:2], last[:2]])):
                scene.triangle('Building_RitzEntryVaultEnd', 'WarmGlass', middle, first, last)
                scene.triangle('Building_RitzEntryVaultEnd', 'WarmGlass', middle, last, first)
                scene.beam('Building_RitzEntryVaultFrame', 'White', first, last, .10)
    scene.landmarks.append({'name': 'Ritz-Carlton mapped three-storey podium and glazed barrel-vault entrance',
                            'osm_id': building.osm_id, 'height_m': 16.0,
                            'source_note': 'Mapped 16 m/three-level outline, primary BCA description and owner entryway photo. Granite-coloured piers, glazing and an aluminium/glass barrel vault replace a generic roof-based extrusion. Exact vault width, position and mullion sizes are estimates.'})


def ritz_tower(scene: CircuitScene) -> None:
    element = features()[326926564]
    shape = Polygon(path(scene, element.id))
    ring = list(shape.exterior.coords)
    base = scene.at(4100).z + .15
    underside, top = base + 37, base + 140
    for a, b in itertools.pairwise(ring):
        span = math.dist(a, b)
        if span < .1:
            continue
        pa, pb = (a[0], a[1], underside), (b[0], b[1], underside)
        scene.banner(pa, pb, top - underside, 'White', 'Building_RitzTower')
        tangent = (b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.
        winding = 1 if shape.exterior.is_ccw else -1
        outward = tangent[1] * winding * .05, -tangent[0] * winding * .05, 0.
        bays = max(1, round(span / 3.7))
        for floor in range(29):
            for bay in range(bays):
                left = add(add(pa, outward), mul(tangent, span * (bay + .16) / bays))
                right = add(add(pa, outward), mul(tangent, span * (bay + .84) / bays))
                lift = (top - underside) * (floor + .14) / 29
                scene.banner(add(left, (0, 0, lift)), add(right, (0, 0, lift)),
                             (top - underside) / 29 * .72,
                             'WarmGlass' if (floor * 7 + bay * 3) % 11 < 5 else 'Glass', 'Building_RitzTowerWindows')
        scene.beam('Building_RitzTowerStructure', 'White', pa, (a[0], a[1], top), .32)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coordinates = list(triangle.exterior.coords)[:3]
        roof = [(x, y, top) for x, y in coordinates]
        soffit = [(x, y, underside) for x, y in coordinates]
        if not triangle.exterior.is_ccw:
            roof[1], roof[2] = roof[2], roof[1]
            soffit[1], soffit[2] = soffit[2], soffit[1]
        scene.triangle('Building_RitzTower', 'White', roof[0], roof[1], roof[2])
        scene.triangle('Building_RitzTower', 'White', soffit[2], soffit[1], soffit[0])
    for osm_id in (591301835, 591301847, 591301844):
        support = Polygon(path(scene, osm_id))
        for a, b in itertools.pairwise(support.exterior.coords):
            scene.banner((a[0], a[1], base + 10), (b[0], b[1], base + 10),
                         27, 'White', 'Building_RitzTowerLegs')
    scene.landmarks.append({'name': 'The Ritz-Carlton, Millenia Singapore mapped slender tower and exposed legs',
                            'osm_id': element.id, 'height_m': 140, 'underbody_height_m': 37,
                            'source_note': 'Previously omitted OSM building-part outline: height 140 m, min_height 30 m, 32 levels. Owner describes 37 m stilt-like legs, while BCA places first guestrooms about 30 m above street. The rendered 37 m clearance follows the owner, with the 30–37 m source discrepancy retained. Twenty-nine upper floor bands follow the mapped three-level podium offset; exact window spacing is reconstructed. No source pixels are shipped.'})


def build_context(scene: CircuitScene) -> None:
    construction_frontage(scene)
    podium(scene)
    ritz_tower(scene)
    raised_driveway(scene)


def driveway_points(scene: CircuitScene) -> list[tuple[float, float]]:
    result = list(reversed(path(scene, 620797981)))
    result.extend(reversed(path(scene, 784662624)[:-1]))
    result.extend(reversed(path(scene, 741167072)[:-1]))
    return result


def raised_driveway(scene: CircuitScene) -> None:
    line = LineString(driveway_points(scene))
    base = scene.at(4100).z + .15
    count = math.ceil(line.length / 2)
    for index in range(count):
        progress0, progress1 = index / count, (index + 1) / count
        c0, c1 = line.interpolate(progress0, normalized=True), line.interpolate(progress1, normalized=True)
        distance = math.hypot(c1.x - c0.x, c1.y - c0.y)
        if distance < .01:
            continue
        normal = -(c1.y - c0.y) / distance, (c1.x - c0.x) / distance
        z0 = base + 8.0 * (progress0 * progress0 * (3 - 2 * progress0))
        z1 = base + 8.0 * (progress1 * progress1 * (3 - 2 * progress1))
        a = c0.x + normal[0] * 2.4, c0.y + normal[1] * 2.4, z0
        b = c1.x + normal[0] * 2.4, c1.y + normal[1] * 2.4, z1
        c = c1.x - normal[0] * 2.4, c1.y - normal[1] * 2.4, z1
        d = c0.x - normal[0] * 2.4, c0.y - normal[1] * 2.4, z0
        shape = Polygon([a[:2], b[:2], c[:2], d[:2]]).difference(scene.corridor_mask.buffer(.25))
        if shape.is_empty:
            continue
        scene.terrain_cutouts.append(shape)
        for triangle in constrained_delaunay_triangles(shape).geoms:
            points: list[Point] = []
            for x, y in list(triangle.exterior.coords)[:3]:
                fraction = max(0., min(1., ((x - c0.x) * (c1.x - c0.x) + (y - c0.y) * (c1.y - c0.y)) / distance ** 2))
                points.append((x, y, z0 + (z1 - z0) * fraction + .02))
            if not triangle.exterior.is_ccw:
                points[1], points[2] = points[2], points[1]
            scene.triangle('Building_RitzRaisedDriveway', 'Concrete', points[0], points[1], points[2])
        for first, last in ((a, b), (d, c)):
            edge = LineString([first[:2], last[:2]])
            if edge.intersects(scene.corridor_mask.buffer(.35)):
                continue
            scene.quad('Building_RitzDrivewayRetainingWall', 'White',
                       (first[0], first[1], base), (last[0], last[1], base), last, first)
            scene.quad('Building_RitzDrivewayRetainingWall', 'White',
                       (last[0], last[1], base), (first[0], first[1], base), first, last)
            scene.beam('Building_RitzDrivewayParapet', 'White', add(first, (0, 0, .35)), add(last, (0, 0, .35)), .18, .6)
    scene.landmarks.append({'name': 'Ritz-Carlton mapped rising lobby driveway', 'height_rise_estimate_m': 8.0,
                            'height_uncertainty_m': 2.0,
                            'source_note': 'Exact mapped access paths 620797981/784662624/741167072 connect Raffles Avenue with the podium. Marriott identifies the lobby on Level 3; the owner shows the glazed barrel-vault arrival. The 8.0 m rise, 4.8 m pavement width and retaining edges are reconstructed estimates, not survey. The raised driveway is retained instead of flattening the entire hotel property. Paving beyond the closed race wall is visual only.'})


def frontage_trees(scene: CircuitScene) -> None:
    driveway = LineString(driveway_points(scene)).buffer(4)
    occupied = [Polygon(building.ring).buffer(2) for building in scene.buildings
                if building.osm_id != 1492514975]
    for side in (-1, 1):
        placed = 0
        for index in range(36):
            station = 3892.119939 + (4446.291439 - 3892.119939) * (index + .5) / 36
            sample = scene.at(station)
            shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
            lane = side * (sample.half_width + .95 + shoulder + (12 if side < 0 else 9) + (index % 3) * .7)
            point = sample.point(lane)
            root = ShapePoint(point[:2])
            if driveway.covers(root) or any(shape.covers(root) for shape in occupied + scene.water_shapes):
                continue
            nearby, distance = scene.nearest(point[0], point[1])
            if distance < nearby.half_width + 5:
                continue
            scene.broadleaf((point[0], point[1], scene.ground(point[0], point[1])),
                            9.5 + index % 4 * .6, index + (100 if side > 0 else 0))
            placed += 1
        scene.vegetation.append({'type': 'Raffles Avenue broadleaf frontage', 'side': side,
                                 'start_m': 3892.119939, 'end_m': 4446.291439, 'count': placed,
                                 'placement': 'Observed near-wall canopy in the direct Flyer approach reference; individual positions and heights estimated. Roots avoid the mapped rising driveway, buildings, water and every racing arm.'})


def flyer_terminal(scene: CircuitScene) -> None:
    building = scene.footprint(51761904)
    shape = Polygon(building.ring)
    base = scene.at(4519.459519).z + 1.
    ring = list(shape.exterior.coords)
    for a, b in itertools.pairwise(ring):
        span = math.dist(a, b)
        if span < .2:
            continue
        tangent = (b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.
        pa, pb = (a[0], a[1], base), (b[0], b[1], base)
        scene.banner(pa, pb, 16, 'White', 'Building_FlyerTerminal')
        winding = 1 if shape.exterior.is_ccw else -1
        normal = tangent[1] * winding * .04, -tangent[0] * winding * .04, 0.
        for floor in range(3):
            bays = max(1, round(span / 5.5))
            for bay in range(bays):
                left = add(add(pa, normal), mul(tangent, span * (bay + .1) / bays))
                right = add(add(pa, normal), mul(tangent, span * (bay + .9) / bays))
                scene.banner(add(left, (0, 0, floor * 5.15 + .9)), add(right, (0, 0, floor * 5.15 + .9)),
                             3.4, 'WarmGlass' if (bay + floor) % 4 else 'Glass', 'Building_FlyerTerminalWindows')
            scene.beam('Building_FlyerTerminalTerraces', 'White', add(pa, (0, 0, floor * 5.15 + 4.8)),
                       add(pb, (0, 0, floor * 5.15 + 4.8)), .35, .30)
    wheel_center, axis, normal, _length, _width = frame(scene.footprint(230082125))
    atrium = Polygon([(wheel_center[0] + axis[0] * 30 * math.cos(step * math.tau / 64) + normal[0] * 14 * math.sin(step * math.tau / 64),
                       wheel_center[1] + axis[1] * 30 * math.cos(step * math.tau / 64) + normal[1] * 14 * math.sin(step * math.tau / 64))
                      for step in range(64)]).intersection(shape)
    occupied = shape.difference(atrium)
    for triangle in constrained_delaunay_triangles(occupied).geoms:
        points = [(x, y, base + 16) for x, y in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            points[1], points[2] = points[2], points[1]
        scene.triangle('Building_FlyerTerminalRoof', 'White', points[0], points[1], points[2])
    scene.terrain_cutouts.append(occupied)
    for index, (along, across) in enumerate(((-10, -6), (-8, 7), (9, -7), (11, 6))):
        x = wheel_center[0] + axis[0] * along + normal[0] * across
        y = wheel_center[1] + axis[1] * along + normal[1] * across
        if atrium.covers(ShapePoint(x, y)):
            scene.broadleaf((x, y, base), 7.5 + index * .4, 600 + index)
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'name': 'Singapore Flyer mapped three-storey retail terminal',
                            'osm_id': building.osm_id, 'height_estimate_m': 16.0, 'levels': 3,
                            'source_note': 'Retained operator retail description specifies a 16 m, three-storey centre beneath the 150 m wheel. The mapped exterior replaces a generic four-window-level extrusion. Exact shopfront rhythm, terraces and 60 by 28 m central roof opening are reconstructed. The operator describes the central rainforest atrium; the opening also clears the lowest capsule path. Its exact inner outline is not surveyed.'})
