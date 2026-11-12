"""Build circuit-specific scenery around the exact native simulation samples."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from circuit_dataclasses import (
    BarrierPanel,
    Building,
    Catalogue,
    EdgeCorrection,
    OsmData,
    PitLane,
    Provenance,
    RetainedTerrainSource,
    RoadStation,
    SurfaceProjection,
    TerrainGrid,
)
from circuit_mesh import MeshScene, Point, add, cross, mul, norm, sub
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as GeoPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
MAX_TILE_TRIANGLES = 400_000


class CircuitScene(MeshScene):
    def __init__(self, slug: str) -> None:
        super().__init__()
        self.slug = slug
        self.scratch = ROOT / "build/circuits" / slug
        self.sources = ROOT / "Attribution/Sources" / slug
        self.catalogue = TypeAdapter(Catalogue).validate_json(
            (self.scratch / "catalogue.json").read_bytes()
        )
        self.provenance = TypeAdapter(Provenance).validate_json(
            (self.sources / "provenance.json").read_bytes()
        )
        self.data = ROOT / "Content/Generated" / self.catalogue.content_dir
        self.length = self.catalogue.length_m
        with (self.scratch / "road.csv").open() as handle:
            self.road = TypeAdapter(list[RoadStation]).validate_python(
                list(csv.DictReader(handle))
            )
        self.segments = STRtree(
            [
                LineString(
                    [
                        (p.x, p.y),
                        (
                            self.road[(i + 1) % len(self.road)].x,
                            self.road[(i + 1) % len(self.road)].y,
                        ),
                    ]
                )
                for i, p in enumerate(self.road)
            ]
        )
        self.ground_join_distance = 20.0
        ground_source = self.sources / "scenery-ground.json"
        if ground_source.exists():
            ground_profile = TypeAdapter(RetainedTerrainSource).validate_json(ground_source.read_bytes())
            self.ground_join_distance = ground_profile.road_join_distance_m
        payload = (self.data / "terrain.bin").read_bytes()
        if payload[:8] != b"FFTRN1\0\0":
            raise ValueError("Invalid terrain header")
        x, y, step, columns, rows = struct.unpack_from("<ddfII", payload, 8)
        self.grid = TerrainGrid(
            x,
            y,
            step,
            columns,
            rows,
            struct.unpack_from(f"<{columns * rows}f", payload, 36),
        )
        self.osm: list[OsmData] = []
        for name in (
            "buildings.osm.json.gz",
            "circuit.osm.json.gz",
            "environment.osm.json.gz",
        ):
            path = self.sources / name
            if path.exists():
                self.osm.append(
                    TypeAdapter(OsmData).validate_json(
                        gzip.decompress(path.read_bytes())
                    )
                )
        self.buildings = self._load_buildings()
        self.modeled_buildings: set[int] = set()
        self.landmarks: list[dict[str, str | float | int]] = []
        self.vegetation: list[dict[str, str | float | int]] = []
        self.surface_ranges: list[dict[str, str | float | int]] = []
        self.extra_corridors: list[Polygon] = []
        self.water_shapes: list[Polygon] = []
        self.terrain_cutouts: list[Polygon] = []
        self.ground_patches: list[tuple[Polygon, float, str]] = []
        self.verge_patches: list[tuple[BaseGeometry, str, RoadStation | None]] = []
        self.surface_shapes: list[Polygon] = []
        self.surface_points: list[tuple[Point, Point, Point]] = []
        self.surface_index: STRtree | None = None
        self.panels: list[BarrierPanel] = []
        self._ground_normals: dict[tuple[float, float], Point] = {}
        edge_path = self.sources / "edge-corrections.json"
        self.edge_corrections = (
            TypeAdapter(list[EdgeCorrection]).validate_json(edge_path.read_bytes())
            if edge_path.exists() else []
        )
        self._edge_mask: BaseGeometry = Polygon()

    def geo(self, latitude: float, longitude: float) -> tuple[float, float]:
        origin = self.provenance.origin
        scale = self.provenance.route.uniform_scale
        return (
            math.radians(longitude - origin.longitude)
            * 6378137
            * math.cos(math.radians(origin.latitude))
            * scale,
            math.radians(latitude - origin.latitude) * 6378137 * scale,
        )

    def _rings(self, dataset: OsmData) -> dict[int, list[list[tuple[float, float]]]]:
        nodes = {
            e.id: self.geo(e.lat, e.lon) for e in dataset.elements if e.type == "node"
        }
        paths = {
            e.id: (
                [self.geo(p.lat, p.lon) for p in e.geometry]
                if e.geometry
                else [nodes[n] for n in e.nodes if n in nodes]
            )
            for e in dataset.elements
            if e.type == "way"
        }
        rings: dict[int, list[list[tuple[float, float]]]] = {}
        for element in dataset.elements:
            if element.type == "way":
                points = paths[element.id]
                if len(points) >= 4 and math.dist(points[0], points[-1]) < 0.1:
                    rings[element.id] = [points[:-1]]
            elif (
                element.type == "relation"
                and element.tags.get("type") == "multipolygon"
            ):
                edges = []
                for member in element.members:
                    if member.type != "way" or member.role not in ("", "outer"):
                        continue
                    path = (
                        [self.geo(p.lat, p.lon) for p in member.geometry]
                        if member.geometry
                        else paths.get(member.ref, [])
                    )
                    if len(path) > 1:
                        edges.append(LineString(path))
                components = list(polygonize(unary_union(edges)))
                if components:
                    rings[element.id] = [
                        list(p.exterior.coords)[:-1] for p in components
                    ]
        return rings

    def _load_buildings(self) -> list[Building]:
        result: dict[int, Building] = {}
        for dataset in self.osm:
            rings = self._rings(dataset)
            for element in dataset.elements:
                tags = element.tags
                if element.id not in rings or not any(
                    k in tags for k in ("building", "building:part")
                ):
                    continue
                ring = max(rings[element.id], key=lambda r: Polygon(r).area)
                if not Polygon(ring).is_valid:
                    continue
                height_match = re.search(r"\d+(?:\.\d+)?", tags.get("height", ""))
                floors = re.search(r"\d+", tags.get("building:levels", ""))
                height = (
                    float(height_match[0])
                    if height_match
                    else float(floors[0]) * 3.4
                    if floors
                    else 6.8
                )
                use = tags.get("building:part", tags.get("building", "yes"))
                if (
                    tags.get("leisure") in ("grandstand", "bleachers")
                    or tags.get("grandstand") == "yes"
                    or use == "grandstand"
                ):
                    use = "grandstand"
                result[element.id] = Building(
                    element.id, tags.get("name", ""), use, height, ring, tags
                )
        return list(result.values())

    def footprint(self, osm_id: int) -> Building:
        return next(b for b in self.buildings if b.osm_id == osm_id)

    def area_polygons(self, tags: dict[str, str]) -> list[list[tuple[float, float]]]:
        result = []
        seen: set[int] = set()
        for dataset in self.osm:
            rings = self._rings(dataset)
            for element in dataset.elements:
                if (
                    element.id not in seen
                    and element.id in rings
                    and all(element.tags.get(k) == v for k, v in tags.items())
                ):
                    result.extend(rings[element.id])
                    seen.add(element.id)
        return result

    def at(self, station: float) -> RoadStation:
        position = (station % self.length) / self.length * len(self.road)
        index = int(position)
        t = position - index
        a, b = self.road[index], self.road[(index + 1) % len(self.road)]
        tangent = norm((a.tx * (1 - t) + b.tx * t, a.ty * (1 - t) + b.ty * t, 0))
        return RoadStation(
            station % self.length,
            a.x * (1 - t) + b.x * t,
            a.y * (1 - t) + b.y * t,
            a.z * (1 - t) + b.z * t,
            tangent[0],
            tangent[1],
            a.half_width * (1 - t) + b.half_width * t,
            a.bank * (1 - t) + b.bank * t,
            a.left_shoulder * (1 - t) + b.left_shoulder * t,
            a.right_shoulder * (1 - t) + b.right_shoulder * t,
        )

    def nearest(self, x: float, y: float) -> tuple[RoadStation, float]:
        index = int(self.segments.nearest(GeoPoint(x, y)))
        a, b = self.road[index], self.road[(index + 1) % len(self.road)]
        dx, dy = b.x - a.x, b.y - a.y
        t = max(
            0.0,
            min(1.0, ((x - a.x) * dx + (y - a.y) * dy) / max(1e-9, dx * dx + dy * dy)),
        )
        distance = math.hypot(x - a.x - t * dx, y - a.y - t * dy)
        return self.at(a.station + t * self.length / len(self.road)), distance

    def raw_ground(self, x: float, y: float) -> float:
        for shape, height, _material in self.ground_patches:
            if shape.covers(GeoPoint(x, y)):
                return height
        grid = self.grid
        cx = max(0.0, min(grid.columns - 1.00001, (x - grid.x) / grid.step))
        cy = max(0.0, min(grid.rows - 1.00001, (y - grid.y) / grid.step))
        c, r = int(cx), int(cy)
        tx, ty = cx - c, cy - r
        index = r * grid.columns + c
        return (
            grid.heights[index] * (1 - tx) * (1 - ty)
            + grid.heights[index + 1] * tx * (1 - ty)
            + grid.heights[index + grid.columns] * (1 - tx) * ty
            + grid.heights[index + grid.columns + 1] * tx * ty
        )

    def ground(self, x: float, y: float) -> float:
        sample, distance = self.nearest(x, y)
        if self.catalogue.deck_separation and 4637 < sample.station < 4667:
            seed = self.at(2272)
            along = (x - seed.x) * seed.tx + (y - seed.y) * seed.ty
            lower = self.at(2272 + along)
            if math.hypot(x - lower.x, y - lower.y) < 50:
                sample = lower
                distance = math.hypot(x - lower.x, y - lower.y)
        lane = (x - sample.x) * sample.ty - (y - sample.y) * sample.tx
        shoulder = sample.left_shoulder if lane > 0 else sample.right_shoulder
        edge = sample.half_width + self.kerb_margin(sample.station) + shoulder
        for surface in self.surface_ranges:
            if surface["type"] != "runoff" or int(surface["side"]) != (
                1 if lane > 0 else -1
            ):
                continue
            start, end = float(surface["start_m"]), float(surface["end_m"])
            if (sample.station - start) % self.length <= (end - start) % self.length:
                edge = max(
                    edge, sample.half_width + float(surface["requested_width_m"])
                )
        t = max(0.0, min(1.0, (distance - edge) / self.ground_join_distance))
        blend = t * t * (3 - 2 * t)
        return (sample.z + sample.bank * lane - 0.015) * (1 - blend) + self.raw_ground(
            x, y
        ) * blend

    def _ground_normal(self, x: float, y: float) -> Point:
        key = x, y
        cached = self._ground_normals.get(key)
        if cached is not None:
            return cached
        step = self.grid.step / 4
        normal = norm(
            (
                self.ground(x - step, y) - self.ground(x + step, y),
                self.ground(x, y - step) - self.ground(x, y + step),
                2 * step,
            )
        )
        if len(self._ground_normals) >= 8192:
            self._ground_normals.clear()
        self._ground_normals[key] = normal
        return normal

    def polygon_surface(
        self,
        shape: BaseGeometry,
        material: str,
        lift: float = 0.0,
        sample: RoadStation | None = None,
        paved: bool = False,
        smooth_ground: bool = False,
    ) -> None:
        for triangle in constrained_delaunay_triangles(shape).geoms:
            points: list[Point] = []
            for x, y in list(triangle.exterior.coords)[:3]:
                if sample:
                    branch, _ = self.nearest(x, y)
                    gap = abs(branch.station - sample.station)
                    if min(gap, self.length - gap) > 20:
                        along = (x - sample.x) * sample.tx + (y - sample.y) * sample.ty
                        branch = self.at(sample.station + along)
                    lane = (x - branch.x) * branch.ty - (y - branch.y) * branch.tx
                    z = branch.z + branch.bank * lane
                else:
                    z = self.ground(x, y)
                points.append((x, y, z + lift))
            if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                points.reverse()
            if paved:
                self.surface_shapes.append(Polygon([point[:2] for point in points]))
                self.surface_points.append((points[0], points[1], points[2]))
                self.surface_index = None
            self.triangle(
                "Tile_Ground",
                material,
                points[0],
                points[1],
                points[2],
                tuple((p[0] / 8, p[1] / 8) for p in points),
                tuple(self._ground_normal(p[0], p[1]) for p in points)
                if smooth_ground and sample is None
                else None,
            )

    def paint_surface(
        self, shape: BaseGeometry, material: str, lift: float = 0.005,
        projection: SurfaceProjection | None = None,
    ) -> None:
        if not self.surface_shapes or shape.is_empty:
            return
        if self.surface_index is None:
            self.surface_index = STRtree(self.surface_shapes)
        for index in self.surface_index.query(shape, predicate="intersects"):
            piece = shape.intersection(self.surface_shapes[index])
            a, b, c = self.surface_points[index]
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) < 1e-9 or piece.area < 1e-9:
                continue
            for triangle in constrained_delaunay_triangles(piece).geoms:
                points = []
                for x, y in list(triangle.exterior.coords)[:3]:
                    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
                    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
                    points.append((x, y, u * a[2] + v * b[2] + (1 - u - v) * c[2] + lift))
                if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                    points.reverse()
                uv = tuple((p[0] / 8, p[1] / 8) for p in points)
                if projection:
                    uv = tuple((
                        0.5 + ((p[0] - projection.origin[0]) * projection.axis[0]
                               + (p[1] - projection.origin[1]) * projection.axis[1]) / projection.length_m,
                        0.5 - (-(p[0] - projection.origin[0]) * projection.axis[1]
                               + (p[1] - projection.origin[1]) * projection.axis[0]) / projection.depth_m,
                    ) for p in points)
                self.triangle("Tile_Paint", material, points[0], points[1], points[2], uv)

    def surface_mask(self, sample: RoadStation) -> BaseGeometry:
        if self.catalogue.deck_separation:
            if 4637 < sample.station < 4667:
                return self.deck_road_mask
            if 2150 < sample.station < 2380:
                return self.ground_road_mask
        return self.road_mask

    def kerb_margin(self, station: float) -> float:
        if self.slug != "baku" or station < 2480 or station > 2920:
            return 0.95
        weight = min(1.0, (station - 2480) / 100, (2920 - station) / 120)
        weight = weight * weight * (3 - 2 * weight)
        return 0.95 - 0.8 * weight

    def _edge_section(self, start: float, end: float, side: int) -> BaseGeometry:
        span = (end - start) % self.length
        count = max(1, math.ceil(span / 0.5))
        samples = [self.at(start + span * index / count) for index in range(count + 1)]
        reach = max(
            p.half_width + (p.left_shoulder if side > 0 else p.right_shoulder)
            + self.kerb_margin(p.station) + 4
            for p in samples
        )
        return LineString([(p.x, p.y) for p in samples]).buffer(
            -side * reach, single_sided=True, cap_style="flat", join_style="round"
        )

    def _edge_surface(
        self, shape: BaseGeometry, material: str, lift: float, kind: str,
        kerb_width: float | None = None,
    ) -> None:
        boundary = self.road_mask.boundary if kerb_width else None
        for triangle in constrained_delaunay_triangles(shape).geoms:
            points: list[Point] = []
            for x, y in list(triangle.exterior.coords)[:3]:
                road, _ = self.nearest(x, y)
                lane = (x - road.x) * road.ty - (y - road.y) * road.tx
                height = lift
                if kerb_width and boundary is not None:
                    point = GeoPoint(x, y)
                    distance = boundary.distance(point) * (-1 if self.road_mask.covers(point) else 1)
                    fraction = max(0.0, min(1.0, (distance + 0.01) / kerb_width))
                    height = 0.021 + (lift - 0.021) * fraction
                points.append((x, y, road.z + road.bank * lane + height))
            if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                points.reverse()
            self.triangle(kind, material, points[0], points[1], points[2],
                          tuple((p[0] / 8, p[1] / 8) for p in points))

    def road_surfaces(self, base_material: str = "Grass") -> None:
        if self.edge_corrections:
            self._edge_mask = unary_union([
                self._edge_section(section.start_m, section.end_m, section.side)
                for section in self.edge_corrections
            ])
        road_shapes: list[Polygon] = []
        corridor_shapes: list[Polygon] = []
        ground_roads: list[Polygon] = []
        deck_roads: list[Polygon] = []
        ground_corridors: list[Polygon] = []
        for i, a in enumerate(self.road):
            road_begin, corridor_begin = len(road_shapes), len(corridor_shapes)
            b = self.road[(i + 1) % len(self.road)]
            for target, extra_a, extra_b in (
                (road_shapes, (0.15, 0.15), (0.15, 0.15)),
                (
                    corridor_shapes,
                    (
                        a.left_shoulder + self.kerb_margin(a.station),
                        a.right_shoulder + self.kerb_margin(a.station),
                    ),
                    (
                        b.left_shoulder + self.kerb_margin(b.station),
                        b.right_shoulder + self.kerb_margin(b.station),
                    ),
                ),
            ):
                points = [
                    a.point(a.half_width + extra_a[0]),
                    b.point(b.half_width + extra_b[0]),
                    b.point(-b.half_width - extra_b[1]),
                    a.point(-a.half_width - extra_a[1]),
                ]
                polygon = Polygon([(p[0], p[1]) for p in points])
                if polygon.is_valid:
                    target.append(polygon)
                else:
                    for indices in ((0, 1, 2), (0, 2, 3)):
                        triangle = Polygon(
                            [(points[j][0], points[j][1]) for j in indices]
                        )
                        if triangle.is_valid:
                            target.append(triangle)
            is_deck = self.catalogue.deck_separation and 4637 < a.station < 4667
            if is_deck:
                deck_roads.extend(road_shapes[road_begin:])
            else:
                ground_roads.extend(road_shapes[road_begin:])
                ground_corridors.extend(corridor_shapes[corridor_begin:])
            ds = self.length / len(self.road)
            previous = self.road[(i - 1) % len(self.road)]
            following = self.road[(i + 2) % len(self.road)]

            def normal(p: RoadStation, grade: float) -> Point:
                return norm(
                    (-grade * p.tx - p.bank * p.ty, -grade * p.ty + p.bank * p.tx, 1.0)
                )

            na = normal(a, (b.z - previous.z) / (2 * ds))
            nb = normal(b, (following.z - a.z) / (2 * ds))
            p = [
                a.point(-a.half_width - 0.15, 0.006),
                b.point(-b.half_width - 0.15, 0.006),
                b.point(b.half_width + 0.15, 0.006),
                a.point(a.half_width + 0.15, 0.006),
            ]
            # The accepted asphalt shader expects U along the road and V across it, in 2 m units.
            uv = (
                (a.station / 2, -a.half_width / 2),
                ((a.station + ds) / 2, -b.half_width / 2),
                ((a.station + ds) / 2, b.half_width / 2),
                (a.station / 2, a.half_width / 2),
            )
            self.triangle("Tile_Road", "Road", p[0], p[1], p[2], uv[:3], (na, nb, nb))
            self.triangle(
                "Tile_Road",
                "Road",
                p[0],
                p[2],
                p[3],
                (uv[0], uv[2], uv[3]),
                (na, nb, na),
            )
            for side in (-1, 1):
                stripe_points = [
                    a.point(side * (a.half_width - 0.12), 0.019),
                    b.point(side * (b.half_width - 0.12), 0.019),
                    b.point(side * b.half_width, 0.019),
                    a.point(side * a.half_width, 0.019),
                ]
                if self.edge_corrections and any(
                    Polygon([stripe_points[j][:2] for j in indices]).intersects(self._edge_mask)
                    for indices in ((0, 1, 2), (0, 2, 3))
                ):
                    for indices in ((0, 1, 2), (0, 2, 3)):
                        shape = Polygon([stripe_points[j][:2] for j in indices])
                        if shape.is_valid and shape.area > 1e-10:
                            self._edge_surface(shape.difference(self._edge_mask), "White", 0.019, "Tile_Road")
                    continue
                self.quad(
                    "Tile_Road",
                    "White",
                    a.point(side * (a.half_width - 0.12), 0.019),
                    b.point(side * (b.half_width - 0.12), 0.019),
                    b.point(side * b.half_width, 0.019),
                    a.point(side * a.half_width, 0.019),
                    ds,
                    0.12,
                )
        self.road_mask = unary_union(road_shapes)
        self.ground_road_mask = unary_union(ground_roads)
        self.deck_road_mask = unary_union(deck_roads)
        margin = min(
            min(p.left_shoulder, p.right_shoulder) + self.kerb_margin(p.station) - 0.15
            for p in self.road
        )
        self.corridor_mask = unary_union(
            [self.road_mask.buffer(max(0.05, margin)), *corridor_shapes]
        )
        self.ground_corridor_mask = unary_union(
            [self.ground_road_mask.buffer(max(0.05, margin)), *ground_corridors]
        )
        if self.edge_corrections:
            stripe = self.road_mask.buffer(-0.15).difference(self.road_mask.buffer(-0.27))
            self._edge_surface(stripe.intersection(self._edge_mask), "White", 0.019, "Tile_Road")
        verge_shapes: list[Polygon] = []
        for i, a in enumerate(self.road):
            b = self.road[(i + 1) % len(self.road)]
            for side, sa, sb in (
                (1, a.left_shoulder, b.left_shoulder),
                (-1, a.right_shoulder, b.right_shoulder),
            ):
                points = [
                    a.point(side * (a.half_width + 0.14)),
                    b.point(side * (b.half_width + 0.14)),
                    b.point(
                        side * (b.half_width + self.kerb_margin(b.station) + 0.01 + sb)
                    ),
                    a.point(
                        side * (a.half_width + self.kerb_margin(a.station) + 0.01 + sa)
                    ),
                ]
                polygon = Polygon([(p[0], p[1]) for p in points])
                if polygon.is_valid:
                    verge_shapes.append(polygon)
                    mask = self.road_mask
                    material = base_material
                    if self.catalogue.deck_separation:
                        if 4637 < a.station < 4667:
                            mask = self.deck_road_mask
                            material = "Concrete"
                        elif 2150 < a.station < 2380:
                            mask = self.ground_road_mask
                    patch = polygon.difference(mask)
                    if self.edge_corrections:
                        patch = patch.difference(self._edge_mask)
                    self.verge_patches.append((patch, material, a))
        seams = self.corridor_mask.difference(
            unary_union([self.road_mask, *verge_shapes])
        )
        if self.edge_corrections:
            seams = seams.difference(self._edge_mask)
            patch = self.corridor_mask.intersection(self._edge_mask).difference(self.road_mask)
            self.verge_patches.append((patch, base_material, None))
        if not seams.is_empty:
            self.verge_patches.append((seams, base_material, None))

    def terrain(self, material: str = "Grass") -> None:
        exclusions = unary_union([*self.extra_corridors, *self.terrain_cutouts, *self.water_shapes])
        for shape, verge_material, sample in self.verge_patches:
            upper_deck = sample and self.catalogue.deck_separation and 4637 < sample.station < 4667
            self.polygon_surface(
                shape if upper_deck else shape.difference(exclusions),
                verge_material,
                -0.015,
                sample,
                smooth_ground=True,
            )
        self.corridor_mask = unary_union([self.corridor_mask, *self.extra_corridors])
        ground_corridor = (
            self.ground_corridor_mask
            if self.catalogue.deck_separation
            else self.corridor_mask
        )
        terrain_voids = unary_union(
            [
                ground_corridor,
                *self.extra_corridors,
                *self.water_shapes,
                *self.terrain_cutouts,
            ]
        )
        for shape, _height, patch_material in self.ground_patches:
            self.polygon_surface(shape.difference(terrain_voids), patch_material, smooth_ground=True)
        terrain_voids = unary_union([terrain_voids, *[shape for shape, _, _ in self.ground_patches]])
        grid = self.grid
        for row in range(grid.rows - 1):
            for column in range(grid.columns - 1):
                x, y = grid.x + column * grid.step, grid.y + row * grid.step
                shape = box(x, y, x + grid.step, y + grid.step).difference(
                    terrain_voids
                )
                if not shape.is_empty:
                    self.polygon_surface(shape, material, smooth_ground=True)

    def kerb(
        self,
        start: float,
        end: float,
        side: int,
        width: float = 1.1,
        material: str = "Red",
        height: float = 0.055,
        alternate_material: str = "White",
    ) -> None:
        span = (end - start) % self.length
        corrected = any(
            section.side == side
            and (start - section.start_m) % self.length <= (section.end_m - section.start_m) % self.length
            and (end - section.start_m) % self.length <= (section.end_m - section.start_m) % self.length
            for section in self.edge_corrections
        )
        if corrected:
            shape = self.road_mask.buffer(width - 0.01).difference(self.road_mask.buffer(-0.01))
            shape = shape.intersection(self._edge_section(start, end, side))
            claimed: BaseGeometry = Polygon()
            count = max(1, math.ceil(span / 0.8))
            for index in range(count):
                stripe_start = start + span * index / count
                stripe_end = start + span * (index + 1) / count
                stripe = shape.intersection(self._edge_section(stripe_start, stripe_end, side)).difference(claimed)
                color = material if int((stripe_start + stripe_end) / 4) % 2 == 0 else alternate_material
                self._edge_surface(stripe, color, height, "Tile_Kerb", width)
                claimed = unary_union([claimed, stripe])
            remaining = shape.difference(claimed)
            self._edge_surface(remaining, material, height, "Tile_Kerb", width)
            pieces = [shape] if isinstance(shape, Polygon) else list(shape.geoms)
            self.terrain_cutouts.extend(piece for piece in pieces if isinstance(piece, Polygon))
            self.surface_ranges.append({"type": "kerb", "start_m": start, "end_m": end,
                                        "side": side, "width_m": width})
            return
        count = max(1, math.ceil(span / 0.8))
        for i in range(count):
            a, b = (
                self.at(start + span * i / count),
                self.at(start + span * (i + 1) / count),
            )
            color = (
                material
                if int((start + span * (i + 0.5) / count) / 2) % 2 == 0
                else alternate_material
            )
            edge_a, edge_b = side * (a.half_width + 0.14), side * (b.half_width + 0.14)
            self.quad(
                "Tile_Kerb",
                color,
                a.point(edge_a, 0.021),
                b.point(edge_b, 0.021),
                b.point(edge_b + side * width, height),
                a.point(edge_a + side * width, height),
            )
        self.surface_ranges.append(
            {
                "type": "kerb",
                "start_m": start,
                "end_m": end,
                "side": side,
                "width_m": width,
            }
        )

    def runoff(
        self,
        start: float,
        end: float,
        side: int,
        width: float,
        material: str = "Runoff",
    ) -> None:
        self.surface_ranges.append(
            {
                "type": "runoff",
                "start_m": start,
                "end_m": end,
                "side": side,
                "requested_width_m": width,
                "material": material,
            }
        )
        span = (end - start) % self.length
        count = max(1, math.ceil(span / 2))
        for i in range(count):
            a, b = (
                self.at(start + span * i / count),
                self.at(start + span * (i + 1) / count),
            )
            wa = wb = width
            p = [
                a.point(side * (a.half_width + 0.15)),
                b.point(side * (b.half_width + 0.15)),
                b.point(side * (b.half_width + wb)),
                a.point(side * (a.half_width + wa)),
            ]
            shape = Polygon([(q[0], q[1]) for q in p])
            if shape.is_valid:
                self.extra_corridors.append(shape)
                self.polygon_surface(
                    shape.difference(self.surface_mask(a)), material, 0.001, a, paved=True
                )

    def barriers(self, street: bool = False) -> None:
        post_distance = 4.0
        wall_ends: dict[tuple[float, float], list[tuple[float, float]]] = {}
        with (self.scratch / "barriers.csv").open() as handle:
            for row in csv.DictReader(handle):
                x, y, bx, by, bottom, _top, radius = (
                    float(row[key])
                    for key in ("ax", "ay", "bx", "by", "bottom", "top", "radius")
                )
                connections = wall_ends.get((round(x, 4), round(y, 4)), [])
                wall_connections = [entry for entry in connections if abs(entry[0] - bottom) < 1.0]
                segment_start = min(wall_connections, key=lambda entry: abs(entry[0] - bottom))[1] if wall_connections else 0.0
                segment_length = math.hypot(bx - x, by - y)
                wall_ends.setdefault((round(bx, 4), round(by, 4)), []).append(
                    (bottom, segment_start + segment_length)
                )
                sample, _ = self.nearest((x + bx) / 2, (y + by) / 2)
                if self.catalogue.deck_separation:
                    nearby = [
                        p
                        for p in self.road
                        if math.hypot(p.x - (x + bx) / 2, p.y - (y + by) / 2) < 25
                    ]
                    if nearby:
                        sample = min(nearby, key=lambda p: abs(p.z - bottom))

                def base(px: float, py: float, sample: RoadStation = sample) -> Point:
                    endpoint, _ = self.nearest(px, py)
                    if self.catalogue.deck_separation:
                        gap = abs(endpoint.station - sample.station)
                        if min(gap, self.length - gap) > 100:
                            along = (px - sample.x) * sample.tx + (
                                py - sample.y
                            ) * sample.ty
                            endpoint = self.at(sample.station + along)
                    lane = (px - endpoint.x) * endpoint.ty - (
                        py - endpoint.y
                    ) * endpoint.tx
                    return px, py, endpoint.z + endpoint.bank * lane

                a, b = base(x, y), base(bx, by)
                lane = (x - sample.x) * sample.ty - (y - sample.y) * sample.tx
                pit_wall = (
                    self.slug == "japan"
                    and (
                        (lane > 0 and (sample.station > 5450 or sample.station < 210))
                        or 4637 < sample.station < 4667
                    )
                )
                if street or pit_wall:
                    self.beam(
                        "Tile_Barrier",
                        "Concrete",
                        add(a, (0, 0, 0.47)),
                        add(b, (0, 0, 0.47)),
                        radius * 2,
                        0.94,
                    )
                else:
                    for lift in (0.27, 0.58, 0.88):
                        self.beam(
                            "Tile_Barrier",
                            "Steel",
                            add(a, (0, 0, lift)),
                            add(b, (0, 0, lift)),
                            0.13,
                            0.25,
                        )
                for panel in self.panels:
                    if (lane > 0) != (panel.side > 0) or (
                        sample.station - panel.start
                    ) % self.length > (panel.end - panel.start) % self.length:
                        continue
                    inward = norm(
                        (
                            sample.x - (a[0] + b[0]) / 2,
                            sample.y - (a[1] + b[1]) / 2,
                            0.0,
                        )
                    )
                    pa, pb = (
                        add(a, mul(inward, radius + 0.02)),
                        add(b, mul(inward, radius + 0.02)),
                    )
                    along = (pb[0] - pa[0]) * sample.tx + (pb[1] - pa[1]) * sample.ty
                    reverse = (along > 0) == (panel.side > 0)
                    if reverse:
                        pa, pb = pb, pa
                    # Use continuous wall distance; nearest road stations jump between samples.
                    phase = -(segment_start + segment_length) / 8 if reverse else segment_start / 8
                    self.banner(
                        add(pa, (0, 0, 0.08)),
                        add(pb, (0, 0, 0.08)),
                        0.80,
                        panel.material,
                        u0=phase,
                        repeat=segment_length / 8,
                    )
                    break
                self.banner(add(a, (0, 0, 0.95)), add(b, (0, 0, 0.95)), 2.2, "Fence")
                post_distance += math.dist(a, b)
                if post_distance >= 4:
                    post_distance = 0.0
                    self.beam("Tile_Barrier", "Steel", a, add(a, (0, 0, 3.2)), 0.08)
                    self.beam(
                        "Tile_Barrier",
                        "Steel",
                        add(a, (0, 0, 3.2)),
                        add(a, (0, 0, 3.6)),
                        0.08,
                    )

    def branding(self, start: float, end: float, side: int, material: str) -> None:
        self.panels.append(BarrierPanel(start, end, side, material))
        self.landmarks.append(
            {
                "name": "Reference event panels",
                "start_m": start,
                "end_m": end,
                "side": side,
                "material": material,
            }
        )

    def braking_boards(
        self, apex: float, side: int, distances: tuple[int, ...] = (150, 100, 50)
    ) -> None:
        for distance in distances:
            p = self.at(apex - distance)
            shoulder = p.left_shoulder if side > 0 else p.right_shoulder
            lane = side * (p.half_width + self.kerb_margin(p.station) + shoulder - 0.25)
            a, b = p.point(lane - 0.6, 0.55), p.point(lane + 0.6, 0.55)
            self.banner(a, b, 1.1, str(distance))
            self.beam("Tile_Boards", "Steel", p.point(lane), p.point(lane, 0.55), 0.08)
        self.landmarks.append(
            {
                "name": "Braking distance boards",
                "apex_m": apex,
                "side": side,
                "placement": "Reference/map approach reconstruction; exact event mounting positions estimated.",
            }
        )

    def markings(self) -> None:
        station = self.catalogue.start_station_m
        p = self.at(station)
        q = self.at(station + 0.15)
        self.quad(
            "Tile_Road",
            "White",
            p.point(-p.half_width, 0.022),
            q.point(-q.half_width, 0.022),
            q.point(q.half_width, 0.022),
            p.point(p.half_width, 0.022),
        )
        grid_front = {"spa": 930.0, "buddh": 720.0, "portimao": 650.0}.get(
            self.slug, station
        )
        for position in range(20):
            p = self.at(grid_front - 10 - position * 8)
            lane = (-1 if position % 2 else 1) * 2.8
            a, b = p.point(lane - 1, 0.023), p.point(lane + 1, 0.023)
            self.beam("Tile_Grid", "White", a, b, 0.09, 0.008)
            for edge in (lane - 1, lane + 1):
                a = p.point(edge, 0.023)
                self.beam(
                    "Tile_Grid",
                    "White",
                    a,
                    add(a, (-p.tx * 1.8, -p.ty * 1.8, 0)),
                    0.09,
                    0.008,
                )
        p = self.at(station + 10)
        width = p.half_width + max(p.left_shoulder, p.right_shoulder) + 3
        a, b = p.point(-width), p.point(width)
        self.beam("Building_Gantry", "Steel", a, add(a, (0, 0, 6.5)), 0.25)
        self.beam("Building_Gantry", "Steel", b, add(b, (0, 0, 6.5)), 0.25)
        self.beam(
            "Building_Gantry", "Steel", add(a, (0, 0, 6.5)), add(b, (0, 0, 6.5)), 0.25
        )
        self.banner(
            add(a, (0, 0, 5.3)),
            add(b, (0, 0, 5.3)),
            1.2,
            "VenueSign",
            "Building_Gantry",
        )

    def stand(
        self,
        start: float,
        end: float,
        side: int,
        rows: int = 16,
        setback: float = 4.0,
        roofed: bool = False,
        seat_material: str | None = None,
    ) -> None:
        span = (end - start) % self.length
        steps = max(1, math.ceil(span / 8))
        for step in range(steps):
            a, b = (
                self.at(start + span * step / steps),
                self.at(start + span * (step + 1) / steps),
            )
            near_a = (
                a.half_width
                + 0.95
                + (a.left_shoulder if side > 0 else a.right_shoulder)
                + setback
            )
            near_b = (
                b.half_width
                + 0.95
                + (b.left_shoulder if side > 0 else b.right_shoulder)
                + setback
            )
            for row in range(rows):
                lane_a, lane_b = (
                    side * (near_a + row * 0.88),
                    side * (near_b + row * 0.88),
                )
                za, zb = 0.8 + row * 0.45, 0.8 + (row + 1) * 0.45
                self.quad(
                    "Building_Stand",
                    "Concrete",
                    a.point(lane_a, za),
                    b.point(lane_b, za),
                    b.point(lane_b + side * 0.88, za),
                    a.point(lane_a + side * 0.88, za),
                    2,
                    1,
                    up=True,
                )
                self.beam(
                    "Building_Stand",
                    "Concrete",
                    a.point(lane_a, za - 0.225),
                    b.point(lane_b, za - 0.225),
                    0.12,
                    0.45,
                )
                self.beam(
                    "Building_Stand",
                    seat_material or "SeatBlue",
                    a.point(lane_a + side * 0.3, za + 0.1),
                    b.point(lane_b + side * 0.3, za + 0.1),
                    0.4,
                    0.14,
                )
                self.spectators(
                    a.point(lane_a + side * 0.32, za + 0.2),
                    b.point(lane_b + side * 0.32, za + 0.2),
                    row,
                    "Building_Crowd_Stand",
                )
                self.beam(
                    "Building_Stand",
                    "Concrete",
                    a.point(lane_a, za),
                    a.point(lane_a + side * 0.88, zb),
                    0.12,
                )
            roof_height = 0.8 + rows * 0.45 + 3
            rear_a = a.point(side * (near_a + rows * 0.88), roof_height)
            rear_b = b.point(side * (near_b + rows * 0.88), roof_height)
            for sample, near, rear in ((a, near_a, rear_a), (b, near_b, rear_b)):
                for lane in (side * near, side * (near + rows * 0.88)):
                    top = sample.point(
                        lane, 0.8 + (0 if lane == side * near else rows * 0.45)
                    )
                    base = (top[0], top[1], self.ground(top[0], top[1]))
                    self.beam("Building_Stand", "Steel", base, top, 0.22)
                if step in (0, steps - 1):
                    front = sample.point(side * near, 0.8)
                    back = sample.point(side * (near + rows * 0.88), 0.8 + rows * 0.45)
                    foot_a = (front[0], front[1], self.ground(front[0], front[1]))
                    foot_b = (back[0], back[1], self.ground(back[0], back[1]))
                    self.quad("Building_Stand", "Concrete", foot_a, foot_b, back, front)
                    self.quad("Building_Stand", "Concrete", front, back, foot_b, foot_a)
                self.beam(
                    "Building_Stand",
                    "Steel",
                    sample.point(side * (near + rows * 0.88)),
                    rear,
                    0.16,
                )
                self.beam(
                    "Building_Stand", "Steel", sample.point(side * near), rear, 0.14
                )
            if roofed:
                front_a, front_b = (
                    a.point(side * (near_a - 1), roof_height - 1),
                    b.point(side * (near_b - 1), roof_height - 1),
                )
                self.quad(
                    "Building_Stand",
                    "Roof",
                    front_a,
                    front_b,
                    rear_b,
                    rear_a,
                    2,
                    2,
                    up=True,
                )
                self.quad(
                    "Building_Stand",
                    "Steel",
                    rear_a,
                    rear_b,
                    front_b,
                    front_a,
                    2,
                    2,
                    up=False,
                )
                self.beam("Building_Stand", "Steel", front_a, rear_a, 0.18)
                self.beam(
                    "Building_Stand", "Steel", add(front_a, (0, 0, -0.8)), rear_a, 0.12
                )
        self.landmarks.append(
            {
                "name": "Authored grandstand",
                "start_m": start,
                "end_m": end,
                "side": side,
                "rows": rows,
            }
        )

    def pit_lane(self, profile: PitLane) -> None:
        span = (profile.end_m - profile.start_m) % self.length
        steps = max(1, math.ceil(span / 2))
        inner = self.kerb_margin(profile.start_m) + profile.shoulder_m + 0.16
        for step in range(steps):
            a = self.at(profile.start_m + span * step / steps)
            b = self.at(profile.start_m + span * (step + 1) / steps)
            points = (
                a.point(profile.side * (a.half_width + inner)),
                b.point(profile.side * (b.half_width + inner)),
                b.point(profile.side * (b.half_width + profile.outer_offset_m)),
                a.point(profile.side * (a.half_width + profile.outer_offset_m)),
            )
            shape = Polygon([point[:2] for point in points])
            if not shape.is_valid:
                continue
            shape = shape.difference(self.road_mask)
            self.terrain_cutouts.append(shape)
            self.polygon_surface(shape, "Runoff", 0.001, a, paved=True)
            for offset in (inner + 3.5, profile.outer_offset_m - 0.4):
                line = Polygon([
                    p.point(profile.side * (p.half_width + lane))[:2]
                    for p, lane in ((a, offset), (b, offset), (b, offset + 0.12), (a, offset + 0.12))
                ])
                if line.is_valid:
                    self.paint_surface(line.intersection(shape), "White")
        self.landmarks.append({
            "name": "Paved pit lane and working apron",
            "start_m": profile.start_m,
            "end_m": profile.end_m,
            "side": profile.side,
            "outer_offset_m": profile.outer_offset_m,
            "source_note": profile.source_note,
            "access": "Visual service area outside the closed driving boundary.",
        })

    def pit_building(
        self,
        start: float,
        end: float,
        side: int = -1,
        depth: float = 18.0,
        height: float = 12.0,
        levels: int = 2,
        bay: float = 8.0,
    ) -> None:
        span = (end - start) % self.length
        steps = max(1, math.ceil(span / bay))
        for step in range(steps):
            a, b = (
                self.at(start + span * step / steps),
                self.at(start + span * (step + 1) / steps),
            )
            lane_a, lane_b = side * (a.half_width + 13), side * (b.half_width + 13)
            footprint = Polygon([
                a.point(lane_a)[:2],
                b.point(lane_b)[:2],
                b.point(lane_b + side * depth)[:2],
                a.point(lane_a + side * depth)[:2],
            ])
            if footprint.is_valid:
                self.terrain_cutouts.append(footprint.difference(self.road_mask))
            for level in range(levels + 1):
                z = height * level / levels
                self.beam(
                    "Building_Pits",
                    "Concrete",
                    a.point(lane_a + side * depth / 2, z),
                    b.point(lane_b + side * depth / 2, z),
                    depth,
                    0.4,
                )
                if level < levels:
                    self.banner(
                        a.point(lane_a, z + 0.25),
                        b.point(lane_b, z + 0.25),
                        height / levels - 0.6,
                        "Black" if level == 0 else "Glass",
                        "Building_Pits",
                    )
            self.beam(
                "Building_Pits",
                "Concrete",
                a.point(lane_a),
                a.point(lane_a, height),
                0.5,
            )
        self.landmarks.append(
            {
                "name": "Authored pit building",
                "start_m": start,
                "end_m": end,
                "side": side,
                "height_m": height,
            }
        )

    def save(self) -> int:
        records = []
        for name, tile in sorted(self.tiles.items()):
            triangle_count = len(tile.triangles) // 100
            for part, first in enumerate(range(0, triangle_count, MAX_TILE_TRIANGLES)):
                chunk = tile.triangles[first * 100 : (first + MAX_TILE_TRIANGLES) * 100]
                split = triangle_count > MAX_TILE_TRIANGLES
                asset_name = f"{name}_Part_{part:02d}" if split else name
                minimum, maximum = tile.minimum, tile.maximum
                if split:
                    minimum, maximum = [math.inf] * 3, [-math.inf] * 3
                    for offset in range(4, len(chunk), 100):
                        for vertex in range(3):
                            point = struct.unpack_from("<3f", chunk, offset + vertex * 32)
                            for axis in range(3):
                                minimum[axis] = min(minimum[axis], point[axis])
                                maximum[axis] = max(maximum[axis], point[axis])
                count = len(chunk) // 100
                payload = b"FFLVM1\0\0" + struct.pack("<I", count) + chunk
                path = self.scratch / (asset_name + ".mesh")
                path.write_bytes(payload)
                records.append(
                    {
                        "name": asset_name,
                        "file": path.name,
                        "materials": tile.materials,
                        "bounds": minimum + maximum,
                        "triangles": count,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
        (self.scratch / "manifest.json").write_text(
            json.dumps(
                {
                    "slug": self.slug,
                    "content_dir": self.catalogue.content_dir,
                    "tiles": records,
                    "landmarks": self.landmarks,
                    "vegetation": self.vegetation,
                    "surface_ranges": self.surface_ranges,
                },
                indent=2,
            )
            + "\n"
        )
        return len(records)
