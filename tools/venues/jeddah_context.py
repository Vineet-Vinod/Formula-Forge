"""context authoring, with source-frame plans and bounded old-ground preservation."""

from __future__ import annotations

from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from venues.jeddah_context_dataclasses import (
    ContextGroundLookup,
    ContextResidency,
    MallArchitecture,
    SailArchitecture,
)
from venues.jeddah_context_ground import courtyard, ground_at, remove_building_ground
from venues.jeddah_context_shapes import rectangle
from venues.jeddah_context_skyline import context_residency
from venues.jeddah_mall import curved_front, mall_complex, validate_service_clearance
from venues.jeddah_sail import podium_plans, sail_complex, site_frame


def build_context(scene: CircuitScene, sail: SailArchitecture, mall: MallArchitecture) -> None:
    if scene.slug != 'jeddah':
        raise ValueError('The context coordinates require the retained Jeddah frame')
    frame, sail_site = site_frame(sail, scene.geo)
    tower = rectangle(frame, 0, 0, sail.length_m, sail.width_m)
    main, ballroom = podium_plans(sail, frame, sail_site, tower)
    mall_site = Polygon([scene.geo(lat, lon) for lon, lat in mall.site.outer_wgs84])
    mall_body, _frontage = curved_front(mall_site, *mall.frontage_source_range, mall.frontage_inset_m)
    validate_service_clearance(mall_body, mall, scene.geo)
    tower_base = tower
    sail_mask = unary_union([sail_site, tower_base])
    removal = unary_union([sail_mask, mall_site])
    before_grid, before_road = scene.grid, list(scene.road)
    before_cutouts = list(scene.terrain_cutouts)
    faces, count = remove_building_ground(scene, removal)
    polygons = tuple(Polygon([p[:2] for p in face.points]) for face in faces)
    original = unary_union(polygons)
    lookup = ContextGroundLookup(tuple(faces), polygons, STRtree(polygons), original.bounds)

    def ground(x: float, y: float) -> float:
        return ground_at(lookup, (x, y))

    sail_report = sail_complex(scene, sail, scene.geo)
    mall_report = mall_complex(scene, mall, scene.geo, ground)
    sail_paving = sail_mask.difference(unary_union([tower_base, main, ballroom]))
    mall_paving = mall_site.difference(mall_body)
    sail_paved_area = courtyard(scene, sail_paving, sail.base_relative_m, lookup)
    mall_paved_area = courtyard(scene, mall_paving, mall.street_relative_m, lookup)
    scene.modeled_buildings.update({sail.site.osm_id, mall.site.osm_id})
    grid = scene.grid
    grid_extent = box(grid.x, grid.y, grid.x + grid.step * (grid.columns - 1),
                      grid.y + grid.step * (grid.rows - 1))
    scene.landmarks.append({
        'name': 'Sail and Red Sea Mall architectural context',
        'sail_height_m': sail_report['tower_height_m'], 'sail_floorplate_m2': sail_report['tower_floorplate_m2'],
        'sail_podium_site_m2': sail_report['podium_site_m2'],
        'sail_projection_outside_podium_m2': sail_report['tower_outside_podium_m2'],
        'sail_courtyard_m2': sail_paved_area, 'mall_courtyard_m2': mall_paved_area,
        'mall_original_envelope_m2': mall_report['mapped_site_m2'],
        'mall_modeled_body_m2': mall_report['rendered_body_m2'],
        'mall_flat_roof_relative_m': mall_report['flat_roof_relative_m'],
        'mall_roof_plant_clusters': mall_report['roof_mechanical_clusters'],
        'local_terrain_cells': count,
        'new_coverage_outside_original_field_m2': removal.difference(grid_extent).area,
        'source_limits': 'Source-qualified architectural estimates. CVU location is approximate, not a surveyed '
                         'tower centroid; tower plate, podium split, floor pitches and mall components are '
                         'bounded estimates. All old ground outside actual property interiors keeps its '
                         'planes, normals and UVs. Only the small new mall tip uses a declared horizontal '
                         'extension of actual emitted boundary heights for foundation closure. '
                         'Existing Diamond residency, native field, road/contact data and global streaming '
                         'radii remain unchanged. Sail is behind the T27 exit camera and cannot alone close '
                         'that skyline finding. Fresh native/cooked views remain required.',
    })
    if scene.grid != before_grid or scene.road != before_road or scene.terrain_cutouts != before_cutouts:
        raise AssertionError('Context authoring changed source field, driving road or global cutout geometry')


def corniche_context(scene: CircuitScene) -> None:
    residency = TypeAdapter(ContextResidency).validate_json(
        (scene.sources / 'context-residency.json').read_bytes()
    )
    if abs(scene.provenance.route.uniform_scale - residency.uniform_scale) > 1e-9:
        raise ValueError('The named Corniche residency requires the retained Jeddah source frame')
    sail = TypeAdapter(SailArchitecture).validate_json(
        (scene.sources / 'sail-architecture.json').read_bytes()
    )
    mall = TypeAdapter(MallArchitecture).validate_json(
        (scene.sources / 'mall-architecture.json').read_bytes()
    )
    build_context(scene, sail, mall)
    context_residency(scene, residency)
