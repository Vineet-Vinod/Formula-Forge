"""Footprint-bound exposed concrete and the source-visible low luffing crane."""

from __future__ import annotations

import math
from dataclasses import asdict
from itertools import pairwise
from pathlib import Path

from circuit_dataclasses import Building, Point
from circuit_mesh import MeshScene, add, mul
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point as PlanPoint
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, triangulate

from venues.east_architecture import frame, mapped
from venues.jeddah_construction_dataclasses import ConstructionProof, ConstructionRecipe

SOURCE = Path(__file__).resolve().parents[2] / 'Attribution/Sources/jeddah/construction-reconstruction.json'


def source_record() -> ConstructionRecipe:
    return TypeAdapter(ConstructionRecipe).validate_json(SOURCE.read_bytes())


def floor_plate(building: Building, recipe: ConstructionRecipe, fraction: float) -> Polygon:
    center, _axis, _normal, length, width = frame(building)
    radius = min(length, width) * recipe.plate_radius_fraction
    radius *= 1 - .32 * fraction * fraction
    angle = fraction * math.pi * .48
    polygon = Polygon([(center[0] + radius * math.cos(angle + face * math.pi / 2 + math.pi / 4),
                        center[1] + radius * math.sin(angle + face * math.pi / 2 + math.pi / 4))
                       for face in range(4)]).intersection(Polygon(building.ring))
    if not isinstance(polygon, Polygon) or polygon.area <= 1:
        raise ValueError('Construction floor must remain one footprint-bound plate')
    return orient(polygon, sign=1)


def slab(scene: MeshScene, polygon: Polygon, z: float, depth: float) -> None:
    for triangle in triangulate(polygon):
        if not polygon.covers(triangle):
            continue
        a, b, c = list(orient(triangle, sign=1).exterior.coords)[:3]
        scene.triangle('Building_DiamondConcreteSlab', 'Concrete',
                       (a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z))
        scene.triangle('Building_DiamondConcreteSlab', 'JeddahConstruction',
                       (c[0], c[1], z - depth), (b[0], b[1], z - depth), (a[0], a[1], z - depth))
    ring = list(polygon.exterior.coords)
    for a, b in pairwise(ring):
        scene.quad('Building_DiamondConcreteSlab', 'Concrete',
                   (a[0], a[1], z - depth), (b[0], b[1], z - depth),
                   (b[0], b[1], z), (a[0], a[1], z))


def luffing_crane(scene: MeshScene, base: Point, direction: Point, recipe: ConstructionRecipe) -> None:
    side = (-direction[1], direction[0], 0.0)
    half = recipe.side_crane_mast_width_m / 2
    head = add(base, (0, 0, recipe.side_crane_height_m))
    for x, y in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
        foot = add(add(base, mul(direction, x * half)), mul(side, y * half))
        scene.beam('Building_DiamondSideCraneMast', 'Steel', foot,
                   add(foot, (0, 0, recipe.side_crane_height_m)), .16)
    divisions = math.ceil(recipe.side_crane_height_m / 3)
    corners = [add(mul(direction, x * half), mul(side, y * half))
               for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for level in range(divisions + 1):
        center = add(base, (0, 0, recipe.side_crane_height_m * level / divisions))
        for first, last in zip(corners, corners[1:] + corners[:1], strict=True):
            scene.beam('Building_DiamondSideCraneMastTies', 'Steel',
                       add(center, first), add(center, last), .12)
    for level in range(divisions):
        z0 = recipe.side_crane_height_m * level / divisions
        z1 = recipe.side_crane_height_m * (level + 1) / divisions
        for x, y, dx, dy in ((-1, -1, 1, -1), (1, -1, 1, 1), (1, 1, -1, 1), (-1, 1, -1, -1)):
            a = add(add(add(base, mul(direction, x * half)), mul(side, y * half)), (0, 0, z0))
            b = add(add(add(base, mul(direction, dx * half)), mul(side, dy * half)), (0, 0, z1))
            scene.beam('Building_DiamondSideCraneLattice', 'Steel', a, b, .09)
    heading = math.atan2(direction[1], direction[0])
    scene.box('Building_DiamondSideCraneCab', 'Yellow', add(head, (0, 0, .2)), 2.8, 2.4, 1.8, heading)
    scene.box('Building_DiamondSideCraneCabWindow', 'Steel',
              add(add(head, mul(direction, 1.42)), (0, 0, .4)), .08, 1.7, .9, heading)
    angle = math.radians(recipe.side_crane_boom_angle_deg)
    boom = (direction[0] * math.cos(angle), direction[1] * math.cos(angle), math.sin(angle))
    tip = add(head, mul(boom, recipe.side_crane_jib_m))
    perpendicular = (-direction[0] * math.sin(angle),
                     -direction[1] * math.sin(angle), math.cos(angle))
    corners = [mul(side, -recipe.side_crane_boom_width_m / 2),
               mul(side, recipe.side_crane_boom_width_m / 2),
               mul(perpendicular, recipe.side_crane_boom_depth_m)]
    for offset in corners:
        scene.beam('Building_DiamondSideCraneBoom', 'Yellow',
                   add(head, offset), add(tip, offset), .18)
    divisions = math.ceil(recipe.side_crane_jib_m / 3)
    for level in range(divisions):
        a = add(head, mul(boom, recipe.side_crane_jib_m * level / divisions))
        b = add(head, mul(boom, recipe.side_crane_jib_m * (level + 1) / divisions))
        for first, last in zip(corners, corners[1:] + corners[:1], strict=True):
            scene.beam('Building_DiamondSideCraneBoomLattice', 'Steel',
                       add(a, first), add(b, last), .10)
            scene.beam('Building_DiamondSideCraneBoomTies', 'Yellow',
                       add(a, first), add(a, last), .10)
    for first, last in zip(corners, corners[1:] + corners[:1], strict=True):
        scene.beam('Building_DiamondSideCraneBoomTies', 'Yellow',
                   add(tip, first), add(tip, last), .10)
    counter = add(head, mul(direction, -recipe.side_crane_counter_jib_m))
    scene.beam('Building_DiamondSideCraneCounterJib', 'Steel', head, counter, .35, .7)
    scene.box('Building_DiamondSideCraneCounterweight', 'Concrete', counter, 2.6, 2.8, 1.5, heading)
    crown = add(head, (0, 0, 4))
    scene.beam('Building_DiamondSideCraneBackstay', 'Steel', counter, crown, .075)
    scene.beam('Building_DiamondSideCraneBackstay', 'Steel', crown, tip, .055)
    hook = add(tip, (0, 0, -recipe.side_crane_height_m * .7))
    scene.beam('Building_DiamondSideCraneCable', 'Steel', tip, hook, .04)


def build_construction(scene: MeshScene, building: Building, base_z: float,
                       recipe: ConstructionRecipe) -> ConstructionProof:
    if building.osm_id != recipe.osm_id:
        raise ValueError('Construction recipe cannot replace another mapped building')
    center, axis, normal, _length, _width = frame(building)
    heading = math.atan2(axis[1], axis[0])
    footprint = Polygon(building.ring)
    core = Polygon([(center[0] + axis[0] * a + normal[0] * b,
                     center[1] + axis[1] * a + normal[1] * b)
                    for a, b in ((-recipe.core_length_m / 2, -recipe.core_width_m / 2),
                                 (recipe.core_length_m / 2, -recipe.core_width_m / 2),
                                 (recipe.core_length_m / 2, recipe.core_width_m / 2),
                                 (-recipe.core_length_m / 2, recipe.core_width_m / 2))])
    outside = core.difference(footprint).area
    if outside > 1e-6:
        raise ValueError('Exposed core leaves the mapped construction footprint')
    scene.box('Building_DiamondExposedCore', 'Concrete',
              (center[0], center[1], base_z + recipe.height_m / 2),
              recipe.core_length_m, recipe.core_width_m, recipe.height_m, heading)
    for along in (-recipe.core_length_m / 3, 0, recipe.core_length_m / 3):
        for side in (-1, 1):
            rib = add(add(center, mul(axis, along)),
                      mul(normal, side * (recipe.core_width_m / 2 + recipe.core_rib_depth_m / 2)))
            scene.box('Building_DiamondCoreFormworkRibs', 'JeddahConstruction',
                      (rib[0], rib[1], base_z + recipe.height_m / 2), recipe.core_rib_width_m,
                      recipe.core_rib_depth_m, recipe.height_m, heading)
    plates = [floor_plate(building, recipe, level / (recipe.levels - 1)) for level in range(recipe.levels)]
    pitch = recipe.height_m / (recipe.levels - 1)
    for level, plate in enumerate(plates):
        z = base_z + level * pitch
        slab(scene, plate, z, recipe.slab_depth_m)
        ring = list(plate.exterior.coords)
        column_centers = plate.buffer(-recipe.column_width_m * .8)
        if column_centers.is_empty:
            raise ValueError('Construction plate leaves no room for its columns')
        for a, b in pairwise(ring):
            if level < recipe.levels - 1:
                for fraction in (.15, .5, .85):
                    x, y = a[0] * (1 - fraction) + b[0] * fraction, a[1] * (1 - fraction) + b[1] * fraction
                    # The mapped outline has a concave notch; radial inset can cross it.
                    interior = nearest_points(column_centers, PlanPoint(x, y))[0]
                    x, y = interior.x, interior.y
                    scene.box('Building_DiamondConcreteColumns', 'Concrete',
                              (x, y, z + pitch / 2), recipe.column_width_m,
                              recipe.column_width_m, pitch, heading)
            if level >= recipe.levels - recipe.formwork_levels:
                scene.banner((a[0], a[1], z), (b[0], b[1], z), 1.1,
                             'JeddahConstruction', 'Building_DiamondUpperFormwork')
        if level > 0:
            for side in (-1, 1):
                a = add(add(center, mul(axis, -recipe.core_length_m / 2)),
                        mul(normal, side * (recipe.core_width_m / 2 + .01)))
                b = add(a, mul(axis, recipe.core_length_m))
                scene.beam('Building_DiamondCorePourJoints', 'JeddahConstruction',
                           (a[0], a[1], z), (b[0], b[1], z), .035, .06)
    crane_base = add(add(center, mul(axis, recipe.side_crane_offset_along_m)),
                     mul(normal, recipe.side_crane_offset_across_m))
    luffing_crane(scene, (crane_base[0], crane_base[1], base_z), mul(normal, -1), recipe)
    return ConstructionProof(building.osm_id, recipe.height_m, recipe.height_uncertainty_m,
                             recipe.levels, base_z, min(p.area for p in plates), max(p.area for p in plates),
                             max(p.difference(footprint).area for p in plates), outside,
                             recipe.side_crane_height_m,
                             recipe.side_crane_height_m + recipe.side_crane_jib_m *
                             math.sin(math.radians(recipe.side_crane_boom_angle_deg)), recipe.source_note)


def construction_tower(scene: CircuitScene) -> None:
    recipe = source_record()
    building = mapped(scene, recipe.osm_id)
    if building is None:
        return
    center, _axis, _normal, _length, _width = frame(building)
    road, _distance = scene.nearest(center[0], center[1])
    proof = build_construction(scene, building, road.z, recipe)
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'name': 'Diamond Tower exposed concrete construction', **asdict(proof),
                            'source': SOURCE.name, 'planned_osm_height_m': building.height,
                            'adjacent_road_station_m': road.station,
                            'state': 'Closed exposed concrete slabs/core, open structural bays, formwork and lower luffing crane; no completed glazing or inferred hidden podium.'})
