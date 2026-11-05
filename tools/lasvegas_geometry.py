"""Original Las Vegas scenery in the registered source frame (metres, east/north/up)."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import struct
from pathlib import Path

from lasvegas_dataclasses import MeshTile, Point, RoadStation, TerrainGrid

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
        if len(self.road) != 1536:
            raise ValueError('Run make check to export the canonical Las Vegas samples')
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
                                   a.tx, a.ty, a.half_width + t * (b.half_width - a.half_width), a.bank)
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
        blend = max(0.0, min(1.0, (distance - sample.half_width - 1) / 14))
        blend = blend * blend * (3 - 2 * blend)
        return sample.z * (1 - blend) + z * blend - .055

    def tile(self, kind: str, point: Point) -> MeshTile:
        category = 'Tile_Street' if kind.startswith('Tile_') else ('Building_Crowd' if kind.startswith('Building_Crowd') else 'Building_City')
        step = 240 if category == 'Tile_Street' else 360
        name = f'{category}_{math.floor(point[0] / step):02d}_{math.floor(point[1] / step):02d}'.replace('-', 'm')
        return self.tiles.setdefault(name, MeshTile())

    def triangle(self, kind: str, material: str, a: Point, b: Point, c: Point,
                 uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1))) -> None:
        normal = cross(sub(b, a), sub(c, a))
        if sum(value * value for value in normal) < 1e-12:
            return
        normal = norm(normal)
        tile = self.tile(kind, mul(add(add(a, b), c), 1 / 3))
        if material not in tile.materials:
            tile.materials.append(material)
        tile.triangles.extend(struct.pack('<I', tile.materials.index(material)))
        n = -normal[1], -normal[0], normal[2]
        for point, texcoord in zip((a, b, c), uv):
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

    def banner(self, a: Point, b: Point, height: float, material: str, kind: str = 'Tile_Detail') -> None:
        u = math.dist(a, b) / .5 if material == 'Fence' else 1
        v = height / .5 if material == 'Fence' else 1
        top_a, top_b = add(a, (0, 0, height)), add(b, (0, 0, height))
        self.triangle(kind, material, top_a, top_b, b, ((0, 0), (u, 0), (u, v)))
        self.triangle(kind, material, top_a, b, a, ((0, 0), (u, v), (0, v)))
        self.triangle(kind, material, top_b, top_a, a, ((u, 0), (0, 0), (0, v)))
        self.triangle(kind, material, top_b, a, b, ((u, 0), (0, v), (u, v)))

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
        for barrier in barriers:
            ax, ay, bx, by, bottom, top, radius = (float(value) for value in barrier.values())
            a, b = (ax, ay, bottom), (bx, by, bottom)
            self.beam('Tile_Protection', 'Concrete', add(a, (0, 0, (top - bottom) / 2)),
                      add(b, (0, 0, (top - bottom) / 2)), radius * 2, top - bottom)
            sample, _ = self.nearest((ax + bx) / 2, (ay + by) / 2)
            heading = sample.station
            panel = 'WallGold' if 3400 < heading < 4200 else 'WallDark'
            inward = mul(norm((sample.x - (ax + bx) / 2, sample.y - (ay + by) / 2, 0)), radius + .012)
            panel_a, panel_b = add(a, inward), add(b, inward)
            if (ax - sample.x) * sample.ty - (ay - sample.y) * sample.tx > 0:
                panel_a, panel_b = panel_b, panel_a
            self.banner(add(panel_a, (0, 0, .02)), add(panel_b, (0, 0, .02)), .88, panel, 'Tile_Protection')
            self.banner(add(a, (0, 0, top - bottom)), add(b, (0, 0, top - bottom)), 2.55, 'Fence', 'Tile_Protection')
            if int(sample.station / 4) % 2 == 0:
                self.beam('Tile_Protection', 'Steel', add(a, (0, 0, top - bottom)), add(a, (0, 0, 3.75)), .065)
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
                outer = sample.point(sign * (sample.half_width + 5), -.012)
                outer_next = nxt.point(sign * (nxt.half_width + 5), -.012)
                a, b, c, d = sample.point(lane), nxt.point(lane_next), outer_next, outer
                if sign > 0:
                    a, b, c, d = d, c, b, a
                self.quad('Tile_Road', 'Runoff', a, b, c, d, 1, 1)
            before = self.road[(index - 4) % len(self.road)]
            after = self.road[(index + 4) % len(self.road)]
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
            if 1580 < sample.station < 1950 and index % 4 == 0:
                for side in (-1, 1):
                    lane_a, lane_b = side * 2.5, side * 4.5
                    self.quad('Tile_Road', 'White', sample.point(lane_a, .016), sample.point(lane_b, .016),
                              add(sample.point(lane_b, .016), (sample.tx * .12, sample.ty * .12, 0)),
                              add(sample.point(lane_a, .016), (sample.tx * .12, sample.ty * .12, 0)))
                    self.quad('Tile_Road', 'White', sample.point(lane_b, .016), nxt.point(lane_b, .016),
                              nxt.point(lane_b - side * .10, .016), sample.point(lane_b - side * .10, .016))
            if index % 12 == 0:
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
        for station in (650, 2050, 3370, 4180, 5000, 6080):
            for distance in (150, 100, 50):
                sample = min(self.road, key=lambda sample: abs(sample.station - (station - distance)))
                a = sample.point(-(sample.half_width + 4.9), 1.5)
                b = sample.point(-(sample.half_width + 4.1), 1.5)
                self.quad('Tile_Detail', str(distance), add(a, (0, 0, 1.1)), add(b, (0, 0, 1.1)), b, a)

    def floodlight(self, sample: RoadStation, sign: int) -> None:
        base = sample.point(sign * (sample.half_width + 5.7))
        high = add(base, (0, 0, 10.5))
        arm = sample.point(sign * (sample.half_width + 2.5), 10.1)
        self.beam('Tile_Detail', 'Steel', base, high, .12)
        self.beam('Tile_Detail', 'Steel', high, arm, .09)
        self.box('Tile_Detail', 'Black', arm, 1.1, .45, .16, math.atan2(sample.ty, sample.tx))
        self.box('Tile_Detail', 'Lamp', add(arm, (0, 0, -.09)), .95, .4, .02, math.atan2(sample.ty, sample.tx))

    def gantry(self, station: float, material: str) -> None:
        sample = min(self.road, key=lambda sample: abs(sample.station - station))
        left = sample.point(sample.half_width + 5.4)
        right = sample.point(-(sample.half_width + 5.4))
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
                if any(distance < sample.half_width + 4 for sample, distance in samples):
                    continue
                corners = [(px, py, self.ground(px, py)) for px, py in points]
                self.quad('Tile_Ground', 'CityGround', corners[0], corners[1], corners[2], corners[3], step / 5, step / 5)
        # A finer strip joins the road shoulder to the city sheet, without crossing the road itself.
        for index, sample in enumerate(self.road):
            nxt = self.road[(index + 1) % len(self.road)]
            for sign in (-1, 1):
                for inner, outer in [(4.8, 12), (12, 24)]:
                    a, b = sample.point(sign * (sample.half_width + inner)), nxt.point(sign * (nxt.half_width + inner))
                    c, d = nxt.point(sign * (nxt.half_width + outer)), sample.point(sign * (sample.half_width + outer))
                    strip = [a, b, c, d]
                    if any(self.nearest(p[0], p[1])[1] < self.nearest(p[0], p[1])[0].half_width + 3 for p in strip):
                        continue
                    corners = [(p[0], p[1], self.ground(p[0], p[1]) - .03) for p in strip]
                    if sign > 0:
                        corners.reverse()
                    self.quad('Tile_Ground', 'CityGround', corners[0], corners[1], corners[2], corners[3], 1, 2)

    def building(self, ring: list[tuple[float, float]], height: float, material: str, name: str, osm_id: int) -> None:
        center = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        z = min(self.ground(*p) for p in ring)
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
        if area < 0:
            ring.reverse()
        for index, a in enumerate(ring):
            b = ring[(index + 1) % len(ring)]
            width = math.dist(a, b)
            low_a, low_b = (*a, z), (*b, z)
            top_a, top_b = (*a, z + height), (*b, z + height)
            self.quad('Building_City', material, low_a, low_b, top_b, top_a, width / 4.0, height / 3.6)
            self.beam('Building_City', 'Cream', top_a, top_b, .4, .7)
            if height > 30:
                for floor in range(4, int(height), 14):
                    self.beam('Building_City', 'Cream', (*a, z + floor), (*b, z + floor), .16, .3)
        for keyword, label in [('Bellagio Las Vegas', 'Bellagio'), ('Venetian Tower', 'Venetian'),
                               ('Palazzo Tower', 'Palazzo'), ('Wynn Las Vegas', 'Wynn'),
                               ('Le Boulevard At Paris', 'Paris'), ('Cosmopolitan', 'Cosmopolitan'),
                               ('Planet Hollywood Resort', 'Planet')]:
            if keyword not in name or height < 60:
                continue
            edge = min(range(len(ring)), key=lambda i: self.nearest((ring[i][0] + ring[(i + 1) % len(ring)][0]) / 2,
                                                                   (ring[i][1] + ring[(i + 1) % len(ring)][1]) / 2)[1])
            a, b = ring[edge], ring[(edge + 1) % len(ring)]
            dx, dy = b[0] - a[0], b[1] - a[1]
            span = math.hypot(dx, dy)
            if span < 4:
                continue
            center_x, center_y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            half = min(span * .43, 22)
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

    def city(self) -> None:
        payload = json.loads(gzip.decompress((SOURCE / 'skyline.osm.json.gz').read_bytes()))
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
            if len(ring) > 120:
                ring = ring[::2]
            if any(self.nearest(*point)[1] < self.nearest(*point)[0].half_width + 7 for point in ring):
                continue
            if any(self.nearest((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)[1] < 18 for a, b in zip(ring, ring[1:] + ring[:1])):
                continue
            height = float(tags.get('height', str(float(tags.get('building:levels', '3')) * 3.4)).split()[0])
            material = 'BronzeFacade' if any(word in name for word in ('Wynn', 'Trump', 'Venetian', 'Palazzo')) else 'CreamFacade'
            if any(word in name for word in ('Cosmopolitan', 'Horseshoe', 'Planet Hollywood', 'Hilton')):
                material = 'BlueFacade'
            self.building(ring, height, material, name, element['id'])
        self.sphere()
        self.eiffel()
        self.wheel()
        self.pits()
        for a, b, sign in [(1500, 1970, 1), (3350, 3500, 1), (3700, 3960, 1), (5500, 5750, -1)]:
            self.grandstand(a, b, sign)
        for index, sample in enumerate(self.road):
            if index % 10 or not (sample.station < 700 or sample.station > 4650):
                continue
            for sign in (-1, 1):
                position = sample.point(sign * (sample.half_width + 11 + (index % 3) * 2))
                self.palm((position[0], position[1], self.ground(position[0], position[1])), 8 + index % 5)

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
                self.beam('Building_HighRoller', 'White', a, b, .35)
            if index % 4 == 0:
                a = x + radius * math.cos(angle), y, center[2] + radius * math.sin(angle)
                self.beam('Building_HighRoller', 'Steel', center, a, .045)
                self.box('Building_HighRoller', 'BlueFacade', a, 4.8, 4.8, 3.4)
        self.landmarks.append({'name': 'High Roller', 'x': x, 'y': y, 'height_m': 167})

    def pits(self) -> None:
        for index, sample in enumerate(self.road):
            if not 1530 < sample.station < 1940:
                continue
            nxt = self.road[(index + 1) % len(self.road)]
            near = sample.half_width + 8
            near_next = nxt.half_width + 8
            # Pit lane, garages, three hospitality decks and cantilever roof.
            self.quad('Tile_Paddock', 'Runoff', sample.point(-near), nxt.point(-near_next), nxt.point(-near_next - 13), sample.point(-near - 13), 1, 3)
            for height in (0, 5.2, 10.5, 15.6):
                self.beam('Building_Paddock', 'Cream', sample.point(-near - 24, height), nxt.point(-near_next - 24, height), 17, .5)
            self.banner(sample.point(-near - 22, .3), nxt.point(-near_next - 22, .3), 4.6, 'Garage', 'Building_Paddock')
            for height in (5.5, 10.8):
                self.banner(sample.point(-near - 28, height), nxt.point(-near_next - 28, height), 3.5, 'BlueFacade', 'Building_Paddock')
                self.banner(sample.point(-near - 15.4, height), nxt.point(-near_next - 15.4, height), 1.0, 'RaceSign', 'Building_Paddock')
            self.beam('Building_Paddock', 'Roof', sample.point(-near - 24, 18.8), nxt.point(-near_next - 24, 18.8), 22, .7)
            if index % 2 == 0:
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 16, 4.8), sample.point(-near - 16, 18.8), .2)
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 13, 18.1), sample.point(-near - 34, 18.1), .18)
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 13, 18.1), sample.point(-near - 24, 17), .10)
                self.beam('Building_Paddock', 'Steel', sample.point(-near - 34, 18.1), sample.point(-near - 24, 17), .10)
            if index % 5 == 0:
                self.spectators(sample.point(-near - 16, 6.1), nxt.point(-near_next - 16, 6.1), index, 'Building_Crowd_Paddock')

    def grandstand(self, start: float, end: float, sign: int) -> None:
        for index in range(0, len(self.road), 2):
            sample = self.road[index]
            if not start < sample.station < end:
                continue
            nxt = self.road[(index + 2) % len(self.road)]
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
        for frond in range(13):
            angle = frond * math.tau / 13 + base[0] % 1
            direction = math.cos(angle), math.sin(angle), 0.0
            side = -math.sin(angle), math.cos(angle), 0.0
            length = 3.4 + (frond % 3) * .4
            previous = top
            for segment in range(1, 17):
                t = segment / 16
                point = add(top, add(mul(direction, length * t), (0, 0, 2 * math.sin(t * math.pi) - t * 1.7)))
                self.beam('Building_Palms', 'Leaves', previous, point, .035)
                width = .75 * math.sin(t * math.pi) + .05
                for sign in (-1, 1):
                    blade = add(point, add(mul(side, sign * width), mul(direction, -.30)))
                    blade = add(blade, (0, 0, -.18))
                    self.triangle('Building_Palms', 'Leaves', previous, blade, point)
                previous = point

    def save(self) -> dict[str, object]:
        SCRATCH.mkdir(parents=True, exist_ok=True)
        records = []
        for name, tile in sorted(self.tiles.items()):
            path = SCRATCH / f'{name}.mesh'
            path.write_bytes(b'FFLVM1\0\0' + struct.pack('<I', len(tile.triangles) // 100) + tile.triangles)
            records.append({'name': name, 'file': path.name, 'materials': tile.materials, 'bounds': tile.minimum + tile.maximum,
                            'triangles': len(tile.triangles) // 100, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
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
