"""The integrated garden, ravine and Larvotto bridge setting."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import RetainedTerrainSource
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.monaco_approaches import approach_segment, ground_sample
from venues.monaco_bridge import larvotto_bridge
from venues.monaco_dataclasses import (
    ApproachGround,
    BridgeApproach,
    BridgeFrame,
    BridgeProfile,
    CasaGardenSetting,
    LarvottoBridge,
)
from venues.monaco_garden import patio, stairs
from venues.monaco_landcover import (
    cell_indices,
    original_faces,
    split_face,
    touched_cells,
)
from venues.monaco_setting import cypress, leaf_banks, local_polygon, setting_masks


def bridge_setting(scene: CircuitScene, bridge_config: LarvottoBridge,
                   approaches: list[BridgeApproach], garden: CasaGardenSetting) -> None:
    if scene.emitted_terrain_cells:
        raise ValueError('The integrated setting replaces the original Costa land-cover call')
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    bridge = Polygon([scene.geo(lat, lon) for lon, lat in bridge_config.outline_wgs84])
    apron = unary_union([Polygon(r.plan_xy_m) for r in approaches])
    masks = setting_masks(scene, garden, bridge, apron)
    estimated_patio = local_polygon(garden, garden.patio_uv_m)
    garden_patio = estimated_patio.intersection(masks['Terracotta'])
    if not isinstance(garden_patio, Polygon):
        raise TypeError('The qualified patio must retain one connected paved platform')
    first_stair = local_polygon(garden, garden.central_stair_uv_m)
    last_stair = local_polygon(garden, garden.lower_stair_uv_m)
    central_landing = local_polygon(garden, garden.central_landing_uv_m)
    lower_top_landing = local_polygon(garden, garden.lower_top_landing_uv_m)
    lower_bottom_landing = local_polygon(garden, garden.lower_bottom_landing_uv_m)
    paving = unary_union([garden_patio, first_stair, last_stair, central_landing,
                          lower_top_landing, lower_bottom_landing])
    if paving.difference(masks['Terracotta']).area > 1e-7:
        raise ValueError('The engineered garden must remain clear of all property and path exclusions')
    engineered = unary_union([apron, paving])
    cover = unary_union([*masks.values(), engineered])
    cells = touched_cells(scene, cover)
    faces = original_faces(scene, cells)
    polygons = tuple(Polygon([p[:2] for p in face.points]) for face in faces)
    original = unary_union(polygons)
    if cover.difference(original).area > 1e-7:
        raise ValueError('The local setting crosses an existing nonterrain surface or body')
    ground = ApproachGround(tuple(faces), polygons, STRtree(polygons))
    centerline = [scene.geo(lat, lon) for lon, lat in bridge_config.centerline_wgs84]
    east, west = centerline[0], centerline[-1]
    span = math.dist(east, west)
    frame = BridgeFrame(east, ((west[0] - east[0]) / span, (west[1] - east[1]) / span), span)
    profile = BridgeProfile(frame, bridge_config.east_deck_absolute_m - datum,
                            bridge_config.west_deck_absolute_m - datum,
                            bridge_config.crown_thickness_m, bridge_config.arch_rise_m)
    # Resolve every support boundary before emitting or registering any replacement cell.
    for approach in approaches:
        if abs(approach.transition_length_m - bridge_config.approach_transition_m) > 1e-9:
            raise ValueError('Bridge and approach transition lengths disagree')
        translations = [(b[0] - a[0], b[1] - a[1])
                        for a, b in zip(approach.bridge_cap_xy_m, approach.outer_tie_xy_m, strict=True)]
        if any(math.dist(translations[0], vector) > 1e-8 for vector in translations):
            raise ValueError('The approach ties must translate the literal three-point bridge cap')
        # An 8 m curved road-axis interval has a slightly shorter end-to-end displacement.
        if abs(math.hypot(*translations[0]) - approach.transition_length_m) > .001:
            raise ValueError('The actual approach ties drifted from their declared transition length')
        for point in [*approach.bridge_cap_xy_m, *approach.outer_tie_xy_m]:
            ground_sample(ground, point)
    for point in [*garden_patio.exterior.coords, *first_stair.exterior.coords, *last_stair.exterior.coords]:
        ground_sample(ground, point[:2])
    for tree in garden.cypresses:
        p = Point(tree.xy_m)
        if not unary_union([masks['MonacoIvyGround'], masks['MonacoRockGround']]).covers(p.buffer(.15)):
            raise ValueError('The reconstructed cypress must remain in a classified natural bank')
        if any(Polygon(b.ring).buffer(1.5).covers(p) for b in scene.buildings) or bridge.buffer(1).covers(p):
            raise ValueError('The reconstructed cypress overlaps a mapped body or bridge')
        ground_sample(ground, tree.xy_m)
    for face in faces:
        shape = Polygon([p[:2] for p in face.points])
        regions = [('Runoff', shape.difference(cover)),
                   *[(material, shape.intersection(mask).difference(engineered)) for material, mask in masks.items()]]
        for material, region in regions:
            for part in split_face(face, region):
                scene.triangle('Tile_CostaSetting', material, part.points[0], part.points[1], part.points[2],
                               tuple((p[0] / 8, p[1] / 8) for p in part.points), part.normals)
    for approach in approaches:
        cap, outer = approach.bridge_cap_xy_m, approach.outer_tie_xy_m
        translation = outer[0][0] - cap[0][0], outer[0][1] - cap[0][1]
        for index, (a, b) in enumerate(pairwise(cap)):
            approach_segment(scene, a, b, translation, faces, profile, (index == 0, index == 1))
    terrace = garden.patio_anchor_absolute_m - datum
    patio(scene, garden_patio, terrace, ground, first_stair)
    first_bottom = garden.central_stair_bottom_absolute_m - datum
    lower_top = garden.lower_stair_top_absolute_m - datum
    lower_bottom = garden.lower_stair_bottom_absolute_m - datum
    first = stairs(scene, list(first_stair.exterior.coords)[:4], terrace, first_bottom, ground)
    lower = stairs(scene, list(last_stair.exterior.coords)[:4], lower_top, lower_bottom, ground)
    patio(scene, central_landing, first_bottom, ground, first_stair)
    patio(scene, lower_top_landing, lower_top, ground, last_stair)
    patio(scene, lower_bottom_landing, lower_bottom, ground, last_stair)
    scene.emitted_terrain_cells.update(cell_indices(scene, cells))
    banks = leaf_banks(scene, masks['MonacoIvyGround'].difference(bridge.buffer(1)), faces, garden)
    for tree in garden.cypresses:
        z, _normal = ground_sample(ground, tree.xy_m)
        cypress(scene, (*tree.xy_m, z), tree.height_m, tree.seed)
    bridge_report = larvotto_bridge(scene, bridge_config, scene.geo, datum)
    scene.landmarks.append({
        'name': 'Casa garden, Larvotto arch and separate ravine planting',
        'terrain_cells': len(cells), 'leaf_banks': banks, 'cypress_count': len(garden.cypresses),
        'patio_area_m2': garden_patio.area, 'patio_anchor_absolute_m': garden.patio_anchor_absolute_m,
        'patio_property_exclusion_m2': estimated_patio.difference(garden_patio).area,
        'central_stair_count': first['step_count'], 'lower_stair_count': lower['step_count'],
        'bridge_plan_area_m2': bridge_report['mapped_plan_area_m2'],
        'status': 'Bounded architectural reconstruction. Exact bridge plan and source approach anchors; '
                  'arch rise, garden terrace level, steps and planting positions are declared reconstructions. '
                  'Existing valley and all terrain planes outside the exact engineered patio/stair/apron plans '
                  'remain untouched. Source field/native contact data do not change. Supplied edited reference '
                  'year unverified; 2019 ortho and 2024 arch photo have different epochs. Annex 4420 remains held.',
    })


def costa_setting(scene: CircuitScene) -> None:
    bridge = TypeAdapter(LarvottoBridge).validate_json(
        (scene.sources / 'architecture/larvotto-bridge.json').read_bytes()
    )
    approaches = TypeAdapter(list[BridgeApproach]).validate_json(
        (scene.sources / 'architecture/larvotto-approaches.json').read_bytes()
    )
    garden = TypeAdapter(CasaGardenSetting).validate_json(
        (scene.sources / 'architecture/casa-garden.json').read_bytes()
    )
    bridge_setting(scene, bridge, approaches, garden)
