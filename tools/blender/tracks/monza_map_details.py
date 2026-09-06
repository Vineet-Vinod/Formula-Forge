"""Targeted Monza repairs and distance boards. Called by monza_layout.apply()."""
import json
import math
import re

import bmesh
import bpy
from mathutils import Vector
from shapely import LineString, MultiPoint, Point, unary_union

import build_monza as B
import monza_environment as E
from braking_markers import plan_markers


def source_mesh(ob):
    name='DETAIL_SOURCE | '+ob.name
    source=bpy.data.meshes.get(name)
    if source is None:
        source=ob.data.copy();source.name=name;source.use_fake_user=True
    ob.data=source.copy()
    return ob.data


def bounds(ob):
    # A replaced mesh can leave the object's cached bound_box stale until the
    # dependency graph updates. Read the actual vertices for diagnostic bounds.
    pts=[ob.matrix_world@v.co for v in ob.data.vertices]
    return [[min(p[k] for p in pts) for k in range(3)],
            [max(p[k] for p in pts) for k in range(3)]]


def repair_geometry():
    report=[]
    stands=unary_union([MultiPoint([tuple(v.co[:2]) for v in ob.data.vertices]).convex_hull.buffer(.3)
        for ob in B.collection('Grandstands').objects if 'concrete terraces' in ob.name])
    for name in ['Historic oval 1313097098','Historic oval 19982933']:
        ob=bpy.data.objects.get(name)
        if ob is None: continue
        source_mesh(ob)
        original_bounds=bounds(ob)
        feature=next(f for f in B.SURVEY['features'] if f['osm_way']==int(name.split()[-1]))
        axis=LineString(feature['points'])
        moved=0
        for vertex in ob.data.vertices:
            p=vertex.co
            _,i,d=B.TREE.find((p.x,p.y,0))
            if not (100<i*B.STEP<640 and d<45): continue
            station=axis.project(Point(p.x,p.y))
            a=axis.interpolate(max(0,station-4));b=axis.interpolate(min(axis.length,station+4))
            t=Vector((b.x-a.x,b.y-a.y)).normalized()
            angle=math.degrees(math.acos(max(-1,min(1,abs(t.dot(B.TANGENTS[i]))))))
            strength=max(0,min(1,(angle-5)/15));strength=strength*strength*(3-2*strength)
            # This OSM way is entirely the straight approach. Its endpoint kink
            # must not reintroduce banking before the separate curved way.
            if name=='Historic oval 1313097098':strength=0
            ground=B.terrain(p.x,p.y)+.035
            p.z=ground+(p.z-ground)*strength
            moved+=1
        bm=bmesh.new();bm.from_mesh(ob.data)
        obscured=[f for f in bm.faces if any(stands.contains(Point(v.co.x,v.co.y)) for v in f.verts)]
        bmesh.ops.delete(bm,geom=obscured,context='FACES')
        # These historic bank sheets had neither an underside nor an embankment.
        # Join exposed local perimeter edges down to terrain, with no floating caps.
        edges=[e for e in bm.edges if e.is_boundary and
               all(100<v.co.y<640 and v.co.x<170 for v in e.verts)]
        skirt_faces=0
        for edge in edges:
            a,b=edge.verts
            za=B.terrain(a.co.x,a.co.y)-.10;zb=B.terrain(b.co.x,b.co.y)-.10
            if max(a.co.z-za,b.co.z-zb)<.25: continue
            low_a=bm.verts.new((a.co.x,a.co.y,za));low_b=bm.verts.new((b.co.x,b.co.y,zb))
            bm.faces.new((b,a,low_a,low_b));skirt_faces+=1
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.normal_update();bm.to_mesh(ob.data);bm.free();ob.data.update()
        item=dict(name=name,original_bounds=original_bounds,bounds=bounds(ob),
                  grounded_straight_vertices=moved,faces_removed_at_stands=len(obscured),grounded_boundary_faces=skirt_faces)
        print('MAP DETAIL',json.dumps(item),flush=True);report.append(item)
        ob['straight_banking_repaired']=True
    # Remove the straight's decorative kerbs, preserving the actual Alboreto corner.
    for name in ['Alboreto kerb 5280','Alboreto green apron 5280']:
        ob=bpy.data.objects.get(name)
        if ob:
            report.append(dict(name=name,original_bounds=bounds(ob),action='remove straight pit-approach kerb/apron'))
            bpy.data.objects.remove(ob,do_unlink=True)
    for name in ['Alboreto kerb 4990','Alboreto green apron 4990']:
        ob=bpy.data.objects.get(name)
        if not ob:continue
        source_mesh(ob)
        bm=bmesh.new();bm.from_mesh(ob.data)
        remove=[f for f in bm.faces if B.TREE.find((*f.calc_center_median()[:2],0))[1]*B.STEP>=5230]
        count=len(remove);bmesh.ops.delete(bm,geom=remove,context='FACES')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(ob.data);bm.free();ob.data.update()
        report.append(dict(name=name,removed_pit_approach_faces=count))
    # The pit buildings and central lane remain behind the wall. Remove entry/exit
    # tapers and paint that would invite a car into the now-closed branches.
    for name in ['Pit lane | mapped entry and exit','Pit edge -1','Pit edge 1']:
        ob=bpy.data.objects.get(name)
        if not ob:continue
        source_mesh(ob)
        bm=bmesh.new();bm.from_mesh(ob.data)
        remove=[]
        for face in bm.faces:
            x,y,_=face.calc_center_median();_,i,_=B.TREE.find((x,y,0));station=i*B.STEP
            if 95<station<5510:remove.append(face)
        count=len(remove);bmesh.ops.delete(bm,geom=remove,context='FACES')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(ob.data);bm.free();ob.data.update()
        report.append(dict(name=name,removed_branch_faces=count))
    (B.OUT/'qa/map_detail_repairs.json').write_text(json.dumps(report,indent=2)+'\n')


def build_markers(layout):
    E.B=B
    for ob in list(bpy.data.objects):
        if ob.name.startswith('BRAKE | ') or re.fullmatch(r'T\d+ (braking board \d+|\d+m)',ob.name):
            bpy.data.objects.remove(ob,do_unlink=True)
    plan=plan_markers(layout['braking_zones'],B.L)
    report=[]
    for board in plan:
        s=board['station_m'];side=board['side'];p,t,n=B.station_point(s)
        direction=n*side
        # Intersect the transverse station line, so the board's distance stays exact
        # along the road even when the safety barrier is angled or offset.
        ray=LineString([p[:2],(p.x+direction.x*200,p.y+direction.y*200)])
        hits=[]
        for path in layout['barriers']:
            hit=ray.intersection(LineString(path['points']))
            for q in getattr(hit,'geoms',[hit]):
                if q.geom_type=='Point':
                    distance=math.hypot(q.x-p.x,q.y-p.y)
                    if distance>B.width(s)/2: hits.append(distance)
        if not hits:raise ValueError(f'No barrier alongside braking board {board}')
        offset=min(hits)+.8
        center=Vector((p.x+direction.x*offset,p.y+direction.y*offset,0))
        ground=B.terrain(center.x,center.y);center.z=ground+2.05
        angle=math.atan2(t.y,t.x)-math.pi/2
        name=f"BRAKE | T{board['turn']} | {board['distance_m']}m"
        panel=B.box(name,center,(2.0,.12,1.4),B.MATS['White_paint'],'Signage',angle)
        E.text_object(name+' digits',str(board['distance_m']),center-Vector((t.x,t.y,0))*.074,
                      .95,angle,'Rubber')
        for sign in [-1,1]:
            foot=center+Vector((n.x,n.y,0))*.75*sign
            B.box(name+f' post {sign}',(foot.x,foot.y,ground+.88),(.06,.06,1.76),B.MATS['Armco'],'Signage')
        panel['distance_to_corner_entry_m']=board['distance_m'];panel['station_m']=s
        panel['corner_entry_m']=board['entry_m'];panel['marker_policy']='approach-length-v1'
        report.append({**board,'center':list(center),'barrier_offset_m':offset-.8,
                       'front_normal':[-t.x,-t.y,0],'text_face_clearance_m':.014})
    (B.OUT/'qa/braking_markers.json').write_text(json.dumps(report,indent=2)+'\n')
    print('BRAKING MARKERS',len(report),flush=True)
