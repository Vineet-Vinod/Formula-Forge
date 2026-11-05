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

from lasvegas_dataclasses import (
    LandmarkProfile,
    MeshTile,
    Point,
    RoadStation,
    TerrainGrid,
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
        if len(self.road) != 6144:
            raise ValueError('Run make check to export the canonical Las Vegas samples')
        self.detail_stride = len(self.road) // 1536
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
        profiles = json.loads((SOURCE / 'landmark-architecture.json').read_text())['profiles']
        self.profiles = {int(key): LandmarkProfile(**value) for key, value in profiles.items()}
        self.scale = provenance['route']['uniform_scale']

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

    def track(self) -> None:
        raw = (DATA / 'drive_surface.bin').read_bytes()
        if raw[:8] != b'FFSURF1\0':
            raise ValueError('Invalid driving surface')
        triangles = list(struct.iter_unpack('<9f', raw[12:]))
        for values in triangles:
            a, b, c = values[:3], values[3:6], values[6:9]
            if cross(sub(b, a), sub(c, a))[2] < 0:
                b, c = c, b
            self.triangle('Tile_Road', 'Road', a, b, c,
                          tuple((p[0] / 4, p[1] / 4) for p in (a, b, c)))
        barriers = list(csv.DictReader((SCRATCH / 'barriers.csv').open()))
        wall_coordinates: dict[tuple[float, float], tuple[float, bool]] = {}
        for barrier in barriers:
            ax, ay, bx, by, bottom, top, radius = (float(value) for value in barrier.values())
            a, b = (ax, ay, bottom), (bx, by, bottom)
            self.beam('Tile_Protection', 'Concrete', add(a, (0, 0, (top - bottom) / 2)),
                      add(b, (0, 0, (top - bottom) / 2)), radius * 2, top - bottom)
            sample, _ = self.nearest((ax + bx) / 2, (ay + by) / 2)
            heading = sample.station
            panel = 'WallGold' if 660 < heading < 1450 else 'WallPink' if 3400 < heading < 4200 else ('WallBlue' if 2200 < heading < 3400 else 'WallDark')
            inward = mul(norm((sample.x - (ax + bx) / 2, sample.y - (ay + by) / 2, 0)), radius + .012)
            panel_a, panel_b = add(a, inward), add(b, inward)
            start_key, end_key = (round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))
            default_reverse = (ax - sample.x) * sample.ty - (ay - sample.y) * sample.tx > 0
            distance, reverse = wall_coordinates.get(start_key, (0.0, default_reverse))
            span = math.dist(a, b)
            wall_coordinates[end_key] = distance + span, reverse
            if reverse:
                panel_a, panel_b = panel_b, panel_a
            phase = -(distance + span) / 8 if reverse else distance / 8
            self.banner(add(panel_a, (0, 0, .02)), add(panel_b, (0, 0, .02)), .88, panel, 'Tile_Protection', phase, span / 8)
            self.banner(add(a, (0, 0, top - bottom)), add(b, (0, 0, top - bottom)), 2.55, 'Fence', 'Tile_Protection')
            if int(sample.station / 8) != int((sample.station - LENGTH / len(self.road)) / 8):
                self.beam('Tile_Protection', 'Steel', add(a, (0, 0, top - bottom)), add(a, (0, 0, 3.5)), .065)
                self.beam('Tile_Protection', 'Steel', add(a, (0, 0, 3.5)), add(add(a, (0, 0, 4.05)), mul(inward, 2.8)), .065)
            upper_a, upper_b = add(add(a, (0, 0, 4.05)), mul(inward, 2.8)), add(add(b, (0, 0, 4.05)), mul(inward, 2.8))
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
                # Asphalt shoulder reaches the physical wall; no unmodelled slit outside the white line.
                outer = sample.point(sign * (sample.half_width + .85 + (sample.left_shoulder if sign > 0 else sample.right_shoulder)), -.012)
                outer_next = nxt.point(sign * (nxt.half_width + .85 + (nxt.left_shoulder if sign > 0 else nxt.right_shoulder)), -.012)
                a, b, c, d = sample.point(lane), nxt.point(lane_next), outer_next, outer
                if sign > 0:
                    a, b, c, d = d, c, b, a
                self.quad('Tile_Road', 'Runoff', a, b, c, d, 1, 1)
            if 1962 < sample.station < 2047:
                lane = sample.half_width + sample.left_shoulder + .4
                next_lane = nxt.half_width + nxt.left_shoulder + .4
                self.quad('Tile_Road', 'Red', sample.point(lane, .015), sample.point(lane + .5, .015),
                          nxt.point(next_lane + .5, .015), nxt.point(next_lane, .015))
            for apex, outside in ((688, 1), (1999, 1), (3289, -1), (3748, 1), (3954, 1), (4926, 1)):
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
            if abs(bend) > .13:
                sign = -1 if bend > 0 else 1
                a = sample.point(sign * (sample.half_width + .02), .025)
                b = nxt.point(sign * (nxt.half_width + .02), .025)
                c = nxt.point(sign * (nxt.half_width + .78), .025)
                d = sample.point(sign * (sample.half_width + .78), .025)
                if sign > 0:
                    a, b, c, d = d, c, b, a
                span = (nxt.station - sample.station) % LENGTH
                stripes = max(1, round(span))
                for stripe in range(stripes):
                    t0, t1 = stripe / stripes, (stripe + 1) / stripes
                    paint = 'Red' if int(sample.station + span * (t0 + t1) / 2) % 2 else 'White'
                    start_outer = add(a, mul(sub(b, a), t0))
                    end_outer = add(a, mul(sub(b, a), t1))
                    end_inner = add(d, mul(sub(c, d), t1))
                    start_inner = add(d, mul(sub(c, d), t0))
                    self.quad('Tile_Road', paint, start_outer, end_outer, end_inner, start_inner)
            if 1580 < sample.station < 1950 and index % (4 * self.detail_stride) == 0:
                for side in (-1, 1):
                    lane_a, lane_b = side * 2.5, side * 4.5
                    self.quad('Tile_Road', 'White', sample.point(lane_a, .016), sample.point(lane_b, .016),
                              add(sample.point(lane_b, .016), (sample.tx * .12, sample.ty * .12, 0)),
                              add(sample.point(lane_a, .016), (sample.tx * .12, sample.ty * .12, 0)))
                    self.quad('Tile_Road', 'White', sample.point(lane_b, .016), nxt.point(lane_b, .016),
                              nxt.point(lane_b - side * .10, .016), sample.point(lane_b - side * .10, .016))
            if index % (12 * self.detail_stride) == 0:
                for side in (-1, 1):
                    self.floodlight(sample, side)
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
        self.gantry(1830, 'VegasSign')
        for station in (670, 2050, 3350, 4150, 4990, 6080):
            self.gantry(station, 'RaceSign')
        for apex, outside in ((688, 1), (1999, 1), (3289, -1), (3748, 1), (3954, 1), (4926, 1)):
            for distance in (150, 100, 50):
                station = apex - distance
                sample = min(self.road, key=lambda sample: abs(sample.station - station))
                shoulder = sample.left_shoulder if outside > 0 else sample.right_shoulder
                lane = outside * (sample.half_width + shoulder - .1)
                a, b = sample.point(lane - .65, 1.25), sample.point(lane + .65, 1.25)
                offset = (-sample.tx * .12, -sample.ty * .12, 0.)
                self.banner(add(a, offset), add(b, offset), 1.25, str(distance))
                self.beam('Tile_Detail', 'Steel', sample.point(outside * (sample.half_width + shoulder + .85), 1.9),
                          sample.point(lane, 1.9), .05)
                self.boards.append({'apex': apex, 'distance': distance, 'station': sample.station, 'side': outside})

    def floodlight(self, sample: RoadStation, sign: int) -> None:
        shoulder = sample.left_shoulder if sign > 0 else sample.right_shoulder
        base = sample.point(sign * (sample.half_width + shoulder + 1.4))
        high = add(base, (0, 0, 11.5))
        arm = sample.point(sign * (sample.half_width + .8), 11.2)
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

    def gantry(self, station: float, material: str) -> None:
        sample = min(self.road, key=lambda sample: abs(sample.station - station))
        left = sample.point(sample.half_width + sample.left_shoulder + 1.6)
        right = sample.point(-(sample.half_width + sample.right_shoulder + 1.6))
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
        # The sign faces the approaching driver and reads once across the gantry.
        offset = (-sample.tx * .4, -sample.ty * .4, 0)
        self.banner(add(right, add(offset, (0, 0, 5.8))), add(left, add(offset, (0, 0, 5.8))), 1.7, material)
        if station == 1830:
            for lane in (-1.8, -.9, 0, .9, 1.8):
                a = sample.point(lane, 5.2)
                self.box('Tile_Detail', 'Black', a, .24, .5, .65, math.atan2(sample.ty, sample.tx))
                self.box('Tile_Detail', 'Red', add(a, (-sample.tx * .14, -sample.ty * .14, 0)), .02, .24, .24,
                         math.atan2(sample.ty, sample.tx))

    def terrain_mesh(self) -> None:
        grid = self.terrain
        step = 12.0
        for y_index in range(int((grid.rows - 1) * grid.step / step)):
            y = grid.y + y_index * step
            for x_index in range(int((grid.columns - 1) * grid.step / step)):
                x = grid.x + x_index * step
                points = [(x, y), (x + step, y), (x + step, y + step), (x, y + step)]
                samples = [self.nearest(px, py) for px, py in points]
                if any(distance < sample.half_width + max(sample.left_shoulder, sample.right_shoulder) + 1 for sample, distance in samples):
                    continue
                corners = [(px, py, self.ground(px, py)) for px, py in points]
                self.quad('Tile_Ground', 'CityGround', corners[0], corners[1], corners[2], corners[3], step / 5, step / 5)
        # A finer strip joins the road shoulder to the city sheet, without crossing the road itself.
        for index, sample in enumerate(self.road):
            nxt = self.road[(index + 1) % len(self.road)]
            for sign in (-1, 1):
                shoulder = sample.left_shoulder if sign > 0 else sample.right_shoulder
                shoulder_next = nxt.left_shoulder if sign > 0 else nxt.right_shoulder
                for inner, outer in [(.7, 8), (8, 24)]:
                    a = sample.point(sign * (sample.half_width + shoulder + inner))
                    b = nxt.point(sign * (nxt.half_width + shoulder_next + inner))
                    c = nxt.point(sign * (nxt.half_width + shoulder_next + outer))
                    d = sample.point(sign * (sample.half_width + shoulder + outer))
                    strip = [a, b, c, d]
                    if any(self.nearest(p[0], p[1])[1] < self.nearest(p[0], p[1])[0].half_width + .6 for p in strip):
                        continue
                    corners = [(p[0], p[1], self.ground(p[0], p[1]) - .03) for p in strip]
                    if sign > 0:
                        corners.reverse()
                    self.quad('Tile_Ground', 'CityGround', corners[0], corners[1], corners[2], corners[3], 1, 2)

    def building(self, ring: list[tuple[float, float]], height: float, material: str, name: str, osm_id: int) -> None:
        profile = self.profiles.get(osm_id)
        if profile is not None:
            height, material = profile.height_m - profile.crown_m, profile.facade
            name = name or profile.name
        center = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        z = min(self.ground(*p) for p in ring)
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
        if area < 0:
            ring.reverse()
        face_normals = [norm((b[1] - a[1], a[0] - b[0], 0)) for a, b in zip(ring, ring[1:] + ring[:1])]
        def corner_normal(index: int, face: Point) -> Point:
            previous, nxt = face_normals[index - 1], face_normals[index % len(ring)]
            return norm(add(previous, nxt)) if sum(a * b for a, b in zip(previous, nxt)) > .9 else face
        facade_u = 0.0
        for index, a in enumerate(ring):
            b = ring[(index + 1) % len(ring)]
            width = math.dist(a, b)
            low_a, low_b = (*a, z), (*b, z)
            top_a, top_b = (*a, z + height), (*b, z + height)
            na, nb = corner_normal(index, face_normals[index]), corner_normal(index + 1, face_normals[index])
            u, v = width / 32, -height / 28.8
            self.triangle('Building_City', material, low_a, low_b, top_b, ((facade_u, 0), (facade_u + u, 0), (facade_u + u, v)), (na, nb, nb))
            self.triangle('Building_City', material, low_a, top_b, top_a, ((facade_u, 0), (facade_u + u, v), (facade_u, v)), (na, nb, na))
            facade_u += u
            self.beam('Building_City', 'IlluminatedCream' if material == 'BronzeFacade' else 'Cream', top_a, top_b, .4, .7)
            if profile is None and height > 30 and material == 'CreamFacade':
                for floor in range(4, int(height), 14):
                    self.beam('Building_City', 'Cream', (*a, z + floor), (*b, z + floor), .16, .3)
        if profile is not None:
            self.hotel_architecture(ring, z, height, profile)
        for keyword, label in [('Bellagio Las Vegas', 'Bellagio'), ('Venetian Tower', 'Venetian'),
                               ('Palazzo Tower', 'Palazzo'), ('Wynn Las Vegas', 'Wynn'),
                               ('Le Boulevard At Paris', 'Paris'), ('Cosmopolitan', 'Cosmopolitan'),
                               ('Planet Hollywood Resort', 'Planet')]:
            if profile is not None or keyword not in name or height < 60:
                continue
            edge = min(range(len(ring)), key=lambda i: self.nearest((ring[i][0] + ring[(i + 1) % len(ring)][0]) / 2,
                                                                   (ring[i][1] + ring[(i + 1) % len(ring)][1]) / 2)[1])
            a, b = ring[edge], ring[(edge + 1) % len(ring)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            span = math.hypot(dx, dy)
            if span < .1:
                continue
            center_x, center_y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            half = min(max(p[0] for p in ring) - min(p[0] for p in ring),
                       max(p[1] for p in ring) - min(p[1] for p in ring), 44) * .43
            center_x += dy / span * .15
            center_y -= dx / span * .15
            left = center_x - dx / span * half, center_y - dy / span * half, z + height - 7
            right = center_x + dx / span * half, center_y + dy / span * half, z + height - 7
            self.banner(left, right, 3.0, label, 'Building_City')
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
                self.triangle('Building_City', 'Roof', (*a, z + height), (*b, z + height), (*c, z + height))
                indices.remove(ib)
                found = True
                break
            if not found:
                break
        if name:
            self.landmarks.append({'name': name, 'osm_id': osm_id, 'x': center[0], 'y': center[1], 'height_m': height})

    def hotel_architecture(self, ring: list[tuple[float, float]], z: float, height: float,
                           profile: LandmarkProfile) -> None:
        kind = 'Building_Hotel'
        cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        edges = list(zip(ring, ring[1:] + ring[:1]))
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
                        a[1] + (b[1] - a[1]) * t + normal[1] * offset, z + level)
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
                self.quad(kind, 'Copper' if profile.style == 'dome' else 'Roof' if profile.style == 'mansard' else trim, pa, pb, qb, qa)
                self.beam(kind, 'IlluminatedCream' if classical else trim, qa, qb, .18, .25)
        # Road-facing fascia and lower entrance signs remain visible from the cockpit.
        sign_edges = [edge for edge in edges if math.dist(*edge) > 14] or edges
        a, b = min(sign_edges, key=lambda edge: self.nearest((edge[0][0] + edge[1][0]) / 2,
                                                      (edge[0][1] + edge[1][1]) / 2)[1])
        span = math.dist(a, b)
        if span < 2:
            return
        direction = ((b[0] - a[0]) / span, (b[1] - a[1]) / span, 0.)
        outward = direction[1], -direction[0], 0.
        center = add(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), mul(outward, .85))
        if classical:
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
        for level, width in ((height - 5, min(span * .7, 42)), (7, min(span * .75, 24))):
            middle = add(center, (0, 0, level))
            self.banner(sub(middle, mul(direction, width / 2)), add(middle, mul(direction, width / 2)),
                        min(3.8, width / 6), profile.name, kind)
        self.landmarks.append({'name': profile.name + ' architectural profile', 'height_m': profile.height_m,
                               'style': profile.style, 'x': cx, 'y': cy})

    def race_decor(self) -> None:
        for station, label, side in ((4700, 'Palazzo', -1), (5100, 'Venetian', -1),
                                     (5050, 'TreasureIsland', 1), (4520, 'Wynn', 1),
                                     (5660, 'Caesars', 1), (5970, 'Bellagio', 1),
                                     (6030, 'Paris', -1), (900, 'Planet', -1),
                                     (720, 'Cosmopolitan', -1), (5400, 'Flamingo', -1)):
            sample = min(self.road, key=lambda p: abs(p.station - station))
            shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
            point = sample.point(side * (sample.half_width + shoulder + 6), .2)
            heading = math.atan2(sample.ty, sample.tx)
            self.box('Tile_Entrance', 'Cream', add(point, (0, 0, 4)), .8, 1.4, 8, heading)
            direction = (sample.ty, -sample.tx, 0.)
            middle = add(point, (-sample.tx * .9, -sample.ty * .9, 5.7))
            self.banner(sub(middle, mul(direction, 4.8)), add(middle, mul(direction, 4.8)), 2.2, label)
            for offset in (-3, 3):
                base = add(point, (sample.tx * offset, sample.ty * offset, .2))
                self.box('Tile_Entrance', 'Cream', base, 2, 2, .65, heading)
                self.box('Tile_Entrance', 'Leaves', add(base, (0, 0, .5)), 1.7, 1.7, .6, heading)
        for station in (615, 1960, 3235, 3710, 3910, 4870):
            sample = min(self.road, key=lambda p: abs(p.station - station))
            lane = sample.half_width + sample.left_shoulder + 3.5
            base = sample.point(lane)
            heading = math.atan2(sample.ty, sample.tx)
            self.box('Tile_Marshal', 'White', add(base, (0, 0, 1.2)), 3.2, 2, 2.4, heading)
            self.box('Tile_Marshal', 'Canopy', add(base, (0, 0, 2.5)), 3.7, 2.5, .15, heading)
            front = add(base, (-sample.ty * 1.1, sample.tx * 1.1, 0))
            self.box('Tile_Marshal', 'Glass', add(front, (0, 0, 1.7)), 2.4, .06, .7, heading)
            self.box('Tile_Marshal', 'Orange', add(base, (sample.tx * 2.8, sample.ty * 2.8, .6)), .8, .8, 1.2, heading)
            self.beam('Tile_Marshal', 'Steel', add(base, (0, 0, 2.4)), add(base, (0, 0, 4)), .08)
            self.box('Tile_Marshal', 'Black', add(base, (0, 0, 3.6)), .7, .15, .7, heading)
        for station, label in ((1830, 'EastHarmon'), (3410, 'SphereZone'), (4080, 'Sands'), (5520, 'Strip'), (1200, 'WestHarmon')):
            sample = min(self.road, key=lambda p: abs(p.station - station))
            for side in (-1, 1):
                shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
                lane = side * (sample.half_width + shoulder + 1)
                base = sample.point(lane, 4.6)
                direction = (sample.ty, -sample.tx, 0.)
                panel = add(base, (-sample.tx * .15, -sample.ty * .15, 0.))
                self.banner(sub(panel, mul(direction, 2.5)), add(panel, mul(direction, 2.5)), 1.1, label)
                self.beam('Tile_Detail', 'Steel', sample.point(lane), add(base, (0, 0, 1.1)), .09)

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
            if any(self.nearest(*point)[1] < self.nearest(*point)[0].half_width + 7 for point in ring):
                continue
            if any(self.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)[1] < 18 for a, b in zip(ring, ring[1:] + ring[:1])):
                continue
            height = float(tags.get('height', str(float(tags.get('building:levels', '3')) * 3.4)).split()[0])
            material = 'BronzeFacade' if any(word in name for word in ('Wynn', 'Trump')) else 'CreamFacade'
            if any(word in name for word in ('Cosmopolitan', 'Horseshoe', 'Planet Hollywood', 'Hilton')):
                material = 'BlueFacade'
            if element['id'] == 43875964:
                self.campanile(ring, element['id'])
            else:
                self.building(ring, height, material, name, element['id'])
        self.sphere()
        self.eiffel()
        self.wheel()
        self.pits()
        self.bridges()
        self.race_decor()
        for a, b, sign in [(1500, 1900, 1), (3350, 3500, 1), (3700, 3960, 1), (5500, 5750, -1)]:
            self.grandstand(a, b, sign)
        for index, sample in enumerate(self.road[::self.detail_stride]):
            if index % 10 or not (sample.station < 700 or sample.station > 4650):
                continue
            for sign in (-1, 1):
                position = sample.point(sign * (sample.half_width + 11 + (index % 3) * 2))
                self.palm((position[0], position[1], self.ground(position[0], position[1])), 8 + index % 5)

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
            if not 1530 < sample.station < 1940:
                continue
            nxt = road[(index + 1) % len(road)]
            near = sample.half_width + 8
            near_next = nxt.half_width + 8
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

    def grandstand(self, start: float, end: float, sign: int) -> None:
        road = self.road[::self.detail_stride]
        for index in range(0, len(road), 2):
            sample = road[index]
            if not start < sample.station < end:
                continue
            nxt = road[(index + 2) % len(road)]
            base = sample.half_width + 7.5
            next_base = nxt.half_width + 7.5
            for row in range(18):
                lane, lane_next = sign * (base + row * 1.1), sign * (next_base + row * 1.1)
                a, b = sample.point(lane, 1.4 + row * .45), nxt.point(lane_next, 1.4 + row * .45)
                self.spectators(a, b, row, 'Building_Crowd_Stands')
                self.beam('Building_Stands', 'Steel', add(a, (0, 0, -.1)), add(b, (0, 0, -.1)), 1.2, .12)
            if index % 6 == 0:
                rear = sample.point(sign * (base + 19), 9.8)
                foot = sample.point(sign * (base + 19))
                self.beam('Building_Stands', 'Steel', foot, rear, .18)
                self.beam('Building_Stands', 'Steel', sample.point(sign * base, .8), rear, .16)
                self.beam('Building_Stands', 'Steel', foot, nxt.point(sign * (next_base + 19), 9.8), .10)
            if start == 1500:
                front = sample.point(sign * (base - 1.5), 12.4)
                rear = sample.point(sign * (base + 20), 14.2)
                front_next = nxt.point(sign * (next_base - 1.5), 12.4)
                rear_next = nxt.point(sign * (next_base + 20), 14.2)
                self.quad('Building_Stands', 'Canopy', front, front_next, rear_next, rear)
                self.quad('Building_Stands', 'Canopy', rear, rear_next, front_next, front)
                self.beam('Building_Stands', 'IlluminatedCream', front, front_next, .12)
                for depth in (4, 8, 12, 16):
                    height = 12.4 + depth / 21.5 * 1.8 - .08
                    self.beam('Building_Stands', 'Steel', sample.point(sign * (base - 1.5 + depth), height),
                              nxt.point(sign * (next_base - 1.5 + depth), height), .065)
                self.beam('Building_Stands', 'Steel', rear, front, .15)
                self.beam('Building_Stands', 'Steel', add(rear, (0, 0, -.8)), front, .10)
                if index % 6 == 0:
                    self.beam('Building_Stands', 'Steel', foot, rear, .24)
                    self.beam('Building_Stands', 'Steel', rear, front, .18)
                    self.beam('Building_Stands', 'Steel', add(rear, (0, 0, -1.2)), front, .12)
                    self.box('Building_Stands', 'Lamp', add(front, (0, 0, -.18)), .7, .6, .05)
            self.beam('Building_Stands', 'Steel', sample.point(sign * (base + 19), 10.5),
                      nxt.point(sign * (next_base + 19), 10.5), .07)

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
        for frond in range(19):
            angle = frond * math.tau / 19 + base[0] % 1
            direction = math.cos(angle), math.sin(angle), 0.0
            side = -math.sin(angle), math.cos(angle), 0.0
            length = 3.4 + (frond % 3) * .4
            previous = top
            for segment in range(1, 17):
                t = segment / 16
                point = add(top, add(mul(direction, length * t), (0, 0, 2 * math.sin(t * math.pi) - t * 1.7)))
                self.beam('Building_Palms', 'Leaves', previous, point, .035)
                width = .8 * math.sin(t * math.pi) + .04
                for sign in (-1, 1):
                    last = point
                    leaf_side = norm(cross(add(mul(side, sign), mul(direction, .25)), (0, 0, 1)))
                    for blade_step in range(1, 4):
                        fraction = blade_step / 3
                        blade = add(point, add(mul(side, sign * width * fraction), mul(direction, .3 * fraction)))
                        blade = add(blade, (0, 0, -.28 * fraction * fraction))
                        half_width = .022 * (1 - fraction) + .003
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
        manifest: dict[str, object] = {'tiles': records, 'landmarks': self.landmarks}
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
