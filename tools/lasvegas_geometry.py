"""Original Las Vegas scenery in the registered source frame (metres, east/north/up)."""
from __future__ import annotations

import csv
import gzip
import hashlib
import itertools
import json
import math
import struct
from pathlib import Path

from lasvegas_art import HOTEL_NAMES
from lasvegas_dataclasses import (
    CurbRun,
    EscapeRegion,
    LandmarkProfile,
    LeaningTower,
    MeshTile,
    Point,
    RoadStation,
    RoofShard,
    RouteSector,
    StreetDisplay,
    TerrainGrid,
    TowerRoof,
)

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / 'build/lasvegas'
SOURCE = ROOT / 'Attribution/Sources/lasvegas'
DATA = ROOT / 'Content/Generated/LasVegas/Data'
LENGTH = 6201.0


def add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def mul(a: Point, value: float) -> Point:
    return a[0] * value, a[1] * value, a[2] * value


def cross(a: Point, b: Point) -> Point:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def norm(a: Point) -> Point:
    length = math.sqrt(sum(value * value for value in a))
    return mul(a, 1 / max(length, 1e-9))


def world(p: Point) -> Point:
    return -p[1] * 100, -p[0] * 100, p[2] * 100


class Scenery:
    def __init__(self) -> None:
        self.road = [RoadStation(**{key: float(value) for key, value in row.items()})
                     for row in csv.DictReader((SCRATCH / 'road.csv').open())]
        if len(self.road) != 12288:
            raise ValueError('Run make check to export the canonical Las Vegas samples')
        self.detail_stride = len(self.road) // 1536
        trackside = json.loads((SOURCE/'trackside-layout.json').read_text())
        self.curb_extensions = [CurbRun(**run) for run in trackside['curb_extensions']]
        self.curb_profile = [(float(lane),float(z)) for lane,z in trackside['curb_profile_m']]
        environment = json.loads((SOURCE/'route-environment.json').read_text())
        self.sectors = [RouteSector(**value) for value in environment['sectors']]
        self.wynn_display_profile = StreetDisplay(**environment['wynn_display'])
        self.vegetation: list[dict[str,str|float|int]] = []
        self.city_rings: list[list[tuple[float,float]]] = []
        self.lights: list[Point] = []
        self.boards: list[dict[str, float | int]] = []
        self.tiles: dict[str, MeshTile] = {}
        self.landmarks: list[dict[str, str | float | int]] = []
        self.cells: dict[tuple[int, int], list[int]] = {}
        for index, sample in enumerate(self.road):
            self.cells.setdefault((int(sample.x // 40), int(sample.y // 40)), []).append(index)
        payload = (DATA / 'terrain.bin').read_bytes()
        x, y, step, columns, rows = struct.unpack_from('<ddfII', payload, 8)
        if payload[:8] != b'FFTRN1\0\0' or len(payload) != 36 + columns * rows * 4:
            raise ValueError('Invalid Las Vegas terrain grid')
        self.terrain = TerrainGrid(x, y, step, columns, rows, struct.unpack_from(f'<{columns * rows}f', payload, 36))
        provenance = json.loads((SOURCE / 'provenance.json').read_text())
        self.latitude = provenance['origin']['latitude']
        self.longitude = provenance['origin']['longitude']
        architecture = json.loads((SOURCE / 'landmark-architecture.json').read_text())
        self.profiles = {int(key): LandmarkProfile(**value) for key, value in architecture['profiles'].items()}
        self.leaning_towers = {int(key): LeaningTower(**value) for key, value in architecture['leaning_towers'].items()}
        self.crystal_roofs = [RoofShard(**value) for value in architecture['crystal_roofs']]
        self.scale = provenance['route']['uniform_scale']
        boundary_record = SOURCE / 'boundaries.json'
        regions = json.loads(boundary_record.read_text())['regions'] if boundary_record.exists() else []
        self.escapes = [EscapeRegion(**region) for region in regions]
        recipe = json.loads((SOURCE / 'layout-corrections.json').read_text())
        self.turns = {}
        for turn in recipe['turns']:
            x,y = (value * self.scale for value in turn['near_source_xy_m'])
            self.turns[turn['number']] = min(self.road, key=lambda p: (p.x-x)**2+(p.y-y)**2).station


    @staticmethod
    def in_region(x: float, y: float, region: EscapeRegion) -> bool:
        return Scenery.in_polygon(x,y,region.ring)

    @staticmethod
    def in_polygon(x: float,y: float,ring: list[tuple[float,float]]) -> bool:
        inside = False
        for a,b in zip(ring,ring[1:]+ring[:1]):
            if (a[1] > y) != (b[1] > y) and x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                inside = not inside
        return inside

    @staticmethod
    def polygons_overlap(a: list[tuple[float,float]], b: list[tuple[float,float]]) -> bool:
        if (any(Scenery.in_polygon(x,y,b) for x,y in a)
                or any(Scenery.in_polygon(x,y,a) for x,y in b)):
            return True
        for p,q in zip(a,a[1:]+a[:1]):
            dx,dy = q[0]-p[0],q[1]-p[1]
            for r,s in zip(b,b[1:]+b[:1]):
                ex,ey = s[0]-r[0],s[1]-r[1]
                denominator = dx*ey-dy*ex
                if abs(denominator)<1e-10:
                    continue
                rx,ry = r[0]-p[0],r[1]-p[1]
                t,u = (rx*ey-ry*ex)/denominator,(rx*dy-ry*dx)/denominator
                if 0 <= t <= 1 and 0 <= u <= 1:
                    return True
        return False

    def blue_paint(self, x: float, y: float) -> bool:
        return any(region.paint == 'BlueRunoff' and self.in_region(x,y,region) for region in self.escapes)

    def outer_lane(self, sample: RoadStation, side: int) -> float:
        lane = sample.half_width + .95
        dx,dy = sample.ty*side,-sample.tx*side
        for region in self.escapes:
            hits = []
            for a,b in zip(region.ring,region.ring[1:]+region.ring[:1]):
                ex,ey = b[0]-a[0],b[1]-a[1]
                divisor = dx*ey-dy*ex
                if abs(divisor) < .00001:
                    continue
                ax,ay = a[0]-sample.x,a[1]-sample.y
                t = (ax*ey-ay*ex)/divisor
                u = (ax*dy-ay*dx)/divisor
                if 0 <= u <= 1:
                    hits.append(t)
            if hits and min(hits) <= lane+.01 and max(hits) >= 0:
                lane = max(lane,max(hits))
        return lane

    def projected(self, lat: float, lon: float) -> tuple[float, float]:
        x = math.radians(lon - self.longitude) * 6378137 * math.cos(math.radians(self.latitude)) * self.scale
        y = math.radians(lat - self.latitude) * 6378137 * self.scale
        return x, y

    def nearest(self, x: float, y: float) -> tuple[RoadStation, float]:
        cell = int(x // 40), int(y // 40)
        indices: list[int] = []
        for radius in range(1, 8):
            indices = [index for cx in range(cell[0] - radius, cell[0] + radius + 1)
                       for cy in range(cell[1] - radius, cell[1] + radius + 1)
                       for index in self.cells.get((cx, cy), [])]
            if indices:
                break
        if not indices:
            indices = list(range(len(self.road)))
        index = min(indices, key=lambda index: (self.road[index].x - x) ** 2 + (self.road[index].y - y) ** 2)
        best = self.road[index]
        distance = float('inf')
        for a_index in (index - 1, index):
            a, b = self.road[a_index], self.road[(a_index + 1) % len(self.road)]
            dx, dy = b.x - a.x, b.y - a.y
            t = max(0.0, min(1.0, ((x - a.x) * dx + (y - a.y) * dy) / max(.0001, dx * dx + dy * dy)))
            px, py = a.x + t * dx, a.y + t * dy
            candidate = math.hypot(x - px, y - py)
            if candidate < distance:
                distance = candidate
                best = RoadStation(a.station + t * LENGTH / len(self.road), px, py, a.z + t * (b.z - a.z),
                                   a.tx, a.ty, a.half_width + t * (b.half_width - a.half_width), a.bank,
                                   a.left_shoulder + t * (b.left_shoulder - a.left_shoulder),
                                   a.right_shoulder + t * (b.right_shoulder - a.right_shoulder))
        return best, distance

    def ground(self, x: float, y: float) -> float:
        grid = self.terrain
        col = max(0.0, min(grid.columns - 1.001, (x - grid.x) / grid.step))
        row = max(0.0, min(grid.rows - 1.001, (y - grid.y) / grid.step))
        c, r = int(col), int(row)
        tx, ty = col - c, row - r
        index = r * grid.columns + c
        z = (grid.heights[index] * (1 - tx) * (1 - ty) + grid.heights[index + 1] * tx * (1 - ty)
             + grid.heights[index + grid.columns] * (1 - tx) * ty + grid.heights[index + grid.columns + 1] * tx * ty)
        sample, distance = self.nearest(x, y)
        lane = (x - sample.x) * sample.ty - (y - sample.y) * sample.tx
        shoulder = sample.left_shoulder if lane > 0 else sample.right_shoulder
        blend = max(0.0, min(1.0, (distance - sample.half_width - shoulder - 1) / 14))
        blend = blend * blend * (3 - 2 * blend)
        return sample.z * (1 - blend) + z * blend - .055

    def tile(self, kind: str, point: Point) -> MeshTile:
        category = 'Tile_Street' if kind.startswith('Tile_') else ('Building_Crowd' if kind.startswith('Building_Crowd') else 'Building_City')
        step = 240 if category == 'Tile_Street' else 360
        name = f'{category}_{math.floor(point[0] / step):02d}_{math.floor(point[1] / step):02d}'.replace('-', 'm')
        return self.tiles.setdefault(name, MeshTile())

    def triangle(self, kind: str, material: str, a: Point, b: Point, c: Point,
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                 normals: tuple[Point, ...] | None = None) -> None:
        normal = cross(sub(b, a), sub(c, a))
        if sum(value * value for value in normal) < 1e-12:
            return
        normal = norm(normal)
        tile = self.tile(kind, mul(add(add(a, b), c), 1 / 3))
        if material not in tile.materials:
            tile.materials.append(material)
        tile.triangles.extend(struct.pack('<I', tile.materials.index(material)))
        for point, texcoord, vertex_normal in zip((a, b, c), uv, normals or (normal, normal, normal)):
            n = -vertex_normal[1], -vertex_normal[0], vertex_normal[2]
            p = world(point)
            tile.triangles.extend(struct.pack('<8f', *p, *n, *texcoord))
            for axis in range(3):
                tile.minimum[axis] = min(tile.minimum[axis], p[axis])
                tile.maximum[axis] = max(tile.maximum[axis], p[axis])

    def quad(self, kind: str, material: str, a: Point, b: Point, c: Point, d: Point,
             u: float = 1, v: float = 1) -> None:
        self.triangle(kind, material, a, b, c, ((0, 0), (u, 0), (u, v)))
        self.triangle(kind, material, a, c, d, ((0, 0), (u, v), (0, v)))

    def beam(self, kind: str, material: str, a: Point, b: Point, width: float, depth: float | None = None) -> None:
        tangent = norm(sub(b, a))
        side = mul(norm(cross(tangent, (0, 0, 1) if abs(tangent[2]) < .95 else (0, 1, 0))), width / 2)
        up = mul(norm(cross(side, tangent)), (depth if depth is not None else width) / 2)
        corners = [add(a, add(side, up)), add(a, sub(up, side)), sub(a, add(side, up)), add(a, sub(side, up)),
                   add(b, add(side, up)), add(b, sub(up, side)), sub(b, add(side, up)), add(b, sub(side, up))]
        for indices in [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]:
            self.quad(kind, material, corners[indices[0]], corners[indices[1]], corners[indices[2]], corners[indices[3]])

    def box(self, kind: str, material: str, center: Point, length: float, width: float, height: float,
            heading: float = 0) -> None:
        direction = math.cos(heading), math.sin(heading), 0.0
        self.beam(kind, material, sub(center, mul(direction, length / 2)),
                  add(center, mul(direction, length / 2)), width, height)

    def banner(self, a: Point, b: Point, height: float, material: str, kind: str = 'Tile_Detail',
               u0: float = 0, repeat: float = 1) -> None:
        u = math.dist(a, b) / .5 if material == 'Fence' else repeat
        v = height / .5 if material == 'Fence' else 1
        if 'Facade' in material:
            u, v = math.dist(a, b) / 16, height / 14.4
        top_a, top_b = add(a, (0, 0, height)), add(b, (0, 0, height))
        self.triangle(kind, material, top_a, top_b, b, ((u0, 0), (u0 + u, 0), (u0 + u, v)))
        self.triangle(kind, material, top_a, b, a, ((u0, 0), (u0 + u, v), (u0, v)))
        if material == 'Fence':
            return
        self.triangle(kind, material, top_b, top_a, a, ((u0 + u, 0), (u0, 0), (u0, v)))
        self.triangle(kind, material, top_b, a, b, ((u0 + u, 0), (u0, v), (u0 + u, v)))

    def spectators(self, a: Point, b: Point, row: int, kind: str) -> None:
        span = sub(b, a)
        count = max(1, round(math.dist(a, b) / .62))
        direction = norm(span)
        for person in range(count):
            center = add(a, mul(span, (person + .5) / count))
            left = sub(center, mul(direction, .40))
            right = add(center, mul(direction, .40))
            top_left, top_right = add(left, (0, 0, 1.35)), add(right, (0, 0, 1.35))
            column = (person + row) % 3
            u0, u1 = column / 3, (column + 1) / 3
            self.triangle(kind, 'Crowd', top_left, top_right, right, ((u0, .5), (u1, .5), (u1, 1)))
            self.triangle(kind, 'Crowd', top_left, right, left, ((u0, .5), (u1, 1), (u0, 1)))
            self.triangle(kind, 'Crowd', top_right, top_left, left, ((u1, .5), (u0, .5), (u0, 1)))
            self.triangle(kind, 'Crowd', top_right, left, right, ((u1, .5), (u0, 1), (u1, 1)))

    def escape_end(self, x: float, y: float) -> bool:
        for region in self.escapes:
            if region.paint != 'Runoff':
                continue
            a,b=region.ring[2],region.ring[3]
            dx,dy=b[0]-a[0],b[1]-a[1]
            t=max(0.,min(1.,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
            if math.hypot(x-a[0]-t*dx,y-a[1]-t*dy) < .3:
                return True
        return False

    def tyre_barriers(self) -> None:
        for region in self.escapes:
            if region.paint != 'Runoff':
                continue
            a,b=region.ring[2],region.ring[3]
            count=max(1,math.ceil(math.dist(a,b)/.63))
            for stack in range(count):
                t=(stack+.5)/count
                x=a[0]+(b[0]-a[0])*t+region.direction[0]*.17
                y=a[1]+(b[1]-a[1])*t+region.direction[1]*.17
                z=region.origin[2]
                for level in range(3):
                    for segment in range(16):
                        p0,p1=segment*math.tau/16,(segment+1)*math.tau/16
                        lower0=(x+.32*math.cos(p0),y+.32*math.sin(p0),z+level*.29)
                        lower1=(x+.32*math.cos(p1),y+.32*math.sin(p1),z+level*.29)
                        upper0=add(lower0,(0,0,.27))
                        upper1=add(lower1,(0,0,.27))
                        self.quad('Tile_Tyres','TyreRubber',lower0,lower1,upper1,upper0)
                        inner0=(x+.17*math.cos(p0),y+.17*math.sin(p0),upper0[2])
                        inner1=(x+.17*math.cos(p1),y+.17*math.sin(p1),upper1[2])
                        self.quad('Tile_Tyres','TyreSidewall',upper0,upper1,inner1,inner0)

    def curb(self, sample: RoadStation, nxt: RoadStation, side: int) -> None:
        span = (nxt.station-sample.station)%LENGTH
        boundary = math.floor(sample.station)+1
        cuts = [sample.station]
        if boundary < sample.station+span:
            cuts.append(float(boundary))
        cuts.append(sample.station+span)
        for begin,end in itertools.pairwise(cuts):
            t0,t1 = (begin-sample.station)/span,(end-sample.station)/span
            paint = 'Red' if int((begin+end)/2)%2 else 'White'
            for (inner,low),(outer,high) in itertools.pairwise(self.curb_profile):
                ai,bi = sample.point(side*(sample.half_width+inner),low),nxt.point(side*(nxt.half_width+inner),low)
                ao,bo = sample.point(side*(sample.half_width+outer),high),nxt.point(side*(nxt.half_width+outer),high)
                a,b = add(ai,mul(sub(bi,ai),t0)),add(ai,mul(sub(bi,ai),t1))
                c,d = add(ao,mul(sub(bo,ao),t1)),add(ao,mul(sub(bo,ao),t0))
                if cross(sub(b,a),sub(c,a))[2] < 0:
                    a,b,c,d = d,c,b,a
                self.quad('Tile_Road',paint,a,b,c,d)

    def track(self) -> None:
        raw = (DATA / 'drive_surface.bin').read_bytes()
        if raw[:8] != b'FFSURF1\0':
            raise ValueError('Invalid driving surface')
        triangles = list(struct.iter_unpack('<9f', raw[12:]))
        for triangle_index, values in enumerate(triangles):
            a, b, c = values[:3], values[3:6], values[6:9]
            if cross(sub(b, a), sub(c, a))[2] < 0:
                b, c = c, b
            material = 'Road' if triangle_index < len(self.road)*2 else 'Runoff'
            if material != 'Road' and self.blue_paint((a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3):
                material = 'BlueRunoff'
            self.triangle('Tile_Road', material, a, b, c,
                          tuple((p[0] / 4, p[1] / 4) for p in (a, b, c)))
        barriers = list(csv.DictReader((SCRATCH / 'barriers.csv').open()))
        profile = (SOURCE / 'barrier_heights.bin').read_bytes()
        if profile[:8] != b'FFWALL1\0' or len(profile) != 12 + len(barriers)*8 or struct.unpack_from('<I',profile,8)[0] != len(barriers):
            raise ValueError('Barrier endpoint heights do not match the exported walls')
        wall_normals = [norm((float(w['by'])-float(w['ay']),float(w['ax'])-float(w['bx']),0)) for w in barriers]
        ends = {(round(float(w['bx']),3),round(float(w['by']),3)):i for i,w in enumerate(barriers)}
        miters: dict[tuple[float,float],Point] = {}
        for i,w in enumerate(barriers):
            key = (round(float(w['ax']),3),round(float(w['ay']),3))
            previous_normal = wall_normals[ends[key]]
            average = norm(add(previous_normal,wall_normals[i]))
            projection = sum(a*b for a,b in zip(average,wall_normals[i]))
            miters[key] = mul(average,min(4.,1/max(.001,projection)))
        samples = [self.nearest((float(w['ax'])+float(w['bx']))/2,(float(w['ay'])+float(w['by']))/2)[0] for w in barriers]
        panels = [self.wall_material(sample,float(w['ax']),float(w['ay'])) for w,sample in zip(barriers,samples,strict=True)]
        lengths = [math.hypot(float(w['bx'])-float(w['ax']),float(w['by'])-float(w['ay'])) for w in barriers]
        starts = {(round(float(w['ax']),3),round(float(w['ay']),3)):i for i,w in enumerate(barriers)}
        following = [starts[(round(float(w['bx']),3),round(float(w['by']),3))] for w in barriers]
        run_starts = [i for i,w in enumerate(barriers) if panels[i] != panels[ends[(round(float(w['ax']),3),round(float(w['ay']),3))]]]
        coordinates = [(0.,0.) for _ in barriers]
        visited: set[int] = set()
        for run_start in itertools.chain(run_starts,range(len(barriers))):
            if run_start in visited:
                continue
            run = []
            index = run_start
            while index not in visited and panels[index] == panels[run_start]:
                visited.add(index)
                run.append(index)
                index = following[index]
            length = sum(lengths[index] for index in run)
            scale = max(1,round(length/8))/length
            phase = 0.
            for index in run:
                repeat = lengths[index]*scale
                coordinates[index] = phase,repeat
                phase += repeat
        for index,(barrier,(za,zb)) in enumerate(zip(barriers,struct.iter_unpack('<2f',profile[12:]),strict=True)):
            ax, ay, bx, by, _bottom, _top, radius = (float(value) for value in barrier.values())
            a, b = (ax, ay, za), (bx, by, zb)
            start_key,end_key = (round(ax,3),round(ay,3)),(round(bx,3),round(by,3))
            miter_a,miter_b = miters[start_key],miters[end_key]
            wall_height = .95
            end_barrier = self.escape_end((ax+bx)/2,(ay+by)/2)
            if not end_barrier:
                side_a,side_b = mul(miter_a,radius),mul(miter_b,radius)
                corners = [sub(a,side_a),add(a,side_a),add(b,side_b),sub(b,side_b)]
                upper = [add(point,(0,0,wall_height)) for point in corners]
                self.quad('Tile_Protection','Concrete',corners[3],corners[2],corners[1],corners[0])
                self.quad('Tile_Protection','Concrete',upper[0],upper[1],upper[2],upper[3])
                for i in range(4):
                    j = (i+1)%4
                    self.quad('Tile_Protection','Concrete',corners[i],corners[j],upper[j],upper[i])
            sample,panel = samples[index],panels[index]
            inward_a,inward_b = mul(miter_a,radius+.012),mul(miter_b,radius+.012)
            panel_a, panel_b = add(a,inward_a),add(b,inward_b)
            phase,repeat = coordinates[index]
            if not end_barrier:
                self.banner(add(panel_a, (0, 0, .02)), add(panel_b, (0, 0, .02)), .88, panel, 'Tile_Protection', phase, repeat)
            self.banner(add(a, (0, 0, wall_height)), add(b, (0, 0, wall_height)), 2.55, 'Fence', 'Tile_Protection')
            if int(sample.station / 8) != int((sample.station - LENGTH / len(self.road)) / 8):
                self.beam('Tile_Protection', 'Steel', add(a, (0, 0, wall_height)), add(a, (0, 0, 3.5)), .065)
                self.beam('Tile_Protection', 'Steel', add(a, (0, 0, 3.5)), add(add(a, (0, 0, 4.05)), mul(inward_a, 2.8)), .065)
            upper_a, upper_b = add(add(a, (0, 0, 4.05)), mul(inward_a, 2.8)), add(add(b, (0, 0, 4.05)), mul(inward_b, 2.8))
            self.quad('Tile_Protection', 'Fence', add(a, (0, 0, 3.5)), add(b, (0, 0, 3.5)), upper_b, upper_a, math.dist(a, b) / .5, 1.4)
            self.beam('Tile_Protection', 'Steel', add(a, (0, 0, 3.5)), add(b, (0, 0, 3.5)), .028)
        for index, sample in enumerate(self.road):
            nxt = self.road[(index + 1) % len(self.road)]
            for sign in (-1, 1):
                lane = sign * sample.half_width
                lane_next = sign * nxt.half_width
                a, b = sample.point(lane, .012), nxt.point(lane_next, .012)
                c, d = nxt.point(lane_next - sign * .15, .012), sample.point(lane - sign * .15, .012)
                if sign < 0:
                    a, b, c, d = d, c, b, a
                self.quad('Tile_Road', 'White', a, b, c, d)
            for number, outside in ((14, 1), (1, 1), (5, -1), (7, 1), (9, 1), (12, 1)):
                apex = self.turns[number]
                if not apex - 135 < sample.station < apex + 25:
                    continue
                def rubber_lane(station: RoadStation, apex: float = apex, outside: int = outside) -> float:
                    t = max(0.0, min(1.0, (station.station - apex + 80) / 105))
                    return outside * station.half_width * (.45 - .8 * t * t * (3 - 2 * t))
                for wheel in (-.8, .8):
                    lane_a, lane_b = rubber_lane(sample) + wheel, rubber_lane(nxt) + wheel
                    self.quad('Tile_Road', 'Rubber', sample.point(lane_a - .16, .019), sample.point(lane_a + .16, .019),
                              nxt.point(lane_b + .16, .019), nxt.point(lane_b - .16, .019), 1, (nxt.station - sample.station) / 2)
            before = self.road[(index - 4 * self.detail_stride) % len(self.road)]
            after = self.road[(index + 4 * self.detail_stride) % len(self.road)]
            bend = before.tx * after.ty - before.ty * after.tx
            curb_sides = {-1 if bend > 0 else 1} if abs(bend) > .13 else set()
            curb_sides.update(run.side for run in self.curb_extensions if run.start_m <= sample.station < run.end_m)
            for curb_side in sorted(curb_sides):
                self.curb(sample,nxt,curb_side)
            if 1580 < sample.station < 1950 and index % (4 * self.detail_stride) == 0:
                for side in (-1, 1):
                    lane_a, lane_b = side * 2.5, side * 4.5
                    self.quad('Tile_Road', 'White', sample.point(lane_a, .016), sample.point(lane_b, .016),
                              add(sample.point(lane_b, .016), (sample.tx * .12, sample.ty * .12, 0)),
                              add(sample.point(lane_a, .016), (sample.tx * .12, sample.ty * .12, 0)))
                    self.quad('Tile_Road', 'White', sample.point(lane_b, .016), nxt.point(lane_b, .016),
                              nxt.point(lane_b - side * .10, .016), sample.point(lane_b - side * .10, .016))
            if index % (6 * self.detail_stride) == 0:
                for side in (-1, 1):
                    self.floodlight(sample, side)
        self.tyre_barriers()
        start = min(self.road, key=lambda sample: abs(sample.station - 1815))
        for side in range(20):
            lane_a = -start.half_width + side * start.half_width / 10
            lane_b = lane_a + start.half_width / 10
            for row in range(2):
                material = 'White' if (side + row) % 2 else 'Black'
                p = add(start.point(lane_a, .025), (start.tx * row * .35, start.ty * row * .35, 0))
                q = add(start.point(lane_b, .025), (start.tx * row * .35, start.ty * row * .35, 0))
                self.quad('Tile_Road', material, p, q, add(q, (start.tx * .35, start.ty * .35, 0)),
                          add(p, (start.tx * .35, start.ty * .35, 0)))
        self.gantry(1830)
        for gantry_station in (670, 2050, 3350, 4150, 4990, 6080):
            self.gantry(gantry_station)
        for number, outside in ((14, 1), (1, 1), (5, -1), (7, 1), (9, 1), (12, 1)):
            apex = self.turns[number]
            for distance in (150, 100, 50):
                station = apex - distance
                sample = min(self.road, key=lambda sample: abs(sample.station - station))
                lane = outside * (self.outer_lane(sample,outside) - .9)
                a, b = sample.point(lane - .65, 1.25), sample.point(lane + .65, 1.25)
                offset = (-sample.tx * .12, -sample.ty * .12, 0.)
                self.banner(add(a, offset), add(b, offset), 1.25, str(distance))
                self.beam('Tile_Detail', 'Steel', sample.point(outside * (self.outer_lane(sample,outside) + .2), 1.9),
                          sample.point(lane, 1.9), .05)
                self.boards.append({'apex': apex, 'distance': distance, 'station': sample.station, 'side': outside})

    def floodlight(self, sample: RoadStation, sign: int) -> None:
        base = sample.point(sign * (self.outer_lane(sample,sign) + .6))
        high = add(base, (0, 0, 11.5))
        arm = sample.point(sign * (self.outer_lane(sample,sign) - 1.2), 11.2)
        heading = math.atan2(sample.ty, sample.tx)
        self.beam('Tile_Detail', 'Steel', base, high, .14)
        self.beam('Tile_Detail', 'Steel', high, arm, .11)
        for offset in (-.8, .8):
            center = add(arm, (sample.tx * offset, sample.ty * offset, 0))
            self.box('Tile_Detail', 'Black', center, 1.2, .65, .16, heading)
            self.box('Tile_Detail', 'Lamp', add(center, (0, 0, -.10)), 1.06, .52, .035, heading)
        for axis in ((1., 0., 0.), (0., 1., 0.)):
            center = add(arm, (0, 0, -.1))
            a, b = sub(center, mul(axis, 1.4)), add(center, mul(axis, 1.4))
            self.quad('Tile_Detail', 'LightHalo', add(a, (0, 0, -1.4)), add(b, (0, 0, -1.4)),
                      add(b, (0, 0, 1.4)), add(a, (0, 0, 1.4)))
        self.lights.append(arm)

    def gantry(self, station: float) -> None:
        sample = min(self.road, key=lambda sample: abs(sample.station - station))
        left = sample.point(self.outer_lane(sample,1) + .6)
        right = sample.point(-(self.outer_lane(sample,-1) + .6))
        for point in (left, right):
            self.beam('Tile_Detail', 'Steel', point, add(point, (0, 0, 7)), .3)
        if station != 1830:
            for height in (6.2, 6.9):
                self.beam('Tile_Detail', 'Steel', add(left, (0, 0, height)), add(right, (0, 0, height)), .08)
            span = sub(right, left)
            for panel in range(12):
                a = add(left, mul(span, panel / 12))
                b = add(left, mul(span, (panel + 1) / 12))
                self.beam('Tile_Detail', 'Steel', add(a, (0, 0, 6.2)), add(b, (0, 0, 6.9)), .055)
                self.beam('Tile_Detail', 'Steel', add(a, (0, 0, 6.9)), add(b, (0, 0, 6.2)), .055)
                if panel % 3 == 0:
                    self.box('Tile_Detail', 'Lamp', add(a, (0, 0, 6.1)), .8, .5, .06)
            label = 'WestHarmon' if station < 1500 else ('SphereZone' if 3300 < station < 4200 else 'RaceSign')
            self.banner(add(right, (0, 0, 5.4)), add(left, (0, 0, 5.4)), .85, label)
            return
        self.beam('Tile_Detail', 'Steel', add(left, (0, 0, 6.6)), add(right, (0, 0, 6.6)), .65, .65)
        if station == 1830:
            for lane in (-1.8, -.9, 0, .9, 1.8):
                a = sample.point(lane, 5.2)
                self.box('Tile_Detail', 'Black', a, .24, .5, .65, math.atan2(sample.ty, sample.tx))
                self.box('Tile_Detail', 'Red', add(a, (-sample.tx * .14, -sample.ty * .14, 0)), .02, .24, .24,
                         math.atan2(sample.ty, sample.tx))

    def terrain_mesh(self) -> None:
        payload = (SOURCE / 'terrain_mesh.bin').read_bytes()
        for values in struct.iter_unpack('<9f', payload):
            a, b, c = values[:3], values[3:6], values[6:9]
            if cross(sub(b,a),sub(c,a))[2] < 0:
                b,c = c,b
            self.triangle('Tile_Ground', 'CityGround', a,b,c,
                          tuple((p[0]/5,p[1]/5) for p in (a,b,c)))

    @staticmethod
    def curved_footprint(ring: list[tuple[float,float]]) -> list[tuple[float,float]]:
        result = []
        count = len(ring)
        for i,a in enumerate(ring):
            previous,b,after = ring[i-1],ring[(i+1)%count],ring[(i+2)%count]
            span = math.dist(a,b)
            if span < .05:
                continue
            edge = norm((b[0]-a[0],b[1]-a[1],0))
            incoming = norm((a[0]-previous[0],a[1]-previous[1],0))
            outgoing = norm((after[0]-b[0],after[1]-b[1],0))
            m0 = mul(norm(add(incoming,edge)),span) if sum(x*y for x,y in zip(incoming,edge)) > .92 else mul(edge,span)
            m1 = mul(norm(add(edge,outgoing)),span) if sum(x*y for x,y in zip(edge,outgoing)) > .92 else mul(edge,span)
            steps = max(1,math.ceil(span/2))
            for j in range(steps):
                t=j/steps
                value = tuple((2*t**3-3*t*t+1)*a[k] + (t**3-2*t*t+t)*m0[k]
                              + (-2*t**3+3*t*t)*b[k] + (t**3-t*t)*m1[k] for k in (0,1))
                result.append((value[0],value[1]))
        return result

    def leaning_tower(self, ring: list[tuple[float, float]], tower: LeaningTower, osm_id: int) -> None:
        z = min(self.ground(*p) for p in ring)
        slope = math.tan(math.radians(tower.north_lean_deg))
        if sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1])) < 0:
            ring.reverse()
        for a,b in zip(ring,ring[1:]+ring[:1]):
            span = math.dist(a,b)
            if span < .1:
                continue
            def point(t: float, level: float, a: tuple[float,float] = a,
                      b: tuple[float,float] = b) -> Point:
                return a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t+slope*level,z+level
            self.quad('Building_Veer','VeerFacade',point(0,24),point(1,24),
                      point(1,tower.height_m),point(0,tower.height_m),span/16,(tower.height_m-24)/28.8)
            self.quad('Building_Veer','Glass',point(0,0),point(1,0),point(1,24),point(0,24),span/8,3)
            for level in range(25,int(tower.height_m),2):
                self.beam('Building_Veer','Steel',point(0,level),point(1,level),.45,.09)
            bays = max(1,round(span/3))
            for bay in range(bays+1):
                self.beam('Building_Veer','Steel',point(bay/bays,0),point(bay/bays,tower.height_m),.06)
            self.beam('Building_Veer','Steel',point(0,tower.height_m),point(1,tower.height_m),.6,.6)
        top = [(x,y+slope*tower.height_m,z+tower.height_m) for x,y in ring]
        center = tuple(sum(p[axis] for p in top)/len(top) for axis in range(3))
        for top_a,top_b in zip(top,top[1:]+top[:1]):
            self.triangle('Building_Veer','Roof',(center[0],center[1],center[2]),top_a,top_b)
        self.landmarks.append({'name':tower.name,'osm_id':osm_id,'height_m':tower.height_m,
                               'north_lean_deg':tower.north_lean_deg,
                               'x':sum(p[0] for p in ring)/len(ring),'y':sum(p[1] for p in ring)/len(ring)})

    def building(self, ring: list[tuple[float, float]], height: float, material: str, name: str, osm_id: int) -> None:
        profile = self.profiles.get(osm_id)
        if profile is None:
            style = 'office' if height < 25 else 'modern'
            profile = LandmarkProfile('',style,height,'RetailFacade' if height < 25 else material,1.)
        height, material = profile.height_m - profile.crown_m, profile.facade
        name = name or profile.name
        if profile.style == 'arcade':
            material = 'PodiumStone'
        if profile.name in ('Wynn','Encore','Bellagio') and height > 60:
            ring = self.curved_footprint(ring)
        center = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        roof = None
        if profile.name in ('Wynn','Encore') and height > 60:
            xx = sum((x-center[0])**2 for x,y in ring)
            yy = sum((y-center[1])**2 for x,y in ring)
            xy = sum((x-center[0])*(y-center[1]) for x,y in ring)
            angle = .5*math.atan2(2*xy,xx-yy)
            ax,ay = math.cos(angle),math.sin(angle)
            values = [x*ax+y*ay for x,y in ring]
            roof = TowerRoof(ax,ay,(max(values)+min(values))/2,(max(values)-min(values))/2,
                             12. if profile.name == 'Wynn' else 8.)
        z = min(self.ground(*p) for p in ring)
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
        if area < 0:
            ring.reverse()
        face_normals = [norm((b[1] - a[1], a[0] - b[0], 0)) for a, b in zip(ring, ring[1:] + ring[:1])]
        def corner_normal(index: int, face: Point) -> Point:
            previous, nxt = face_normals[index - 1], face_normals[index % len(ring)]
            return norm(add(previous, nxt)) if sum(a * b for a, b in zip(previous, nxt)) > .9 else face
        facade_u = (osm_id%17)/17
        for index, a in enumerate(ring):
            b = ring[(index + 1) % len(ring)]
            width = math.dist(a, b)
            low_a, low_b = (*a, z), (*b, z)
            height_a = height + (roof.offset(*a) if roof else 0.)
            height_b = height + (roof.offset(*b) if roof else 0.)
            top_a, top_b = (*a, z + height_a), (*b, z + height_b)
            na, nb = corner_normal(index, face_normals[index]), corner_normal(index + 1, face_normals[index])
            u = width / 32
            self.triangle('Building_City', material, low_a, low_b, top_b, ((facade_u, 0), (facade_u + u, 0), (facade_u + u, -height_b/28.8)), (na, nb, nb))
            self.triangle('Building_City', material, low_a, top_b, top_a, ((facade_u, 0), (facade_u + u, -height_b/28.8), (facade_u, -height_a/28.8)), (na, nb, na))
            facade_u += u
            self.beam('Building_City', 'IlluminatedCream' if material == 'BronzeFacade' else 'Cream', top_a, top_b, .4, .7)
        self.hotel_architecture(ring, z, height, profile, roof)
        if (height < 35 and profile.name in ('Linq','Harrahs','CasinoRoyale')) or osm_id in (116761428,134795273):
            self.casino_frontage(ring,z,height,profile,osm_id)
        # Concave roofs use ear clipping instead of a fan through the exterior.
        indices = list(range(len(ring)))
        while len(indices) >= 3:
            found = False
            for offset in range(len(indices)):
                ia, ib, ic = indices[offset - 1], indices[offset], indices[(offset + 1) % len(indices)]
                a, b, c = ring[ia], ring[ib], ring[ic]
                if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) <= 1e-8:
                    continue
                def inside(p: tuple[float, float], a: tuple[float, float] = a, b: tuple[float, float] = b, c: tuple[float, float] = c) -> bool:
                    return all((v[0] - u[0]) * (p[1] - u[1]) - (v[1] - u[1]) * (p[0] - u[0]) >= 0
                               for u, v in ((a, b), (b, c), (c, a)))
                if any(inside(ring[index]) for index in indices if index not in (ia, ib, ic)):
                    continue
                self.triangle('Building_City', 'Roof', (*a, z + height + (roof.offset(*a) if roof else 0.)),
                              (*b, z + height + (roof.offset(*b) if roof else 0.)),
                              (*c, z + height + (roof.offset(*c) if roof else 0.)))
                indices.remove(ib)
                found = True
                break
            if not found:
                break
        if name:
            self.landmarks.append({'name': name, 'osm_id': osm_id, 'x': center[0], 'y': center[1], 'height_m': height})

    def hotel_architecture(self, ring: list[tuple[float, float]], z: float, height: float,
                           profile: LandmarkProfile, roof: TowerRoof | None) -> None:
        kind = 'Building_Hotel'
        cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        edges = list(zip(ring, ring[1:] + ring[:1]))
        if profile.style in ('retail','motel','office','exhibition','display','wynn_plaza'):
            self.urban_architecture(ring,z,height,profile)
            return
        if profile.style == 'venetian_palace':
            self.venetian_palace(ring,z,height)
            return
        if profile.name in ('GrandChateau','Signature'):
            self.residential_tower(ring,z,height,profile)
            return
        if profile.style == 'forum':
            self.hotel_architecture(ring,z,height,LandmarkProfile('Caesars','arcade',height+2,'Terracotta',2),None)
            self.forum_entrance(ring,z,height)
            return
        if profile.style == 'parking':
            for a,b in edges:
                span = math.dist(a,b)
                if span < .1:
                    continue
                direction = norm((b[0]-a[0],b[1]-a[1],0))
                parking_normal = (direction[1],-direction[0],0.)
                for parking_level in range(1,int(height-2),3):
                    start = add((*a,z+parking_level),mul(parking_normal,.04))
                    finish = add((*b,z+parking_level),mul(parking_normal,.04))
                    self.banner(start,finish,2.2,'Black',kind)
                    self.beam(kind,'Cream',add(start,(0,0,-.15)),add(finish,(0,0,-.15)),.3,.3)
                bays = max(1,round(span/7))
                for bay in range(bays+1):
                    base = add((*a,z),add(mul(direction,span*bay/bays),mul(parking_normal,.15)))
                    self.beam(kind,'Cream',base,add(base,(0,0,height)),.5)
            return
        if profile.style in ('retail','crystalline'):
            for a,b in edges:
                span = math.dist(a,b)
                if span < .1:
                    continue
                direction = norm((b[0]-a[0],b[1]-a[1],0))
                retail_normal = (direction[1],-direction[0],0.)
                bays = max(1,round(span/5))
                for bay in range(bays):
                    half = span/bays*.45
                    for floor in range(max(1,int((height-1)/4.5))):
                        shop_center = add((a[0],a[1],z+1+floor*4.5),
                                          add(mul(direction,span*(bay+.5)/bays),mul(retail_normal,.15)))
                        glazing = ('ShopWarm','ShopCool','ShopFashion')[(bay+floor)%3] if floor == 0 or (bay+floor)%4 == 0 else 'Glass'
                        self.banner(sub(shop_center,mul(direction,half)),add(shop_center,mul(direction,half)),
                                    min(3.5,height-1-floor*4.5),glazing,kind)
                    foot = add((a[0],a[1],z),mul(direction,span*bay/bays))
                    self.beam(kind,'Steel',foot,add(foot,(0,0,height)),.12)
                for floor in range(1,int(height/4.5)+1):
                    self.beam(kind,'PodiumStone',add((*a,z+floor*4.5),mul(retail_normal,.25)),
                              add((*b,z+floor*4.5),mul(retail_normal,.25)),.65,.4)
            if profile.style == 'crystalline':
                for shard in self.crystal_roofs:
                    s0,s1,s2,s3 = [(x*self.scale,y*self.scale,z+height) for x,y in shard.corners]
                    s4,s5 = [(x*self.scale,y*self.scale,z+level) for x,y,level in shard.ridge]
                    for shard_face,material in [((s0,s1,s4),'WarmGlass'),((s1,s2,s4),'Steel'),((s2,s5,s4),'Steel'),
                                                ((s2,s3,s5),'Steel'),((s3,s0,s5),'Glass'),((s0,s4,s5),'Steel')]:
                        roof_a,roof_b,roof_c = shard_face
                        if cross(sub(roof_b,roof_a),sub(roof_c,roof_a))[2] < 0:
                            roof_b,roof_c = roof_c,roof_b
                        self.triangle(kind,material,roof_a,roof_b,roof_c)
                    for roof_start,roof_end in ((s0,s4),(s1,s4),(s2,s4),(s2,s5),(s3,s5),(s0,s5),(s4,s5)):
                        self.beam(kind,'Cream',roof_start,roof_end,.12)
            return
        classical = profile.style in ('classical', 'arcade', 'mansard', 'dome')
        trim = 'Cream' if classical else ('PinkNeon' if profile.name == 'Flamingo' else 'Steel')
        # Separate floors, recessed glazing and structural bays break up the silhouette.
        for a, b in edges:
            span = math.dist(a, b)
            if span < .1:
                continue
            normal = (b[1] - a[1]) / span, (a[0] - b[0]) / span
            def point(t: float, level: float, offset: float = .22,
                      a: tuple[float, float] = a, b: tuple[float, float] = b,
                      normal: tuple[float, float] = normal) -> Point:
                return (a[0] + (b[0] - a[0]) * t + normal[0] * offset,
                        a[1] + (b[1] - a[1]) * t + normal[1] * offset,
                        z + min(level,height + roof.offset(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)) if roof else z + level)
            if profile.style == 'arcade' and self.nearest((a[0]+b[0])/2,(a[1]+b[1])/2)[1] < 190:
                bays = max(1,round(span/5.5))
                for bay in range(bays):
                    t = (bay+.5)/bays
                    middle = point(t,1.0,.10)
                    width = min(3.7,span/bays*.72)
                    direction = norm((b[0]-a[0],b[1]-a[1],0))
                    self.banner(sub(middle,mul(direction,width/2)),add(middle,mul(direction,width/2)),5.7,
                                'ShopWarm' if bay%4 == 0 else 'ShopCool' if bay%4 == 1 else 'Glass',kind)
                    foot = point(bay/bays,0,.4)
                    self.beam(kind,'Cream',foot,add(foot,(0,0,height-1)),.6,.6)
                    if height > 17:
                        arch_base = point(t,11.2,.12)
                        radius = width/2
                        self.banner(sub(arch_base,mul(direction,radius)),add(arch_base,mul(direction,radius)),3.2,'Glass',kind)
                        center = add(arch_base,(0,0,3.2))
                        previous = sub(center,mul(direction,radius))
                        for segment in range(1,13):
                            angle = math.pi*(1-segment/12)
                            end = add(center,add(mul(direction,math.cos(angle)*radius),(0,0,math.sin(angle)*radius)))
                            self.triangle(kind,'Glass',center,previous,end)
                            self.beam(kind,'Cream',previous,end,.16)
                            previous = end
            if classical:
                for level in (3.5, 7.5, height - 4, height):
                    self.beam(kind, 'IlluminatedCream', point(0, level), point(1, level), .7, .45)
                if height > 40:
                    bays = max(1, round(span / 8))
                    for bay in range(bays + 1):
                        t = bay / bays
                        self.beam(kind, 'Cream', point(t, 8), point(t, height - 4), .55, .55)
                        self.box(kind, 'Cream', point(t, height - 4), 1.1, 1.1, 1)
                for level in range(11, int(height - 4), 11):
                    self.beam(kind, 'Cream', point(0, level), point(1, level), .20, .28)
            elif roof is not None:
                for level in range(12,int(height-15),12):
                    self.beam(kind,'BronzeTrim',point(0,level),point(1,level),.13,.24)
                self.beam(kind,'BronzeTrim',point(0,height),point(1,height),.22,.45)
            elif profile.style == 'balconies':
                for level in range(4, int(height), 4):
                    self.beam(kind, 'Steel', point(0, level, .9), point(1, level, .9), 1.6, .25)
                    self.beam(kind, 'Glass', point(0, level + .65, 1.5), point(1, level + .65, 1.5), .08, .9)
            else:
                for level in range(4, int(height), 4):
                    self.beam(kind, 'Steel', point(0, level), point(1, level), .08, .08)
                self.beam(kind, 'IlluminatedCream' if profile.style == 'glass' else trim,
                          point(0, height), point(1, height), .3, .6)
        top = z + height
        if profile.style == 'dome':
            levels = [(math.cos(step / 12 * math.pi / 2), top + math.sin(step / 12 * math.pi / 2) * profile.crown_m)
                      for step in range(13)]
        elif profile.style == 'mansard':
            levels = [(1., top), (.91, top + profile.crown_m * .8), (.90, top + profile.crown_m)]
        elif classical:
            levels = [(1.015, top), (1.015, top + 1.2), (.96, top + 2),
                      (.96, top + profile.crown_m * .6), (.90, top + profile.crown_m)]
        else:
            levels = [(1., top), (.98, top + profile.crown_m)]
        for (scale_a, za), (scale_b, zb) in itertools.pairwise(levels):
            for a, b in edges:
                pa, pb = (cx + (a[0] - cx) * scale_a, cy + (a[1] - cy) * scale_a, za), (cx + (b[0] - cx) * scale_a, cy + (b[1] - cy) * scale_a, za)
                qa, qb = (cx + (a[0] - cx) * scale_b, cy + (a[1] - cy) * scale_b, zb), (cx + (b[0] - cx) * scale_b, cy + (b[1] - cy) * scale_b, zb)
                if roof is not None:
                    pa,pb = add(pa,(0,0,roof.offset(*a))),add(pb,(0,0,roof.offset(*b)))
                    qa,qb = add(qa,(0,0,roof.offset(*a))),add(qb,(0,0,roof.offset(*b)))
                self.quad(kind, 'Copper' if profile.style == 'dome' else 'Roof' if profile.style == 'mansard' else trim, pa, pb, qb, qa)
                self.beam(kind, 'IlluminatedCream' if classical else trim, qa, qb, .18, .25)
        if profile.style == 'mansard':
            for a,b in edges:
                length = math.dist(a,b)
                if length < 12:
                    continue
                direction=norm((b[0]-a[0],b[1]-a[1],0))
                outward=(direction[1],-direction[0],0.)
                for index in range(max(1,round(length/7))):
                    t=(index+.5)/max(1,round(length/7))
                    center=(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,z+height+2)
                    self.box(kind,'Cream',center,1.8,1.4,2.8,math.atan2(direction[1],direction[0]))
                    face=add(center,add(mul(outward,.75),(0,0,-.8)))
                    self.banner(sub(face,mul(direction,.58)),add(face,mul(direction,.58)),1.7,'Glass',kind)
                    left,right=sub(center,mul(direction,1.2)),add(center,mul(direction,1.2))
                    ridge=add(center,(0,0,2.4))
                    self.triangle(kind,'Roof',add(left,(0,0,1.3)),add(right,(0,0,1.3)),ridge)
        if not profile.name:
            return
        # Wordmarks sit on the actual tower facade, without roadside hotel boards.
        sign_edges = [edge for edge in edges if math.dist(*edge) > 14] or edges
        a, b = min(sign_edges, key=lambda edge: self.nearest((edge[0][0] + edge[1][0]) / 2,
                                                      (edge[0][1] + edge[1][1]) / 2)[1])
        span = math.dist(a, b)
        if span < .1:
            return
        direction = ((b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.)
        outward = direction[1], -direction[0], 0.
        center = add(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), mul(outward, .85))
        if profile.style == 'arcade':
            frontage = min(span, 90.)
            bays = max(1, round(frontage / 5.5))
            bay_width = frontage / bays
            start = sub(add(center, mul(outward, 1.3)), mul(direction, frontage / 2))
            self.beam(kind, 'Cream', add(start, (0, 0, 7.8)),
                      add(add(start, mul(direction, frontage)), (0, 0, 7.8)), 3.0, .8)
            for bay in range(bays + 1):
                foot = add(start, mul(direction, bay * bay_width))
                self.beam(kind, 'Cream', foot, add(foot, (0, 0, 4.1)), .55)
                self.box(kind, 'Cream', add(foot, (0, 0, .25)), .9, .9, .5)
                if bay == bays:
                    continue
                arc_center = add(foot, mul(direction, bay_width / 2))
                previous = add(arc_center, add(mul(direction, -bay_width / 2), (0, 0, 4.1)))
                for segment in range(1, 13):
                    angle = math.pi * (1 - segment / 12)
                    arch_point = add(arc_center, add(mul(direction, math.cos(angle) * bay_width / 2),
                                              (0, 0, 4.1 + math.sin(angle) * bay_width / 2)))
                    self.beam(kind, 'IlluminatedCream', previous, arch_point, .28, .45)
                    previous = arch_point
        for level, width in ((height - 12 if roof else height - 5, 32. if roof else min(span * .7, 42)),):
            middle = add(center, (0, 0, level + (roof.offset(center[0],center[1]) if roof else 0.)))
            if len(ring) > 80:
                arc = [0.0]
                for edge_a,edge_b in edges:
                    arc.append(arc[-1]+math.dist(edge_a,edge_b))
                candidates = list(range(len(edges)))
                if roof is not None:
                    candidates = [i for i,(edge_a,edge_b) in enumerate(edges)
                                  if abs((edge_b[0]-edge_a[0])*roof.axis_x+(edge_b[1]-edge_a[1])*roof.axis_y)
                                  > math.dist(edge_a,edge_b)*.65]
                edge_index = min(candidates,key=lambda i:self.nearest((edges[i][0][0]+edges[i][1][0])/2,
                                                                      (edges[i][0][1]+edges[i][1][1])/2)[1])
                middle_arc = (arc[edge_index]+arc[edge_index+1])/2
                width = 32. if roof else 20.
                begin,arc_end = middle_arc-width/2,middle_arc+width/2
                level_z = z+level+(roof.offset(*ring[edge_index]) if roof else 0.)
                for shift in (-arc[-1],0.,arc[-1]):
                    for i,(edge_a,edge_b) in enumerate(edges):
                        lo,hi=max(begin,arc[i]+shift),min(arc_end,arc[i+1]+shift)
                        if hi <= lo:
                            continue
                        span_edge=arc[i+1]-arc[i]
                        surface_normal=norm((edge_b[1]-edge_a[1],edge_a[0]-edge_b[0],0))
                        t0,t1=(lo-arc[i]-shift)/span_edge,(hi-arc[i]-shift)/span_edge
                        start=add((edge_a[0]+(edge_b[0]-edge_a[0])*t0,edge_a[1]+(edge_b[1]-edge_a[1])*t0,level_z),mul(surface_normal,.18))
                        finish=add((edge_a[0]+(edge_b[0]-edge_a[0])*t1,edge_a[1]+(edge_b[1]-edge_a[1])*t1,level_z),mul(surface_normal,.18))
                        self.banner(start,finish,3.8,profile.name,kind,(lo-begin)/width,(hi-lo)/width)
            else:
                self.banner(sub(middle, mul(direction, width / 2)), add(middle, mul(direction, width / 2)),
                            min(3.8, width / 6), profile.name, kind)
        self.landmarks.append({'name': profile.name + ' architectural profile', 'height_m': profile.height_m,
                               'style': profile.style, 'x': cx, 'y': cy})

    def race_decor(self) -> None:
        for station in (615, 1960, 3235, 3710, 3910, 4870):
            sample = min(self.road, key=lambda p: abs(p.station - station))
            lane = self.outer_lane(sample,1) + 2.5
            base = sample.point(lane)
            heading = math.atan2(sample.ty, sample.tx)
            self.box('Tile_Marshal', 'White', add(base, (0, 0, 1.2)), 3.2, 2, 2.4, heading)
            self.box('Tile_Marshal', 'Canopy', add(base, (0, 0, 2.5)), 3.7, 2.5, .15, heading)
            front = add(base, (-sample.ty * 1.1, sample.tx * 1.1, 0))
            self.box('Tile_Marshal', 'Glass', add(front, (0, 0, 1.7)), 2.4, .06, .7, heading)
            self.box('Tile_Marshal', 'Orange', add(base, (sample.tx * 2.8, sample.ty * 2.8, .6)), .8, .8, 1.2, heading)
            self.beam('Tile_Marshal', 'Steel', add(base, (0, 0, 2.4)), add(base, (0, 0, 4)), .08)
            self.box('Tile_Marshal', 'Black', add(base, (0, 0, 3.6)), .7, .15, .7, heading)

    def city(self) -> None:
        payload = json.loads(gzip.decompress((SOURCE / 'skyline.osm.json.gz').read_bytes()))
        encore = json.loads(gzip.decompress((SOURCE / 'encore.osm.json.gz').read_bytes()))
        payload['elements'].extend(element for element in encore['elements'] if element['id'] == 27910891)
        for element in payload['elements']:
            tags = element.get('tags', {})
            name = tags.get('name', '')
            if tags.get('building') in ('bridge', 'roof', 'construction') or name in ('Sphere', 'Eiffel Tower', 'Grand Prix Plaza'):
                continue
            geometry = element.get('geometry', [])
            ring = [self.projected(point['lat'], point['lon']) for point in geometry]
            if len(ring) < 4:
                continue
            if math.dist(ring[0], ring[-1]) < 1:
                ring.pop()
            if any(self.in_region(*point,region) for point in ring for region in self.escapes):
                continue
            if any(self.nearest(*point)[1] < self.nearest(*point)[0].half_width + 1.4 for point in ring):
                continue
            if any(self.nearest((a[0]+b[0])/2,(a[1]+b[1])/2)[1] < self.nearest((a[0]+b[0])/2,(a[1]+b[1])/2)[0].half_width+1.4 for a,b in zip(ring,ring[1:]+ring[:1])):
                continue
            self.city_rings.append(ring)
            height = float(tags.get('height', str(float(tags.get('building:levels', '3')) * 3.4)).split()[0])
            if element['id'] not in self.profiles and (tags.get('amenity') == 'parking' or tags.get('building') in ('parking','garages')):
                self.profiles[element['id']] = LandmarkProfile('','parking',height,'Cream',0.)
            material = 'BronzeFacade' if any(word in name for word in ('Wynn', 'Trump')) else 'CreamFacade'
            if any(word in name for word in ('Cosmopolitan', 'Horseshoe', 'Planet Hollywood', 'Hilton')):
                material = 'BlueFacade'
            if element['id'] in self.leaning_towers:
                self.leaning_tower(ring,self.leaning_towers[element['id']],element['id'])
            elif element['id'] == 364846544:
                self.paris_balloon(ring,element['id'])
            elif element['id'] == 43875964:
                self.campanile(ring, element['id'])
            else:
                self.building(ring, height, material, name, element['id'])
        self.sphere()
        self.eiffel()
        self.wheel()
        self.pits()
        self.opening_hospitality()
        self.bridges()
        self.race_decor()
        self.grandstand(1660,1980,1,True)
        for a, b, sign in [(2070,2210,1),(2850,3230,-1),(3350,3500,1),(3700,3960,1)]:
            self.grandstand(a, b, sign)
        self.grandstand(5500,5750,-1,rows=9)
        self.wynn_display()
        self.streetscape()

    def wall_material(self, sample: RoadStation, ax: float, ay: float) -> str:
        sector = self.sector(sample.station)
        side = int(sample.tx*(ay-sample.y)-sample.ty*(ax-sample.x)>0)
        panel = sector.wall_panels[(int(sample.station/96)+side)%len(sector.wall_panels)]
        if sector.name == 'paddock':
            panel = 'WallWhite' if int(sample.station/8)%2 else 'WallBlack'
        if 3500 < sample.station < 3840:
            lane = (ax-sample.x)*sample.ty-(ay-sample.y)*sample.tx
            panel = 'WallBlue' if sample.station > 3700 or lane < 0 else 'WallDark'
        return panel

    def sector(self, station: float) -> RouteSector:
        return next(sector for sector in self.sectors if sector.start_m <= station < sector.end_m)

    def broadleaf(self, base: Point, height: float, seed: int) -> None:
        fork = add(base,(0,0,height*.52))
        self.beam('Building_Trees','Trunk',base,fork,.25)
        for cluster in range(5):
            azimuth = cluster*math.tau/5+seed*.13
            center = add(base,(math.cos(azimuth)*height*.16,math.sin(azimuth)*height*.16,
                               height*(.68+.04*(cluster%3))))
            self.beam('Building_Trees','Trunk',fork,center,.10)
            column,row = (2,5)[(seed+cluster)%2],(seed+cluster)%3
            u0,u1 = (column+.012)/6,(column+.988)/6
            v0,v1 = (row+.012)/6,(row+.988)/6
            for plane in range(3):
                angle = plane*math.pi/3+azimuth
                axis = (math.cos(angle),math.sin(angle),0.)
                bottom = add(center,(0,0,-height*.23))
                a,b = sub(bottom,mul(axis,height*.25)),add(bottom,mul(axis,height*.25))
                ta,tb = add(a,(0,0,height*.5)),add(b,(0,0,height*.5))
                self.triangle('Building_Trees','TreeCanopy',ta,tb,b,((u0,v0),(u1,v0),(u1,v1)))
                self.triangle('Building_Trees','TreeCanopy',ta,b,a,((u0,v0),(u1,v1),(u0,v1)))

    def streetscape(self) -> None:
        for sector in self.sectors:
            if sector.tree_spacing_m == 0:
                continue
            station = sector.start_m+sector.tree_spacing_m/2
            number = 0
            while station < sector.end_m:
                sample = min(self.road,key=lambda p:abs(p.station-station))
                for side in (-1,1):
                    seed = int(station*3)+side
                    for setback in (4.8,7.5,11.):
                        lane = side*(self.outer_lane(sample,side)+setback)
                        x,y,_ = sample.point(lane)
                        if any(self.in_polygon(x+dx,y+dy,ring) for ring in self.city_rings
                               for dx,dy in ((0.,0.),(-1.2,0.),(1.2,0.),(0.,-1.2),(0.,1.2))):
                            continue
                        if any(self.in_region(x,y,region) for region in self.escapes):
                            continue
                        z = max(self.ground(x,y),sample.z+.08)
                        palm = sector.palm_every > 0 and (number+side)%sector.palm_every == 0
                        height = 9.+seed%4 if palm else 8.+seed%5
                        if palm:
                            self.palm((x,y,z),height)
                        else:
                            self.broadleaf((x,y,z),height,seed)
                        self.vegetation.append({'sector':sector.name,'station_m':sample.station,'x':x,'y':y,'z':z,
                                                'kind':'palm' if palm else 'broadleaf','height_m':height,'side':side})
                        break
                station += sector.tree_spacing_m
                number += 1
        road = self.road[::self.detail_stride]
        for i,sample in enumerate(road):
            if self.sector(sample.station).name in ('paddock','opening','sphere'):
                continue
            nxt = road[(i+1)%len(road)]
            for side in (-1,1):
                outer,next_outer = self.outer_lane(sample,side),self.outer_lane(nxt,side)
                if outer > sample.half_width+2 or next_outer > nxt.half_width+2:
                    continue
                points = [sample.point(side*(outer+.2),.08),nxt.point(side*(next_outer+.2),.08),
                          nxt.point(side*(next_outer+9),.08),sample.point(side*(outer+9),.08)]
                if any(self.polygons_overlap([p[:2] for p in points],region.ring) for region in self.escapes):
                    continue
                if side > 0:
                    points.reverse()
                self.quad('Tile_Pavement','Pavement',points[0],points[1],points[2],points[3],1,2)

    def residential_tower(self, ring: list[tuple[float,float]], z: float, height: float,
                          profile: LandmarkProfile) -> None:
        kind = 'Building_ResidentialTower'
        signature = profile.name == 'Signature'
        stone = 'Cream' if signature else 'ChateauStone'
        for a,b in zip(ring,ring[1:]+ring[:1]):
            span = math.dist(a,b)
            if span < 2:
                continue
            axis = norm((b[0]-a[0],b[1]-a[1],0))
            out = (axis[1],-axis[0],0.)
            def point(t: float,level: float,projection: float = .4,
                      a: tuple[float,float] = a,b: tuple[float,float] = b,out: Point = out) -> Point:
                return add((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,z+level),mul(out,projection))
            bays = max(1,round(span/(11 if signature else 15)))
            for bay in range(bays+1):
                t = bay/bays
                self.beam(kind,stone,point(t,0),point(t,height+1),1.1 if signature else 1.9,1.0)
                if signature and bay in (0,bays):
                    self.beam(kind,'IlluminatedCream',point(t,height*.62,1.05),point(t,height+4,1.05),.22)
            if signature:
                for level in range(5,int(height-3),4):
                    for t in (.08,.92):
                        middle = point(t,level,1.0)
                        half = min(2.2,span*.07)
                        left,right = sub(middle,mul(axis,half)),add(middle,mul(axis,half))
                        self.beam(kind,'Cream',left,right,2.2,.24)
                        self.banner(add(left,mul(out,1.1)),add(right,mul(out,1.1)),.9,'Glass',kind)
                        self.beam(kind,'Cream',add(left,add(mul(out,1.1),(0,0,1))),
                                  add(right,add(mul(out,1.1),(0,0,1))),.07)
            else:
                for belt_level in (8.,height*.48,height-4):
                    self.beam(kind,'ChateauStone',point(0,belt_level),point(1,belt_level),.8,.8)
            if span < 30:
                continue
            crown_width = min(26.,span*.7)
            crown_center = point(.5,height,0)
            crown_depth = 6. if signature else 5.
            for segment in range(24):
                def roof(t: float,depth: float,crown_center: Point = crown_center,axis: Point = axis,
                         crown_width: float = crown_width,out: Point = out) -> Point:
                    lift = profile.crown_m*math.sin(math.pi*t) if signature else profile.crown_m*(1-.55*abs(2*t-1))
                    return add(crown_center,add(mul(axis,(t-.5)*crown_width),add(mul(out,depth),(0,0,lift))))
                t0,t1 = segment/24,(segment+1)/24
                front_a,front_b = roof(t0,.7),roof(t1,.7)
                back_a,back_b = roof(t0,-crown_depth),roof(t1,-crown_depth)
                self.quad(kind,'Canopy' if signature else 'Roof',front_a,front_b,back_b,back_a)
                self.beam(kind,'IlluminatedCream',front_a,front_b,.28)
                self.quad(kind,stone,point(.5+(t0-.5)*crown_width/span,height,.7),
                          point(.5+(t1-.5)*crown_width/span,height,.7),front_b,front_a)
            if signature:
                for t in (.35,.5,.65):
                    self.beam(kind,'IlluminatedCream',point(t,height*.63,.9),point(t,height+4,.9),.24)
            else:
                for sign in (-1,1):
                    t = .5+sign*min(.11,7/span)
                    self.beam(kind,'ChateauStone',point(t,8,1.3),point(t,height+6,1.3),2.8,2.6)
        self.landmarks.append({'name':profile.name+' reconstructed piers and crown','height_m':height+profile.crown_m})

    def stone_column(self, base: Point, height: float, radius: float) -> None:
        for segment in range(16):
            a,b = segment*math.tau/16,(segment+1)*math.tau/16
            def shaft(angle: float,level: float,scale: float) -> Point:
                return add(base,(math.cos(angle)*radius*scale,math.sin(angle)*radius*scale,level))
            self.quad('Building_Colonnade','Cream',shaft(a,0,1),shaft(b,0,1),
                      shaft(b,height,.86),shaft(a,height,.86))
        for level,size in ((.12,1.5),(height-.15,1.45),(height+.12,1.65)):
            self.box('Building_Colonnade','IlluminatedCream',add(base,(0,0,level)),radius*size*2,radius*size*2,.25)

    def venetian_palace(self, ring: list[tuple[float,float]], z: float, height: float) -> None:
        kind = 'Building_VenetianPalace'
        for a,b in zip(ring,ring[1:]+ring[:1]):
            span = math.dist(a,b)
            if span < 5 or self.nearest((a[0]+b[0])/2,(a[1]+b[1])/2)[1]>190:
                continue
            axis = norm((b[0]-a[0],b[1]-a[1],0))
            out = (axis[1],-axis[0],0.)
            def point(t: float,level: float,projection: float = 2.5,
                      a: tuple[float,float] = a,b: tuple[float,float] = b,out: Point = out) -> Point:
                return add((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,z+level),mul(out,projection))
            for level,spacing,column_height,rise in ((0.,5.,3.7,2.7),(7.8,2.5,2.7,2.1)):
                bays = max(1,round(span/spacing))
                self.banner(point(0,level+.2,.15),point(1,level+.2,.15),column_height+rise,'ArcadeRecess',kind)
                self.beam(kind,'Cream',point(0,level+column_height+rise+.4),point(1,level+column_height+rise+.4),3.2,.45)
                for bay in range(bays+1):
                    self.stone_column(point(bay/bays,level),column_height,.34 if level == 0 else .23)
                    if bay == bays:
                        continue
                    previous = point(bay/bays,level+column_height)
                    for segment in range(1,17):
                        t = segment/16
                        end = point((bay+t)/bays,level+column_height+rise*(1-abs(2*t-1))**.55)
                        self.beam(kind,'IlluminatedCream',previous,end,.16)
                        previous = end
            self.beam(kind,'Cream',point(0,height-.5,.45),point(1,height-.5,.45),.8,.5)
            for window in range(max(1,round(span/8))):
                t = (window+.5)/max(1,round(span/8))
                middle = point(t,17,.18)
                left,right = sub(middle,mul(axis,.8)),add(middle,mul(axis,.8))
                self.banner(left,right,4.5,'ArcadeRecess',kind)
                peak = add(middle,(0,0,6))
                self.triangle(kind,'ArcadeRecess',add(left,(0,0,4.5)),peak,add(right,(0,0,4.5)))
                for foot in (left,right):
                    self.beam(kind,'Cream',foot,add(foot,(0,0,4.5)),.14)
                    self.beam(kind,'Cream',add(foot,(0,0,4.5)),peak,.14)
            merlons = max(1,round(span/2.8))
            for merlon in range(merlons):
                foot = point((merlon+.5)/merlons,height,.3)
                self.box(kind,'Cream',foot,.65,.65,1.2)
                self.beam(kind,'IlluminatedCream',add(foot,(0,0,.6)),add(foot,(0,0,1.3)),.18)
        self.landmarks.append({'name':'Venetian paired pointed colonnades','height_m':height+1.3})

    def forum_entrance(self, ring: list[tuple[float,float]], z: float, height: float) -> None:
        edges = [(a,b) for a,b in zip(ring,ring[1:]+ring[:1]) if math.dist(a,b)>14]
        a,b = min(edges,key=lambda edge:self.nearest((edge[0][0]+edge[1][0])/2,(edge[0][1]+edge[1][1])/2)[1])
        axis = norm((b[0]-a[0],b[1]-a[1],0))
        out = (axis[1],-axis[0],0.)
        center = ((a[0]+b[0])/2,(a[1]+b[1])/2,z)
        def point(along: float,projection: float,level: float) -> Point:
            return add(center,add(mul(axis,along),add(mul(out,projection),(0,0,level))))
        kind = 'Building_ForumEntrance'
        self.banner(point(-8,.3,1),point(8,.3,1),16,'Glass',kind)
        previous = point(-8,.35,17)
        for segment in range(1,25):
            angle = math.pi*(1-segment/24)
            end = point(math.cos(angle)*8,.35,17+math.sin(angle)*8)
            self.triangle(kind,'Glass',point(0,.35,17),end,previous)
            self.beam(kind,'IlluminatedCream',previous,end,.6)
            previous = end
        for along in (-11.,-9.,9.,11.):
            self.stone_column(point(along,2.5,0),22,.65)
        for level in (7.,15.,23.):
            self.beam(kind,'Cream',point(-14,2.5,level),point(14,2.5,level),1.1,.7)
        for along in (-6.,-3.,0.,3.,6.):
            self.beam(kind,'Steel',point(along,.45,1),point(along,.45,23),.10)
        self.banner(point(-7,.6,14),point(7,.6,14),1.8,'ForumShops',kind)
        dome_center = point(0,-7,25)
        for row in range(12):
            p0,p1 = row*math.pi/24,(row+1)*math.pi/24
            for column in range(40):
                t0,t1 = column*math.tau/40,(column+1)*math.tau/40
                def dome(phi: float,theta: float) -> Point:
                    return add(dome_center,(9*math.cos(phi)*math.cos(theta),9*math.cos(phi)*math.sin(theta),11.6*math.sin(phi)))
                self.quad(kind,'Canopy',dome(p0,t0),dome(p0,t1),dome(p1,t1),dome(p1,t0))
                if column%5 == 0:
                    self.beam(kind,'IlluminatedCream',dome(p0,t0),dome(p1,t0),.10)
        self.landmarks.append({'name':'Forum Shops domed Strip entrance','height_m':36.6})

    def casino_frontage(self, ring: list[tuple[float,float]], z: float, height: float,
                        profile: LandmarkProfile, osm_id: int) -> None:
        edges = [(a,b) for a,b in zip(ring,ring[1:]+ring[:1]) if math.dist(a,b)>14]
        if not edges:
            return
        a,b = min(edges,key=lambda edge:self.nearest((edge[0][0]+edge[1][0])/2,(edge[0][1]+edge[1][1])/2)[1])
        span = math.dist(a,b)
        axis = norm((b[0]-a[0],b[1]-a[1],0))
        outward = (axis[1],-axis[0],0.)
        center = ((a[0]+b[0])/2,(a[1]+b[1])/2,z)
        def point(along: float,projection: float,level: float) -> Point:
            return add(center,add(mul(axis,along),add(mul(outward,projection),(0,0,level))))
        kind = 'Building_CasinoFrontage'
        width = min(24.,span*.85)
        if osm_id == 134795273:
            for level in (7.,14.,21.,28.,36.):
                self.beam(kind,'Cream',point(-span/2,.3,level),point(span/2,.3,level),.25,.4)
            for sign in (-1,1):
                middle = sign*min(span*.28,24.)
                left,right = point(middle-4,2.2,7),point(middle+4,2.2,7)
                self.banner(left,right,min(35.,height-7),'StripDisplay',kind)
                for side in (-4.2,4.2):
                    self.beam(kind,'PinkNeon',point(middle+side,2.3,7),point(middle+side,2.3,min(42.,height)),.10)
        elif profile.name == 'Flamingo':
            for lobe in (-1,0,1):
                middle = lobe*width/3
                hub = point(middle,.2,5.6)
                for segment in range(16):
                    def rim(angle: float, middle: float = middle) -> Point:
                        return point(middle+math.cos(angle)*width/6,.2+math.sin(angle)*4,5.6+.7*math.sin(angle))
                    p,q = rim(segment*math.pi/16),rim((segment+1)*math.pi/16)
                    self.triangle(kind,'Canopy',hub,p,q)
                    self.triangle(kind,'Canopy',hub,q,p)
                    self.beam(kind,'PinkNeon',p,q,.14,.10)
            self.beam(kind,'PinkNeon',point(-width/2,.4,10),point(width/2,.4,10),.22)
        else:
            accent = {'Linq':'BlueNeon','Harrahs':'PinkNeon','CasinoRoyale':'RedNeon'}[profile.name]
            rear_a,rear_b = point(-width/2,.2,7.3),point(width/2,.2,7.3)
            front_a,front_b = point(-width/2,3.6,6),point(width/2,3.6,6)
            self.quad(kind,'Canopy',rear_a,rear_b,front_b,front_a)
            self.quad(kind,'Canopy',front_a,front_b,rear_b,rear_a)
            self.beam(kind,accent,front_a,front_b,.20)
            for side in (-1,1):
                self.beam(kind,'PodiumStone',point(side*width/2,3.3,0),point(side*width/2,3.3,6),.5)
                self.beam(kind,accent,point(side*(width/2-.35),3.4,0),point(side*(width/2-.35),3.4,6),.12)
            if profile.name in ('Linq','Harrahs'):
                for side in (-1,1):
                    offset = side*(width/2-2.2)
                    self.banner(point(offset-1.4,.3,2),point(offset+1.4,.3,2),min(12.,height-3),
                                'StripDisplay' if profile.name == 'Harrahs' else 'HarmonDisplay',kind)
        self.landmarks.append({'name':profile.name+' integrated street frontage','osm_id':osm_id,
                               'x':center[0],'y':center[1],'height_m':min(height,42.)})

    def urban_architecture(self, ring: list[tuple[float,float]], z: float, height: float,
                           profile: LandmarkProfile) -> None:
        edges = list(zip(ring,ring[1:]+ring[:1]))
        kind = 'Building_Frontage'
        for a,b in edges:
            span = math.dist(a,b)
            if span < .5:
                continue
            direction = norm((b[0]-a[0],b[1]-a[1],0))
            outward = (direction[1],-direction[0],0.)
            def point(t: float,level: float,a: tuple[float,float] = a,b: tuple[float,float] = b,
                      outward: Point = outward) -> Point:
                return add((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,z+level),mul(outward,.13))
            if profile.style == 'motel':
                for floor in range(0,int(height-1),3):
                    self.beam(kind,'Cream',point(0,floor),point(1,floor),1.7,.22)
                    if floor > 0:
                        self.beam(kind,'Steel',point(0,floor+1.05),point(1,floor+1.05),.08)
                for bay in range(max(1,round(span/4))):
                    t = (bay+.5)/max(1,round(span/4))
                    self.banner(sub(point(t,.3),mul(direction,.6)),add(point(t,.3),mul(direction,.6)),2.2,'WarmGlass',kind)
            elif profile.style in ('office','exhibition'):
                for floor in range(3,int(height-2),4):
                    self.banner(point(0,floor),point(1,floor),1.8,'Glass',kind)
                    self.beam(kind,'Cream',point(0,floor-.25),point(1,floor-.25),.22,.3)
                self.beam(kind,'IlluminatedCream',point(0,height-.4),point(1,height-.4),.12)
            else:
                bays = max(1,round(span/6))
                for bay in range(bays):
                    middle = point((bay+.5)/bays,1)
                    half = min(2.6,span/bays*.43)
                    self.banner(sub(middle,mul(direction,half)),add(middle,mul(direction,half)),
                                min(6.,height-2),('ShopWarm','ShopFashion','ShopCool')[bay%3],kind)
                for bay in range(bays+1):
                    self.beam(kind,'PodiumStone',point(bay/bays,0),point(bay/bays,height),.45)
                levels = (4.,height-1.1,height) if profile.style == 'wynn_plaza' else (height-.8,)
                accent = 'RedNeon' if profile.name in ('EllisIsland','OleRed','HellsKitchen') else 'PinkNeon' if profile.name in ('Harrahs','Flamingo') else 'IlluminatedCream'
                for level in levels:
                    self.beam(kind,accent,point(0,level),point(1,level),.5,.4)
        if profile.style in ('office','motel','exhibition'):
            cx,cy = sum(p[0] for p in ring)/len(ring),sum(p[1] for p in ring)/len(ring)
            self.box(kind,'Steel',(cx,cy,z+height+.7),5,3,1.4)
        a,b = min(edges,key=lambda e:self.nearest((e[0][0]+e[1][0])/2,(e[0][1]+e[1][1])/2)[1])
        span = math.dist(a,b)
        if span < .5:
            return
        direction = norm((b[0]-a[0],b[1]-a[1],0))
        outward = (direction[1],-direction[0],0.)
        middle = add(((a[0]+b[0])/2,(a[1]+b[1])/2,z+height-3),mul(outward,.3))
        if profile.style == 'exhibition':
            bays = max(1,round(span/13))
            for bay in range(bays):
                foot = add((a[0],a[1],z+2.2),add(mul(direction,span*(bay+.5)/bays),mul(outward,.35)))
                self.banner(sub(foot,mul(direction,1.2)),add(foot,mul(direction,1.2)),3.6,
                            ('WallWhite','WallPurple','WallBlack')[bay%3],kind)
                self.beam(kind,'Cream',add(foot,(0,0,4)),add(foot,add(mul(outward,1.4),(0,0,4))),.12)
                self.box(kind,'Lamp',add(foot,add(mul(outward,1.3),(0,0,3.9))),.45,.25,.08)
        if profile.style == 'display':
            self.harmon_corner(ring,z,height)
        if profile.name in HOTEL_NAMES:
            half = min(span*.42,15.)
            self.banner(sub(middle,mul(direction,half)),add(middle,mul(direction,half)),2.3,profile.name,kind)

    def harmon_corner(self, ring: list[tuple[float,float]], z: float, height: float) -> None:
        edges = [(a,b) for a,b in zip(ring,ring[1:]+ring[:1]) if math.dist(a,b)>30]
        a,b = min(edges,key=lambda e:self.nearest((e[0][0]+e[1][0])/2,(e[0][1]+e[1][1])/2)[1])
        axis = norm((b[0]-a[0],b[1]-a[1],0))
        out = (axis[1],-axis[0],0.)
        center = ((a[0]+b[0])/2,(a[1]+b[1])/2,z)
        def point(x: float,projection: float,level: float) -> Point:
            return add(center,add(mul(axis,x),add(mul(out,projection),(0,0,level))))
        width,screen_height = 93.2688,18.288
        main = min(73.,math.dist(a,b)-3)
        border = self.curved_footprint(ring)
        outside: list[Point] = []
        for index,vertex in enumerate(border):
            previous,nxt = border[index-1],border[(index+1)%len(border)]
            incoming = norm((vertex[1]-previous[1],previous[0]-vertex[0],0))
            outgoing = norm((nxt[1]-vertex[1],vertex[0]-nxt[0],0))
            bisector = norm(add(incoming,outgoing))
            offset = 1.2/max(.4,sum(v*w for v,w in zip(bisector,outgoing)))
            outside.append(add((*vertex,z+height+1),mul(bisector,offset)))
        lengths = [0.]
        for p,q in zip(outside,outside[1:]+outside[:1]):
            lengths.append(lengths[-1]+math.dist(p,q))
        closest = min(range(len(outside)),key=lambda i:self.nearest(outside[i][0],outside[i][1])[1])
        path: list[Point] = []
        steps = math.ceil(width)
        for step in range(steps+1):
            distance = (lengths[closest]-width/2+width*step/steps)%lengths[-1]
            edge = next(i for i in range(len(outside)) if lengths[i+1]>=distance)
            t = (distance-lengths[edge])/(lengths[edge+1]-lengths[edge])
            path.append(add(mul(outside[edge],1-t),mul(outside[(edge+1)%len(outside)],t)))
        clearance_points = path+[mul(add(p,q),.5) for p,q in itertools.pairwise(path)]
        if any(self.in_polygon(p[0],p[1],ring) for p in clearance_points):
            raise ValueError('Harmon Corner screen crosses its mapped building footprint')
        run = 0.
        for p,q in itertools.pairwise(path):
            length = math.dist(p,q)
            bottom_a,bottom_b = p,q
            top_a,top_b = add(bottom_a,(0,0,screen_height)),add(bottom_b,(0,0,screen_height))
            self.triangle('Building_HarmonDisplay','HarmonDisplay',bottom_a,bottom_b,top_b,
                          ((run/width,1),((run+length)/width,1),((run+length)/width,0)))
            self.triangle('Building_HarmonDisplay','HarmonDisplay',bottom_a,top_b,top_a,
                          ((run/width,1),((run+length)/width,0),(run/width,0)))
            self.beam('Building_HarmonDisplay','Steel',top_a,top_b,.35)
            self.beam('Building_HarmonDisplay','Steel',bottom_a,bottom_b,.35)
            run += length
        for level in (4.5,9.):
            self.beam('Building_HarmonRetail','Cream',point(-main/2,2,level),point(main/2,2,level),3,.35)
            self.banner(point(-main/2,3.3,level+.25),point(main/2,3.3,level+.25),.9,'HospitalityGlass','Building_HarmonRetail')
            for offset in range(-int(main/2),int(main/2),7):
                self.beam('Building_HarmonRetail','Cream',point(offset,2.5,0),point(offset,2.5,height),.35)
        self.landmarks.append({'name':'Harmon Corner upper curved LED and retail balconies',
                               'screen_width_m':width,'screen_height_m':screen_height,'base_height_m':height+1,
                               'height_m':height+1+screen_height})

    def wynn_display(self) -> None:
        display = self.wynn_display_profile
        x,y = (value*self.scale for value in display.source_xy_m)
        z = self.ground(x,y)
        angle = math.radians(display.orientation_deg)
        axis = (math.cos(angle),math.sin(angle),0.)
        normal = (axis[1],-axis[0],0.)
        def point(phi: float,level: float,offset: float = 0.) -> Point:
            return add((x,y,z+level),add(mul(axis,math.cos(phi)*(display.width_m/2+offset)),
                                        mul(normal,math.sin(phi)*(display.depth_m/2+offset))))
        for i in range(64):
            p0,p1 = i*math.tau/64,(i+1)*math.tau/64
            a,b = point(p0,0),point(p1,0)
            self.quad('Building_WynnDisplay','PodiumStone',b,a,point(p0,display.base_height_m+2),point(p1,display.base_height_m+2))
            low = display.base_height_m+3
            self.triangle('Building_WynnDisplay','WynnDisplay',point(p0,display.height_m),point(p1,display.height_m),point(p1,low),
                          ((i/32,0),((i+1)/32,0),((i+1)/32,1)))
            self.triangle('Building_WynnDisplay','WynnDisplay',point(p0,display.height_m),point(p1,low),point(p0,low),
                          ((i/32,0),((i+1)/32,1),(i/32,1)))
            for level in (display.base_height_m,display.base_height_m+2,display.height_m):
                self.beam('Building_WynnDisplay','IlluminatedCream',point(p0,level),point(p1,level),.25,.35)
        for i in range(24):
            p0 = math.pi/6+i*math.pi*2/3/24
            p1 = math.pi/6+(i+1)*math.pi*2/3/24
            self.banner(point(p0,display.base_height_m-.3,.18),point(p1,display.base_height_m-.3,.18),2.,'WynnPlaza','Building_WynnDisplay',1-i/24,-1/24)
        self.city_rings.append([point(i*math.tau/64,0)[:2] for i in range(64)])
        self.landmarks.append({'name':'Wynn Plaza curved digital monument','x':x,'y':y,'height_m':display.height_m})

    def bridges(self) -> None:
        payload = json.loads(gzip.decompress((SOURCE / 'pedestrian_bridges.osm.json.gz').read_bytes()))
        for element in payload['elements']:
            tags = element.get('tags', {})
            if tags.get('highway') != 'footway':
                continue
            points = [self.projected(p['lat'], p['lon']) for p in element['geometry']]
            probes: list[tuple[RoadStation, float]] = []
            for a, b in itertools.pairwise(points):
                count = max(1, math.ceil(math.dist(a, b) / 3))
                probes.extend(self.nearest(a[0] + (b[0] - a[0]) * step / count,
                                           a[1] + (b[1] - a[1]) * step / count) for step in range(count + 1))
            sample, distance = min(probes, key=lambda probe: probe[1])
            if distance > sample.half_width or max(p[1] for p in probes) < sample.half_width + 4:
                continue
            z = sample.z + 6.5
            for a, b in itertools.pairwise(points):
                length = math.dist(a, b)
                if length < .1:
                    continue
                tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.0)
                side = (-tangent[1], tangent[0], 0.0)
                start, end = (*a, z), (*b, z)
                self.beam('Building_Bridge', 'Cream', start, end, 4.2, .45)
                self.beam('Building_Bridge', 'Roof', add(start, (0, 0, 2.9)), add(end, (0, 0, 2.9)), 4.6, .18)
                for sign in (-1, 1):
                    edge_a, edge_b = add(start, mul(side, sign * 2)), add(end, mul(side, sign * 2))
                    self.banner(edge_a, edge_b, 1.1, 'Glass', 'Building_Bridge')
                    self.beam('Building_Bridge', 'Steel', add(edge_a, (0, 0, 1.1)), add(edge_b, (0, 0, 1.1)), .08)
                    for support in range(max(1, math.ceil(length / 3)) + 1):
                        point = add(edge_a, mul(sub(edge_b, edge_a), support / max(1, math.ceil(length / 3))))
                        self.beam('Building_Bridge', 'Cream', point, add(point, (0, 0, 2.9)), .12)
                        if support < max(1, math.ceil(length / 3)):
                            end_point = add(point, mul(tangent, length / max(1, math.ceil(length / 3))))
                            self.beam('Building_Bridge', 'Cream', add(point, (0, 0, 1.1)), add(end_point, (0, 0, 2.9)), .08)
                    self.beam('Building_Bridge', 'IlluminatedCream', add(edge_a, (0, 0, -.3)), add(edge_b, (0, 0, -.3)), .10)
                if length > 14 and self.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)[1] < sample.half_width:
                    edge_a, edge_b = add(start, mul(side, 2.12)), add(end, mul(side, 2.12))
                    if sum(a * b for a, b in zip(sub(edge_b, edge_a), (sample.ty, -sample.tx, 0))) < 0:
                        edge_a, edge_b = edge_b, edge_a
                    self.banner(add(edge_a, (0, 0, -1.4)), add(edge_b, (0, 0, -1.4)), 1.1, 'RaceSign', 'Building_Bridge')
            for x, y in (points[0], points[-1]):
                road, distance = self.nearest(x, y)
                if distance > road.half_width + max(road.left_shoulder, road.right_shoulder) + 3:
                    self.beam('Building_Bridge', 'Cream', (x, y, self.ground(x, y)), (x, y, z), .8)
            self.landmarks.append({'name': tags.get('name', 'Strip pedestrian bridge'), 'osm_id': element['id'],
                                   'station_m': sample.station, 'height_m': 6.5})

    def paris_balloon(self, ring: list[tuple[float,float]], osm_id: int) -> None:
        x,y = sum(p[0] for p in ring)/len(ring),sum(p[1] for p in ring)/len(ring)
        z = self.ground(x,y)
        for angle in range(0,360,90):
            t=math.radians(angle)
            self.beam('Building_Paris','IlluminatedCream',(x+6*math.cos(t),y+6*math.sin(t),z),
                      (x+5*math.cos(t),y+5*math.sin(t),z+15),.35)
        for row in range(24):
            a0,a1=-math.pi/2+math.pi*row/24,-math.pi/2+math.pi*(row+1)/24
            for col in range(64):
                p0,p1=col*math.tau/64,(col+1)*math.tau/64
                def point(a: float,phi: float) -> Point:
                    return x+10*math.cos(a)*math.cos(phi),y+10*math.cos(a)*math.sin(phi),z+28+16*math.sin(a)
                self.quad('Building_Paris','BalloonBlue',point(a0,p0),point(a0,p1),point(a1,p1),point(a1,p0))
                if col%8 == 0:
                    self.beam('Building_Paris','BronzeTrim',point(a0,p0),point(a1,p0),.10)
                if row in (4,11,18):
                    self.beam('Building_Paris','IlluminatedCream',point(a0,p0),point(a0,p1),.14)
        road,_=self.nearest(x,y)
        facing = norm((road.x-x,road.y-y,0))
        center=add((x,y,z+27),mul(facing,10.1))
        side=(facing[1],-facing[0],0.)
        self.banner(sub(center,mul(side,7)),add(center,mul(side,7)),3.8,'Paris','Building_Paris')
        self.landmarks.append({'name':'Paris balloon','osm_id':osm_id,'height_m':44.,'x':x,'y':y})

    def campanile(self, ring: list[tuple[float, float]], osm_id: int) -> None:
        x, y = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        z = self.ground(x, y)
        self.box('Building_Campanile', 'Cream', (x, y, z + 2), 17, 17, 4)
        self.box('Building_Campanile', 'Brick', (x, y, z + 36), 13, 13, 68)
        for side in (-1, 1):
            for offset in (-4.8, 4.8):
                self.beam('Building_Campanile', 'Cream', (x + side * 6.6, y + offset, z + 5),
                          (x + side * 6.6, y + offset, z + 70), .38)
                self.beam('Building_Campanile', 'Cream', (x + offset, y + side * 6.6, z + 5),
                          (x + offset, y + side * 6.6, z + 70), .38)
        for height, width, depth in ((70, 15.5, 1.5), (73, 15, 1), (85, 16, 1.5), (88, 14, 2)):
            self.box('Building_Campanile', 'Cream', (x, y, z + height), width, width, depth)
        self.box('Building_Campanile', 'Black', (x, y, z + 79), 12, 12, 10)
        for side in (-1, 1):
            for offset in (-6, -2, 2, 6):
                self.beam('Building_Campanile', 'IlluminatedCream', (x + side * 6.6, y + offset, z + 73),
                          (x + side * 6.6, y + offset, z + 85), .65)
                self.beam('Building_Campanile', 'IlluminatedCream', (x + offset, y + side * 6.6, z + 73),
                          (x + offset, y + side * 6.6, z + 85), .65)
        corners = [(x - 7, y - 7, z + 89), (x + 7, y - 7, z + 89),
                   (x + 7, y + 7, z + 89), (x - 7, y + 7, z + 89)]
        for index in range(4):
            self.triangle('Building_Campanile', 'Copper', corners[index], corners[(index + 1) % 4], (x, y, z + 96))
        self.landmarks.append({'name': 'Venetian Campanile', 'osm_id': osm_id, 'x': x, 'y': y, 'height_m': 96})

    def sphere(self) -> None:
        x, y = self.projected(36.12076, -115.16182)
        z = self.ground(x, y)
        # 157 m wide, 112 m high, clipped at ground level. Original LED artwork.
        radius = 78.5
        center_z = z + 112 - radius
        bottom = math.asin(-center_z / radius + z / radius)
        for row in range(32):
            a0, a1 = bottom + (math.pi / 2 - bottom) * row / 32, bottom + (math.pi / 2 - bottom) * (row + 1) / 32
            for col in range(96):
                p0, p1 = col * math.tau / 96, (col + 1) * math.tau / 96
                def point(a: float, phi: float) -> Point:
                    return x + radius * math.cos(a) * math.cos(phi), y + radius * math.cos(a) * math.sin(phi), center_z + radius * math.sin(a)
                a, b, c, d = point(a0, p0), point(a0, p1), point(a1, p1), point(a1, p0)
                u0, u1, v0, v1 = col / 96, (col + 1) / 96, 1 - row / 32, 1 - (row + 1) / 32
                self.triangle('Building_Sphere', 'Sphere', a, b, c, ((u0, v0), (u1, v0), (u1, v1)))
                self.triangle('Building_Sphere', 'Sphere', a, c, d, ((u0, v0), (u1, v1), (u0, v1)))
        self.landmarks.append({'name': 'Sphere', 'x': x, 'y': y, 'height_m': 112, 'width_m': 157})

    def eiffel(self) -> None:
        x, y = self.projected(36.11252, -115.17216)
        z = self.ground(x, y)
        for sign_x, sign_y in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            previous = x + sign_x * 24, y + sign_y * 24, z
            for height, radius in [(25, 15), (58, 9), (100, 5), (145, 1.5), (165, .2)]:
                nxt = x + sign_x * radius, y + sign_y * radius, z + height
                self.beam('Building_Eiffel', 'TowerSteel', previous, nxt, .65 if height < 100 else .35)
                previous = nxt
        for height in range(8, 145, 6):
            radius = max(2, 24 * (1 - height / 165) ** 1.8)
            next_radius = max(1, 24 * (1 - (height + 6) / 165) ** 1.8)
            ring = [(x - radius, y - radius, z + height), (x + radius, y - radius, z + height),
                    (x + radius, y + radius, z + height), (x - radius, y + radius, z + height)]
            higher = [(x - next_radius, y - next_radius, z + height + 6), (x + next_radius, y - next_radius, z + height + 6),
                      (x + next_radius, y + next_radius, z + height + 6), (x - next_radius, y + next_radius, z + height + 6)]
            for index in range(4):
                self.beam('Building_Eiffel', 'TowerSteel', ring[index], ring[(index + 1) % 4], .2)
                self.beam('Building_Eiffel', 'TowerSteel', ring[index], higher[(index + 1) % 4], .16)
                self.beam('Building_Eiffel', 'TowerSteel', ring[(index + 1) % 4], higher[index], .16)
        for height, width in [(27, 34), (58, 21), (144, 7)]:
            self.box('Building_Eiffel', 'TowerSteel', (x, y, z + height), width, width, 1.6)
        self.landmarks.append({'name': 'Paris Eiffel Tower', 'x': x, 'y': y, 'height_m': 165})

    def wheel(self) -> None:
        x, y = self.projected(36.11757, -115.16894)
        z = self.ground(x, y)
        radius = 79.0
        center = x, y, z + 88
        for sign in (-1, 1):
            self.beam('Building_HighRoller', 'White', (x + sign * 23, y - 18, z), center, 1.8)
            self.beam('Building_HighRoller', 'White', (x + sign * 23, y + 18, z), center, 1.8)
        for index in range(112):
            angle, nxt = index * math.tau / 112, (index + 1) * math.tau / 112
            for dy in (-1.8, 1.8):
                a = x + radius * math.cos(angle), y + dy, center[2] + radius * math.sin(angle)
                b = x + radius * math.cos(nxt), y + dy, center[2] + radius * math.sin(nxt)
                self.beam('Building_HighRoller', 'WheelLight', a, b, .35)
            if index % (4 * self.detail_stride) == 0:
                a = x + radius * math.cos(angle), y, center[2] + radius * math.sin(angle)
                self.beam('Building_HighRoller', 'Steel', center, a, .045)
                self.box('Building_HighRoller', 'BlueFacade', a, 4.8, 4.8, 3.4)
        self.landmarks.append({'name': 'High Roller', 'x': x, 'y': y, 'height_m': 167})

    def pits(self) -> None:
        road = self.road[::self.detail_stride]
        for index, sample in enumerate(road):
            if not 1660 < sample.station < 1980:
                continue
            nxt = road[(index + 1) % len(road)]
            near = sample.half_width + 8
            near_next = nxt.half_width + 8
            self.city_rings.append([sample.point(-near-13)[:2],nxt.point(-near_next-13)[:2],
                                    nxt.point(-near_next-35)[:2],sample.point(-near-35)[:2]])
            # Pit lane, garages, three hospitality decks and cantilever roof.
            self.quad('Tile_Paddock', 'Runoff', sample.point(-near), nxt.point(-near_next), nxt.point(-near_next - 13), sample.point(-near - 13), 1, 3)
            for height in (0, 5.2, 10.5, 15.6):
                self.beam('Building_Paddock', 'Cream', sample.point(-near - 24, height), nxt.point(-near_next - 24, height), 17, .5)
                self.beam('Building_Paddock', 'IlluminatedCream', sample.point(-near - 15.4, height + .3),
                          nxt.point(-near_next - 15.4, height + .3), .14, .08)
            self.banner(sample.point(-near - 22, .3), nxt.point(-near_next - 22, .3), 4.6, 'Garage', 'Building_Paddock')
            for height in (5.5, 10.8):
                self.banner(sample.point(-near - 28, height), nxt.point(-near_next - 28, height), 3.5, 'BlueFacade', 'Building_Paddock', sample.station / 16)
                self.banner(sample.point(-near - 15.4, height), nxt.point(-near_next - 15.4, height), 1.0, 'RaceSign', 'Building_Paddock')
            self.beam('Building_Paddock', 'Canopy', sample.point(-near - 24, 18.8), nxt.point(-near_next - 24, 18.8), 22, .7)
            if index % 2 == 0:
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 16, 4.8), sample.point(-near - 16, 18.8), .2)
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 13, 18.1), sample.point(-near - 34, 18.1), .18)
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 13, 18.1), sample.point(-near - 24, 17), .10)
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 34, 18.1), sample.point(-near - 24, 17), .10)
            if index % 5 == 0:
                self.spectators(sample.point(-near - 16, 6.1), nxt.point(-near_next - 16, 6.1), index, 'Building_Crowd_Paddock')

    def opening_hospitality(self) -> None:
        road = self.road[::self.detail_stride]
        for index,sample in enumerate(road):
            if not 2210 < sample.station < 2830:
                continue
            nxt = road[(index+1)%len(road)]
            near = self.outer_lane(sample,-1)+6
            next_near = self.outer_lane(nxt,-1)+6
            self.city_rings.append([sample.point(-near)[:2],nxt.point(-next_near)[:2],
                                    nxt.point(-next_near-16)[:2],sample.point(-near-16)[:2]])
            for level in (0.,3.6,7.2,10.8):
                self.beam('Building_OpeningGallery','Cream',sample.point(-near-8,level),
                          nxt.point(-next_near-8,level),16,.35)
                self.banner(sample.point(-near-4,level+.4),nxt.point(-next_near-4,level+.4),
                            2.7,'HospitalityGlass','Building_OpeningGallery')
                self.banner(sample.point(-near-15.8,level+.4),nxt.point(-next_near-15.8,level+.4),
                            2.7,'ArcadeRecess','Building_OpeningGallery')
                self.beam('Building_OpeningGallery','Steel',sample.point(-near-4,level+.4),
                          sample.point(-near-4,level+3.1),.07)
                self.beam('Building_OpeningGallery','IlluminatedCream',sample.point(-near-7,level+3.25),
                          nxt.point(-next_near-7,level+3.25),.18,.06)
                if index%3 == 0:
                    self.banner(sample.point(-near-4,level+.4),sample.point(-near-15.8,level+.4),
                                2.7,'ArcadeRecess','Building_OpeningGallery')
                if level > 0:
                    for rail in (.5,1.1):
                        self.beam('Building_OpeningGallery','Steel',sample.point(-near,level+rail),
                                  nxt.point(-next_near,level+rail),.055)
                    self.beam('Building_OpeningGallery','IlluminatedCream',sample.point(-near,level+.1),
                              nxt.point(-next_near,level+.1),.07)
                if index%2 == 0:
                    self.beam('Building_OpeningGallery','Cream',sample.point(-near,level),
                              sample.point(-near,level+3.6),.22)
                    if level > 0:
                        self.spectators(sample.point(-near-1,level+.25),nxt.point(-next_near-1,level+.25),
                                        index,'Building_Crowd_Gallery')
            self.beam('Building_OpeningGallery','Steel',sample.point(-near-7,14.4),
                      nxt.point(-next_near-7,14.4),19,.45)
            self.beam('Building_OpeningGallery','Cream',sample.point(-near+2,14.3),
                      nxt.point(-next_near+2,14.3),.3,.4)
            if index%2 == 0:
                self.beam('Building_OpeningGallery','Steel',sample.point(-near+2,14.2),sample.point(-near-16,14.2),.16)
                self.beam('Building_OpeningGallery','Steel',sample.point(-near+2,14.2),sample.point(-near-16,13.2),.12)
        self.landmarks.append({'name':'Opening sequence hospitality gallery','start_station_m':2210,
                               'end_station_m':2830,'height_m':14.4,'side':-1})

    def grandstand(self, start: float, end: float, sign: int, roofed: bool = False, rows: int = 18) -> None:
        road = self.road[::self.detail_stride]
        back_depth = (rows-1)*1.1+.3
        rear_height = 1.4+(rows-1)*.45+.75
        for index in range(0, len(road), 2):
            sample = road[index]
            if not start < sample.station < end:
                continue
            nxt = road[(index + 2) % len(road)]
            base = self.outer_lane(sample,sign) + 4.5
            next_base = self.outer_lane(nxt,sign) + 4.5
            self.city_rings.append([sample.point(sign*base)[:2],nxt.point(sign*next_base)[:2],
                                    nxt.point(sign*(next_base+back_depth+2))[:2],sample.point(sign*(base+back_depth+2))[:2]])
            for row in range(rows):
                lane, lane_next = sign * (base + row * 1.1), sign * (next_base + row * 1.1)
                a, b = sample.point(lane, 1.4 + row * .45), nxt.point(lane_next, 1.4 + row * .45)
                self.spectators(a, b, row, 'Building_Crowd_Stands')
                self.beam('Building_Stands', 'Steel', add(a, (0, 0, -.1)), add(b, (0, 0, -.1)), 1.2, .12)
            if index % 6 == 0:
                rear = sample.point(sign * (base + back_depth), rear_height)
                foot = sample.point(sign * (base + back_depth))
                self.beam('Building_Stands', 'Steel', foot, rear, .18)
                self.beam('Building_Stands', 'Steel', sample.point(sign * base, .8), rear, .16)
                self.beam('Building_Stands', 'Steel', foot, nxt.point(sign * (next_base + back_depth), rear_height), .10)
            if roofed:
                front = sample.point(sign * (base - 1.5), 12.4)
                rear = sample.point(sign * (base + 20), 14.2)
                front_next = nxt.point(sign * (next_base - 1.5), 12.4)
                rear_next = nxt.point(sign * (next_base + 20), 14.2)
                self.quad('Building_Stands', 'Steel', front, front_next, rear_next, rear)
                self.quad('Building_Stands', 'Steel', rear, rear_next, front_next, front)
                self.beam('Building_Stands', 'IlluminatedCream', front, front_next, .12)
                for depth in (4, 8, 12, 16):
                    height = 12.4 + depth / 21.5 * 1.8 - .08
                    self.beam('Building_Stands', 'Steel', sample.point(sign * (base - 1.5 + depth), height),
                              nxt.point(sign * (next_base - 1.5 + depth), height), .12)
                    self.beam('Building_Stands','Steel',sample.point(sign*(base-1.5+depth),height-.6),
                              nxt.point(sign*(next_base-1.5+depth),height-.6),.10)
                    self.beam('Building_Stands','Steel',sample.point(sign*(base-1.5+depth),height-.6),
                              nxt.point(sign*(next_base-1.5+depth),height),.08)
                    if depth in (4,12):
                        self.beam('Building_Stands','IlluminatedCream',sample.point(sign*(base-1.5+depth),height-.15),
                                  nxt.point(sign*(next_base-1.5+depth),height-.15),.10,.06)
                self.beam('Building_Stands', 'Steel', rear, front, .15)
                self.beam('Building_Stands', 'Steel', add(rear, (0, 0, -.8)), front, .10)
                if index % 6 == 0:
                    self.beam('Building_Stands', 'Steel', foot, rear, .24)
                    self.beam('Building_Stands', 'Steel', rear, front, .18)
                    self.beam('Building_Stands', 'Steel', add(rear, (0, 0, -1.2)), front, .12)
                    self.box('Building_Stands', 'Lamp', add(front, (0, 0, -.18)), .7, .6, .05)
            self.beam('Building_Stands', 'Steel', sample.point(sign * (base + back_depth), rear_height+.7),
                      nxt.point(sign * (next_base + back_depth), rear_height+.7), .07)

    def palm(self, base: Point, height: float) -> None:
        top = add(base, (.4, .2, height))
        for row in range(8):
            z0, z1 = height * row / 8, height * (row + 1) / 8
            r0, r1 = .23 - row * .008, .23 - (row + 1) * .008
            for column in range(8):
                a0, a1 = column * math.tau / 8, (column + 1) * math.tau / 8
                def trunk(z: float, radius: float, angle: float) -> Point:
                    return base[0] + .4 * z / height + radius * math.cos(angle), base[1] + .2 * z / height + radius * math.sin(angle), base[2] + z
                self.quad('Building_Palms', 'Trunk', trunk(z0, r0, a0), trunk(z0, r0, a1), trunk(z1, r1, a1), trunk(z1, r1, a0))
        for frond in range(25):
            angle = frond * math.tau / 25 + base[0] % 1
            direction = math.cos(angle), math.sin(angle), 0.0
            side = -math.sin(angle), math.cos(angle), 0.0
            length = 3.8 + (frond % 4) * .35
            previous = top
            previous_width = .02
            for segment in range(1, 13):
                t = segment / 12
                point = add(top, add(mul(direction, length * t), (0, 0, 2 * math.sin(t * math.pi) - t * 1.7)))
                self.beam('Building_Palms', 'Leaves', previous, point, .035)
                width = .8 * math.sin(t * math.pi) + .04
                self.quad('Building_Palms','Leaves',sub(previous,mul(side,previous_width)),
                          sub(point,mul(side,width*.45)),add(point,mul(side,width*.45)),
                          add(previous,mul(side,previous_width)))
                previous_width = width*.45
                for sign in (-1, 1):
                    last = point
                    leaf_side = norm(cross(add(mul(side, sign), mul(direction, .25)), (0, 0, 1)))
                    for blade_step in range(1, 3):
                        fraction = blade_step / 2
                        blade = add(point, add(mul(side, sign * width * fraction), mul(direction, .3 * fraction)))
                        blade = add(blade, (0, 0, -.28 * fraction * fraction))
                        half_width = .10 * (1 - fraction) + .016
                        self.quad('Building_Palms', 'Leaves', sub(last, mul(leaf_side, half_width)),
                                  sub(blade, mul(leaf_side, half_width)), add(blade, mul(leaf_side, half_width)),
                                  add(last, mul(leaf_side, half_width)))
                        last = blade
                previous = point

    def save(self) -> dict[str, object]:
        SCRATCH.mkdir(parents=True, exist_ok=True)
        records = []
        for name, tile in sorted(self.tiles.items()):
            path = SCRATCH / f'{name}.mesh'
            path.write_bytes(b'FFLVM1\0\0' + struct.pack('<I', len(tile.triangles) // 100) + tile.triangles)
            records.append({'name': name, 'file': path.name, 'materials': tile.materials, 'bounds': tile.minimum + tile.maximum,
                            'triangles': len(tile.triangles) // 100, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        (DATA / 'night_lights.csv').write_text('\n'.join(','.join(f'{v:.3f}' for v in world(p)) for p in self.lights) + '\n')
        (SCRATCH / 'braking_boards.json').write_text(json.dumps(self.boards, indent=2) + '\n')
        recipe = json.loads((SOURCE / 'layout-corrections.json').read_text())
        registered = []
        for turn in recipe['turns']:
            x, y = (value * self.scale for value in turn['near_source_xy_m'])
            sample = min(self.road, key=lambda p: (p.x - x) ** 2 + (p.y - y) ** 2)
            registered.append({'turn': turn['number'], 'station_m': sample.station,
                               'direction': 'left' if turn['direction'] > 0 else 'right',
                               'source_anchor_residual_m': round(math.hypot(sample.x - x, sample.y - y), 3)})
        registration = {'reference': '2025 FIA event notes circuit map V2, issued 2025-11-19',
                        'controls': 'layout-corrections.json',
                        'registration_note': 'Anchors express observed turn order on the OSM street frame, not an independently surveyed set of apex positions. Residual is sampling distance to authored control, not absolute geospatial accuracy.',
                        'turns': registered}
        (SOURCE / 'turn-registration.json').write_text(json.dumps(registration, indent=2) + '\n')
        manifest: dict[str, object] = {'tiles': records, 'landmarks': self.landmarks,'vegetation':self.vegetation}
        (SCRATCH / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        return manifest


def generate() -> dict[str, object]:
    scenery = Scenery()
    scenery.track()
    scenery.terrain_mesh()
    scenery.city()
    return scenery.save()


if __name__ == '__main__':
    generate()
