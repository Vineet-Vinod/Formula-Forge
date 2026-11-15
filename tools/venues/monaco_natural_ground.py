"""Preserve terrain planes while assigning qualified mixed-natural site cover."""
from __future__ import annotations

import csv
import hashlib
import struct

from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt, get_parts
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_natural_ground_dataclasses import NaturalSites
from venues.monaco_ravine_dataclasses import RavineSource
from venues.monaco_surfaces import face, replace_surfaces
from venues.monaco_surfaces_dataclasses import SurfaceRegion

MATERIAL = 'MonacoNaturalGround'


def classify(scene: MeshScene, domain: BaseGeometry) -> tuple[int, float, int]:
    changed = 0
    area = 0.0
    untouched = 0
    for name, tile in scene.tiles.items():
        if not name.startswith('Tile_Street_'):
            continue
        bounds = box(-tile.maximum[1] / 100, -tile.maximum[0] / 100,
                     -tile.minimum[1] / 100, -tile.minimum[0] / 100)
        if not bounds.intersects(domain):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from('<I', tile.triangles, offset)[0]]
            if material != 'Runoff':
                untouched += 1
                continue
            source = face(tile, offset)
            if not domain.contains(source.plan.representative_point()):
                untouched += 1
                continue
            outside = source.plan.difference(domain).area
            if outside > max(1e-7, source.plan.length * .000025):
                raise ValueError('Natural base requires the already clipped ravine terrain')
            if MATERIAL not in tile.materials:
                tile.materials.append(MATERIAL)
            struct.pack_into('<I', tile.triangles, offset, tile.materials.index(MATERIAL))
            changed += 1
            area += source.plan.area
    if changed == 0:
        raise ValueError('The qualified ravine contains no exposed asphalt-like base')
    return changed, area, untouched


def finish(scene: CircuitScene) -> None:
    source = TypeAdapter(RavineSource).validate_json(
        (scene.sources / 'architecture/ravine-source.json').read_bytes())
    if scene.slug != 'monaco' or max(
        abs(scene.provenance.origin.latitude - source.origin_lat_lon[0]),
        abs(scene.provenance.origin.longitude - source.origin_lat_lon[1]),
        abs(scene.provenance.route.uniform_scale - source.uniform_scale),
    ) > 1e-9:
        raise ValueError('Natural ravine cover requires its qualified Monaco frame')
    changed, area, untouched = classify(scene, from_wkt(source.expected_domain_wkt))
    scene.landmarks.append({'name': 'Finite mixed-natural ravine base',
                            'material_only_faces': changed, 'plan_area_m2': area,
                            'unchanged_overlap_tile_faces': untouched,
                            'source': 'architecture/ravine-outline.json; architecture/natural-ground-source-review.md',
                            'limits': 'General mixed natural land use, not uniform lawn or bare rock. Existing photographed rock/ivy and all structures/paths remain separate. Original1–2m outline uncertainty and grid-crop edge retained; no height, normal, UV, tree pose or native contact changes. Applied after canopy support checks; those original supporting vertex payloads remain exact.'})
    finish_lower_sites(scene, source)


def lower_regions(scene: CircuitScene, source: NaturalSites, ravine: BaseGeometry) -> list[SurfaceRegion]:
    blocked = [
        (LineString(item.vertices) if item.linear else Polygon(item.vertices)).buffer(item.buffer_m)
        for item in source.exclusions
    ]
    margin = source.road_and_protection_margin_m
    blocked.extend([
        ravine,
        scene.corridor_mask.buffer(margin),
        *[plan.buffer(margin) for plan in scene.extra_corridors],
        *scene.water_shapes,
        *[Polygon(building.ring).buffer(source.building_margin_m) for building in scene.buildings],
    ])
    with (scene.scratch / 'barriers.csv').open() as stream:
        for row in csv.DictReader(stream):
            blocked.append(LineString([
                (float(row['ax']), float(row['ay'])),
                (float(row['bx']), float(row['by'])),
            ]).buffer(float(row['radius']) + margin))
    cover = unary_union(blocked)
    regions = []
    for record in source.regions:
        candidate = Polygon(record.vertices)
        if not candidate.is_valid or candidate.area <= .05:
            raise ValueError('Natural site requires a valid finite source polygon')
        for index, part in enumerate(get_parts(candidate.difference(cover))):
            if isinstance(part, Polygon) and part.area > .05:
                regions.append(SurfaceRegion(record.name + f'_{index}', part, 'natural'))
    if not regions:
        raise ValueError('No qualified natural ground remains after architecture/path exclusions')
    return regions


def finish_lower_sites(scene: CircuitScene, ravine: RavineSource) -> None:
    source = TypeAdapter(NaturalSites).validate_json(
        (scene.sources / 'architecture/lower-natural-sites.json').read_bytes())
    if max(
        abs(source.origin_latitude - scene.provenance.origin.latitude),
        abs(source.origin_longitude - scene.provenance.origin.longitude),
        abs(source.uniform_scale - scene.provenance.route.uniform_scale),
    ) > 1e-9:
        raise ValueError('Lower natural sites require the qualified Monaco frame')
    root = scene.sources.parents[2]
    for relative, expected in source.source_input_sha256.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Natural-site source changed: {relative}')
    regions = lower_regions(scene, source, from_wkt(ravine.expected_domain_wkt))
    report = replace_surfaces(scene, regions, allowed_materials=frozenset({'Runoff'}))
    scene.landmarks.append({
        'name': 'Finite photographed planted sites and exposed natural spur',
        'classified_ground_area_m2': report.classified_area_m2,
        'source': 'architecture/lower-natural-sites.json',
        'limits': 'Mixed natural appearance only; no species or height claim. Original planes retained. Roofs, buildings, paths and actual protection are excluded with stated margins. Existing precise rock/ivy/paving roles and the ambiguous house-eave ray remain separate. Native contact, terrain field and tree poses unchanged; cooked review pending.',
    })
