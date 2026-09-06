"""Checks for grounded legacy approach, closed-pit kerbs and readable distance boards."""
import json

import bpy
from mathutils import Vector
import build_monza as B
from braking_markers import marker_distances, plan_markers


def verify():
    assert marker_distances(90)==()
    assert marker_distances(140)==(50,)
    assert marker_distances(230)==(100,50)
    assert marker_distances(400)==(150,100,50)
    assert marker_distances(1000)==(200,150,100,50)
    assert marker_distances(1000,False)==()
    B.load()
    layout=json.loads((B.OUT/'layout.json').read_text())
    plan=plan_markers(layout['braking_zones'],B.L)
    assert len(plan)==20
    assert next(p for p in plan if p['turn']==1 and p['distance_m']==200)['station_m']==409
    ob=bpy.data.objects['Historic oval 1313097098']
    max_hover=max(v.co.z-B.terrain(v.co.x,v.co.y) for v in ob.data.vertices)
    assert max_hover<.04,max_hover
    assert 'Alboreto kerb 5280' not in bpy.data.objects
    assert 'Alboreto green apron 5280' not in bpy.data.objects
    for name in ['Alboreto kerb 4990','Alboreto green apron 4990']:
        for face in bpy.data.objects[name].data.polygons:
            assert B.TREE.find((*face.center[:2],0))[1]*B.STEP<5230,name
    for item in plan:
        name=f"BRAKE | T{item['turn']} | {item['distance_m']}m"
        panel=bpy.data.objects[name];digits=bpy.data.objects[name+' digits']
        p,t,_=B.station_point(item['station_m'])
        center=sum((panel.matrix_world@v.co for v in panel.data.vertices),Vector())/len(panel.data.vertices)
        assert abs((center-p).xy.dot(t))<.01,name
        assert digits.data.body==str(item['distance_m']),name
        normal=digits.rotation_euler.to_matrix()@Vector((0,0,1))
        assert normal.dot(Vector((-t.x,-t.y,0)))>.999,name
        assert (digits.location-center).dot(normal)>.07,name
        assert center.z-B.terrain(center.x,center.y)>2,name
    result=dict(marker_count=20,policy='approach-length-v1',marker_stations_and_facing_valid=True,
                historic_straight_max_clearance_m=max_hover,pit_approach_kerbs_removed=True)
    (B.OUT/'qa/map_detail_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':verify()
