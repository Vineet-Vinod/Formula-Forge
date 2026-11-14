"""Classify clipped ravine faces without changing a packed vertex or outside row."""
from __future__ import annotations

import struct

from circuit_mesh import MeshScene
from circuit_scene import CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from venues.monaco_ravine_dataclasses import RavineSource
from venues.monaco_surfaces import face

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
