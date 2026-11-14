"""The integrated garden, ravine and Larvotto bridge setting."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import RetainedTerrainSource, TerrainGrid
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.monaco_approaches import approach_segment, ground_sample
from venues.monaco_belvedere import belvedere, belvedere_preflight, half_disc
from venues.monaco_bridge import larvotto_bridge
from venues.monaco_cliff import cliff_preflight, cliff_regions, cliff_vegetation
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
from venues.monaco_west_dataclasses import BelvedereArchitecture, CliffPatch
from venues.monaco_west_ground import belvedere_ground, existing_wood_ground


def bridge_setting(scene: CircuitScene, bridge_config: LarvottoBridge,
                   approaches: list[BridgeApproach], garden: CasaGardenSetting) -> None:
    if scene.emitted_terrain_cells:
        raise ValueError('The integrated setting replaces the original Costa land-cover call')
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / 'scenery-ground.json').read_bytes()
    ).relative_datum_m
    west_belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / 'architecture/west-belvedere.json').read_bytes()
    )
    west_cliff = TypeAdapter(CliffPatch).validate_json(
        (scene.sources / 'architecture/west-cliff.json').read_bytes()
    )
    west_grid = TypeAdapter(TerrainGrid).validate_json(
        (scene.sources / west_cliff.ground_grid_file).read_bytes()
    )
    if abs(west_cliff.uniform_scale - scene.provenance.route.uniform_scale) > 1e-9:
        raise ValueError('The west cliff source frame differs from the registered route')
    if max(abs(west_cliff.relative_datum_m - datum), abs(west_belvedere.relative_datum_m - datum)) > 1e-9:
        raise ValueError('The west setting source datum differs from the retained field')
    cliff_plan = Polygon(west_cliff.outer_xy_m)
    support_plan = half_disc(west_belvedere, west_belvedere.radius_m - .18)
    support_rim = half_disc(west_belvedere, west_belvedere.radius_m)
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
    woodland_plan, woodland_faces = existing_wood_ground(scene, west_belvedere, support_rim)
    blocked = unary_union([scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes,
                           *scene.terrain_cutouts, bridge, apron, local_polygon(garden, garden.garden_uv_m),
                           *[Polygon(b.ring).buffer(.4) for b in scene.buildings]])
    support_blocked = unary_union([scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes,
                                   *[shape for shape in scene.terrain_cutouts if not shape.equals(woodland_plan)],
                                   bridge, apron, local_polygon(garden, garden.garden_uv_m),
                                   *[Polygon(b.ring).buffer(.4) for b in scene.buildings]])
    if cliff_plan.intersection(blocked).area > 1e-8 or support_rim.intersection(support_blocked).area > 1e-8:
        raise ValueError('The west setting overlaps an existing body, road or engineered surface')
    if cliff_plan.distance(support_rim) < 1:
        raise ValueError('The west cliff must remain separate from the original-ground belvedere supports')
    engineered = unary_union([apron, paving])
    cover = unary_union([*masks.values(), engineered])
    west_domains = unary_union([cliff_plan, support_plan])
    lookup_cover = unary_union([cover, cliff_plan, support_rim])
    cells = touched_cells(scene, lookup_cover)
    faces = original_faces(scene, cells)
    polygons = tuple(Polygon([p[:2] for p in face.points]) for face in faces)
    original = unary_union(polygons)
    if lookup_cover.difference(unary_union([original, woodland_plan])).area > 1e-7:
        raise ValueError('The local setting crosses an existing nonterrain surface or body')
    ground = ApproachGround(tuple(faces), polygons, STRtree(polygons))
    cliff_preflight(ground, west_grid, west_cliff)
    support_ground = belvedere_ground(faces, woodland_faces)
    belvedere_preflight(west_belvedere, support_ground)
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
    west_triangles = 0
    for face in faces:
        shape = Polygon([p[:2] for p in face.points])
        regions = [('Runoff', shape.difference(cover)),
                   *[(material, shape.intersection(mask).difference(engineered)) for material, mask in masks.items()]]
        for material, region in regions:
            for part in split_face(face, region):
                original_plan = Polygon([p[:2] for p in part.points])
                if original_plan.intersection(west_domains).area <= 1e-10:
                    remaining = [part]
                else:
                    remaining = split_face(part, original_plan.difference(west_domains))
                for retained in remaining:
                    scene.triangle('Tile_CostaSetting', material, *retained.points,
                                   tuple((p[0] / 8, p[1] / 8) for p in retained.points), retained.normals)
                west_triangles += cliff_regions(scene, ground, west_grid, part, west_cliff)
    west_structure = belvedere(scene, west_belvedere, support_ground)
    west_banks = cliff_vegetation(scene, ground, west_grid, west_cliff)
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
    banks = leaf_banks(scene, masks['MonacoIvyGround'].difference(bridge.buffer(1)), faces, garden,
                       unary_union([support_rim.buffer(.25), cliff_plan]))
    for tree in garden.cypresses:
        z, _normal = ground_sample(ground, tree.xy_m)
        cypress(scene, (*tree.xy_m, z), tree.height_m, tree.seed)
    bridge_report = larvotto_bridge(scene, bridge_config, scene.geo, datum)
    scene.landmarks.append({
        'name': 'Separate west belvedere and source-grid natural cliff below held terraces',
        'cliff_area_m2': cliff_plan.area, 'cliff_render_triangles': west_triangles,
        'west_leaf_banks': west_banks, 'retained_existing_grass_support_triangles': len(woodland_faces),
        'enclosed_existing_grass_area_m2': support_plan.intersection(woodland_plan).area, 'belvedere_radius_m': west_structure['radius_m'],
        'belvedere_paving_absolute_m': west_structure['paving_absolute_m'],
        'belvedere_cap_absolute_m': west_structure['cap_absolute_m'],
        'source': 'architecture/west-setting-provenance.json',
        'status': 'Bounded reconstruction from primary 2012/2014 photos, 2019 ortho and retained 2 m IGN grid. '
                  'The 0.5 m rendered cliff estimates between source observations, ties to original outer planes, '
                  'and does not change the native field or road/contact data. Curved masonry and natural rock/ivy '
                  'remain separate. Roof/paving/support details and canopy positions are estimated. '
                  'No unsupported L terrace deck or enclosed annex is emitted. Fresh cooked review is required.',
    })
    scene.landmarks.append({
        'name': 'Casa garden, Larvotto arch and separate ravine planting',
        'terrain_cells': len(cells), 'leaf_banks': banks, 'cypress_count': len(garden.cypresses),
        'patio_area_m2': garden_patio.area, 'patio_anchor_absolute_m': garden.patio_anchor_absolute_m,
        'patio_property_exclusion_m2': estimated_patio.difference(garden_patio).area,
        'central_stair_count': first['step_count'], 'lower_stair_count': lower['step_count'],
        'bridge_plan_area_m2': bridge_report['mapped_plan_area_m2'],
        'status': 'Bounded architectural reconstruction. Exact bridge plan and source approach anchors; '
                  'arch rise, garden terrace level, steps and planting positions are declared reconstructions. '
                  'Existing terrain planes outside the engineered patio/stair/apron and separately bounded '
                  'west cliff/belvedere plans remain untouched. Source field/native contact data do not change. Supplied edited reference '
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
