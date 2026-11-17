"""Register actual mapped pit paths to unchanged runtime roads and export candidates."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import itertools
import json
import math
import struct
from dataclasses import asdict
from pathlib import Path
from typing import cast

from circuit_portals_dataclasses import Portal
from pit_routes import ROOT, candidate, encode_barriers, encode_route
from pit_routes_dataclasses import (
    PitCatalogue,
    PitFloorTriangle,
    PitRecipe,
    PitRoadSample,
    PitRoute,
    PitSection,
    Provenance,
)
from pydantic import TypeAdapter
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree


def load_road(support: Path, slug: str) -> tuple[PitCatalogue,list[PitRoadSample]]:
    folder = support / slug
    catalogue = TypeAdapter(PitCatalogue).validate_json((folder/'catalogue.json').read_bytes())
    with (folder/'road.csv').open() as stream:
        road = TypeAdapter(list[PitRoadSample]).validate_python(list(csv.DictReader(stream)))
    return catalogue,road


def source_path(recipe: PitRecipe) -> list[tuple[float,float]]:
    if recipe.native_xy_controls:
        if len(recipe.native_xy_controls)<2:
            raise ValueError('Native pit path needs at least two qualified source controls')
        return recipe.native_xy_controls
    source = candidate(recipe.slug)
    registration = TypeAdapter(Provenance).validate_json((ROOT/'Attribution/Sources'/recipe.slug/'provenance.json').read_bytes())
    origin,scale = registration.origin,registration.route.uniform_scale
    ways = {way.osm_id:way for way in source.ways}
    result: list[tuple[float,float]] = []
    for way_id in recipe.way_ids:
        way = ways[way_id]
        points = [(math.radians(lon-origin.longitude)*6378137*math.cos(math.radians(origin.latitude))*scale,
                   math.radians(lat-origin.latitude)*6378137*scale) for lat,lon in way.points_lat_lon]
        if result:
            if math.dist(result[-1],points[-1]) < math.dist(result[-1],points[0]):
                points.reverse()
            if math.dist(result[-1],points[0])>.25:
                raise ValueError(f'{recipe.slug}: disconnected mapped ways')
            points = points[1:]
        result.extend(points)
    if recipe.plan_adjustment_controls:
        controls = recipe.plan_adjustment_controls
        corrected: list[tuple[float,float]] = []
        raw_line = LineString(result)
        vertex_distances = [0.0]
        for first_point,last_point in itertools.pairwise(result):
            vertex_distances.append(vertex_distances[-1]+math.dist(first_point,last_point))
        control_distances = sorted({*vertex_distances,*[c[0] for c in controls if 0<=c[0]<=raw_line.length]})
        for distance in control_distances:
            source_point = raw_line.interpolate(distance)
            point = (source_point.x,source_point.y)
            j = max(0,min(len(controls)-2,bisect.bisect_right([c[0] for c in controls],distance)-1))
            first,last = controls[j],controls[j+1]
            t = max(0,min(1,(distance-first[0])/(last[0]-first[0])))
            corrected.append((point[0]+first[1]+(last[1]-first[1])*t,
                              point[1]+first[2]+(last[2]-first[2])*t))
        result = corrected
    return result


def road_at(road: list[PitRoadSample], length: float, station: float) -> PitRoadSample:
    station %= length
    index = min(len(road)-1,int(station/length*len(road)))
    if road[index].station > station and index > 0:
        index -= 1
    a,b = road[index],road[(index+1)%len(road)]
    span = (b.station-a.station)%length
    t = ((station-a.station)%length)/span
    tx,ty = a.tx+(b.tx-a.tx)*t,a.ty+(b.ty-a.ty)*t
    norm = math.hypot(tx,ty)
    return PitRoadSample(station,a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.z+(b.z-a.z)*t,tx/norm,ty/norm,
        a.half_width+(b.half_width-a.half_width)*t,a.bank+(b.bank-a.bank)*t,
        a.left_shoulder+(b.left_shoulder-a.left_shoulder)*t,a.right_shoulder+(b.right_shoulder-a.right_shoulder)*t)


def load_floor(path: Path, bounds: tuple[float,float,float,float]) -> tuple[list[PitFloorTriangle],STRtree]:
    triangles: list[PitFloorTriangle] = []
    if path.exists():
        with path.open('rb') as stream:
            header = stream.read(12)
            if header[:8] != b'FFSURF1\0':
                raise ValueError('Invalid retained floor surface')
            count, = struct.unpack_from('<I',header,8)
            for _ in range(count):
                values = cast(tuple[float,...],struct.unpack('<9f',stream.read(36)))
                xs,ys = values[0::3],values[1::3]
                if max(xs)<bounds[0] or min(xs)>bounds[2] or max(ys)<bounds[1] or min(ys)>bounds[3]:
                    continue
                triangles.append(PitFloorTriangle((values[0],values[1],values[2]),
                    (values[3],values[4],values[5]),(values[6],values[7],values[8])))
            if stream.read(1):
                raise ValueError('Trailing retained floor bytes')
    return triangles,STRtree([Polygon([t.a[:2],t.b[:2],t.c[:2]]) for t in triangles])


def floor_height(triangles: list[PitFloorTriangle], tree: STRtree, x: float, y: float) -> float | None:
    result: float | None = None
    for index in tree.query(Point(x,y)):
        triangle = triangles[int(index)]
        a,b,c = triangle.a,triangle.b,triangle.c
        area = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        first = ((b[0]-x)*(c[1]-y)-(b[1]-y)*(c[0]-x))/area
        second = ((c[0]-x)*(a[1]-y)-(c[1]-y)*(a[0]-x))/area
        third = 1-first-second
        if min(first,second,third)<-.00001:
            continue
        height = first*a[2]+second*b[2]+third*c[2]
        result = height if result is None else max(result,height)
    return result


def build_route(recipe: PitRecipe, support: Path) -> tuple[PitRoute,dict[str,float | int | str | list[float]]]:
    catalogue,road = load_road(support,recipe.slug)
    points = source_path(recipe)
    segments = [LineString([(a.x,a.y),(b.x,b.y)]) for a,b in zip(road,road[1:]+road[:1])]
    tree = STRtree(segments)
    ends = [Point(points[0]),Point(points[-1])]
    indices = [int(tree.nearest(point)) for point in ends]
    stations: list[float] = []
    errors: list[float] = []
    for point,index in zip(ends,indices):
        a,b = road[index],road[(index+1)%len(road)]
        t = segments[index].project(point,normalized=True)
        stations.append((a.station+t*((b.station-a.station)%catalogue.length_m))%catalogue.length_m)
        errors.append(point.distance(segments[index]))
    span = (stations[1]-stations[0])%catalogue.length_m
    if not 20<span<catalogue.length_m*.45 or max(errors)>recipe.maximum_endpoint_join_m:
        raise ValueError(f'{recipe.slug}: unsupported road joins {stations}, errors {errors}')
    # Retain mapped vertices. Only the endpoint registration residual is absorbed over 25m.
    line = LineString(points)
    count = max(2,math.ceil(line.length/2)+1)
    distances = [line.length*i/(count-1) for i in range(count)]
    endpoint_targets = [road_at(road,catalogue.length_m,value) for value in stations]
    projected = [line.interpolate(value) for value in distances]
    xy: list[tuple[float,float]] = []
    for distance,point in zip(distances,projected):
        w0 = max(0,1-distance/25)**2
        w1 = max(0,1-(line.length-distance)/25)**2
        xy.append((point.x+w0*(endpoint_targets[0].x-points[0][0])+w1*(endpoint_targets[1].x-points[-1][0]),
                   point.y+w0*(endpoint_targets[0].y-points[0][1])+w1*(endpoint_targets[1].y-points[-1][1])))
    triangles,floor_tree = load_floor(ROOT/'Content/Generated'/catalogue.content_dir/'drive_surface.bin',
        (min(x for x,y in xy)-10,min(y for x,y in xy)-10,max(x for x,y in xy)+10,max(y for x,y in xy)+10))
    road_indices = [i for i,row in enumerate(road) if (row.station-stations[0])%catalogue.length_m<=span]
    adjacent_tree = STRtree([segments[i] for i in road_indices])
    sections: list[PitSection] = []
    sampled_floor_count = 0
    maximum_source_floor_displacement = 0.0
    actual_distance = 0.0
    for i,(distance,point) in enumerate(zip(distances,xy)):
        before,after = xy[max(0,i-1)],xy[min(len(xy)-1,i+1)]
        dx,dy = after[0]-before[0],after[1]-before[1]
        norm = math.hypot(dx,dy)
        station = stations[0]+span*distance/line.length
        adjacent_index = road_indices[int(adjacent_tree.nearest(Point(*point)))]
        adjacent_a,adjacent_b = road[adjacent_index],road[(adjacent_index+1)%len(road)]
        adjacent_t = segments[adjacent_index].project(Point(*point),normalized=True)
        reference = road_at(road,catalogue.length_m,adjacent_a.station+adjacent_t*((adjacent_b.station-adjacent_a.station)%catalogue.length_m))
        expected = road_at(road,catalogue.length_m,station)
        branch_gap = abs(reference.station-expected.station)
        branch_gap = min(branch_gap,catalogue.length_m-branch_gap)
        branch_chord = math.hypot(reference.x-expected.x,reference.y-expected.y)
        if branch_gap>20 and branch_gap>2*branch_chord:
            along = (point[0]-expected.x)*expected.tx+(point[1]-expected.y)*expected.ty
            reference = road_at(road,catalogue.length_m,expected.station+along)
        lateral = (point[0]-reference.x)*reference.ty-(point[1]-reference.y)*reference.tx
        height = reference.z+reference.bank*lateral
        retained_height = floor_height(triangles,floor_tree,*point)
        slope = reference.bank*((dy/norm)*reference.ty+(-dx/norm)*(-reference.tx))
        if retained_height is not None and not recipe.reconstruct_pit_floor_from_road:
            sampled_floor_count += 1
            maximum_source_floor_displacement = max(maximum_source_floor_displacement,abs(retained_height-height))
            height = retained_height
            left = floor_height(triangles,floor_tree,point[0]+dy/norm,point[1]-dx/norm)
            right = floor_height(triangles,floor_tree,point[0]-dy/norm,point[1]+dx/norm)
            if left is not None and right is not None:
                slope = (left-right)/2
        if recipe.reconstruct_pit_floor_from_road:
            edge_lane = max(-reference.half_width,min(reference.half_width,lateral))
            height = reference.z+reference.bank*edge_lane
            slope = endpoint_targets[0].bank+(endpoint_targets[1].bank-endpoint_targets[0].bank)*distance/line.length
        if i in (0,len(xy)-1):
            height = endpoint_targets[0 if i==0 else 1].z
            slope = endpoint_targets[0 if i==0 else 1].bank*((dy/norm)*reference.ty+(-dx/norm)*(-reference.tx))
        if recipe.layer_height_controls:
            controls = recipe.layer_height_controls
            j = max(0,min(len(controls)-2,bisect.bisect_right([p[0] for p in controls],distance)-1))
            low_control,high_control = controls[j],controls[j+1]
            t = max(0,min(1,(distance-low_control[0])/(high_control[0]-low_control[0])))
            height = low_control[1]+(high_control[1]-low_control[1])*t
        if i:
            actual_distance += math.dist(xy[i-1],point)
        sections.append(PitSection(*point,height,recipe.half_width_m,station,actual_distance,dy/norm,-dx/norm,slope))
    entry = recipe.limit_entry_distance_m if recipe.limit_entry_distance_m is not None else min(60,line.length*.12)
    exit_distance = recipe.limit_exit_distance_m if recipe.limit_exit_distance_m is not None else sections[-1].distance-min(60,line.length*.12)
    portals: list[Portal] = []
    # One finite corridor quad per original mapped straight; this cuts walls only where the actual pit path runs.
    for i,(first,last) in enumerate(itertools.pairwise(points)):
        dx,dy = last[0]-first[0],last[1]-first[1]
        norm = math.hypot(dx,dy)
        nx,ny = dy/norm,-dx/norm
        width = recipe.half_width_m+.35
        along = .5
        quad = ((first[0]-dx/norm*along+nx*width,first[1]-dy/norm*along+ny*width),
                (last[0]+dx/norm*along+nx*width,last[1]+dy/norm*along+ny*width),
                (last[0]+dx/norm*along-nx*width,last[1]+dy/norm*along-ny*width),
                (first[0]-dx/norm*along-nx*width,first[1]-dy/norm*along-ny*width))
        near = [section.z for section in sections if LineString([first,last]).distance(Point(section.x,section.y))<3]
        portals.append(Portal(f'{recipe.slug}-pit-{i:02d}',quad,min(near)-.35,max(near)+2.8,
            'Mapped pit-path corridor; height-qualified wall opening. Main road and overhead deck retained.'))
    route = PitRoute(recipe.slug,recipe.source_urls,recipe.source_note,sections,entry,exit_distance,
                     recipe.speed_limit_kph,portals,[])
    maximum_grade = max(abs(b.z-a.z)/math.dist((a.x,a.y),(b.x,b.y)) for a,b in itertools.pairwise(sections))
    report: dict[str,float | int | str | list[float]] = {
        'sections':len(sections),'route_length_m':actual_distance,'main_road_station_start_m':stations[0],
        'main_road_station_end_unwrapped_m':stations[0]+span,'source_endpoint_join_errors_m':errors,
        'maximum_grade':maximum_grade,'portals':len(portals),
        'source_status':'Mapped actual path. Width/speed/gate/elevation reconstruction and native collision/garage clearance require review.',
        'floor_rule':'Retained actual drive_surface paving where present; constrained nearest adjacent main-road height/crossfall otherwise. Endpoints exactly unchanged road. Reconstructed floor, not surveyed pit elevations.',
        'retained_floor_samples':sampled_floor_count,'retained_floor_triangles':len(triangles),
        'maximum_retained_floor_vs_adjacent_road_displacement_m':maximum_source_floor_displacement,
        'bounds_xy_m':[min(s.x-s.half_width for s in sections),min(s.y-s.half_width for s in sections),
                       max(s.x+s.half_width for s in sections),max(s.y+s.half_width for s in sections)]}
    return route,report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe',type=Path)
    parser.add_argument('--support',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    recipe = TypeAdapter(PitRecipe).validate_json(args.recipe.read_bytes())
    route,report = build_route(recipe,args.support)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'route.json').write_text(json.dumps(asdict(route),indent=2)+'\n')
    (args.output/'pit_lane.bin').write_bytes(encode_route(route))
    (args.output/'pit_barriers.bin').write_bytes(encode_barriers(route.portals,route.barriers))
    report['recipe_sha256'] = hashlib.sha256(args.recipe.read_bytes()).hexdigest()
    (args.output/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
