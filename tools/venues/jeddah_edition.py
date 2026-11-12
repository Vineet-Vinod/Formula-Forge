"""Mapped terraced EDITION frontage outside the northern banked hairpin."""

from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.polygon import orient

from venues.east_architecture import frame
from venues.pit_compounds import roof_shell


def edition_hotel(scene: CircuitScene) -> None:
    building = scene.footprint(1258744123)
    center, axis, normal, length, width = frame(building)
    footprint = Polygon(building.ring).difference(scene.road_mask.buffer(3))
    local = affine_transform(footprint, [axis[0], axis[1], normal[0], normal[1],
                                       -center[0] * axis[0] - center[1] * axis[1],
                                       -center[0] * normal[0] - center[1] * normal[1]])
    start, low, end, high = local.bounds
    road, distance = scene.nearest(center[0], center[1])
    facing = 1 if (road.x - center[0]) * normal[0] + (road.y - center[1]) * normal[1] > 0 else -1
    base_z = max(scene.ground(x, y) for x, y in building.ring) + .15

    def point(u: float, v: float, height: float) -> Point:
        return (center[0] + axis[0] * u + normal[0] * v,
                center[1] + axis[1] * u + normal[1] * v, base_z + height)

    def world_shape(shape: Polygon) -> Polygon:
        result = affine_transform(shape, [axis[0], normal[0], axis[1], normal[1], center[0], center[1]])
        if not isinstance(result, Polygon):
            raise TypeError('EDITION terrace must remain one mapped polygon')
        return orient(result)

    def terrace(setback: float, end_inset: float) -> Polygon:
        front_low = low + setback if facing < 0 else low + .6
        rear_high = high - setback if facing > 0 else high - .6
        result = local.intersection(box(start + end_inset, front_low, end - end_inset, rear_high))
        if not isinstance(result, Polygon):
            raise TypeError('EDITION frontage must remain a single terrace')
        return world_shape(result)

    owned = world_shape(local)
    scene.terrain_cutouts.append(owned)
    scene.modeled_buildings.add(building.osm_id)
    for a, b in zip(building.ring, building.ring[1:] + building.ring[:1]):
        za, zb = scene.ground(*a) - .1, scene.ground(*b) - .1
        scene.quad('Building_EditionFoundation', 'Concrete',
                   (a[0], a[1], za), (b[0], b[1], zb),
                   (b[0], b[1], base_z + .2), (a[0], a[1], base_z + .2))
    for level, setback in enumerate((1.3, 3.4, 6.3, 8.8)):
        z = level * 6.0
        slab = terrace(max(.5, setback - 2.4), .5 + level * 1.5)
        body = terrace(setback, 1.1 + level * 1.5).buffer(-.08, join_style='mitre')

        def slab_height(_x: float, _y: float, height: float = base_z + z + .28) -> float:
            return height

        roof_shell(scene, slab, slab_height,
                   'Building_EditionTerrace', 'White', 'Concrete', 'White', thickness=.32)
        ring = list(body.exterior.coords)[:-1]
        for a, b in zip(ring, ring[1:] + ring[:1]):
            pa, pb = (a[0], a[1], base_z + z + .4), (b[0], b[1], base_z + z + .4)
            scene.banner(pa, pb, 5.2, 'Glass', 'Building_EditionRecessedGlazing')
            span = math.dist(a, b)
            for bay in range(max(1, round(span / 6)) + 1):
                fraction = bay / max(1, round(span / 6))
                x, y = a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
                scene.beam('Building_EditionMullions', 'Steel',
                           (x, y, base_z + z + .45), (x, y, base_z + z + 5.5), .075)
        slab_ring = list(slab.exterior.coords)[:-1]
        for a, b in zip(slab_ring, slab_ring[1:] + slab_ring[:1]):
            span = math.dist(a, b)
            outward_x, outward_y = (b[1] - a[1]) / span, (a[0] - b[0]) / span
            if (outward_x * normal[0] + outward_y * normal[1]) * facing < .6:
                continue
            rail_a = a[0] - outward_x * .16, a[1] - outward_y * .16, base_z + z + 1.25
            rail_b = b[0] - outward_x * .16, b[1] - outward_y * .16, base_z + z + 1.25
            scene.beam('Building_EditionTerraceRails', 'Steel', rail_a, rail_b, .09)
    canopy = terrace(.45, .45)
    roof_shell(scene, canopy, lambda _x, _y: base_z + 24.5,
               'Building_EditionProjectingCanopy', 'White', 'Roof', 'White', thickness=.48)
    front_v = high - 1.1 if facing > 0 else low + 1.1
    for u in (-length * .34, 0.0, length * .34):
        frame_a, frame_b = point(u - 4, front_v - facing * .2, .35), point(u + 4, front_v - facing * .2, 18.5)
        if owned.covers(LineString([frame_a[:2], frame_b[:2]]).buffer(.48)):
            scene.beam('Building_EditionAngledWhiteFrame', 'White', frame_a, frame_b, .7, .58)
    for u in (start + 3, end - 3):
        column_a, column_b = point(u, front_v - facing * .25, .35), point(u, front_v - facing * .25, 24.1)
        if owned.covers(LineString([column_a[:2], column_b[:2]]).buffer(.35)):
            scene.beam('Building_EditionCanopyColumns', 'White', column_a, column_b, .55)
    scene.landmarks.append({
        'name': 'The Jeddah EDITION terraced track frontage', 'osm_id': building.osm_id,
        'mapped_length_m': length, 'mapped_width_m': width,
        'adjacent_native_station_m': road.station, 'distance_from_road_m': distance,
        'foundation_top_m': base_z, 'roof_above_foundation_m': 24.5,
        'roof_height_uncertainty_m': 4.0,
        'source': 'Owner identifies four storeys and a 12 m lobby volume; direct overview04/331s show tiered slabs, recessed glazing, deep roof and angled white bracing. Four visual tiers are not a measured floor section. The provisional17.2m total estimate was rejected; no unsupported height reduction is made.',
    })
