"""Source-registered Masarat context added after the original Jeddah terrain is emitted."""

from __future__ import annotations

import math
import struct

from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.jeddah_masarat_dataclasses import MasaratArchitecture, MasaratSource
from venues.jeddah_masarat_geometry import build, panel, plans, xy
from venues.jeddah_masarat_ground import (
    apply_ground_edits,
    capture_ground,
    clipped_rows,
    ground_at,
    support,
)

LANDMARK = 'Masarat five-finger residential complex'


def placement(scene: CircuitScene, source: MasaratSource) -> MasaratArchitecture:
    if scene.slug != 'jeddah':
        raise ValueError('Masarat requires the retained Jeddah source frame')
    if abs(scene.provenance.route.uniform_scale - source.expected_route_uniform_scale) > 1e-9:
        raise ValueError('Masarat frontage controls require the qualified Jeddah scene scale')
    a, b = [scene.geo(lat, lon) for lon, lat in source.frontage_controls_wgs84_lon_lat]
    span = math.dist(a, b)
    if not 150 < span < 167:
        raise ValueError('The Masarat ground frontage no longer matches its qualified source span')
    axis = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    normal = -axis[1], axis[0]
    dims = source.dimensions
    return MasaratArchitecture(origin=a, axis=axis, normal=normal,
                               entrance_relative_m=dims.entrance_relative_m,
                               entrance_uncertainty_m=dims.entrance_uncertainty_m,
                               high_height_m=dims.high_height_m,
                               high_height_uncertainty_m=dims.high_height_uncertainty_m,
                               return_height_m=dims.return_height_m,
                               high_floors=dims.high_floors, return_floors=dims.return_floors,
                               wings=dims.wings)


def validate_site(scene: CircuitScene, source: MasaratSource,
                  components: tuple[tuple[str, Polygon, float], ...]) -> BaseGeometry:
    if any(row.get('name') == LANDMARK for row in scene.landmarks):
        raise ValueError('Masarat has already been added to this scene')
    if any(not plan.is_valid or plan.is_empty for _name, plan, _height in components):
        raise ValueError('A Masarat component has an invalid occupied footprint')
    overlap = sum(a.intersection(b).area for i, (_n, a, _h) in enumerate(components)
                  for _m, b, _j in components[i + 1:])
    mask = unary_union([plan for _name, plan, _height in components])
    if overlap > 1e-8 or not 3700 < mask.area < 4000:
        raise ValueError('Masarat components overlap or escape their bounded occupied-body estimate')
    forbidden = unary_union([scene.corridor_mask, *scene.extra_corridors, *scene.water_shapes,
                             *scene.terrain_cutouts, *[p for p, _m, _s in scene.verge_patches],
                             *[p for p, _z, _m in scene.ground_patches]])
    if mask.intersection(forbidden).area > 1e-8:
        raise ValueError('Masarat overlaps existing road, water, property or engineered ground')
    road = LineString([(r.x, r.y) for r in scene.road])
    reserve = max(r.half_width for r in scene.road) + max(
        max(r.left_shoulder, r.right_shoulder) for r in scene.road) + 3
    if mask.distance(road) <= reserve:
        raise ValueError('Masarat crosses the conservative legal shoulder and protection reserve')
    for street in source.streets:
        line = LineString([scene.geo(lat, lon) for lon, lat in street.path_wgs84_lon_lat])
        if mask.distance(line) < street.estimated_width_m / 2 + street.clearance_m:
            raise ValueError(f'Masarat obstructs the qualified street reserve for OSM way {street.osm_id}')
    for building in scene.buildings:
        if mask.intersection(Polygon(building.ring)).area > 1e-8:
            raise ValueError(f'Masarat overlaps a different mapped property, OSM way {building.osm_id}')
    xmin, ymin, xmax, ymax = mask.bounds
    for name, tile in scene.tiles.items():
        if not name.startswith('Building_'):
            continue
        if (-tile.maximum[1] / 100 > xmax or -tile.minimum[1] / 100 < xmin
                or -tile.maximum[0] / 100 > ymax or -tile.minimum[0] / 100 < ymin):
            continue
        for offset in range(0, len(tile.triangles), 100):
            values = struct.unpack_from('<I24f', tile.triangles, offset)
            points = [(-values[2 + i * 8] / 100, -values[1 + i * 8] / 100) for i in range(3)]
            if (min(p[0] for p in points) > xmax or max(p[0] for p in points) < xmin
                    or min(p[1] for p in points) > ymax or max(p[1] for p in points) < ymin):
                continue
            plan = Polygon(points)
            projected = plan if plan.is_valid and plan.area > 1e-8 else LineString(points)
            if projected.intersects(mask):
                raise ValueError('Masarat overlaps existing emitted building, foliage or venue geometry')
    return mask


def merge_architecture(scene: CircuitScene, architecture: MeshScene) -> None:
    for name, incoming in architecture.tiles.items():
        old = scene.tiles.get(name)
        if old is None:
            scene.tiles[name] = incoming
            continue
        indices = []
        for material in incoming.materials:
            if material not in old.materials:
                old.materials.append(material)
            indices.append(old.materials.index(material))
        for offset in range(0, len(incoming.triangles), 100):
            material = struct.unpack_from('<I', incoming.triangles, offset)[0]
            old.triangles.extend(struct.pack('<I', indices[material]))
            old.triangles.extend(incoming.triangles[offset + 4:offset + 100])
        for axis in range(3):
            old.minimum[axis] = min(old.minimum[axis], incoming.minimum[axis])
            old.maximum[axis] = max(old.maximum[axis], incoming.maximum[axis])


def finish_terrain(scene: CircuitScene) -> None:
    source = TypeAdapter(MasaratSource).validate_json((scene.sources / 'masarat-architecture.json').read_bytes())
    config = placement(scene, source)
    components = plans(config)
    mask = validate_site(scene, source, components)
    fence = LineString([xy(config, 4, 1), xy(config, 153.8, 1)])
    lookup = capture_ground(scene, unary_union([mask, fence]))
    edits = clipped_rows(lookup, mask)
    foundations = support(lookup, config, components)
    architecture = MeshScene()

    def ground(x: float, y: float) -> float:
        return ground_at(lookup, x, y)

    build(architecture, config, ground)
    for quad in foundations.quads:
        architecture.quad('Building_MasaratExactFoundation' + quad.name, 'Concrete', *quad.points)
    panel(architecture, config, (130.8, 10.45), (133.2, 10.45), config.entrance_relative_m,
          config.entrance_relative_m + 2.8, 'Glass', 'Building_MasaratEstimatedEntrance')
    if set(architecture.tiles) != {'Building_City_00_m1'}:
        raise ValueError('Masarat geometry escaped the named tile used by its limited residency estimate')
    apply_ground_edits(scene, edits)
    merge_architecture(scene, architecture)
    scene.landmarks.append({
        'name': LANDMARK,
        'source': 'masarat-source-qualification.json',
        'project_site_area_m2': 9559,
        'occupied_body_area_m2': mask.area,
        'estimated_high_wing_height_m': config.high_height_m,
        'high_wing_height_uncertainty_m': config.high_height_uncertainty_m,
        'cvu_estimated_floors': config.high_floors,
        'developer_storeys': 43,
        'estimated_high_core_top_above_entry_m': config.high_height_m + 1.1,
        'estimated_short_return_height_m': config.return_height_m,
        'estimated_entry_uncertainty_m': config.entrance_uncertainty_m,
        'original_ground_rows_clipped': len(edits),
        'minimum_foundation_burial_m': foundations.minimum_toe_burial_m,
        'maximum_exposed_basement_m': foundations.maximum_exposed_basement_m,
        'maximum_ground_above_first_floor_m': foundations.maximum_ground_above_entry_m,
        'fence_minimum_ground_burial_m': foundations.fence_minimum_burial_m,
        'estimated_entry_step_m': foundations.entrance_step_m,
        'retained_mesh_entry_grade_percent': foundations.retained_entrance_grade_percent,
        'source_limits': 'Original reconstructed architecture, not a surveyed footprint or section. The '
                         'operator point is directions only. Masarat is CVU-estimated 144 m / 42 floors '
                         'versus developer 43 storeys; Sail is a different 264.7 m tower. Component '
                         'depths, 23–25-floor lower fingers, 27-floor return, corner bearing/top extent '
                         'and stepped entry levels remain estimates. Actual original 4–10 m emitted '
                         'ground may represent a raised site or DSM uncertainty; it is not proved bare '
                         'earth. Rear connectors remain unmodeled. No full-site pad, fake building OSM '
                         'ID, field/road/contact mutation, provider change or streaming-radius change. '
                         'Normal-start residency uses an 8,192-source-pose estimate, not a moving '
                         'native proof. Fresh native night and full-route review remain required.',
    })
