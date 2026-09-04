"""Section-by-section environment authoring for build_monza.py.

Footprints and planting masks come from the checked-in survey. Construction
details and heights are artist estimates, kept separate from mapped geometry.
"""
import json
import math
import random

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.geometry import tessellate_polygon

B=None
TAU=math.tau


class Batch:
    def __init__(self):self.v=[];self.f=[];self.m=[]
    def face(self,points,mat=0):
        i=len(self.v);self.v.extend(points);self.f.append(tuple(range(i,i+len(points))));self.m.append(mat)
    def cube(self,c,size,angle=0,mat=0):
        x,y,z=size;ca,sa=math.cos(angle),math.sin(angle);v=[]
        for dz in [-z/2,z/2]:
            for dx,dy in [(-x/2,-y/2),(x/2,-y/2),(x/2,y/2),(-x/2,y/2)]:
                v.append((c[0]+ca*dx-sa*dy,c[1]+sa*dx+ca*dy,c[2]+dz))
        j=len(self.v);self.v.extend(v)
        for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            self.f.append(tuple(j+i for i in f));self.m.append(mat)
    def rod(self,a,b,r,mat=0,sides=7,tip=None):
        a,b=Vector(a),Vector(b);t=(b-a).normalized();n=t.cross(Vector((.123,.932,.343))).normalized();v=t.cross(n)
        j=len(self.v)
        for p,rad in [(a,r),(b,r if tip is None else tip)]:
            for k in range(sides):self.v.append(tuple(p+rad*(n*math.cos(k*TAU/sides)+v*math.sin(k*TAU/sides))))
        for k in range(sides):self.f.append((j+k,j+(k+1)%sides,j+(k+1)%sides+sides,j+k+sides));self.m.append(mat)
        self.f.append(tuple(j+k for k in reversed(range(sides))));self.m.append(mat)
        self.f.append(tuple(j+k+sides for k in range(sides)));self.m.append(mat)
    def ellipsoid(self,c,r,mat=0,lon=10,lat=6,phase=0):
        j=len(self.v)
        for b in range(lat+1):
            p=math.pi*b/lat
            for a in range(lon):
                t=a*TAU/lon
                irregular=1+.12*math.sin(t*3+phase)*math.sin(p*4+phase)
                self.v.append((c[0]+r[0]*math.sin(p)*math.cos(t)*irregular,c[1]+r[1]*math.sin(p)*math.sin(t)*irregular,c[2]+r[2]*math.cos(p)*irregular))
        for b in range(lat):
            for a in range(lon):
                self.f.append((j+b*lon+a,j+b*lon+(a+1)%lon,j+(b+1)*lon+(a+1)%lon,j+(b+1)*lon+a));self.m.append(mat)
    def object(self,name,mats,group,smooth=False):
        ob=B.mesh(name,self.v,self.f,mats,group,self.m)
        if smooth:
            for p in ob.data.polygons:p.use_smooth=True
        return ob


def inside(x,y,polygon):
    yes=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:yes=not yes
    return yes


def centroid(ps):return (sum(p[0] for p in ps)/len(ps),sum(p[1] for p in ps)/len(ps))


def polygon(name,ps,material,group,lift=.05):
    points=[Vector((x,y,B.terrain(x,y)+lift)) for x,y in ps]
    if (points[0]-points[-1]).length<.01:points.pop()
    tris=tessellate_polygon([points]);verts=[];faces=[]
    for tri in tris:
        i=len(verts);verts.extend(tri);faces.append((i,i+1,i+2))
    return B.mesh(name,verts,faces,material,group)


# Kerb segments follow the actual corner order. Positive offsets are driver-left.
KERBS=[(609,642,-1),(644,686,1),(700,790,-1),(1817,1858,1),(1864,1904,-1),(1910,1970,1),
       (2200,2315,-1),(2280,2385,1),(2545,2606,-1),(2590,2680,1),
       (3630,3675,1),(3700,3783,-1),(3800,3872,1),(3865,3940,-1),
       (4820,4945,-1),(4990,5360,-1),(5280,5525,1)]
RUNOFF=[(540,722,1,24,'Asphalt'),(1800,1940,-1,32,'Gravel'),(2180,2390,1,29,'Gravel'),
        (2500,2680,1,28,'Gravel'),(3610,3880,-1,28,'Gravel'),(3620,3860,1,22,'Gravel'),
        (4770,5180,1,35,'Gravel'),(5180,5420,1,26,'Asphalt')]


def barrier_offset(s,side):
    offset=10.5
    if 40<s<490:offset=12 if side==1 else 17
    if s>5460 or s<40:offset=10 if side==1 else 8.5
    for a,b,sign,w,mat in RUNOFF:
        if sign==side:
            center=(a+b)/2;extent=(b-a)/2
            u=max(0,min(1,(extent+65-abs(s-center))/65))
            u=u*u*(3-2*u);offset=max(offset,10.5+(w+5-10.5)*u)
    i=int(s/B.STEP)%B.N;k=B.CURVATURE[i]
    if k*side>0.002:offset=min(offset,max(9,1/abs(k)*.70))
    return B.width(s)/2+offset


def instances(name,prototype,placements,group):
    if not placements:return
    vs=[p[0] for p in placements];ob=B.mesh(name,vs,[],B.MATS['Bark'],group)
    for attr,values in [('instance_scale',[p[1] for p in placements]),('instance_rotation',[(0,0,p[2]) for p in placements])]:
        a=ob.data.attributes.new(attr,'FLOAT_VECTOR','POINT');a.data.foreach_set('vector',[v for val in values for v in val])
    nodes=bpy.data.node_groups.new(name+' instances','GeometryNodeTree')
    nodes.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');nodes.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    n=nodes.nodes;l=nodes.links;i=n.new('NodeGroupInput');o=n.new('NodeGroupOutput');inst=n.new('GeometryNodeInstanceOnPoints')
    info=n.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=prototype;info.transform_space='ORIGINAL'
    l.new(i.outputs['Geometry'],inst.inputs['Points']);l.new(info.outputs['Geometry'],inst.inputs['Instance']);l.new(inst.outputs['Instances'],o.inputs['Geometry'])
    for attr,slot in [('instance_scale','Scale'),('instance_rotation','Rotation')]:
        at=n.new('GeometryNodeInputNamedAttribute');at.data_type='FLOAT_VECTOR';at.inputs['Name'].default_value=attr;l.new(at.outputs['Attribute'],inst.inputs[slot])
    mod=ob.modifiers.new('Linked asset instances','NODES');mod.node_group=nodes
    ob['instance_count']=len(placements)
    return ob


def library():
    if bpy.data.objects.get('LIB_Armco_4m'):return
    b=Batch()
    # Corrugated W-beam, three courses. Local X follows the circuit tangent.
    for z in [.36,.67,.98]:
        profile=[(-.075,z-.145),(.055,z-.10),(.075,z-.035),(-.025,z),(.075,z+.035),(.055,z+.10),(-.075,z+.145)]
        for a,c in zip(profile,profile[1:]):b.face([(-2,a[0],a[1]),(2,a[0],a[1]),(2,c[0],c[1]),(-2,c[0],c[1])])
    for x in [-1,1]:b.cube((x,.10,.56),(.11,.15,1.12));b.cube((x,.075,1.0),(.12,.025,.08))
    ob=b.object('LIB_Armco_4m',[B.MATS['Armco']],'Asset_library');ob.hide_render=True
    f=Batch();f.rod((-2,0,0),(-2,0,3.25),.038);f.rod((-2,0,3.25),(-2,-.42,3.8),.031)
    for h in [.5,1.5,2.5,3.25]:f.rod((-2,0,h),(2,0,h),.008,sides=4)
    # Actual diamond wires, 120 mm mesh. Instanced rather than a solid fence sheet.
    for direction in [-1,1]:
        for k in range(-31,35):
            intercept=k*.17
            candidates=[]
            for x in [-2,2]:
                z=direction*x+intercept
                if .25<=z<=3.25:candidates.append((x,.018,z))
            for z in [.25,3.25]:
                x=(z-intercept)/direction
                if -2<=x<=2:candidates.append((x,.018,z))
            if len(candidates)>=2:f.rod(candidates[0],candidates[1],.0025,sides=3)
    ob=f.object('LIB_Fence_4m',[B.MATS['Fence']],'Asset_library');ob.hide_render=True
    b=Batch();b.cube((0,0,.5),(1.95,.78,1.0));ob=b.object('LIB_Tecpro',[B.MATS['Red_paint']],'Asset_library');ob.hide_render=True
    b=Batch();b.rod((0,0,0),(0,0,1.0),.07,sides=8);ob=b.object('LIB_Bollard',[B.MATS['Orange']],'Asset_library');ob.hide_render=True
    # Twelve broadleaf forms: four mature crowns, mixed younger growth, lower-cost distant crowns.
    for kind in range(12):
        rng=random.Random(9300+kind);near=kind<6;b=Batch();height=17+kind%3*3;spread=5.2+(kind%4)*.7
        if kind%6==4:height=25;spread=3.1
        b.rod((0,0,0),(.35,-.18,height*.77),.34,0,10,.075)
        clusters=[]
        for j in range(22 if near else 15):
            z=height*(.37+.52*rng.random());ang=j*2.399963;radius=spread*(.4+.6*rng.random())*math.sin((z/height)*math.pi)
            end=Vector((math.cos(ang)*radius,math.sin(ang)*radius,z))
            base=Vector((.25,-.1,z-height*.2))
            b.rod(base,end,.12*(1-z/height)+.025,0,6,.018)
            for q in range(3):
                tip=end+Vector((rng.uniform(-1.3,1.3),rng.uniform(-1.3,1.3),rng.uniform(.1,1.8)))
                if near:b.rod(end,tip,.019,0,5,.005)
                clusters.append((tip,Vector((1.15+rng.random()*.65,1.15+rng.random()*.65,1.2+rng.random()*.9))))
        for j,(c,rad) in enumerate(clusters):
            # Inner twig foliage supports fine leaf silhouettes, avoiding smooth ball crowns.
            b.ellipsoid(c,rad*.72,1+j%5,lon=9,lat=5,phase=j)
            for leaf in range(95 if near else 18):
                zz=rng.uniform(-1,1);ang=rng.random()*TAU;rr=math.sqrt(1-zz*zz)
                normal=Vector((rr*math.cos(ang),rr*math.sin(ang),zz))
                p=c+Vector((normal.x*rad.x,normal.y*rad.y,normal.z*rad.z))*rng.uniform(.68,1.15)
                u=normal.cross(Vector((.13,.83,.35))).normalized();v=normal.cross(u)
                size=rng.uniform(.065,.15) if near else rng.uniform(.20,.36)
                b.face([p-u*size,p-v*size*.5+normal*.02,p+u*size,p+v*size*.5],1+(j+leaf)%5)
        ob=b.object(f'LIB_Tree_{kind:02d}',[B.MATS['Bark']]+[B.MATS[f'Leaf_{j}'] for j in range(5)],'Asset_library',True);ob.hide_render=True
        ob['height_m']=height;ob['detail']='foreground leaf geometry' if near else 'distant reduced foliage'


def surface(section):
    start,end=section['start_m'],section['end_m'];inds=list(range(math.ceil(start/B.STEP),min(B.N,math.ceil(end/B.STEP))+1))
    for a,b,side in KERBS:
        a=max(a,start);b=min(b,end)
        if a>=b:continue
        vs=[];fs=[];mi=[]
        for k in range(math.ceil((b-a)/B.STEP)):
            i=int(a/B.STEP)+k;w=B.width(i*B.STEP)/2
            j=len(vs)
            for q in [i,i+1]:
                for offset,z in [(0,0.007),(.3,.042),(1.1,.036),(1.45,.005)]:vs.append(B.point(q,side*(B.width(q%B.N*B.STEP)/2+offset),z))
            for c in range(3):fs.append((j+c,j+4+c,j+5+c,j+1+c));mi.append((int((a+k*B.STEP)/1.5)%2))
        B.mesh(f'{section["name"]} kerb {a:.0f}',vs,fs,[B.MATS['White_paint'],B.MATS['Red_paint']],'Track',mi)
        ids=list(range(int(a/B.STEP),int(b/B.STEP)+1))
        B.strip(f'{section["name"]} green apron {a:.0f}',ids,lambda i:side*(B.width(i%B.N*B.STEP)/2+1.45),
                lambda i:side*(B.width(i%B.N*B.STEP)/2+2.8),B.MATS['Green_paint'],lift=.005)
    # Gravel traps use mapped polygons; these strips fill unmapped transitions only.
    for a,b,side,w,mat in RUNOFF:
        a=max(a,start);b=min(b,end)
        if a>=b:continue
        ids=list(range(int(a/B.STEP),int(b/B.STEP)+1))
        def extent(i):
            t=(i*B.STEP-a)/max(1,b-a);return 3+(w-3)*min(1,t*8,(1-t)*8)
        B.strip(f'{section["name"]} {mat} runoff',ids,lambda i:side*(B.width(i%B.N*B.STEP)/2+2),
                lambda i:side*(B.width(i%B.N*B.STEP)/2+max(3,extent(i))),B.MATS[mat],'Runoff',lift=-.035,steps=6)
    # Racing rubber is a graded material on the asphalt, no floating overlay ribbon.
    road=bpy.data.objects['ASPHALT | continuous crowned surface']
    attr=road.data.attributes.get('rubber_deposit') or road.data.attributes.new('rubber_deposit','FLOAT','POINT')
    for i in range(math.ceil(start/B.STEP),min(B.N,math.ceil(end/B.STEP))):
        s=i*B.STEP;k=B.CURVATURE[i];offset=-math.tanh(k*65)*B.width(s)*.22
        intensity=.18+min(.50,abs(k)*36)
        for a,b,side in KERBS:
            if a-110<s<a:intensity=max(intensity,.44)
        for cross in range(9):
            x=-B.width(s)/2+B.width(s)*cross/8
            attr.data[i*9+cross].value=intensity*math.exp(-((x-offset)/1.9)**4)
    asphalt=B.MATS['Asphalt'];nodes=asphalt.node_tree.nodes;links=asphalt.node_tree.links
    if not nodes.get('Rubber deposit'):
        bs=nodes.get('Principled BSDF');original=bs.inputs['Base Color'].links[0].from_socket
        at=nodes.new('ShaderNodeAttribute');at.attribute_name='rubber_deposit';at.name='Rubber deposit'
        mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[2].default_value=(.013,.014,.014,1)
        links.new(at.outputs['Fac'],mix.inputs[0]);links.new(original,mix.inputs[1]);links.new(mix.outputs[0],bs.inputs['Base Color'])
    # Drain grates and localized repair patches are placed at braking/maintenance locations.
    b=Batch()
    for s in range(math.ceil(start/40)*40,int(end),40):
        for side in [-1,1]:
            p,t,n=B.station_point(s,side*(B.width(s)/2+.2),-.014);ang=math.atan2(t.y,t.x)
            for k in range(7):b.cube(p+Vector((t.x,t.y,0))*(k*.065-.2),(.018,.28,.025),ang)
    b.object(section['name']+' drain gratings',[B.MATS['Fence']],'Track')


def safety(section):
    name=section['name'];a,b=section['start_m'],section['end_m'];report=[]
    for side in [-1,1]:
        rails=[];fences=[];min_offset=1000
        for s in range(math.ceil(a/4)*4,int(b),4):
            off=barrier_offset(s,side);min_offset=min(min_offset,off-B.width(s)/2)
            # Pit merge and split remain open, with a separate pit wall alongside the garages.
            if side==-1 and (s<145 or s>5400):continue
            p,t,n=B.station_point(s,side*off);p.z=B.terrain(p.x,p.y)+.05
            angle=math.atan2(t.y,t.x)
            rails.append((p,(1,1,1),angle))
            q=p+Vector((n.x,n.y,0))*side*.55
            fences.append((q,(1,1,1),angle+(math.pi if side<0 else 0)))
        instances(name+f' Armco {side}',bpy.data.objects['LIB_Armco_4m'],rails,'Safety_barriers')
        instances(name+f' catch fence {side}',bpy.data.objects['LIB_Fence_4m'],fences,'Fencing')
        report.append({'side':side,'minimum_edge_offset_m':min_offset,'armco_modules':len(rails)})
    section['safety_review']=report


def text_object(name,body,p,size,angle=0,mat='White_paint',group='Signage'):
    data=bpy.data.curves.new(name,'FONT');data.body=body;data.size=size;data.align_x='CENTER';data.align_y='CENTER';data.extrude=.004
    ob=bpy.data.objects.new(name,data);B.collection(group).objects.link(ob);data.materials.append(B.MATS[mat]);ob.location=p;ob.rotation_euler=(math.pi/2,0,angle)
    return ob


def signage(section):
    a,b=section['start_m'],section['end_m'];batch=Batch()
    turns=[(620,1),(658,2),(1190,3),(1845,4),(1880,5),(2255,6),(2575,7),(3646,8),(3753,9),(3831,10),(4940,11)]
    for apex,num in turns:
        if not a<=apex<b:continue
        p,t,n=B.station_point(apex,barrier_offset(apex,1)+1);p.z=B.terrain(p.x,p.y)
        batch.cube((p.x,p.y,p.z+1.6),(.08,.08,3.2));ang=math.atan2(t.y,t.x)-math.pi/2
        batch.cube((p.x,p.y,p.z+2.7),(1.15,.13,.9),ang)
        text_object(f'Turn {num}',str(num),p+Vector((-t.x*.08,-t.y*.08,2.7)),.65,ang)
        if num in [1,4,6,7,8,11]:
            for distance in [150,100,50]:
                s=apex-distance;p,t,n=B.station_point(s,barrier_offset(s,1)-.5);p.z=B.terrain(p.x,p.y)+1.4;ang=math.atan2(t.y,t.x)-math.pi/2
                B.box(f'T{num} braking board {distance}',p,(1.05,.12,1.1),B.MATS['White_paint'],'Signage',ang)
                text_object(f'T{num} {distance}m',str(distance),p+Vector((-t.x*.09,-t.y*.09,0)),.45,ang,'Rubber')
    batch.object(section['name']+' corner panels',[B.MATS['Green_paint']],'Signage')
    # Marshal posts follow FIA map stations, rather than equal spacing around the lap.
    posts=[(65,'0.1'),(300,'0.3'),(515,'0.5'),(622,'1'),(698,'2'),(1140,'3'),(1700,'3.4'),(1845,'4'),
           (1940,'5'),(2180,'5.2'),(2290,'6'),(2525,'7.1'),(2730,'7.2'),(3040,'7.5'),(3390,'7.7'),
           (3590,'8.1'),(3735,'9'),(3920,'10'),(4300,'10.3'),(4760,'11.1'),(5020,'11.3'),(5320,'11.5'),(5610,'12.1')]
    for s,label in posts:
        if not a<=s<b:continue
        side=1;p,t,n=B.station_point(s,side*(barrier_offset(s,side)+3));z=B.terrain(p.x,p.y);ang=math.atan2(t.y,t.x)
        B.box('Marshal M'+label,(p.x,p.y,z+1.15),(2.5,2,2.3),B.MATS['Concrete'],'Marshal_posts',ang,.04)
        B.box('M'+label+' glazed front',(p.x-n.x*1.01,p.y-n.y*1.01,z+1.7),(2.15,.06,.72),B.MATS['Glass'],'Marshal_posts',ang)
        B.box('M'+label+' canopy',(p.x,p.y,z+2.42),(3.1,2.5,.16),B.MATS['Roof'],'Marshal_posts',ang,.025)
        text_object('M'+label,label,(p.x-n.x*1.1,p.y-n.y*1.1,z+.72),.4,ang)
        equip=Batch();equip.rod((p.x+1.6,p.y,z),(p.x+1.6,p.y,z+.62),.13,sides=10)
        equip.object('M'+label+' extinguisher',[B.MATS['Red_paint']],'Marshal_posts')


def footprint_axes(f):
    ps=f['points'][:-1] if f['closed'] else f['points'];cx,cy=centroid(ps)
    a,b=max(zip(ps,ps[1:]+ps[:1]),key=lambda ab:math.dist(*ab));u=Vector((b[0]-a[0],b[1]-a[1])).normalized();v=Vector((-u.y,u.x))
    coords=[((p[0]-cx)*u.x+(p[1]-cy)*u.y,(p[0]-cx)*v.x+(p[1]-cy)*v.y) for p in ps]
    xmin,xmax=min(p[0] for p in coords),max(p[0] for p in coords);ymin,ymax=min(p[1] for p in coords),max(p[1] for p in coords)
    cx+=u.x*(xmin+xmax)/2+v.x*(ymin+ymax)/2;cy+=u.y*(xmin+xmax)/2+v.y*(ymin+ymax)/2
    return Vector((cx,cy)),u,v,xmax-xmin,ymax-ymin


def building(f):
    tags=f['tags'];name=tags.get('name',f'Building {f["osm_way"]}');c,u,v,length,depth=footprint_axes(f);ang=math.atan2(u.y,u.x)
    z=B.terrain(c.x,c.y);special=f['osm_way'] in [34404652,194458105]
    if tags.get('building')=='grandstand':
        nearest,idx,dist=B.TREE.find((c.x,c.y,0));toward=Vector((nearest.x-c.x,nearest.y-c.y))
        if toward.dot(v)<0:v=-v;u=-u;ang=math.atan2(u.y,u.x)
        rows=max(5,int(depth/.85));step=.38;batch=Batch();seats=Batch();steel=Batch()
        for row in range(rows):
            yy=depth/2-row*.85;h=.45+row*step;p=c+v*yy
            batch.cube((p.x,p.y,z+h/2),(length,.9,h),ang)
            for x in range(int(-length/2+.5),int(length/2),1):
                if (x+int(length/2))%18 in [0,1]:continue
                q=p+u*x;mi=0 if (x//12+row//3)%5 else 1
                seats.cube((q.x,q.y,z+h+.25),(.44,.4,.09),ang,mi)
                q=q-v*.21;seats.cube((q.x,q.y,z+h+.46),(.44,.075,.38),ang,mi)
        batch.object(name+' concrete terraces',[B.MATS['Concrete']],'Grandstands')
        seats.object(name+' individual seats',[B.MATS['Blue_seat'],B.MATS['White_paint']],'Grandstands')
        covered=f['osm_way'] in [34404645,193647795,193647796,194457667,231026020]
        if covered:
            roof_z=z+rows*step+3.0;roofmat='Terracotta' if f['osm_way']==34404645 else 'Roof'
            B.box(name+' canopy',(c.x,c.y,roof_z),(length+1.5,depth+2,.26),B.MATS[roofmat],'Grandstands',ang,.06)
            for x in range(int(-length/2),int(length/2)+1,9):
                q=c+u*x-v*(depth/2-.5);steel.rod((q.x,q.y,z),(q.x,q.y,roof_z),.1)
                front=c+u*x+v*depth/2;steel.rod((q.x,q.y,roof_z-.6),(front.x,front.y,roof_z-.2),.085)
        steel.object(name+' canopy supports',[B.MATS['Armco']],'Grandstands')
        return
    if tags.get('building')=='tower' and name=='Podio':
        # Monza's circular podium projects over the pit wall on an elevated bridge.
        batch=Batch();batch.rod((c.x,c.y,z+6.8),(c.x,c.y,z+7.2),4.6,0,40)
        batch.rod((c.x,c.y,z+11.7),(c.x,c.y,z+12),5.0,0,40)
        for j in range(6):
            x,y=c.x+4.2*math.cos(j*TAU/6),c.y+4.2*math.sin(j*TAU/6);batch.rod((x,y,z+7),(x,y,z+12),.10)
        batch.object('Monza circular podium',[B.MATS['Roof']],'Pit_buildings')
        B.box('Podium access bridge',(c.x+8,c.y,z+6.8),(16,3,.7),B.MATS['Concrete'],'Bridges',ang)
        return
    if special:height=8.5 if f['osm_way']==34404652 else 13
    else:height=float(tags.get('height',5)) if tags.get('height','').replace('.','').isdigit() else 5
    ps=f['points'];ps=ps[:-1] if f['closed'] else ps;vs=[(x,y,B.terrain(x,y)) for x,y in ps]+[(x,y,z+height) for x,y in ps];n=len(ps)
    fs=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]+[tuple(range(n,2*n))]
    ob=B.mesh(name+' surveyed footprint',vs,fs,B.MATS['Concrete'],'Pit_buildings');ob['osm_way']=f['osm_way'];ob['height_status']='estimated'
    B.box(name+' parapet roof',(c.x,c.y,z+height+.13),(length+.4,depth+.4,.26),B.MATS['Roof'],'Pit_buildings',ang,.035)
    near,idx,dist=B.TREE.find((c.x,c.y,0));front=Vector((near.x-c.x,near.y-c.y))
    if front.dot(v)<0:v=-v
    windows=Batch();frames=Batch()
    spacing=5.5 if special else 3.5
    bays=max(1,int(length/spacing))
    for bay in range(bays):
        along=-length/2+(bay+.5)*length/bays;p=c+u*along+v*(depth/2+.03)
        if special:
            windows.cube((p.x,p.y,z+1.8),(spacing-.4,.10,3.1),ang)
            frames.cube((p.x,p.y,z+3.45),(spacing-.1,.28,.18),ang)
            # Garage upper rolling-door slats catch light at the appropriate 12 cm pitch.
            for h in [.6,.9,1.2,1.5,1.8,2.1,2.4,2.7,3.0]:frames.cube((p.x,p.y,z+h),(spacing-.5,.13,.018),ang)
        windows.cube((p.x,p.y,z+height-2.0),(spacing-.7,.10,1.55),ang)
        frames.cube((p.x,p.y,z+height-2.0),(.10,.19,1.85),ang)
    windows.object(name+' glazing and garage openings',[B.MATS['Glass']],'Pit_buildings');frames.object(name+' facade frames',[B.MATS['Armco']],'Pit_buildings')
    if special:
        frames=Batch()
        for x in range(int(-length/2),int(length/2),9):
            p=c+u*x;left=p-v*depth/2;right=p+v*depth/2;apex=p+Vector((0,0))
            frames.rod((left.x,left.y,z+height+.25),(apex.x,apex.y,z+height+2),.085)
            frames.rod((right.x,right.y,z+height+.25),(apex.x,apex.y,z+height+2),.085)
        frames.object(name+' roof trusses',[B.MATS['White_paint']],'Pit_buildings')


def features(section):
    for f in B.SURVEY['features']:
        t=f['tags'];c=centroid(f['points']);_,idx,dist=B.TREE.find((*c,0));s=idx*B.STEP
        if not section['start_m']<=s<section['end_m']:continue
        if t.get('building') and dist<235:building(f)
        if t.get('natural')=='sand' and f['closed']:polygon(f'Mapped gravel {f["osm_way"]}',f['points'],B.MATS['Gravel'],'Runoff',.055)
        if t.get('amenity')=='parking' and f['closed'] and dist<180:polygon(f'Paddock hardstanding {f["osm_way"]}',f['points'],B.MATS['Asphalt'],'Service_roads',.045)
        if t.get('highway') in ['service','path','footway','track'] and dist<250:
            if t.get('tunnel')=='yes' or t.get('layer')=='-1':continue
            width=4.2 if t.get('highway')=='service' else 2.1
            B.ribbon(f'Service {f["osm_way"]}',f['points'],width,B.MATS['Asphalt'] if width>3 else B.MATS['Soil'],'Service_roads',.075)


def forest(section):
    woods=[f for f in B.SURVEY['features'] if f['tags'].get('landuse')=='forest' or f['tags'].get('natural')=='wood']
    exclusion=[f for f in B.SURVEY['features'] if f['closed'] and ('building' in f['tags'] or f['tags'].get('natural')=='sand' or f['tags'].get('amenity')=='parking')]
    road_points=[]
    for f in B.SURVEY['features']:
        if f['tags'].get('highway') in ['service','raceway','path','footway']:
            for a,b in zip(f['points'],f['points'][1:]):
                d=math.dist(a,b)
                for i in range(max(1,int(d/4))):
                    t=i/max(1,int(d/4));road_points.append((a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t,0))
    roads=KDTree(len(road_points))
    for i,p in enumerate(road_points):roads.insert(p,i)
    roads.balance()
    masks=[]
    for f in woods:
        ps=f['points'];masks.append((min(p[0] for p in ps),max(p[0] for p in ps),min(p[1] for p in ps),max(p[1] for p in ps),f))
    groups=[[] for _ in range(12)];undergrowth=Batch();total=0
    # Low-discrepancy candidates give irregular spacing; ecological masks decide occupancy.
    for i in range(1,56000):
        x=-300+1850*((i*.7548776662466927)%1);y=-950+2620*((i*.5698402909980532)%1)
        _,idx,d=B.TREE.find((x,y,0));s=idx*B.STEP
        if not section['start_m']<=s<section['end_m'] or d>420:continue
        side=1 if (Vector((x,y))-Vector(B.XY[idx])).dot(B.NORMALS[idx])>0 else -1
        if d<barrier_offset(s,side)+8:continue
        found=False
        for xmin,xmax,ymin,ymax,f in masks:
            if xmin<=x<=xmax and ymin<=y<=ymax and inside(x,y,f['points']) and not any(inside(x,y,h) for h in f.get('holes',[])):
                found=True;break
        if not found:continue
        # Broad canopy gaps, thickets, and age mosaics replace constant-density distribution.
        density=.56+.23*math.sin(x/68)*math.cos(y/97)+.15*math.sin(x/24+y/37)
        selector=(i*.41421356237)%1
        if selector>density:continue
        _,_,rd=roads.find((x,y,0))
        if rd<7:continue
        if any(inside(x,y,f['points']) for f in exclusion):continue
        kind=(i*7)%6+(0 if d<100 else 6);age=.65+.43*((i*.6180339887)%1)
        if math.sin(x/103+y/59)>.85:age*=.63
        sx=age*(.88+.22*((i*.381966)%1));sy=age*(.86+.27*((i*.236068)%1))
        groups[kind].append(((x,y,B.terrain(x,y)),(sx,sy,age),(i*2.399963)%TAU));total+=1
        if d<75 and i%3==0:
            undergrowth.ellipsoid((x+1.2,y-1.0,B.terrain(x,y)+.7),(1.6,1.2,.85),i%5,lon=8,lat=4,phase=i)
    for kind,placements in enumerate(groups):instances(section['name']+f' woodland {kind:02d}',bpy.data.objects[f'LIB_Tree_{kind:02d}'],placements,'Forest')
    undergrowth.object(section['name']+' woodland understory',[B.MATS[f'Leaf_{j}'] for j in range(5)],'Forest',True)
    section['tree_instances']=total


def landmarks(section):
    a,b=section['start_m'],section['end_m']
    if a==0:
        batch=Batch()
        for s in range(5510,5785,4):
            p,t,n=B.station_point(s,-8.2);p.z=B.terrain(p.x,p.y)+.7;batch.cube(p,(4.05,.55,1.4),math.atan2(t.y,t.x))
        for s in range(0,101,4):
            p,t,n=B.station_point(s,-8.2);p.z=B.terrain(p.x,p.y)+.7;batch.cube(p,(4.05,.55,1.4),math.atan2(t.y,t.x))
        batch.object('Pit wall | separate entry and exit',[B.MATS['Concrete']],'Safety_barriers')
        # Control line crosses the complete racing surface.
        B.strip('Start finish line',[0,1],-6,6,B.MATS['White_paint'],lift=.013)
        for slot in range(22):
            s=B.L-12-slot*8.0;off=(-1 if slot%2 else 1)*2.6;ids=[int(s/B.STEP),int(s/B.STEP)+1]
            B.strip(f'Grid {slot+1:02d}',ids,off-.9,off+.9,B.MATS['White_paint'],lift=.013)
        p,t,n=B.station_point(12);z=B.terrain(p.x,p.y);ang=math.atan2(t.y,t.x);gantry=Batch()
        for side in [-1,1]:
            q=p+Vector((n.x,n.y,0))*side*11;gantry.rod((q.x,q.y,z),(q.x,q.y,z+7),.16)
        left=p+Vector((n.x,n.y,0))*11;right=p-Vector((n.x,n.y,0))*11
        gantry.rod((left.x,left.y,z+7),(right.x,right.y,z+7),.17)
        gantry.object('Timing gantry',[B.MATS['Armco']],'Signage')
        B.box('MONZA start bridge',p+Vector((0,0,6.5)),(1.2,22,1.3),B.MATS['Green_paint'],'Signage',ang)
        text_object('Start gantry lettering','AUTODROMO NAZIONALE MONZA',p+Vector((-t.x*.65,-t.y*.65,6.5)),.66,ang-math.pi/2)
        lights=Batch()
        for k in range(5):
            q=p+Vector((n.x,n.y,0))*(k-.2)*.5;lights.cube((q.x,q.y,z+5.35),(.38,.28,.8),ang,0)
            for h in [5.15,5.50]:lights.ellipsoid((q.x-t.x*.17,q.y-t.y*.17,z+h),(.12,.12,.12),1,lon=10,lat=6)
        lights.object('Five start light pairs',[B.MATS['Rubber'],B.MATS['Red_paint']],'Signage')
    if a<3300<b:
        # The disused north banking crosses Serraglio. Clear deck underside exceeds 5 m.
        p,t,n=B.station_point(3298);z=B.terrain(p.x,p.y);ang=math.atan2(t.y,t.x)
        B.box('Serraglio historic banking underpass',p+Vector((0,0,6.3)),(15,44,1.1),B.MATS['Concrete'],'Bridges',ang,.07)
        for side in [-1,1]:
            q=p+Vector((n.x,n.y,0))*side*16;B.box('Banking bridge abutment',(q.x,q.y,z+2.8),(15,2.8,5.6),B.MATS['Concrete'],'Bridges',ang,.06)
    for s in [730,3960]:
        if not a<=s<b:continue
        p,t,n=B.station_point(s);z=B.terrain(p.x,p.y);ang=math.atan2(t.y,t.x)
        B.box(f'Pedestrian bridge {s}',(p.x,p.y,z+6.6),(3.2,32,.7),B.MATS['Concrete'],'Bridges',ang,.06)
        for sign in [-1,1]:
            q=p+Vector((n.x,n.y,0))*sign*14;B.box('Bridge support',(q.x,q.y,z+3),(2,1,6),B.MATS['Concrete'],'Bridges',ang)
        B.box('Bridge MONZA fascia',(p.x-t.x*1.7,p.y-t.y*1.7,z+7.3),(.15,31,1.3),B.MATS['Green_paint'],'Signage',ang)
        text_object('Bridge venue name','MONZA  |  TEMPIO DELLA VELOCITA',(p.x-t.x*1.8,p.y-t.y*1.8,z+7.3),.78,ang-math.pi/2)


def build(module,index):
    global B
    B=module;library()
    sc=bpy.context.scene;done=json.loads(sc.get('completed_sections','[]'))
    if index in done:raise RuntimeError('Section already built; rebuild foundation to replace it.')
    if index>0 and index-1 not in done:raise RuntimeError('Build sections in lap order.')
    section=dict(B.SURVEY['sections'][index]);print('Building section',index,section['name'],flush=True)
    surface(section);safety(section);features(section);signage(section);landmarks(section);forest(section)
    done.append(index);sc['completed_sections']=json.dumps(done)
    (B.OUT/'qa').mkdir(exist_ok=True)
    (B.OUT/f'qa/section_{index:02d}.json').write_text(json.dumps(section,indent=2)+'\n')
    B.save();B.render(index)
