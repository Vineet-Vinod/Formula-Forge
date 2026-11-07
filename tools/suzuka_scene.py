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
        # Ground quads were wound downward. Roofs and walls keep the winding they were given,
        # so a soffit can face the cockpit instead of being flipped into the sky.
        if material in {"Road", "Grass", "Line", "Gravel", "KerbRed", "KerbWhite"} and normal[2] < -0.35:
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
        self._straighten()

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

    def _straighten(self) -> None:
        # Same repair as grade_pit_straight in the circuit builder. The mesh
        # follows the survey, and the survey follows this grade.
        def signed(station: float) -> float:
            return station - self.length if station > self.length * 0.5 else station

        def nearest(target: float) -> dict:
            return min(self.samples, key=lambda sample: abs(signed(sample["station"]) - target))

        left, right = nearest(16), nearest(300)
        span = signed(right["station"]) - signed(left["station"])
        grade = (right["z"] - left["z"]) / span
        origin = left["z"] - grade * signed(left["station"])
        self.grade_origin = origin
        self.grade_slope = grade
        start, finish = nearest(0), nearest(300)
        tangent = norm((finish["x"] - start["x"], finish["y"] - start["y"], 0))
        self.straight_tx, self.straight_ty = tangent[0], tangent[1]
        self.straight_nx, self.straight_ny = -tangent[1], tangent[0]
        self.line_x, self.line_y = start["x"], start["y"]
        for sample in self.samples:
            place = signed(sample["station"])
            weight = self._straight_weight(place)
            if weight <= 0:
                continue
            chord_z = origin + grade * place
            line_x = self.line_x + self.straight_tx * place
            line_y = self.line_y + self.straight_ty * place
            sample["x"] += (line_x - sample["x"]) * weight
            sample["y"] += (line_y - sample["y"]) * weight
            sample["z"] += (chord_z - sample["z"]) * weight
            sample["tx"], sample["ty"] = self.straight_tx, self.straight_ty
            sample["nx"], sample["ny"] = self.straight_nx, self.straight_ny
            if weight > 0.99:
                sample["half"] = 7.5
                sample["left"] = sample["right"] = 6.0
        self._smooth_heading()

    def _smooth_heading(self) -> None:
        # Short average so the asphalt edges do not kink on every sample.
        # The pit straight keeps the fitted line. Corners keep their shape.
        count = len(self.samples)
        tangents = [(sample["tx"], sample["ty"]) for sample in self.samples]
        for index, sample in enumerate(self.samples):
            place = sample["station"] if sample["station"] < self.length * 0.5 else sample["station"] - self.length
            if self._straight_weight(place) > 0.99:
                continue
            tx = ty = 0.0
            for offset, weight in ((-1, 1.0), (0, 2.0), (1, 1.0)):
                other = tangents[(index + offset) % count]
                tx += other[0] * weight
                ty += other[1] * weight
            tangent = norm((tx, ty, 0.0))
            sample["tx"], sample["ty"] = tangent[0], tangent[1]
            sample["nx"], sample["ny"] = -tangent[1], tangent[0]

    def _straight_weight(self, place: float) -> float:
        # Full correction on the pit straight, blended out before Turn 1 and the chicane.
        if place < -70 or place > 360:
            return 0.0
        if place < -30:
            return (place + 70) / 40
        if place > 320:
            return (360 - place) / 40
        return 1.0

    def _on_frontage(self, station: float) -> bool:
        return station <= 420 or station >= self.length - 90

    def gravel_at(self, station: float, left: bool) -> bool:
        side = 1 if left else -1
        return any(start <= station <= end and zone_side == side for start, end, zone_side in self.gravel)

    def road(self) -> None:
        samples = self.samples
        count = len(samples)
        index = 0
        while index < count:
            first = samples[index]
            step = 2
            def signed_station(sample: dict) -> float:
                return sample["station"] if sample["station"] < self.length * 0.5 else sample["station"] - self.length

            if self._straight_weight(signed_station(first)) > 0.99:
                step = 8
                while step > 1 and index + step < count and self._straight_weight(signed_station(samples[index + step])) < 0.99:
                    step -= 1
                if index + step >= count:
                    step = count - index
            second = samples[(index + step) % count]
            span = second["station"] - first["station"]
            if span <= 0:
                span += self.length
            span = max(0.5, span)
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
                if self._on_frontage(first["station"]):
                    continue
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
            index += step

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
                    if self._on_frontage(sample["station"]) and distance < 48:
                        # The same culvert that notched the road opens beside the pits.
                        height = max(height, sample["z"] - 0.2)
                        if distance < 30:
                            height = min(height, sample["z"] + 0.4)
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
        # Grandstand on the driver's left, pit building on the right.
        # Source left is the positive normal. Both run on the straight grade,
        # not on the per-sample ribbon that followed the culvert.
        self._pit_straight()
        self._main_grandstand()
        self._grandstand_run(sign=1.0, start=5000.0, end=5550.0, rows=10, setback=11.0)
        self._grandstand_run(sign=-1.0, start=2500.0, end=2750.0, rows=8, setback=12.0)

    def _at(self, station: float) -> dict:
        samples = self.samples
        index = max(0, min(len(samples) - 1, int(station / self.length * len(samples))))
        while index < len(samples) - 1 and samples[index + 1]["station"] <= station:
            index += 1
        while index > 0 and samples[index]["station"] > station:
            index -= 1
        first = samples[index]
        if index + 1 >= len(samples):
            return first
        second = samples[index + 1]
        span = second["station"] - first["station"]
        blend = 0.0 if span <= 0 else max(0.0, min(1.0, (station - first["station"]) / span))
        return {
            "x": first["x"] + (second["x"] - first["x"]) * blend,
            "y": first["y"] + (second["y"] - first["y"]) * blend,
            "z": first["z"] + (second["z"] - first["z"]) * blend,
        }

    def _place(self, signed_station: float, lane: float, lift: float) -> Point:
        station = signed_station if signed_station >= 0 else signed_station + self.length
        sample = self._at(station)
        return (
            sample["x"] + self.straight_nx * lane,
            sample["y"] + self.straight_ny * lane,
            sample["z"] + lift,
        )

    def _horizontal(self, material: str, a: Point, b: Point, c: Point, d: Point, u: float, v: float, up: bool) -> None:
        normal = cross(sub(b, a), sub(c, a))
        if (normal[2] >= 0) != up:
            b, d = d, b
        self.quad(material, a, b, c, d, u, v)

    def _beam(self, material: str, a: Point, b: Point, width: float, depth: float | None = None) -> None:
        tangent = norm(sub(b, a))
        side = mul(norm(cross(tangent, (0.0, 0.0, 1.0) if abs(tangent[2]) < 0.95 else (0.0, 1.0, 0.0))), width / 2)
        up = mul(norm(cross(side, tangent)), (depth if depth is not None else width) / 2)
        corners = [
            add(a, add(side, up)), add(a, sub(up, side)), sub(a, add(side, up)), add(a, sub(side, up)),
            add(b, add(side, up)), add(b, sub(up, side)), sub(b, add(side, up)), add(b, sub(side, up)),
        ]
        for indices in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            self.quad(material, corners[indices[0]], corners[indices[1]], corners[indices[2]], corners[indices[3]], 1, 1)

    def _tree(self, base: Point) -> None:
        x, y, z = base
        height, width = 8.5, 4.2
        self.quad("Trunk", (x - 0.25, y, z), (x + 0.25, y, z), (x + 0.25, y, z + 2.2), (x - 0.25, y, z + 2.2), 0.3, 1.0)
        across = (self.straight_tx, self.straight_ty, 0.0)
        side = (self.straight_nx, self.straight_ny, 0.0)
        diagonal = norm((across[0] + side[0], across[1] + side[1], 0.0))
        crown = (x, y, z + 3.2)
        for axis, scale in ((across, 1.0), (side, 0.9), (diagonal, 0.75)):
            a = add(crown, (-axis[0] * width * scale, -axis[1] * width * scale, -height * 0.35))
            b = add(crown, (axis[0] * width * scale, axis[1] * width * scale, -height * 0.35))
            c = add(crown, (axis[0] * width * scale * 0.5, axis[1] * width * scale * 0.5, height * 0.45))
            d = add(crown, (-axis[0] * width * scale * 0.5, -axis[1] * width * scale * 0.5, height * 0.45))
            self.quad("Leaf", a, b, c, d, 1, 1)

    def _people(self, a: Point, b: Point, row: int) -> None:
        span = sub(b, a)
        distance = math.sqrt(sum(value * value for value in span))
        count = max(1, round(distance / 0.46))
        direction = norm(span)
        for person in range(count):
            center = add(a, mul(span, (person + 0.5) / count))
            left = sub(center, mul(direction, 0.22))
            right = add(center, mul(direction, 0.22))
            top_left, top_right = add(left, (0.0, 0.0, 1.2)), add(right, (0.0, 0.0, 1.2))
            column = (person + row * 2) % 3
            u0, u1 = column / 3, (column + 1) / 3
            self.triangle("Crowd", (top_left, top_right, right), ((u0, 0.5), (u1, 0.5), (u1, 1.0)))
            self.triangle("Crowd", (top_left, right, left), ((u0, 0.5), (u1, 1.0), (u0, 1.0)))
            self.triangle("Crowd", (top_right, top_left, left), ((u1, 0.5), (u0, 0.5), (u0, 1.0)))
            self.triangle("Crowd", (top_right, left, right), ((u1, 0.5), (u0, 1.0), (u1, 1.0)))

    def _run(self, start: float, end: float, step: float) -> list[float]:
        stations = []
        cursor = start
        while cursor < end - 0.05:
            stations.append(cursor)
            cursor += step
        stations.append(end)
        return stations

    def _pit_straight(self) -> None:
        # Wall, pit lane, then a straight garage block. Positive lanes are the
        # driver's left in the cockpit, and the reference puts the pits on the right.
        start, end = -40.0, 360.0
        side = -1.0
        wall, face = side * 8.4, side * 14.6
        for begin, finish in zip(self._run(start, end, 16), self._run(start, end, 16)[1:]):
            span = finish - begin
            self._horizontal(
                "Road",
                self._place(begin, wall + side * 0.35, 0.02), self._place(finish, wall + side * 0.35, 0.02),
                self._place(finish, face - side * 0.4, 0.02), self._place(begin, face - side * 0.4, 0.02),
                span / 4, 2.0, True,
            )
            self._facade("Concrete", self._place(begin, wall, 0.0), self._place(finish, wall, 0.0), 1.05, side, span / 3, 0.4)
            self._beam("Concrete", self._place(begin, wall, 0.0), self._place(begin, wall, 1.2), 0.28, 0.22)
            self._horizontal(
                "Concrete",
                self._place(begin, wall - side * 0.15, 1.05), self._place(finish, wall - side * 0.15, 1.05),
                self._place(finish, wall + side * 0.28, 1.05), self._place(begin, wall + side * 0.28, 1.05),
                span / 3, 0.15, True,
            )
        bay = 8.0
        cursor = start
        while cursor < end - 1:
            nxt = min(end, cursor + bay)
            pier = min(nxt, cursor + 1.15)
            self._facade("Concrete", self._place(cursor, face, 0.0), self._place(pier, face, 0.0), 6.2, side, 0.4, 2.2)
            for edge in (cursor, pier):
                outer = self._place(edge, face, 0.0)
                inner = self._place(edge, face + side * 2.8, 0.0)
                self.quad("Concrete", outer, inner, add(inner, (0, 0, 6.2)), add(outer, (0, 0, 6.2)), 0.8, 2.2)
                self.quad("Concrete", inner, outer, add(outer, (0, 0, 6.2)), add(inner, (0, 0, 6.2)), 0.8, 2.2)
            if pier < nxt - 0.4:
                self._facade("Garage", self._place(pier, face + side * 2.6, 0.25), self._place(nxt, face + side * 2.6, 0.25), 3.7, side, 1.6, 1.2)
                self._facade("Pit", self._place(pier, face, 4.05), self._place(nxt, face, 4.05), 2.15, side, 1.4, 0.7)
                self._beam("Concrete", self._place(pier, face - side * 0.15, 0.2), self._place(nxt, face - side * 0.15, 0.2), 0.22, 0.28)
                self._beam("Concrete", self._place(pier, face - side * 0.15, 3.85), self._place(nxt, face - side * 0.15, 3.85), 0.28, 0.22)
            cursor = nxt
        self._facade("Concrete", self._place(start, face + side * 11.0, 0.0), self._place(end, face + side * 11.0, 0.0), 6.2, -side, (end - start) / 8, 2.0)
        for begin, finish in zip(self._run(start, end, 8), self._run(start, end, 8)[1:]):
            front_a, front_b = self._place(begin, face - side * 6.5, 6.35), self._place(finish, face - side * 6.5, 6.35)
            back_b, back_a = self._place(finish, face + side * 11.0, 6.7), self._place(begin, face + side * 11.0, 6.7)
            self._horizontal("Roof", front_a, front_b, back_b, back_a, (finish - begin) / 6, 3.0, True)
            self._horizontal("Steel", front_a, back_a, back_b, front_b, (finish - begin) / 6, 3.0, False)
            self._beam("Steel", front_a, front_b, 0.22, 0.45)
            self._beam("Steel", self._place(begin, face - side * 6.5, 6.2), self._place(begin, face + side * 4.0, 5.5), 0.14, 0.1)
            self._beam("Steel", self._place(begin, face + side * 4.0, 5.5), back_a, 0.14, 0.1)
            self._beam("Steel", self._place(begin, face - side * 1.0, 0.0), self._place(begin, face - side * 1.0, 6.35), 0.28, 0.28)
            self._tree(self._place(begin, side * 32.0, 0.0))
            self._facade("Glass", self._place(begin, face, 4.2), self._place(finish, face, 4.2), 1.55, side, (finish - begin) / 3, 0.7)
            for depth in (0.0, 5.0, 10.0):
                lane = face - side * 6.5 + side * depth
                self._beam("Steel", self._place(begin, lane, 6.05), self._place(finish, lane, 6.05), 0.12, 0.08)

    def _main_grandstand(self) -> None:
        # Straight rake on the driver's left. Positive lanes are that side.
        start, end = -40.0, 360.0
        side = 1.0
        face = side * 12.2
        rows = 9
        roof = 11.2
        back = face + side * (rows * 0.9 + 2.0)
        for begin, finish in zip(self._run(start, end, 8), self._run(start, end, 8)[1:]):
            span = finish - begin
            self._facade("Concrete", self._place(begin, face, 0.0), self._place(finish, face, 0.0), 1.15, side, span / 3, 0.4)
            for rail in (0.38, 0.72):
                self._beam("Armco", self._place(begin, side * 9.05, rail), self._place(finish, side * 9.05, rail), 0.18, 0.07)
            self._beam("Armco", self._place(begin, side * 9.05, 0.15), self._place(begin, side * 9.05, 0.85), 0.1, 0.1)
            self._facade("Concrete", self._place(begin, back, 0.0), self._place(finish, back, 0.0), roof + 1.2, -side, span / 4, 3.0)
            ramp_a = self._place(begin, face + side * 0.3, 1.15)
            ramp_b = self._place(finish, face + side * 0.3, 1.15)
            ramp_c = self._place(finish, back - side * 0.4, 1.15 + rows * 0.55)
            ramp_d = self._place(begin, back - side * 0.4, 1.15 + rows * 0.55)
            self._horizontal("SeatA", ramp_a, ramp_b, ramp_c, ramp_d, span / 4, 3.0, True)
            for row in range(rows):
                lane = face + side * (0.5 + row * 0.9)
                rise = 1.2 + row * 0.55
                self._people(self._place(begin, lane, rise), self._place(finish, lane, rise), row)
            front_a, front_b = self._place(begin, face - side * 2.8, roof), self._place(finish, face - side * 2.8, roof)
            back_b = self._place(finish, back, roof + 1.3)
            back_a = self._place(begin, back, roof + 1.3)
            self._horizontal("Roof", front_a, front_b, back_b, back_a, span / 4, 3.2, True)
            self._horizontal("Steel", front_a, back_a, back_b, front_b, span / 4, 3.2, False)
            self._beam("Steel", front_a, front_b, 0.28, 0.4)
            self._beam("Steel", self._place(begin, face - side * 2.4, 0.0), front_a, 0.22, 0.22)
            self._beam("Steel", front_a, back_a, 0.12, 0.1)
            for depth in (4.0, 8.0, 12.0, 16.0):
                lane = face - side * 2.8 + side * depth
                height = roof + depth / 18.0 * 1.3 - 0.35
                self._beam("Steel", self._place(begin, lane, height), self._place(finish, lane, height), 0.12, 0.08)
                self._beam("Steel", self._place(begin, lane, height - 0.55), self._place(finish, lane, height - 0.55), 0.1, 0.07)
            self._beam("Steel", front_a, add(back_a, (0.0, 0.0, -0.9)), 0.1, 0.08)
            self._tree(self._place(begin, side * 30.0, 0.0))

    def _offset(self, sample: dict, sign: float, lane: float, lift: float) -> Point:
        return self.point(sample, sign * (sample["half"] + lane), lift)

    def _facade(self, material: str, a: Point, b: Point, height: float, sign: float, u: float, v: float) -> None:
        up = (0.0, 0.0, height)
        # The along-track order points away from the road on the negative side. Flip that side.
        if sign > 0:
            self.quad(material, a, b, add(b, up), add(a, up), u, v)
        else:
            self.quad(material, b, a, add(a, up), add(b, up), u, v)

    def _blend(self, run: list[dict], index: int) -> dict:
        count = len(run)
        sample = run[min(index, count - 1)]
        nxt = run[min(index + 1, count - 1)]
        return sample, nxt

    def _pit(self, sign: float, start: float, end: float) -> None:
        run = self.between(start, end)
        bay = 8.0
        cursor = 0.0
        index = 0
        while index < len(run) - 1:
            first = run[index]
            while index < len(run) - 1 and run[index]["station"] - first["station"] < bay:
                index += 1
            second = run[index]
            span = max(bay * 0.5, second["station"] - first["station"])
            face = 6.2
            pier = 0.55
            # Two concrete piers and a recessed garage between them.
            for end_sample, shift in ((first, 0.15), (second, -0.15)):
                outer = self._offset(end_sample, sign, face, 0.0)
                inner = self._offset(end_sample, sign, face + 0.8, 0.0)
                along = (end_sample["tx"] * shift, end_sample["ty"] * shift, 0.0)
                a = add(outer, along)
                b = add(inner, along)
                self._facade("Concrete", a, b, 6.4, sign, 0.5, 2.2)
            opening_a = self._offset(first, sign, face - 0.05, 0.35)
            opening_b = self._offset(second, sign, face - 0.05, 0.35)
            self._facade("Garage", opening_a, opening_b, 3.1, sign, span / 3, 1.2)
            header_a = self._offset(first, sign, face, 3.5)
            header_b = self._offset(second, sign, face, 3.5)
            self._facade("Pit", header_a, header_b, 2.8, sign, span / 4, 1.0)
            sill_a = self._offset(first, sign, face, 0.0)
            sill_b = self._offset(second, sign, face, 0.0)
            self._facade("Pit", sill_a, sill_b, 0.4, sign, span / 4, 0.2)
            back_a = self._offset(first, sign, face + 9.0, 0.0)
            back_b = self._offset(second, sign, face + 9.0, 0.0)
            self.quad("Roof", self._offset(first, sign, face - 1.2, 6.5), self._offset(second, sign, face - 1.2, 6.5),
                      add(back_b, (0, 0, 6.5)), add(back_a, (0, 0, 6.5)), span / 6, 2.4)
            cursor += span

    def _grandstand_run(self, sign: float, start: float, end: float, rows: int, setback: float) -> None:
        run = self.between(start, end)
        if len(run) < 3:
            return
        rows = min(rows, 9)
        bay = 12.0
        index = 0
        while index < len(run) - 1:
            first = run[index]
            while index < len(run) - 1 and run[index]["station"] - first["station"] < bay:
                index += 1
            second = run[index]
            span = max(4.0, abs(second["station"] - first["station"]))
            back = setback + rows * 0.9 + 2.0
            roof = 1.3 + rows * 0.55 + 2.6
            self._facade("Concrete", self._offset(first, sign, setback, 0.0), self._offset(second, sign, setback, 0.0),
                         1.2, sign, span / 3, 0.45)
            self._facade("Concrete", self._offset(first, sign, back, 0.0), self._offset(second, sign, back, 0.0),
                         roof, -sign, span / 4, 2.4)
            self._horizontal(
                "SeatA",
                self._offset(first, sign, setback + 0.3, 1.2), self._offset(second, sign, setback + 0.3, 1.2),
                self._offset(second, sign, back - 0.4, 1.2 + rows * 0.55),
                self._offset(first, sign, back - 0.4, 1.2 + rows * 0.55),
                span / 4, 2.5, True,
            )
            for row in range(rows):
                lane = setback + 0.6 + row * 0.9
                rise = 1.25 + row * 0.55
                self._people(self._offset(first, sign, lane, rise), self._offset(second, sign, lane, rise), row)
            front = setback - 2.6
            roof_a = self._offset(first, sign, front, roof)
            roof_b = self._offset(second, sign, front, roof)
            roof_c = self._offset(second, sign, back, roof + 1.1)
            roof_d = self._offset(first, sign, back, roof + 1.1)
            self._horizontal("Roof", roof_a, roof_b, roof_c, roof_d, span / 5, 3.0, True)
            self._horizontal("Steel", roof_a, roof_d, roof_c, roof_b, span / 5, 3.0, False)
            self._beam("Steel", roof_a, roof_b, 0.28, 0.35)
            self._beam("Steel", self._offset(first, sign, setback, 0.0), roof_a, 0.22, 0.22)
            self._beam("Steel", roof_a, roof_d, 0.12, 0.1)

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
            depth = max(4.0, height * 0.55)
            a = (ax, ay, base + 4)
            b = (bx, by, base + 4)
            c = add((bx, by, base + height), mul(inward, depth))
            d = add((ax, ay, base + height), mul(inward, depth))
            self._horizontal("SeatA", a, b, c, d, length / 4, 2.0, True)
            self._people(add(a, (0, 0, 0.15)), add(b, (0, 0, 0.15)), 0)
            self._people(add(d, (0, 0, 0.2)), add(c, (0, 0, 0.2)), 1)
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
                crown = (x, y, z + 2.4)
                diagonal = norm((across[0] + side[0], across[1] + side[1], 0))
                for axis, scale in ((across, 1.0), (side, 0.85), (diagonal, 0.7)):
                    a = add(crown, (-axis[0] * width * scale, -axis[1] * width * scale, -height * 0.42))
                    b = add(crown, (axis[0] * width * scale, axis[1] * width * scale, -height * 0.42))
                    c = add(crown, (axis[0] * width * scale * 0.55, axis[1] * width * scale * 0.55, height * 0.48))
                    d = add(crown, (-axis[0] * width * scale * 0.55, -axis[1] * width * scale * 0.55, height * 0.48))
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
