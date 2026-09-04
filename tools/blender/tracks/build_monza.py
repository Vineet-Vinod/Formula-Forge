"""Author the surveyed Monza scene with Blender's Python API.

uv run python tools/blender/tracks/build_monza.py --phase foundation
uv run python tools/blender/tracks/build_monza.py --phase environment --section 0
uv run python tools/blender/tracks/build_monza.py --phase render --section 0
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "assets/tracks/monza/reconstruction"
BLEND = OUT / "monza_reconstruction.blend"
SURVEY = json.loads((OUT / "survey.json").read_text())
XY = SURVEY["centerline_xy"]
N = len(XY)
L = 5793.0
STEP = L/N
TAU = math.tau
COLS = {}
MATS = {}
TANGENTS = []
NORMALS = []
CURVATURE = []
for i in range(N):
    v = Vector(XY[(i+3)%N])-Vector(XY[(i-3)%N])
    v.normalize()
    TANGENTS.append(v)
    NORMALS.append(Vector((-v.y,v.x)))
for i in range(N):
    a,b = TANGENTS[(i-6)%N],TANGENTS[(i+6)%N]
    CURVATURE.append(math.atan2(a.x*b.y-a.y*b.x,a.dot(b))/(12*STEP))
TREE = KDTree(N)
for i,p in enumerate(XY):
    TREE.insert((p[0],p[1],0),i)
TREE.balance()


def terrain(x,y):
    return 0.0022*y + 0.10*math.sin(x/280)*math.sin(y/370)


def width(s):
    anchors = [(0,12),(400,12),(610,11),(710,11),(1480,11),(1800,11),(1950,11),
               (2160,10.5),(2600,10),(3100,10.5),(3640,11),(3900,11),(4750,11),(5130,11),(5500,12),(L,12)]
    for (a,x),(b,y) in zip(anchors,anchors[1:]):
        if a<=s<=b:
            t=(s-a)/(b-a);t=t*t*(3-2*t)
            return x+(y-x)*t
    return 12


def road_z(i,offset=0):
    x,y=XY[i%N]
    crossfall=max(-0.012,min(0.012,CURVATURE[i%N]*1.2))
    return terrain(x,y)+0.19+0.035*(1-min(1,(offset/(width(i%N*STEP)/2))**2))-crossfall*offset


def point(i,offset=0,lift=0):
    i%=N
    p=Vector(XY[i])+NORMALS[i]*offset
    return (p.x,p.y,road_z(i,offset)+lift)


def station_point(s,offset=0,lift=0):
    f=(s%L)/STEP;i=int(f);t=f-i
    return Vector(point(i,offset,lift)).lerp(Vector(point(i+1,offset,lift)),t),TANGENTS[i],NORMALS[i]


def collection(name):
    if name not in COLS:
        c=bpy.data.collections.get(name)
        if c is None:
            c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
        COLS[name]=c
    return COLS[name]


def mesh(name,verts,faces,mat,group,indices=None):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    ob=bpy.data.objects.new(name,data);collection(group).objects.link(ob)
    for m in mat if isinstance(mat,list) else [mat]:
        data.materials.append(m)
    if indices:
        for p,k in zip(data.polygons,indices):p.material_index=k
    return ob


def material(name,color,rough=0.7,metal=0,scale=1,bump=0.03):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True;m.use_fake_user=True
    nd=m.node_tree.nodes;lk=m.node_tree.links;bs=nd.get('Principled BSDF')
    bs.inputs['Metallic'].default_value=metal
    tex=nd.new('ShaderNodeTexCoord')
    noise=nd.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=scale;noise.inputs['Detail'].default_value=4
    # Geometry position is metres regardless of object dimensions or UV seams.
    geo=nd.new('ShaderNodeNewGeometry');lk.new(geo.outputs['Position'],noise.inputs['Vector'])
    ramp=nd.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=0.18;ramp.color_ramp.elements[1].position=0.82
    ramp.color_ramp.elements[0].color=(*(max(0,c*(.89 if name=='Asphalt' else .67)) for c in color),1)
    ramp.color_ramp.elements[1].color=(*(min(1,c*(1.06 if name=='Asphalt' else 1.2)) for c in color),1)
    lk.new(noise.outputs['Fac'],ramp.inputs[0]);lk.new(ramp.outputs[0],bs.inputs['Base Color'])
    remap=nd.new('ShaderNodeMapRange');remap.inputs['To Min'].default_value=max(0,rough-.10);remap.inputs['To Max'].default_value=min(1,rough+.12)
    lk.new(noise.outputs['Fac'],remap.inputs['Value']);lk.new(remap.outputs[0],bs.inputs['Roughness'])
    fine=nd.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=scale*24;fine.inputs['Detail'].default_value=2
    lk.new(geo.outputs['Position'],fine.inputs['Vector'])
    bn=nd.new('ShaderNodeBump');bn.inputs['Strength'].default_value=.3;bn.inputs['Distance'].default_value=bump
    lk.new(fine.outputs['Fac'],bn.inputs['Height']);lk.new(bn.outputs[0],bs.inputs['Normal'])
    MATS[name]=m
    return m


def materials():
    specs=[('Asphalt',(0.075,.081,.084),.91,0,1.1,.006),('Concrete',(.42,.42,.39),.83,0,.7,.016),
           ('White_paint',(.74,.74,.68),.74,0,4,.002),('Red_paint',(.43,.021,.016),.71,0,3,.003),
           ('Green_paint',(.025,.19,.07),.77,0,4,.003),('Grass',(.125,.175,.048),.94,0,.14,.035),
           ('Gravel',(.40,.33,.235),.96,0,4,.038),('Armco',(.43,.47,.48),.43,.82,2,.004),
           ('Fence',(.21,.23,.22),.54,.8,8,.002),('Rubber',(.022,.026,.028),.96,0,2,.003),
           ('Roof',(.49,.51,.48),.48,.38,.8,.009),('Terracotta',(.30,.12,.061),.78,0,3,.01),
           ('Glass',(.052,.098,.12),.19,.55,.3,.001),('Blue_seat',(.018,.075,.22),.63,0,3,.004),
           ('Yellow',(.73,.49,.023),.72,0,3,.004),('Bark',(.10,.073,.043),.97,0,2,.026),
           ('Soil',(.09,.065,.026),1,0,2,.02),('Orange',(.85,.13,.013),.72,0,5,.003)]
    for args in specs:material(*args)
    for j,c in enumerate([(.062,.13,.022),(.095,.18,.025),(.043,.099,.018),(.14,.19,.032),(.11,.145,.021)]):
        m=material(f'Leaf_{j}',c,.86,0,5,.002)
        bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Subsurface Weight'].default_value=.045


def curve(name,points,group,closed=False):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=1
    sp=data.splines.new('POLY');sp.points.add(len(points)-1)
    for v,p in zip(sp.points,points):v.co=(*p,1)
    sp.use_cyclic_u=closed
    ob=bpy.data.objects.new(name,data);collection(group).objects.link(ob)
    ob.hide_render=True;ob.show_in_front=True;ob['units']='metres';ob['editable']=True
    return ob


def box(name,center,size,mat,group,angle=0,bevel=0):
    x,y,z=size;a=math.cos(angle);b=math.sin(angle)
    vs=[]
    for dz in [-z/2,z/2]:
        for dx,dy in [(-x/2,-y/2),(x/2,-y/2),(x/2,y/2),(-x/2,y/2)]:
            vs.append((center[0]+a*dx-b*dy,center[1]+b*dx+a*dy,center[2]+dz))
    ob=mesh(name,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,group)
    if bevel:
        mod=ob.modifiers.new('soft manufactured edges','BEVEL');mod.width=bevel;mod.segments=2
    return ob


def strip(name,inds,left,right,mat,group='Track',lift=0,steps=1,closed=False):
    vs=[];fs=[]
    for i in inds:
        a=left(i) if callable(left) else left;b=right(i) if callable(right) else right
        for k in range(steps+1):vs.append(point(i,a+(b-a)*k/steps,lift))
    for j in range(len(inds) if closed else len(inds)-1):
        for k in range(steps):
            a=j*(steps+1)+k;b=((j+1)%len(inds))*(steps+1)+k
            fs.append((a,b,b+1,a+1))
    ob=mesh(name,vs,fs,mat,group)
    return ob


def ribbon(name,points,w,mat,group,lift=.08):
    vs=[]
    for j,p in enumerate(points):
        a=points[max(0,j-1)];b=points[min(j+1,len(points)-1)]
        t=Vector((b[0]-a[0],b[1]-a[1])).normalized();n=Vector((-t.y,t.x))
        for sign in [-1,1]:
            x,y=p[0]+n.x*w/2*sign,p[1]+n.y*w/2*sign
            vs.append((x,y,terrain(x,y)+lift))
    return mesh(name,vs,[(2*i,2*i+2,2*i+3,2*i+1) for i in range(len(points)-1)],mat,group)


def camera(name,position,target,lens=28):
    d=bpy.data.cameras.new(name);d.lens=lens;d.clip_end=7000;d.clip_start=.08
    ob=bpy.data.objects.new(name,d);collection('QA_cameras').objects.link(ob)
    ob.location=position;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
    return ob


def save():
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND),compress=True)


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc=bpy.context.scene;sc.unit_settings.system='METRIC';sc.unit_settings.scale_length=1
    for c in ['Track','Survey_curves','Safety_barriers','Fencing','Marshal_posts','Signage','Grandstands','Pit_buildings',
              'Bridges','Service_roads','Forest','Distant_environment','QA_cameras','Asset_library','Runoff','Historic_oval']:
        collection(c)
    materials()
    sc.render.engine='CYCLES';sc.cycles.samples=12;sc.cycles.use_denoising=True
    sc.cycles.max_bounces=4;sc.cycles.diffuse_bounces=2;sc.cycles.glossy_bounces=2
    sc.render.threads_mode='FIXED';sc.render.threads=8
    sc.render.resolution_x=960;sc.render.resolution_y=540;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False
    sc.world=bpy.data.worlds.new('September northern Italian daylight');sc.world.use_nodes=True
    wn=sc.world.node_tree.nodes;wl=sc.world.node_tree.links
    sky=wn.new('ShaderNodeTexSky');sky.sky_type='MULTIPLE_SCATTERING';sky.sun_elevation=math.radians(43);sky.sun_rotation=math.radians(135)
    sky.altitude=.15;sky.air_density=1.1;sky.aerosol_density=1.8;sky.sun_intensity=.65
    wl.new(sky.outputs[0],wn.get('Background').inputs[0]);wn.get('Background').inputs[1].default_value=.12
    sc.view_settings.view_transform='AgX';sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=-1.3
    sc['source']='OSM contributors / ODbL 1.0, official Monza circuit guide, FIA Monza 2025 map'
    sc['survey_confidence']=json.dumps(SURVEY['confidence'])
    sc['runtime_integration']='Standalone environment study. Game physics and runtime assets unchanged.'


def foundation():
    setup()
    inds=list(range(N))
    curve('CENTERLINE | 5793 m | clockwise', [point(i) for i in inds],'Survey_curves',True)
    curve('LEFT_EDGE | variable 10-12 m', [point(i,width(i*STEP)/2) for i in inds],'Survey_curves',True)
    curve('RIGHT_EDGE | variable 10-12 m', [point(i,-width(i*STEP)/2) for i in inds],'Survey_curves',True)
    for f in SURVEY['features']:
        t=f['tags']
        if f['osm_way']==38168747 or t.get('highway')=='service':
            curve('PIT_LANE' if f['osm_way']==38168747 else f'SERVICE | OSM {f["osm_way"]}',
                  [(x,y,terrain(x,y)+.14) for x,y in f['points']],'Survey_curves')
    road=strip('ASPHALT | continuous crowned surface',inds,lambda i:-width(i*STEP)/2,lambda i:width(i*STEP)/2,
               MATS['Asphalt'],steps=8,closed=True)
    for p in road.data.polygons:p.use_smooth=True
    road['cross_section']='35 mm crown, inferred camber <= 1.2 percent; 0.75 m longitudinal sampling'
    for sign,side in [(1,'L'),(-1,'R')]:
        strip(f'{side} continuous 150 mm edge line',inds,lambda i:sign*(width(i*STEP)/2-.22),
              lambda i:sign*(width(i*STEP)/2-.07),MATS['White_paint'],lift=.007,closed=True)
        strip(f'{side} drainage concrete',inds,lambda i:sign*(width(i*STEP)/2),
              lambda i:sign*(width(i*STEP)/2+.35),MATS['Concrete'],lift=-.017,closed=True)
        strip(f'{side} grass verge',inds,lambda i:sign*(width(i*STEP)/2+.35),
              lambda i:sign*(width(i*STEP)/2+2),MATS['Grass'],lift=-.035,steps=2,closed=True)
    # Broad continuous terrain, all road/structure grounding uses this same height function.
    vs=[];fs=[];nx=112;ny=160
    for j in range(ny):
        for i in range(nx):
            x=-650+i*22;y=-1300+j*22;vs.append((x,y,terrain(x,y)))
    for j in range(ny-1):
        for i in range(nx-1):
            a=j*nx+i;fs.append((a,a+1,a+nx+1,a+nx))
    mesh('Park ground',vs,fs,MATS['Grass'],'Distant_environment')
    pit=next(f for f in SURVEY['features'] if f['osm_way']==38168747)
    ribbon('Pit lane | mapped entry and exit',pit['points'],8.0,MATS['Asphalt'],'Track',.18)
    for side in [-1,1]:
        # Edges derive from the same pit spline, keeping the entry/exit editable.
        ps=[]
        for i,p in enumerate(pit['points']):
            a=pit['points'][max(0,i-1)];b=pit['points'][min(len(pit['points'])-1,i+1)]
            v=Vector((b[0]-a[0],b[1]-a[1])).normalized();ps.append((p[0]-v.y*side*3.7,p[1]+v.x*side*3.7))
        ribbon(f'Pit edge {side}',ps,.12,MATS['White_paint'],'Track',.191)
    for section in SURVEY['sections']:
        s=section['start_m']+25;p,t,n=station_point(s,0,1.2);target=station_point(s+38)[0]
        camera('DRIVER | '+section['name'],p,target+Vector((0,0,1.2)),28)
        mid=(section['start_m']+section['end_m'])/2;cp,ct,cn=station_point(mid)
        camera('ELEVATED | '+section['name'],cp+Vector((cn.x*180-ct.x*160,cn.y*180-ct.y*160,180)),cp,38)
    overview=camera('OVERVIEW | whole circuit',(1900,-1900,2550),(480,380,0),43)
    bpy.context.scene.camera=overview
    # Foundation diagnostics are completed before environment work is allowed.
    length=sum((Vector(point(i+1))-Vector(point(i))).length for i in range(N))
    stats=[]
    for section in SURVEY['sections']:
        a=int(section['start_m']/STEP);b=min(N,int(section['end_m']/STEP))
        ks=CURVATURE[a:b];zs=[point(i)[2] for i in range(a,b)]
        stats.append({**section,'length_m':section['end_m']-section['start_m'],
                      'heading_change_deg':math.degrees(sum(ks)*STEP),
                      'minimum_radius_m':1/max(abs(k) for k in ks),
                      'width_min_m':min(width(i*STEP) for i in range(a,b)),
                      'width_max_m':max(width(i*STEP) for i in range(a,b)),
                      'elevation_min_m':min(zs),'elevation_max_m':max(zs),
                      'vertical_and_camber_status':'inferred, not surveyed'})
    report={'plan_length_m':SURVEY['plan_length_m'],'spatial_centerline_length_m':length,
            'length_error_m':length-L,'sections':stats,'source_confidence':SURVEY['confidence']}
    assert abs(length-L)<1,report
    (OUT/'geometry_qa.json').write_text(json.dumps(report,indent=2)+'\n')
    bpy.context.scene['foundation_passed']=True
    save()


def load():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    COLS.clear();MATS.update({m.name:m for m in bpy.data.materials})


def render(section=None,foundation_only=False):
    sc=bpy.context.scene
    folder=OUT/('qa/foundation' if foundation_only else 'qa/sections');folder.mkdir(parents=True,exist_ok=True)
    names=['OVERVIEW | whole circuit'] if section is None else [prefix+' | '+SURVEY['sections'][section]['name'] for prefix in ['DRIVER','ELEVATED']]
    for name in names:
        sc.camera=bpy.data.objects[name];sc.render.filepath=str(folder/(name.replace(' | ','_')+'.png'))
        bpy.ops.render.render(write_still=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['foundation','environment','render','finalize','lap'],default='foundation')
    parser.add_argument('--section',type=int);parser.add_argument('--foundation-only',action='store_true')
    args=parser.parse_args()
    if args.phase=='foundation':foundation();render(foundation_only=True)
    else:
        load()
        if args.phase=='render':render(args.section,args.foundation_only)
        elif args.phase=='environment':
            import sys
            from monza_environment import build
            build(sys.modules[__name__],args.section)
        elif args.phase=='finalize':finalize()
        elif args.phase=='lap':lap()


if __name__=='__main__':main()
