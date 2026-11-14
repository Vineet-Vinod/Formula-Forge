"""Planted rock and garden surfaces. Existing ground planes remain explicit."""

from __future__ import annotations

import math
import random

from circuit_dataclasses import Point as XYZ
from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_dataclasses import CasaGardenSetting, CostaGroundFace, CostaLandCover
from venues.monaco_landcover import classified_masks, interpolate


def local_polygon(config: CasaGardenSetting, ring: tuple[tuple[float, float], ...]) -> Polygon:
    return Polygon([(config.origin_xy_m[0] + config.u_axis[0] * u + config.v_axis[0] * v,
                     config.origin_xy_m[1] + config.u_axis[1] * u + config.v_axis[1] * v)
                    for u, v in ring])


def setting_masks(scene: CircuitScene, config: CasaGardenSetting,
                  bridge: Polygon, approaches: BaseGeometry) -> dict[str, BaseGeometry]:
    source = TypeAdapter(CostaLandCover).validate_json(
        (scene.sources / 'architecture/costa-landcover.json').read_bytes()
    )
    old = classified_masks(scene, source)
    paths = unary_union([local_polygon(config, config.patio_uv_m),
                         local_polygon(config, config.central_stair_uv_m),
                         local_polygon(config, config.lower_stair_uv_m),
                         local_polygon(config, config.central_landing_uv_m),
                         local_polygon(config, config.lower_top_landing_uv_m),
                         local_polygon(config, config.lower_bottom_landing_uv_m)])
    garden = local_polygon(config, config.garden_uv_m)
    blocked = unary_union([scene.corridor_mask.buffer(1), *scene.extra_corridors,
                           *scene.water_shapes, *scene.terrain_cutouts, bridge, approaches,
                           *[Polygon(b.ring).buffer(.4) for b in scene.buildings]])
    paths = paths.difference(blocked)
    beds = garden.difference(unary_union([blocked, paths.buffer(.18)]))
    ivy = unary_union([old['Grass'], beds]).difference(unary_union([paths, approaches]))
    rock = old['Limestone'].difference(unary_union([paths, beds, approaches]))
    return {'MonacoIvyGround': ivy, 'MonacoRockGround': rock, 'Terracotta': paths}


def leaf_banks(scene: MeshScene, planted: BaseGeometry,
               faces: list[CostaGroundFace], config: CasaGardenSetting,
               excluded: BaseGeometry | None = None) -> int:
    rng = random.Random(74384420)
    xmin, ymin, xmax, ymax = planted.bounds
    count = 0
    source_count = 0
    y = ymin + config.plant_spacing_m / 2
    while y < ymax:
        x = xmin + config.plant_spacing_m / 2
        while x < xmax:
            px, py = x + rng.uniform(-.55, .55), y + rng.uniform(-.55, .55)
            point = Point(px, py)
            height = rng.uniform(*config.leaf_bank_height_m)
            if planted.covers(point.buffer(height * .41)):
                face = next((face for face in faces
                             if Polygon([p[:2] for p in face.points]).covers(point)), None)
                if face is not None:
                    z, _normal = interpolate(face, px, py)
                    # Sink the original five-cluster recipe until its low leaves meet the slope.
                    if excluded is None or not excluded.covers(point):
                        scene.broadleaf((px, py, z - height * .46), height, 74420 + source_count)
                        count += 1
                    source_count += 1
            x += config.plant_spacing_m
        y += config.plant_spacing_m
    return count


def cypress(scene: MeshScene, base: XYZ, height: float, seed: int) -> None:
    scene.beam('Building_CostaCypress', 'Trunk', base,
               (base[0], base[1], base[2] + height * .8), .16)
    rng = random.Random(seed)
    for tier in range(9):
        fraction = .28 + tier * .075
        radius = height * (.070 - .0048 * max(0, tier - 3)) * rng.uniform(.9, 1.1)
        for plane in range(3):
            angle = plane * math.pi / 3 + tier * .37
            column, row = (2, 5)[(seed + tier) % 2], (seed + tier) % 3
            u0, u1 = (column + .012) / 6, (column + .988) / 6
            v0, v1 = (row + .012) / 6, (row + .988) / 6
            dx, dy = math.cos(angle) * radius, math.sin(angle) * radius
            low, high = base[2] + height * (fraction - .12), base[2] + height * (fraction + .12)
            a, b = (base[0] - dx, base[1] - dy, low), (base[0] + dx, base[1] + dy, low)
            c, d = (base[0] + dx, base[1] + dy, high), (base[0] - dx, base[1] - dy, high)
            scene.triangle('Building_CostaCypress', 'TreeCanopy', d, c, b,
                           ((u0, v0), (u1, v0), (u1, v1)))
            scene.triangle('Building_CostaCypress', 'TreeCanopy', d, b, a,
                           ((u0, v0), (u1, v1), (u0, v1)))
