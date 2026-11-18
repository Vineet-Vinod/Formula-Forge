"""Extract retained mapped pit ways and encode qualified route/portal overlays."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import struct
from dataclasses import asdict
from pathlib import Path

from circuit_portals_dataclasses import Barrier, Portal
from pit_routes_dataclasses import OsmData, PitCandidate, PitRoute, PitWay
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
SLUGS = ('silverstone','monza','interlagos','lasvegas','bahrain','jeddah','australia','japan','china',
         'canada','monaco','austria','spa','zandvoort','baku','malaysia','singapore','cota','turkey',
         'portimao','buddh','hockenheim')


def candidate(slug: str) -> PitCandidate:
    path = ROOT / 'Attribution/Sources' / slug / 'circuit.osm.json.gz'
    raw = path.read_bytes()
    data = TypeAdapter(OsmData).validate_json(gzip.decompress(raw))
    by_id = {element.id:element for element in data.elements if element.type == 'way'}
    chosen: dict[int,PitWay] = {}
    for element in data.elements:
        for member in element.members:
            if member.role.lower() not in ('pit','pit_lane','pitlane') or member.type != 'way':
                continue
            way = by_id.get(member.ref)
            points = member.geometry or (way.geometry if way else [])
            chosen[member.ref] = PitWay(member.ref,[(point.lat,point.lon) for point in points],
                                        way.tags if way else {},member.role)
    if not chosen:
        for way in by_id.values():
            names = ' '.join(value.lower() for key,value in way.tags.items() if key in ('name','name:en','raceway'))
            if ('pit' in names or 'boxen' in names) and way.tags.get('sport','motor') != 'karting':
                chosen[way.id] = PitWay(way.id,[(point.lat,point.lon) for point in way.geometry],way.tags,'')
    if not chosen:
        raise ValueError(f'{slug}: no retained pit-lane way')
    return PitCandidate(slug,str(path.relative_to(ROOT)),hashlib.sha256(raw).hexdigest(),list(chosen.values()),
        'Actual retained OSM pit-way candidates, not generic frontage offsets. Resolve branch selection, source-to-current-road joins, widths/limits and Google/FIA registration before export.')


def encode_route(route: PitRoute) -> bytes:
    if not 2<=len(route.sections)<=10000 or not math.isfinite(route.speed_limit_kph) or not 20<=route.speed_limit_kph<=100:
        raise ValueError('Invalid pit route metadata')
    if not 0 <= route.limit_entry_m < route.limit_exit_m <= route.sections[-1].distance:
        raise ValueError('Pit limit distances must lie inside the route')
    version3 = any((section.positive_extent or section.half_width) != section.half_width or
                   (section.negative_extent or section.half_width) != section.half_width for section in route.sections)
    signature = b'FFPIT3\0\0' if version3 else b'FFPIT2\0\0'
    output = bytearray(struct.pack('<8sI3f',signature,len(route.sections),route.limit_entry_m,
                                   route.limit_exit_m,route.speed_limit_kph))
    previous = None
    for section in route.sections:
        positive = section.positive_extent or section.half_width
        negative = section.negative_extent or section.half_width
        row = (section.x,-section.y,section.z,section.half_width,section.track_station,section.distance,
               section.normal_x,-section.normal_y,section.cross_slope,*((positive,negative) if version3 else ()))
        if not all(math.isfinite(value) and abs(value)<=20000 for value in row):
            raise ValueError('Nonfinite or out-of-range pit section')
        if not 1.5<=section.half_width<=12 or abs(math.hypot(section.normal_x,section.normal_y)-1)>.01 or abs(section.cross_slope)>.08:
            raise ValueError('Invalid pit width/normal/crossfall')
        if not section.half_width <= positive <= 12 or not section.half_width <= negative <= 12:
            raise ValueError('Invalid asymmetric pit support extent')
        if previous is None:
            if abs(section.distance)>.01:
                raise ValueError('Pit route must begin at distance zero')
        else:
            spacing = math.hypot(section.x-previous.x,section.y-previous.y)
            if not .01<=spacing<=10 or not 0<section.distance-previous.distance<=10 or section.track_station<previous.track_station or abs(section.z-previous.z)/spacing>.20:
                raise ValueError('Pit route has a gap, reversing progress or excessive grade')
        output.extend(struct.pack('<11f' if version3 else '<9f',*row))
        previous = section
    return bytes(output)


def encode_barriers(portals: list[Portal], barriers: list[Barrier]) -> bytes:
    if not 0<len(portals)<=128 or len(barriers)>10000:
        raise ValueError('Portal overlay size is invalid')
    output = bytearray(struct.pack('<8sII',b'FFBAR2\0\0',len(barriers),len(portals)))
    for barrier in barriers:
        barrier_values = (barrier.ax,barrier.ay,barrier.bx,barrier.by,barrier.bottom,barrier.top,barrier.radius)
        if not all(math.isfinite(value) and abs(value)*17<=200000 for value in barrier_values):
            raise ValueError('Nonfinite or out-of-range barrier')
        if barrier.bottom>=barrier.top or not 0<barrier.radius<=1 or math.hypot(barrier.bx-barrier.ax,barrier.by-barrier.ay)<.001:
            raise ValueError('Invalid barrier')
        output.extend(struct.pack('<7f',barrier.ax*17,-barrier.ay*17,barrier.bx*17,-barrier.by*17,
                                  barrier.bottom*17,barrier.top*17,barrier.radius*17))
    for portal in portals:
        portal_values = (*[value for point in portal.polygon_xy_m for value in point],portal.bottom_m,portal.top_m)
        if len(portal.polygon_xy_m)!=4 or not all(math.isfinite(value) and abs(value)*17<=200000 for value in portal_values):
            raise ValueError('Nonfinite or out-of-range portal')
        points = [(x*17,-y*17) for x,y in portal.polygon_xy_m]
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))
        if area<0:
            points.reverse()
        if portal.bottom_m>=portal.top_m:
            raise ValueError('Portal height range is invalid')
        for i in range(4):
            a,b,c = points[i],points[(i+1)%4],points[(i+2)%4]
            if (b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])<=1e-6:
                raise ValueError('Portal must be a strictly convex quad')
        output.extend(struct.pack('<10f',*(value for point in points for value in point),portal.bottom_m*17,portal.top_m*17))
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract-candidates',type=Path)
    parser.add_argument('--route',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    if args.extract_candidates:
        args.extract_candidates.mkdir(parents=True,exist_ok=True)
        inventory = {}
        for slug in SLUGS:
            try:
                source = candidate(slug)
                (args.extract_candidates/f'{slug}.json').write_text(json.dumps(asdict(source),indent=2)+'\n')
                inventory[slug] = {'state':'mapped candidates, registration pending','way_ids':[way.osm_id for way in source.ways]}
            except (FileNotFoundError,ValueError) as error:
                inventory[slug] = {'state':'existing Silverstone support' if slug=='silverstone' else 'SOURCE GAP','reason':str(error)}
        (args.extract_candidates/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    elif args.route and args.output:
        route = TypeAdapter(PitRoute).validate_json(args.route.read_bytes())
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'pit_lane.bin').write_bytes(encode_route(route))
        (args.output/'pit_barriers.bin').write_bytes(encode_barriers(route.portals,route.barriers))
    else:
        parser.error('Specify --extract-candidates or --route plus --output')


if __name__ == '__main__':
    main()
