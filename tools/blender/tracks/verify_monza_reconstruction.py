"""Read the authored Blender artifact and audit geometry, instances and cameras.

uv run python tools/blender/tracks/verify_monza_reconstruction.py
"""
import collections
import json
import math

import bpy
import numpy as np
from mathutils import Vector

import build_monza as B


def main():
    B.load();sc=bpy.context.scene;errors=[];checks={}
    def check(name,condition,details):
        checks[name]={'passed':bool(condition),'details':details}
        if not condition:errors.append(name)
    check('metre units',sc.unit_settings.system=='METRIC' and sc.unit_settings.scale_length==1,'X east, Y north, Z up')
    path=bpy.data.objects['CENTERLINE | 5793 m | clockwise'].data.splines[0]
    ps=[Vector(v.co[:3]) for v in path.points]
    length=sum((p-q).length for p,q in zip(ps,ps[1:]+ps[:1]))
    check('closed official length',path.use_cyclic_u and abs(length-5793)<.5,{'spatial_length_m':length,'error_m':length-5793})
    area=sum(p.x*q.y-q.x*p.y for p,q in zip(ps,ps[1:]+ps[:1]))/2
    check('clockwise lap',area<0,{'signed_area_m2':area})
    # Test nonadjacent segment crossings with spatial buckets, not only total length.
    buckets=collections.defaultdict(list);crossings=[];seen=set()
    def orient(a,b,c):return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)
    for i,p in enumerate(ps):
        q=ps[(i+1)%len(ps)]
        for x in range(math.floor(min(p.x,q.x)/12),math.floor(max(p.x,q.x)/12)+1):
            for y in range(math.floor(min(p.y,q.y)/12),math.floor(max(p.y,q.y)/12)+1):
                for j in buckets[x,y]:
                    if min(abs(i-j),len(ps)-abs(i-j))<=2 or (j,i) in seen:continue
                    seen.add((j,i));a,b=ps[j],ps[(j+1)%len(ps)]
                    if orient(p,q,a)*orient(p,q,b)<0 and orient(a,b,p)*orient(a,b,q)<0:crossings.append([i,j])
                buckets[x,y].append(i)
    check('no plan self intersections',not crossings,{'crossing_pairs':crossings[:20]})
    road=bpy.data.objects['ASPHALT | continuous crowned surface'].data
    incidence=collections.Counter()
    for poly in road.polygons:
        for edge in poly.edge_keys:incidence[tuple(sorted(edge))]+=1
    boundary=[edge for edge,count in incidence.items() if count==1];graph=collections.defaultdict(set)
    for a,b in boundary:graph[a].add(b);graph[b].add(a)
    components=0;seen=set()
    for v in graph:
        if v in seen:continue
        components+=1;todo=[v]
        while todo:
            k=todo.pop()
            if k not in seen:seen.add(k);todo.extend(graph[k]-seen)
    check('continuous asphalt annulus',components==2 and all(c in [1,2] for c in incidence.values()) and all(len(v)==2 for v in graph.values()),
          {'boundary_loops':components,'vertices':len(road.vertices),'faces':len(road.polygons)})
    min_clearance=min(v.co.z-B.terrain(v.co.x,v.co.y) for v in road.vertices)
    check('road above terrain',min_clearance>0,{'minimum_surface_clearance_m':min_clearance})
    check('nondegenerate road faces',all(p.area>.015 for p in road.polygons),{'minimum_face_area_m2':min(p.area for p in road.polygons)})
    widths=[]
    for i in range(B.N):
        widths.append((road.vertices[i*9].co-road.vertices[i*9+8].co).length)
    check('realistic road widths',min(widths)>=9.99 and max(widths)<=12.01,{'minimum_m':min(widths),'maximum_m':max(widths)})
    fitted={}
    for way,expected in [('179968220',300),('179968229',75),('179968230',35)]:
        w=B.SURVEY['way_stations'][way];q=np.array(B.XY[int(w['start_m']/B.STEP):int(w['end_m']/B.STEP)])
        fit=np.linalg.lstsq(np.column_stack([q*2,np.ones(len(q))]),np.sum(q*q,axis=1),rcond=None)[0]
        radius=float(math.sqrt(fit[2]+fit[0]**2+fit[1]**2));fitted[w['name']]={'fit_m':radius,'guide_approximate_m':expected}
    check('independent radius checks',all(abs(v['fit_m']/v['guide_approximate_m']-1)<.15 for v in fitted.values()),fitted)
    counts=collections.Counter();barrier_min=100;barrier_errors=[];trees_below=[]
    for ob in bpy.data.objects:
        if 'instance_count' not in ob:continue
        key='trees' if ' woodland ' in ob.name else 'fence' if 'catch fence' in ob.name else 'armco' if ' Armco ' in ob.name else 'other'
        counts[key]+=ob['instance_count']
        if key=='armco':
            for v in ob.data.vertices:
                p=v.co;_,i,d=B.TREE.find((p.x,p.y,0));clearance=d-B.width(i*B.STEP)/2;barrier_min=min(barrier_min,clearance)
                if clearance<2.5:barrier_errors.append([ob.name,round(i*B.STEP,2),clearance])
        if key=='trees':
            for v in ob.data.vertices:
                if abs(v.co.z-B.terrain(v.co.x,v.co.y))>.01:trees_below.append(ob.name)
    check('barrier road clearance',not barrier_errors,{'minimum_edge_clearance_m':barrier_min,'failures':barrier_errors[:20]})
    check('grounded trees',not trees_below,{'incorrect_instances':len(trees_below),'counts':dict(counts)})
    cams=[ob for ob in bpy.data.objects if ob.type=='CAMERA' and ob.name.startswith('DRIVER |')]
    cam_heights=[]
    for cam in cams:
        p=cam.location;_,i,d=B.TREE.find((p.x,p.y,0));cam_heights.append(p.z-B.road_z(i))
    check('driver camera height',len(cams)==10 and max(abs(h-1.2) for h in cam_heights)<.01,{'camera_heights_m':cam_heights})
    lap=bpy.data.objects.get('LAP | 1.2 m | animated survey inspection')
    check('whole lap animation',lap is not None and lap.animation_data is not None and sc.frame_end==1932,{'frames':sc.frame_end})
    check('ten section checkpoints',all((B.OUT/f'qa/section_{i:02d}.json').exists() for i in range(10)),'Section metadata and render checkpoints')
    report={'passed':not errors,'checks':checks,'limitations':B.SURVEY['confidence'],
            'visual_review':'See QA.md. Numerical checks do not certify photogrammetric accuracy or exact event infrastructure.'}
    (B.OUT/'qa/final_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if errors:raise SystemExit('Validation failed: '+', '.join(errors))


if __name__=='__main__':main()
