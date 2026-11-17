"""Keep existing separators where clear; replace barriers crossing actual mapped pits."""
from __future__ import annotations

import csv
import itertools
import math
from dataclasses import replace
from pathlib import Path

from circuit_portals_dataclasses import Barrier, Portal
from pit_route_authoring import load_road
from pit_routes_dataclasses import PitProtectionProof, PitRoute
from pydantic import TypeAdapter
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree


def protect_route(route: PitRoute, support: Path, minimum_separator_gap_m: float = .65) -> tuple[PitRoute,PitProtectionProof]:
    _catalogue,road = load_road(support,route.slug)
    with (support/route.slug/'barriers.csv').open() as stream:
        old = TypeAdapter(list[Barrier]).validate_python(list(csv.DictReader(stream)))
    old_shapes = [LineString([(wall.ax,wall.ay),(wall.bx,wall.by)]) for wall in old]
    old_tree = STRtree(old_shapes)
    segments = [LineString([(a.x,a.y),(b.x,b.y)]) for a,b in zip(road,road[1:]+road[:1])]
    road_tree = STRtree(segments)
    line = LineString([(s.x,s.y) for s in route.sections])
    nearby = old_tree.query(line.buffer(max(s.half_width for s in route.sections)+1))
    intruding = sum(old_shapes[int(i)].distance(line)<min(s.half_width for s in route.sections)+old[int(i)].radius for i in nearby)
    wall_points: list[tuple[float,float,float,float,float] | None] = []
    retained = 0
    road_clearance = math.inf
    pit_clearance = math.inf
    for section in route.sections:
        point = Point(section.x,section.y)
        index = int(road_tree.nearest(point))
        reference = road[index]
        nearest = segments[index].interpolate(segments[index].project(point))
        dx,dy = section.x-nearest.x,section.y-nearest.y
        distance = math.hypot(dx,dy)
        main_edge = reference.half_width+.85
        available = distance-main_edge-section.half_width
        alignment = abs(reference.tx*(-section.normal_y)+reference.ty*section.normal_x)
        if available<minimum_separator_gap_m or alignment<.85 or section.distance<15 or section.distance>route.sections[-1].distance-15:
            wall_points.append(None)
            continue
        nx,ny = dx/distance,dy/distance
        low,high = main_edge+.15,distance-section.half_width-.15
        has_separator = False
        for raw_index in old_tree.query(point.buffer(distance+2)):
            old_index = int(raw_index)
            wall = old[old_index]
            centre = old_shapes[old_index].interpolate(old_shapes[old_index].project(point))
            along = (centre.x-section.x)*reference.tx+(centre.y-section.y)*reference.ty
            across = (centre.x-nearest.x)*nx+(centre.y-nearest.y)*ny
            if abs(along)<2.5 and low<=across<=high and wall.top>section.z+.1 and wall.bottom<section.z+1:
                has_separator = True
                break
        if has_separator:
            retained += 1
            wall_points.append(None)
            continue
        offset = (low+high)/2
        x,y = nearest.x+nx*offset,nearest.y+ny*offset
        bottom = section.z-.05
        wall_points.append((x,y,bottom,offset-main_edge,distance-offset))
    additions: list[Barrier] = []
    maximum_segment = 0.0
    for first,last in itertools.pairwise(wall_points):
        if first is None or last is None:
            continue
        length = math.hypot(last[0]-first[0],last[1]-first[1])
        if not .05<length<8:
            continue
        additions.append(Barrier(first[0],first[1],last[0],last[1],min(first[2],last[2]),
                                 max(first[2],last[2])+.95,.15))
        maximum_segment = max(maximum_segment,length)
        road_clearance = min(road_clearance,first[3]-.15,last[3]-.15)
        pit_clearance = min(pit_clearance,first[4]-.15,last[4]-.15)
    portals = []
    for portal in route.portals:
        # V1 corridor included an extra 0.35m; remove it so valid separator endcaps stay outside the drivable ribbon.
        a,b,c,d = portal.polygon_xy_m
        nx,ny = a[0]-d[0],a[1]-d[1]
        width = math.hypot(nx,ny)
        shift = .35/width
        quad = ((a[0]-nx*shift,a[1]-ny*shift),(b[0]-nx*shift,b[1]-ny*shift),
                (c[0]+nx*shift,c[1]+ny*shift),(d[0]+nx*shift,d[1]+ny*shift))
        portals.append(Portal(portal.id,quad,portal.bottom_m,portal.top_m+.5,
            'Actual mapped pit corridor. Existing barrier outside corridor remains; intrusive obsolete boundary is replaced by a separator outside protected race road. Wall position is an image-qualified reconstruction.'))
    proof = PitProtectionProof(len(nearby),intruding,retained,len(additions),
        0 if math.isinf(road_clearance) else road_clearance,
        0 if math.isinf(pit_clearance) else pit_clearance,maximum_segment,
        'Retained barrier geometry plus primary Google pit/road/garage relationship. New divider lies between unchanged Road+0.85m kerb and actual mapped pit paving; XY is estimated within this visible strip. Existing 0.95m concrete collision height and 0.15m radius retained. Native/source review required, especially joins to retained wall ends.')
    return replace(route,portals=portals,barriers=additions),proof
