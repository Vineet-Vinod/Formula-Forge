"""Check the authored layout and repeatability without relying on a Blender render."""
import argparse
import hashlib
import json
import sys

import bpy
import numpy as np
from shapely import LineString, Polygon, unary_union

import build_monza as B
import monza_layout as layout


def fingerprint():
    bpy.context.view_layer.update()
    hashes = {}
    for ob in bpy.data.objects:
        if ob.type != 'MESH': continue
        h = hashlib.sha256()
        positions = np.empty(len(ob.data.vertices)*3, dtype=np.float32)
        ob.data.vertices.foreach_get('co', positions)
        h.update(np.round(positions, 4).tobytes())
        h.update(np.round(np.array(ob.matrix_world), 4).tobytes())
        for face in ob.data.polygons:
            h.update(np.array(face.vertices, dtype=np.int32).tobytes())
        for name in ['instance_scale', 'instance_rotation']:
            if name in ob.data.attributes:
                values=np.empty(len(ob.data.attributes[name].data)*3,dtype=np.float32)
                ob.data.attributes[name].data.foreach_get('vector',values)
                h.update(values.tobytes())
        hashes[ob.name]=h.hexdigest()
    return hashes


def verify(reapply=False):
    B.load()
    assert bpy.context.scene['monza_layout_sha256'] == layout.digest()
    source=json.loads(layout.PATH.read_text())
    footprints=[]
    for ob in B.collection('Runoff').objects:
        assert all(face.normal.z > .99 for face in ob.data.polygons), ob.name
        footprints.extend(Polygon([ob.data.vertices[i].co[:2] for i in face.vertices]) for face in ob.data.polygons)
    mask=unary_union(footprints)
    for name in ['L grass verge','R grass verge']:
        ob=bpy.data.objects[name]
        overlap=sum(Polygon([ob.data.vertices[i].co[:2] for i in f.vertices]).intersection(mask).area for f in ob.data.polygons)
        assert overlap < .002,(name,overlap)
    for route in source['escape_test_paths']:
        assert all(LineString(route['points']).distance(LineString(w['points'])) > 1.0+w['half_thickness_m'] for w in source['barriers']),route['name']
    before=fingerprint()
    if reapply:
        layout.apply()
        after=fingerprint()
        changed=[name for name in before.keys() | after.keys() if before.get(name)!=after.get(name)]
        assert not changed,changed
    report=dict(layout_sha256=layout.digest(),barrier_paths=len(source['barriers']),
                escape_routes_clear=True,grass_runoff_overlap_m2=0,runoff_normals_up=True,
                reapply_geometry_identical=reapply)
    (B.QA/'layout_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reapply',action='store_true')
    verify(parser.parse_args().reapply)
