"""The low Kennedy retail strip with its declared planning-based roof anchor."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point, RetainedTerrainSource
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.monaco_dataclasses import RetailTerrace


def retail_terrace(scene: CircuitScene, base_z: float, config: RetailTerrace) -> None:
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    roof = config.roof_absolute_m - datum
    if roof - base_z < 2.5:
        raise ValueError('The planning anchor must retain the actual lower retail body')
    building = scene.footprint(config.osm_id)
    original = Polygon(building.ring).difference(scene.road_mask.buffer(1.2))
    if not isinstance(original, Polygon):
        raise TypeError('Retail terrace must retain the original single ground body')
    body = orient(original, sign=1.)
    scene.modeled_buildings.add(building.osm_id)
    scene.terrain_cutouts.append(original)
    neighbor = Polygon(scene.footprint(507048725).ring)
    kind = 'Building_RetailTerrace'
    retaining_area = 0.
    for a, b in pairwise(body.exterior.coords):
        span = math.dist(a, b)
        if span < .001:
            continue
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        nx, ny = ty, -tx
        low_a, low_b = min(base_z, scene.ground(*a) - .12), min(base_z, scene.ground(*b) - .12)
        scene.quad(kind, 'Cream', (*a, low_a), (*b, low_b), (*b, roof), (*a, roof))
        bays = max(1, round(span / 3.8))
        for storey in range(config.lower_storeys if span > 1.5 else 0):
            pitch = (roof - base_z) / config.lower_storeys
            bottom = base_z + pitch * storey + (.35 if storey == 0 else .65)
            top = min(roof - .3, base_z + pitch * (storey + 1) - .45)
            for bay in range(bays):
                mid, width = (bay + .5) * span / bays, min(1.65, span / bays * .58)
                x, y = a[0] + tx * mid + nx * .025, a[1] + ty * mid + ny * .025
                first = x - tx * width / 2, y - ty * width / 2, bottom
                last = x + tx * width / 2, y + ty * width / 2, bottom
                scene.banner(first, last, top - bottom, 'Glass', kind)
                scene.banner((first[0], first[1], bottom - .1),
                             (last[0], last[1], bottom - .1), .12, 'White', kind)
        scene.beam(kind, 'White', (a[0] - nx * .1, a[1] - ny * .1, roof + config.roof_coping_height_m / 2),
                   (b[0] - nx * .1, b[1] - ny * .1, roof + config.roof_coping_height_m / 2), .18,
                   config.roof_coping_height_m)
        points = [a, b]
        for p, q in pairwise(points):
            outside = ((p[0] + q[0]) / 2 + nx * .05, (p[1] + q[1]) / 2 + ny * .05)
            if neighbor.covers(ShapePoint(outside)):
                continue
            za, zb = scene.ground(*p), scene.ground(*q)
            if max(za, zb) <= roof:
                continue
            if min(za, zb) < roof:
                t = (roof - za) / (zb - za)
                crossing = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
                if za < roof:
                    p, za = crossing, roof
                else:
                    q, zb = crossing, roof
            za += config.retaining_ground_overlap_m
            zb += config.retaining_ground_overlap_m
            bottom_a: Point = p[0], p[1], roof
            bottom_b: Point = q[0], q[1], roof
            scene.quad('Building_RetailStreetRetaining', 'Concrete', bottom_a, bottom_b, (*q, zb), (*p, za))
            scene.quad('Building_RetailStreetRetaining', 'Concrete', bottom_b, bottom_a, (*p, za), (*q, zb))
            retaining_area += math.dist(p, q) * ((za + zb) / 2 - roof)
    for triangle in constrained_delaunay_triangles(body).geoms:
        roof_points = [(x, y, roof) for x, y in list(triangle.exterior.coords)[:3]]
        if not triangle.exterior.is_ccw:
            roof_points.reverse()
        scene.triangle('Building_RetailRoofTerrace', 'Concrete', roof_points[0], roof_points[1], roof_points[2])
    scene.landmarks.append({
        'name': 'Quick Silver strip with a planning-based roof anchor',
        'osm_id': building.osm_id, 'roof_absolute_m': config.roof_absolute_m,
        'body_area_m2': body.area, 'base_relative_m': base_z,
        'street_retaining_area_m2': retaining_area,
        'retaining_ground_overlap_m': config.retaining_ground_overlap_m,
        'qualification': 'Planning upper-level 9.95 m anchor, not a new roof survey. Retained 2017 plan and 2019 '
                         'ortho differ in epoch from supplied edited reference with year unverified. Same lower fine-ground '
                         'base and exact original road-clipped parcel. Two lower storeys remain an estimate. '
                         'Pale flat terrace/coping and upper street retaining are bounded reconstruction. '
                         'No public rooftop access, stair or raised pavilion invented. External mapped west '
                         'steps1365041507 and nearby Miramar remain separate. No road/terrain/physics edits.',
    })
