#!/usr/bin/env python3
"""Native Suzuka meshes in the same tile format as Las Vegas.

Materials are the Interlagos and Monza surfaces already used by the accepted
circuits. The reference video is appearance only; none of its pixels are shipped.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "suzuka"
SURVEY = ROOT / "Source/FormulaForge/Native/track_data/japan_survey.inc"
TERRAIN = ROOT / "Content/Generated/Japan/Data/terrain.bin"
BUILDINGS = ROOT / "Content/Generated/Japan/Data/buildings.bin"
LANDMARKS = ROOT / "Content/Generated/Japan/Data/landmarks.bin"

Point = tuple[float, float, float]


def add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def mul(a: Point, value: float) -> Point:
    return a[0] * value, a[1] * value, a[2] * value


def cross(a: Point, b: Point) -> Point:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def norm(a: Point) -> Point:
    length = math.sqrt(sum(value * value for value in a)) or 1e-9
    return mul(a, 1 / length)


def world(point: Point) -> Point:
    return -point[1] * 100, -point[0] * 100, point[2] * 100


def pairs(text: str, name: str) -> list[tuple[float, ...]]:
    block = text.split(name, 1)[1].split(";", 1)[0]
    rows = []
    for line in block.splitlines():
        numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", line)
        if numbers and "{" in line:
            rows.append(tuple(float(number) for number in numbers))
    return rows


class Tile:
    def __init__(self) -> None:
        self.materials: list[str] = []
        self.blob = bytearray()
        self.count = 0
        self.minimum = [1e12, 1e12, 1e12]
        self.maximum = [-1e12, -1e12, -1e12]

    def triangle(self, material: str, corners: tuple[Point, Point, Point], uvs: tuple[tuple[float, float], ...]) -> None:
        edge_a, edge_b = sub(corners[1], corners[0]), sub(corners[2], corners[0])
        normal = cross(edge_a, edge_b)
        if sum(value * value for value in normal) < 1e-8:
            return
        normal = norm(normal)
        # Upward surfaces were wound downward, so the cockpit looked at a black underside.
        if normal[2] < -0.35:
            corners = (corners[0], corners[2], corners[1])
            uvs = (uvs[0], uvs[2], uvs[1])
            normal = mul(normal, -1)
        if material not in self.materials:
            self.materials.append(material)
        slot = self.materials.index(material)
        self.blob += struct.pack("<I", slot)
        for point, uv in zip(corners, uvs):
            placed = world(point)
            spun = (-normal[1], -normal[0], normal[2])
            self.blob += struct.pack("<8f", *placed, *spun, uv[0], uv[1])
            for axis in range(3):
                self.minimum[axis] = min(self.minimum[axis], placed[axis])
                self.maximum[axis] = max(self.maximum[axis], placed[axis])
        self.count += 1

    def quad(self, material: str, a: Point, b: Point, c: Point, d: Point, u: float, v: float) -> None:
        self.triangle(material, (a, b, c), ((0, 0), (u, 0), (u, v)))
        self.triangle(material, (a, c, d), ((0, 0), (u, v), (0, v)))


class Scene:
    def __init__(self) -> None:
        text = SURVEY.read_text()
        centre = pairs(text, "kJapanCenterline")
        elevation = pairs(text, "kJapanElevation")
        width = pairs(text, "kJapanWidth")
        shoulder = pairs(text, "kJapanShoulder")
        self.samples = []
        count = min(len(centre), len(elevation) - 1, len(width) - 1)
        for index in range(count):
            previous = centre[(index - 1) % count]
            nxt = centre[(index + 1) % count]
            tangent = norm((nxt[0] - previous[0], nxt[1] - previous[1], 0))
            left = (-tangent[1], tangent[0], 0)
            turn = 0.0
            if index > 2:
                before = centre[index - 2]
                after = centre[min(count - 1, index + 2)]
                first = (centre[index][0] - before[0], centre[index][1] - before[1])
                second = (after[0] - centre[index][0], after[1] - centre[index][1])
                turn = math.atan2(first[0] * second[1] - first[1] * second[0], first[0] * second[0] + first[1] * second[1])
            shoulder_row = shoulder[min(len(shoulder) - 1, index // 2)]
            self.samples.append({
                "station": elevation[index][0],
                "x": centre[index][0], "y": centre[index][1], "z": elevation[index][1],
                "half": width[index][1] * 0.5,
                "left": shoulder_row[1], "right": shoulder_row[2],
                "tx": tangent[0], "ty": tangent[1], "nx": left[0], "ny": left[1],
                "turn": turn,
            })
        self.length = 5807.0
        data = TERRAIN.read_bytes()
        origin_x, origin_y, step, columns, rows = struct.unpack_from("<ddfII", data, 8)
        self.grid = {
            "x": origin_x, "y": origin_y, "step": step, "columns": columns, "rows": rows,
            "heights": struct.unpack_from(f"<{columns * rows}f", data, 36),
        }
        self.buildings = self._buildings()
        self.wheel_spec = self._wheel()
        self.tiles: dict[str, Tile] = {}
        self.gravel = self._gravel(text)

    def _buildings(self) -> list[tuple[float, list[tuple[float, float]]]]:
        data = BUILDINGS.read_bytes()
        count = struct.unpack_from("<I", data, 8)[0]
        cursor = 12
        buildings = []
        for _ in range(count):
            vertices, height = struct.unpack_from("<If", data, cursor)
            cursor += 8
            ring = []
            for _vertex in range(vertices):
                ring.append(struct.unpack_from("<ff", data, cursor))
                cursor += 8
            buildings.append((height, ring))
        return buildings

    def _wheel(self) -> tuple[float, float, float, float] | None:
        if not LANDMARKS.exists():
            return None
        data = LANDMARKS.read_bytes()
        if data[:6] != b"FFLMK1":
            return None
        count = struct.unpack_from("<I", data, 8)[0]
        if count < 1:
            return None
        kind, x, y, radius, hub = struct.unpack_from("<Iffff", data, 12)
        return (x, y, radius, hub) if kind == 1 else None

    def _gravel(self, text: str) -> list[tuple[float, float, int]]:
        block = text.split("kJapanRunoff", 1)[1].split(";", 1)[0]
        zones = []
        for line in block.splitlines():
            if "Gravel" not in line:
                continue
            numbers = re.findall(r"[-+]?\d*\.?\d+", line)
            if len(numbers) >= 3:
                zones.append((float(numbers[0]), float(numbers[1]), int(float(numbers[2]))))
        return zones

    def tile_for(self, point: Point) -> Tile:
        name = f"Tile_{math.floor(point[0] / 280):02d}_{math.floor(point[1] / 280):02d}".replace("-", "m")
        return self.tiles.setdefault(name, Tile())

    def triangle(self, material: str, corners: tuple[Point, Point, Point], uvs: tuple[tuple[float, float], ...]) -> None:
        centre = mul(add(add(corners[0], corners[1]), corners[2]), 1 / 3)
        self.tile_for(centre).triangle(material, corners, uvs)

    def quad(self, material: str, a: Point, b: Point, c: Point, d: Point, u: float, v: float) -> None:
        self.triangle(material, (a, b, c), ((0, 0), (u, 0), (u, v)))
        self.triangle(material, (a, c, d), ((0, 0), (u, v), (0, v)))

    def point(self, sample: dict, lane: float, lift: float = 0.0) -> Point:
        return (sample["x"] + sample["nx"] * lane, sample["y"] + sample["ny"] * lane, sample["z"] + lift)

    def terrain_at(self, x: float, y: float) -> float:
        grid = self.grid
        column = (x - grid["x"]) / grid["step"]
        row = (y - grid["y"]) / grid["step"]
        if column < 0 or row < 0 or column >= grid["columns"] - 1 or row >= grid["rows"] - 1:
            return 0.0
        c0, r0 = int(column), int(row)
        tx, ty = column - c0, row - r0
        columns = grid["columns"]
        heights = grid["heights"]

        def at(c: int, r: int) -> float:
            return heights[r * columns + c]

        return (at(c0, r0) * (1 - tx) * (1 - ty) + at(c0 + 1, r0) * tx * (1 - ty)
                + at(c0, r0 + 1) * (1 - tx) * ty + at(c0 + 1, r0 + 1) * tx * ty)

    def nearest(self, x: float, y: float) -> tuple[dict, float]:
        best = min(self.samples, key=lambda sample: (sample["x"] - x) ** 2 + (sample["y"] - y) ** 2)
        return best, math.hypot(best["x"] - x, best["y"] - y)

    def gravel_at(self, station: float, left: bool) -> bool:
        side = 1 if left else -1
        return any(start <= station <= end and zone_side == side for start, end, zone_side in self.gravel)

    def road(self) -> None:
        samples = self.samples
        for index, first in enumerate(samples):
            second = samples[(index + 1) % len(samples)]
            span = max(0.5, second["station"] - first["station"])
            if span > 30:
                span = self.length / len(samples)
            half = first["half"]
            corner = abs(first["turn"]) > 0.18
            left_lane = half + (0.85 if corner else 0.12)
            right_lane = -(half + (0.85 if corner else 0.12))
            road = [self.point(first, half), self.point(second, second["half"]),
                    self.point(second, -second["half"]), self.point(first, -half)]
            self.quad("Road", *road, span / 4, half * 2 / 4)
            self.quad("Line", self.point(first, half - 0.12), self.point(second, second["half"] - 0.12),
                      self.point(second, second["half"]), self.point(first, half), span / 8, 0.05)
            self.quad("Line", self.point(first, -half), self.point(second, -second["half"]),
                      self.point(second, -(second["half"] - 0.12)), self.point(first, -(half - 0.12)), span / 8, 0.05)
            if corner:
                material = "KerbRed" if int(first["station"] / 4) % 2 == 0 else "KerbWhite"
                for sign in (1, -1):
                    inner = sign * half
                    outer = sign * (half + 0.9)
                    a = self.point(first, inner, 0.02)
                    b = self.point(second, sign * second["half"], 0.02)
                    c = self.point(second, sign * (second["half"] + 0.9), 0.10)
                    d = self.point(first, outer, 0.10)
                    self.quad(material, a, b, c, d, span / 2, 0.4)
                    self.quad(material, self.point(first, outer, 0.0), self.point(second, sign * (second["half"] + 0.9), 0.0),
                              c, d, span / 2, 0.1)
            for sign, shoulder, left in ((1, first["left"], True), (-1, first["right"], False)):
                inner = sign * (half + (0.9 if corner else 0.12))
                outer = sign * (half + 0.9 + shoulder)
                surface = "Gravel" if self.gravel_at(first["station"], left) else "Grass"
                self.quad(surface, self.point(first, outer, -0.04), self.point(second, sign * (second["half"] + 0.9 + (second["left"] if left else second["right"])), -0.04),
                          self.point(second, sign * (second["half"] + (0.9 if corner else 0.12))), self.point(first, inner), span / 4, shoulder / 4)
                wall_lane = sign * (half + 0.9 + shoulder)
                base = self.point(first, wall_lane)
                base_next = self.point(second, sign * (second["half"] + 0.9 + (second["left"] if left else second["right"])))
                top = add(base, (0, 0, 0.95))
                top_next = add(base_next, (0, 0, 0.95))
                self.quad("Armco", base, base_next, top_next, top, span / 3, 0.4)
                cap = (first["nx"] * sign * 0.18, first["ny"] * sign * 0.18, 0)
                self.quad("Armco", top, top_next, add(top_next, cap), add(top, cap), span / 3, 0.08)
            if first["z"] - self.terrain_at(first["x"], first["y"]) > 3.5:
                for sign in (1.0, -1.0):
                    lane = sign * (half + 1.4)
                    lane_next = sign * (second["half"] + 1.4)
                    self.quad("Concrete", self.point(first, lane, 0.15), self.point(second, lane_next, 0.15),
                              self.point(second, lane_next, 1.25), self.point(first, lane, 1.25), span / 4, 0.5)
            if first["z"] - self.terrain_at(first["x"], first["y"]) > 4.0 and index % 6 == 0:
                centre = (first["x"], first["y"], self.terrain_at(first["x"], first["y"]))
                top = (first["x"], first["y"], first["z"] - 0.6)
                for angle in range(4):
                    direction = (math.cos(angle * math.pi / 2), math.sin(angle * math.pi / 2), 0)
                    side = (math.cos((angle + 1) * math.pi / 2), math.sin((angle + 1) * math.pi / 2), 0)
                    a = add(centre, mul(direction, 0.7))
                    b = add(centre, mul(side, 0.7))
                    self.quad("Concrete", a, b, add(b, sub(top, centre)), add(a, sub(top, centre)), 1, first["z"])

    def terrain(self) -> None:
        grid = self.grid
        step = grid["step"] * 2
        columns = int((grid["columns"] * grid["step"]) / step)
        rows = int((grid["rows"] * grid["step"]) / step)
        for row in range(rows - 1):
            for column in range(columns - 1):
                corners = []
                blocked = False
                for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    x = grid["x"] + (column + dx) * step
                    y = grid["y"] + (row + dy) * step
                    sample, distance = self.nearest(x, y)
                    limit = sample["half"] + max(sample["left"], sample["right"]) + 2.5
                    if distance < limit:
                        blocked = True
                        break
                    height = self.terrain_at(x, y)
                    blend = max(0.0, min(1.0, (distance - limit) / 18))
                    blend = blend * blend * (3 - 2 * blend)
                    corners.append((x, y, sample["z"] * (1 - blend) + height * blend))
                if blocked:
                    continue
                self.quad("Grass", corners[0], corners[1], corners[2], corners[3], step / 8, step / 8)

    def between(self, start: float, end: float) -> list[dict]:
        if start <= end:
            return [sample for sample in self.samples if start <= sample["station"] <= end]
        return [sample for sample in self.samples if sample["station"] >= start or sample["station"] <= end]

    def frontage(self) -> None:
        # Cockpit reference: pit building on the driver's left, roofed grandstand on the right.
        # Source left is the positive normal. The packaged view is checked after this placement.
        self._pit(sign=1.0, start=20.0, end=460.0)
        self._grandstand_run(sign=-1.0, start=0.0, end=520.0, rows=16, setback=9.0)
        self._grandstand_run(sign=1.0, start=5000.0, end=5550.0, rows=10, setback=11.0)
        self._grandstand_run(sign=-1.0, start=2500.0, end=2750.0, rows=8, setback=12.0)

    def _offset(self, sample: dict, sign: float, lane: float, lift: float) -> Point:
        return self.point(sample, sign * (sample["half"] + lane), lift)

    def _pit(self, sign: float, start: float, end: float) -> None:
        run = self.between(start, end)
        for first, second in zip(run, run[1:]):
            span = max(1.0, second["station"] - first["station"])
            wall = 5.5
            a = self._offset(first, sign, wall, 0.0)
            b = self._offset(second, sign, wall, 0.0)
            self.quad("Pit", a, b, add(b, (0, 0, 1.35)), add(a, (0, 0, 1.35)), span / 4, 0.4)
            building = 11.0
            outer = self._offset(first, sign, building + 8.0, 0.0)
            outer_next = self._offset(second, sign, building + 8.0, 0.0)
            inner = self._offset(first, sign, building, 0.0)
            inner_next = self._offset(second, sign, building, 0.0)
            self.quad("Pit", inner, inner_next, add(inner_next, (0, 0, 7.5)), add(inner, (0, 0, 7.5)), span / 6, 2.0)
            self.quad("Roof", inner, inner_next, outer_next, outer, span / 8, 2.0)
            for mouth in (2.2, 4.6):
                low = self._offset(first, sign, building - 0.15, mouth)
                low_next = self._offset(second, sign, building - 0.15, mouth)
                self.quad("Garage", low, low_next, add(low_next, (0, 0, 1.7)), add(low, (0, 0, 1.7)), span / 5, 0.6)

    def _grandstand_run(self, sign: float, start: float, end: float, rows: int, setback: float) -> None:
        run = self.between(start, end)
        for index, (first, second) in enumerate(zip(run, run[1:])):
            span = max(1.0, abs(second["station"] - first["station"]))
            if span > 20:
                span = 4.0
            for row in range(rows):
                near = setback + row * 0.9
                far = near + 0.9
                rise = 1.4 + row * 0.78
                material = "SeatA" if row % 2 == 0 else "SeatB"
                a = self._offset(first, sign, near, rise)
                b = self._offset(second, sign, near, rise)
                c = self._offset(second, sign, far, rise + 0.55)
                d = self._offset(first, sign, far, rise + 0.55)
                self.quad(material, a, b, c, d, span / 2.5, 0.45)
                self.quad(material, a, b, add(b, (0, 0, 0.62)), add(a, (0, 0, 0.62)), span / 2.5, 0.3)
            roof_near = setback - 3.2
            roof_far = setback + rows * 0.9 + 1.5
            roof = 1.6 + rows * 0.78 + 2.4
            self.quad("Roof", self._offset(first, sign, roof_near, roof), self._offset(second, sign, roof_near, roof),
                      self._offset(second, sign, roof_far, roof), self._offset(first, sign, roof_far, roof), span / 6, 3)
            if index % 4 == 0:
                post = self._offset(first, sign, setback, 0.0)
                top = self._offset(first, sign, roof_near, roof)
                self.quad("Steel", post, add(post, (first["tx"] * 0.35, first["ty"] * 0.35, 0)),
                          add(top, (first["tx"] * 0.35, first["ty"] * 0.35, 0)), top, 0.4, roof / 4)

    def stands(self) -> None:
        for height, ring in self.buildings:
            if len(ring) < 3:
                continue
            centroid = (sum(point[0] for point in ring) / len(ring), sum(point[1] for point in ring) / len(ring))
            sample, _distance = self.nearest(*centroid)
            if sample["station"] < 560 or sample["station"] > 5480:
                continue
            base = self.terrain_at(*centroid)
            if height >= 26:
                self._tower(ring, base, height)
                continue
            if height < 9:
                self._box(ring, base, height, "Concrete")
                continue
            self._grandstand(ring, centroid, sample, base, height)

    def _box(self, ring: list[tuple[float, float]], base: float, height: float, material: str) -> None:
        for index, (ax, ay) in enumerate(ring):
            bx, by = ring[(index + 1) % len(ring)]
            a = (ax, ay, base)
            b = (bx, by, base)
            self.quad(material, a, b, add(b, (0, 0, height)), add(a, (0, 0, height)), math.hypot(bx - ax, by - ay) / 4, height / 3)
        roof = [(x, y, base + height) for x, y in ring]
        for index in range(1, len(roof) - 1):
            self.triangle(material, (roof[0], roof[index], roof[index + 1]), ((0, 0), (1, 0), (1, 1)))

    def _grandstand(self, ring, centroid, sample, base: float, height: float) -> None:
        self._box(ring, base, min(4.0, height * 0.25), "Concrete")
        tiers = max(4, int((height - 4) / 1.7))
        for index, (ax, ay) in enumerate(ring):
            bx, by = ring[(index + 1) % len(ring)]
            edge = ((ax + bx) * 0.5 - centroid[0], (ay + by) * 0.5 - centroid[1])
            toward = (sample["x"] - centroid[0], sample["y"] - centroid[1])
            if edge[0] * toward[0] + edge[1] * toward[1] <= 0:
                self.quad("Concrete", (ax, ay, base + 4), (bx, by, base + 4),
                          (bx, by, base + height), (ax, ay, base + height), math.hypot(bx - ax, by - ay) / 6, height / 4)
                continue
            inward = norm((-edge[0], -edge[1], 0))
            length = math.hypot(bx - ax, by - ay)
            for tier in range(tiers):
                depth = tier * 1.15
                rise = 4 + tier * 1.55
                a = add((ax, ay, base + rise), mul(inward, depth))
                b = add((bx, by, base + rise), mul(inward, depth))
                c = add((bx, by, base + rise + 1.35), mul(inward, depth + 1.15))
                d = add((ax, ay, base + rise + 1.35), mul(inward, depth + 1.15))
                self.quad("Seats", a, b, c, d, length / 3, 0.6)
                self.quad("Crowd", a, b, add(b, (0, 0, 0.7)), add(a, (0, 0, 0.7)), length / 4, 0.3)
            roof_z = base + height + 1.2
            overhang = mul(norm((edge[0], edge[1], 0)), 2.4)
            self.quad("Roof", add((ax, ay, roof_z), overhang), add((bx, by, roof_z), overhang),
                      (bx, by, roof_z), (ax, ay, roof_z), length / 6, 1.2)
            self.quad("Steel", (ax, ay, base + 4), (bx, by, base + 4),
                      add((bx, by, roof_z), overhang), add((ax, ay, roof_z), overhang), length / 8, height / 4)

    def _tower(self, ring, base: float, height: float) -> None:
        self._box(ring, base, height, "Concrete")
        cx = sum(point[0] for point in ring) / len(ring)
        cy = sum(point[1] for point in ring) / len(ring)
        self.quad("Glass", (cx - 2, cy - 2, base + height * 0.45), (cx + 2, cy - 2, base + height * 0.45),
                  (cx + 2, cy - 2, base + height * 0.85), (cx - 2, cy - 2, base + height * 0.85), 1, 2)

    def trees(self) -> None:
        for sample in self.samples[::5]:
            station = sample["station"]
            if station < 520 or station > 5450 or sample["z"] - self.terrain_at(sample["x"], sample["y"]) > 2:
                continue
            for sign, left in ((1, True), (-1, False)):
                if self.gravel_at(station, left):
                    continue
                lane = sign * (sample["half"] + 1.2 + (sample["left"] if left else sample["right"]) + 9)
                x, y = sample["x"] + sample["nx"] * lane, sample["y"] + sample["ny"] * lane
                if any(math.hypot(x - sum(p[0] for p in ring) / len(ring), y - sum(p[1] for p in ring) / len(ring)) < 16
                       for _height, ring in self.buildings):
                    continue
                z = self.terrain_at(x, y)
                height = 6 + (int(station) % 4)
                width = 3.2
                self.quad("Trunk", (x - 0.2, y, z), (x + 0.2, y, z), (x + 0.2, y, z + 1.6), (x - 0.2, y, z + 1.6), 0.2, 0.8)
                across = norm((sample["tx"], sample["ty"], 0))
                side = (sample["nx"], sample["ny"], 0)
                crown = (x, y, z + 1.6 + height * 0.35)
                for axis in (across, side):
                    a = add(crown, (-axis[0] * width, -axis[1] * width, -height * 0.28))
                    b = add(crown, (axis[0] * width, axis[1] * width, -height * 0.28))
                    c = add(crown, (axis[0] * width * 0.72, axis[1] * width * 0.72, height * 0.32))
                    d = add(crown, (-axis[0] * width * 0.72, -axis[1] * width * 0.72, height * 0.32))
                    self.quad("Leaf", a, b, c, d, 1, 1)

    def wheel(self) -> None:
        if self.wheel_spec is None:
            return
        x, y, radius, hub = self.wheel_spec
        base = self.terrain_at(x, y)
        sample, _distance = self.nearest(x, y)
        facing = norm((sample["x"] - x, sample["y"] - y, 0))
        axis = norm(cross(facing, (0, 0, 1)))
        centre = (x, y, base + hub)
        segments = 36
        for index in range(segments):
            a0 = math.tau * index / segments
            a1 = math.tau * (index + 1) / segments

            def rim(angle: float, scale: float, lateral: float) -> Point:
                return add(centre, add(add(mul(facing, math.cos(angle) * radius * scale),
                                           (0, 0, math.sin(angle) * radius * scale)), mul(axis, lateral)))

            self.quad("White", rim(a0, 1.0, -0.55), rim(a1, 1.0, -0.55), rim(a1, 1.0, 0.55), rim(a0, 1.0, 0.55), 2, 0.5)
            self.quad("White", rim(a0, 0.90, -0.45), rim(a1, 0.90, -0.45), rim(a1, 1.0, -0.45), rim(a0, 1.0, -0.45), 2, 0.4)
            self.quad("White", rim(a0, 0.90, 0.45), rim(a1, 0.90, 0.45), rim(a1, 1.0, 0.45), rim(a0, 1.0, 0.45), 2, 0.4)
            if index % 3 == 0:
                outer = rim(a0, 0.92, 0.0)
                side = mul(axis, 0.22)
                self.quad("White", add(centre, mul(side, -1)), add(outer, mul(side, -1)), add(outer, side), add(centre, side), radius / 5, 0.25)
                cabin = rim(a0, 1.04, 0.0)
                up = (0, 0, 2.1)
                wide = mul(axis, 1.15)
                deep = mul(facing, 1.1 * math.cos(a0))
                self.quad("Red", sub(sub(cabin, wide), deep), add(sub(cabin, deep), wide),
                          add(add(sub(cabin, deep), wide), up), add(sub(sub(cabin, wide), deep), up), 1.2, 1.0)
        for sign in (1, -1):
            foot = add((x, y, base), mul(axis, sign * radius * 0.62))
            self.quad("Steel", foot, add(foot, mul(facing, 0.4)), add(centre, mul(facing, 0.4)), centre, radius / 6, 0.4)

    def save(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        records = []
        for name, tile in self.tiles.items():
            if tile.count == 0:
                continue
            blob = bytearray(b"FFLVM1\0\0") + struct.pack("<I", tile.count) + tile.blob
            path = OUT / f"{name}.bin"
            path.write_bytes(blob)
            records.append({
                "name": name,
                "file": path.name,
                "materials": tile.materials,
                "bounds": tile.minimum + tile.maximum,
                "sha256": hashlib.sha256(blob).hexdigest(),
            })
        (OUT / "manifest.json").write_text(json.dumps({"tiles": records}, indent=2) + "\n")
        print(f"suzuka: {len(records)} tiles, {sum(tile.count for tile in self.tiles.values())} triangles")


def main() -> None:
    scene = Scene()
    scene.road()
    scene.terrain()
    scene.frontage()
    scene.stands()
    scene.trees()
    scene.wheel()
    scene.save()


if __name__ == "__main__":
    main()
