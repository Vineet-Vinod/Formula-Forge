"""Apply reference-backed Monza boundaries and export the very same contact geometry.

uv run --no-sync python tools/blender/tracks/monza_layout.py
Input is layout.json in the survey's local metre frame. No imagery is packaged.
"""
import hashlib
import itertools
import json
import math
import re

import bpy
import bmesh
from mathutils import Vector
from shapely import LineString, Polygon, constrained_delaunay_triangles, unary_union, contains_xy

import build_monza as B
import monza_environment as E

PATH = B.OUT / 'layout.json'


def digest():
    return hashlib.sha256(PATH.read_bytes()).hexdigest()


def apply():
    E.B = B
    layout = json.loads(PATH.read_text())
    import monza_map_details
    monza_map_details.B = B
    monza_map_details.repair_geometry()
    for ob in bpy.data.objects:
        if 'layout_prop_origin' in ob:
            ob.location = ob['layout_prop_origin']
    bpy.context.view_layer.update()
    road = Polygon([B.point(i, B.width(i * B.STEP) / 2)[:2] for i in range(B.N)],
                   [[B.point(i, -B.width(i * B.STEP) / 2)[:2] for i in range(B.N)]]).buffer(0)
    for path in layout['barriers']:
        line = LineString(path['points'])
        overlap = line.buffer(path['half_thickness_m']).intersection(road)
        if overlap.area > .01:
            raise ValueError(f"Barrier crosses asphalt: {path['name']}, {overlap.bounds}, area={overlap.area}")
    suspects = [ob for ob in bpy.data.objects if (
        ' Armco ' in ob.name or ' catch fence ' in ob.name
        or ob.name in ['Impact tyre stacks', 'Pit wall | separate entry and exit',
                       'Rettifilo escape bollards']
        or ob.get('reference_layout')
        or any(c.name == 'Runoff' for c in ob.users_collection))]
    report = []
    for ob in suspects:
        corners = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
        item = dict(name=ob.name, dimensions=list(ob.dimensions),
                    bounds=[[min(p[k] for p in corners) for k in range(3)],
                            [max(p[k] for p in corners) for k in range(3)]])
        report.append(item)
        print('REPLACE', json.dumps(item), flush=True)
    qa = B.OUT / 'qa'; qa.mkdir(exist_ok=True)
    (qa / 'layout_replaced_objects.json').write_text(json.dumps(report, indent=2)+'\n')
    for ob in suspects:
        bpy.data.objects.remove(ob, do_unlink=True)
    segments = []
    for path in layout['barriers']:
        batch = E.Batch(); fences = []
        half = path['half_thickness_m']; height = path['height_m']
        for a, b in itertools.pairwise(path['points']):
            a, b = Vector(a), Vector(b)
            length = (b-a).length
            if length < .01:
                continue
            angle = math.atan2(b.y-a.y, b.x-a.x)
            count = math.ceil(length / 4)
            for j in range(count):
                p, q = a.lerp(b, j/count), a.lerp(b, (j+1)/count)
                mid = (p+q)/2
                base = B.terrain(mid.x, mid.y) + .015
                segment_length = (q-p).length
                if path.get('kind') == 'concrete':
                    batch.cube((mid.x, mid.y, base+height/2), (segment_length, half*2, height), angle)
                else:
                    for z in [.35, .66, .97]:
                        batch.cube((mid.x, mid.y, base+z), (segment_length, half*2, .22), angle)
                    batch.cube((p.x, p.y, base+.55), (.14, .14, 1.1), angle)
                segments.append([p.x, -p.y, q.x, -q.y, base, base+height, half])
                side = path['fence_side']
                if side:
                    normal = Vector((-math.sin(angle), math.cos(angle))) * side
                    fp = mid + normal * .6
                    fences.append((Vector((fp.x, fp.y, base)), (segment_length/4, 1, 1), angle + (math.pi if side < 0 else 0)))
        material = 'Concrete' if path.get('kind') == 'concrete' else 'Armco'
        ob = batch.object('REFERENCE barrier | '+path['name'], [B.MATS[material]], 'Safety_barriers')
        ob['reference_layout'] = digest(); ob['source'] = path['source']
        if fences:
            ob = E.instances('REFERENCE catch fence | '+path['name'], bpy.data.objects['LIB_Fence_4m'], fences, 'Fencing')
            ob['reference_layout'] = digest()
    for surface in sorted(layout['surfaces'], key=lambda s: s['material'] != 'Asphalt'):
        geom = Polygon(surface['points']).buffer(0)
        verts, faces = [], []
        for triangle in constrained_delaunay_triangles(geom).geoms:
            pts = list(triangle.exterior.coords)[:3]
            if not triangle.exterior.is_ccw:
                pts.reverse()
            i = len(verts)
            verts.extend((x,y,B.terrain(x,y)+.028) for x,y in pts)
            faces.append((i,i+1,i+2))
        ob = B.mesh('REFERENCE '+surface['name'], verts, faces, B.MATS[surface['material']], 'Runoff')
        ob['reference_layout'] = digest(); ob['source'] = surface['source']
    # The established partitioner excludes the road and raised kerb/apron surfaces.
    B.refit_runoff_surfaces()
    # Clipping can leave sub-millimetre slivers whose winding reverses in float32.
    for ob in B.collection('Runoff').objects:
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_area()<1e-5],context='FACES')
        bm.normal_update()
        for face in bm.faces:
            if face.normal.z<0: face.normal_flip()
        bm.to_mesh(ob.data);bm.free();ob.data.update()
    # A grass sheet 7 mm above runoff used to cover the last two metres by the road.
    # Cut it out geometrically; raising asphalt would recreate the depth conflicts.
    masks = []
    for ob in B.collection('Runoff').objects:
        if ob.type == 'MESH':
            masks.extend(Polygon([ob.data.vertices[i].co[:2] for i in face.vertices])
                         for face in ob.data.polygons)
    mask = unary_union(masks)
    grass_cut = mask.buffer(.002)  # Float32 margin, two millimetres on a ground seam.
    for name in ['L grass verge', 'R grass verge']:
        ob = bpy.data.objects[name]
        original_name = 'LAYOUT_SOURCE | '+name
        original = bpy.data.meshes.get(original_name)
        if original is None:
            original = ob.data.copy()
            original.name = original_name
            original.use_fake_user = True
        original.calc_loop_triangles()
        verts, faces = [], []
        for triangle in original.loop_triangles:
            pts = [original.vertices[i].co.copy() for i in triangle.vertices]
            polygon = Polygon([p[:2] for p in pts])
            if polygon.area < 1e-10: continue
            normal = (pts[1]-pts[0]).cross(pts[2]-pts[0])
            if abs(normal.z) < 1e-10: continue
            allowed = polygon.difference(grass_cut)
            for piece in constrained_delaunay_triangles(allowed).geoms:
                ring = list(piece.exterior.coords)[:3]
                if not piece.exterior.is_ccw: ring.reverse()
                j = len(verts)
                for x,y in ring:
                    z = pts[0].z-(normal.x*(x-pts[0].x)+normal.y*(y-pts[0].y))/normal.z
                    verts.append((x,y,z))
                faces.append((j,j+1,j+2))
        data = bpy.data.meshes.new(name+' runoff clipped')
        data.from_pydata(verts, [], faces)
        data.materials.append(B.MATS['Grass'])
        data.update()
        ob.data = data
        bm=bmesh.new();bm.from_mesh(data)
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_area()<1e-5],context='FACES')
        bm.normal_update()
        for face in bm.faces:
            if face.normal.z<0: face.normal_flip()
        bm.to_mesh(data);bm.free();data.update()
        ob['runoff_partition'] = digest()
    prop_report = []
    # Keep existing prop groups, but move misplaced marshal huts behind the actual rail.
    for marker in list(B.collection('Marshal_posts').objects):
        if not re.fullmatch(r'Marshal M[0-9.]+', marker.name): continue
        corners = [marker.matrix_world @ Vector(v) for v in marker.bound_box]
        anchor = sum(corners, Vector())/len(corners)
        if not contains_xy(mask,anchor.x,anchor.y): continue
        best = None
        for path in layout['barriers']:
            if not path['fence_side']: continue
            for a,b in itertools.pairwise(path['points']):
                a,b = Vector(a),Vector(b); v=b-a
                t=max(0,min(1,(Vector(anchor[:2])-a).dot(v)/v.length_squared))
                q=a+v*t
                distance=(q-Vector(anchor[:2])).length
                if best is None or distance<best[0]:
                    outward=Vector((-v.y,v.x)).normalized()*path['fence_side']
                    best=(distance,q+outward*4)
        target=best[1]
        shift=Vector((target.x-anchor.x,target.y-anchor.y,
                      B.terrain(target.x,target.y)-B.terrain(anchor.x,anchor.y)))
        tag=marker.name.removeprefix('Marshal ')
        for ob in B.collection('Marshal_posts').objects:
            if ob == marker or ob.name.startswith(tag+' '):
                if 'layout_prop_origin' not in ob: ob['layout_prop_origin']=list(ob.location)
                item=dict(name=ob.name,original_center=list(anchor),shift_m=list(shift))
                print('RELOCATE',json.dumps(item),flush=True);prop_report.append(item)
                ob.location+=shift
    for ob in B.collection('Forest').objects:
        if not ob.name.endswith('irregular verge tufts'): continue
        source_name='LAYOUT_SOURCE | '+ob.name
        original=bpy.data.meshes.get(source_name)
        if original is None:
            original=ob.data.copy();original.name=source_name;original.use_fake_user=True
        keep=[i for i,v in enumerate(original.vertices) if not contains_xy(mask,v.co.x,v.co.y)]
        data=bpy.data.meshes.new(ob.name+' runoff cleared')
        data.from_pydata([original.vertices[i].co[:] for i in keep],[],[])
        for name in ['instance_scale','instance_rotation']:
            attr=data.attributes.new(name,'FLOAT_VECTOR','POINT')
            attr.data.foreach_set('vector',[v for i in keep for v in original.attributes[name].data[i].vector])
        ob.data=data;ob['instance_count']=len(keep)
        prop_report.append(dict(name=ob.name,removed_instances=len(original.vertices)-len(keep)))
    (qa/'layout_props.json').write_text(json.dumps(prop_report,indent=2)+'\n')
    monza_map_details.build_markers(layout)
    bpy.context.scene['monza_layout_sha256'] = digest()
    bpy.context.scene['monza_contact_segments_m'] = json.dumps(segments)
    export_contact()
    (qa / 'layout_summary.json').write_text(json.dumps(dict(source_sha256=digest(),
        paths=len(layout['barriers']), contact_segments=len(segments),
        surfaces=len(layout['surfaces']), road_barrier_overlap_m2=0,
        elevation=layout['elevation']), indent=2)+'\n')


def export_contact():
    """Called by the GLB exporter too; refuse to pair a stale scene with fresh collision."""
    if bpy.context.scene.get('monza_layout_sha256') != digest():
        raise RuntimeError('layout.json changed: apply monza_layout.py before exporting')
    rows = json.loads(bpy.context.scene['monza_contact_segments_m'])
    out = '// Generated from the applied Blender boundary geometry. Do not edit.\n'
    out += '// layout SHA256: '+digest()+'\n'
    out += 'inline const AuthoredBarrierSegment kMonzaBarriers[] = {\n'
    for xa,ya,xb,yb,lo,hi,half in rows:
        f = lambda n: f'{n*17:.6f}f'
        out += '    {{'+f(xa)+', '+f(ya)+'}, {'+f(xb)+', '+f(yb)+'}, '+', '.join(map(f,[lo,hi,half]))+'},\n'
    out += '};\ninline const AuthoredSurfaceTriangle kMonzaRunoffTriangles[] = {\n'
    for ob in B.collection('Runoff').objects:
        if ob.type != 'MESH': continue
        asphalt = ob.data.materials[0].name == 'Asphalt'
        ob.data.calc_loop_triangles()
        for triangle in ob.data.loop_triangles:
            pts = [ob.matrix_world @ ob.data.vertices[i].co for i in triangle.vertices]
            out += '    {'+', '.join('{'+f(p.x)+', '+f(-p.y)+'}' for p in pts)+', '+str(asphalt).lower()+'},\n'
    out += '};\n'
    (B.ROOT/'src/track_data/monza_boundaries.inc').write_text(out)


if __name__ == '__main__':
    B.load()
    apply()
    B.save()
