"""Reconstruct the finite open ravine from retained IGN observations."""

from __future__ import annotations

import hashlib
import math
import struct
from collections import Counter
from dataclasses import replace
from typing import cast

from circuit_dataclasses import MeshTile, Point, RetainedTerrainSource, TerrainGrid
from circuit_mesh import MeshScene, cross, norm, sub
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter
from shapely import constrained_delaunay_triangles, from_wkt
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_cliff import source_height
from venues.monaco_ravine_dataclasses import (
    RavineChange,
    RavineFace,
    RavinePrecisionFace,
    RavineSource,
)
from venues.monaco_surfaces import (
    GROUND_MATERIALS,
    append,
    face,
    fragment_rows,
    interpolate,
)
from venues.monaco_surfaces_dataclasses import NativeVertex, SurfaceFace
from venues.monaco_west_dataclasses import BelvedereArchitecture


def domain(scene: CircuitScene, source: RavineSource) -> BaseGeometry:
    blocked = unary_union([Polygon(b.ring).buffer(0.5) for b in scene.buildings])
    plan = (
        Polygon(source.outer_xy_m)
        .difference(blocked)
        .intersection(box(*source.window_xy_m))
    )
    belvedere = TypeAdapter(BelvedereArchitecture).validate_json(
        (scene.sources / "architecture/west-belvedere.json").read_bytes()
    )
    plan = plan.difference(
        ShapePoint(belvedere.center_xy_m).buffer(belvedere.radius_m + 0.6)
    )
    for ring in source.mandatory_exclusions:
        plan = plan.difference(Polygon(ring))
    for dataset in scene.osm:
        for element in dataset.elements:
            if (
                element.tags.get("highway")
                in {"footway", "path", "steps", "pedestrian"}
                and len(element.geometry) > 1
            ):
                plan = plan.difference(
                    LineString(
                        [scene.geo(v.lat, v.lon) for v in element.geometry]
                    ).buffer(0.8)
                )
    expected = from_wkt(source.expected_domain_wkt)
    if not plan.is_valid or plan.symmetric_difference(expected).area > 1e-8:
        raise ValueError("The qualified ravine domain or protected features changed")
    protected = unary_union(
        [scene.corridor_mask.buffer(1), *scene.extra_corridors, *scene.water_shapes]
    )
    if plan.intersection(protected).area > 1e-8:
        raise ValueError(
            "The ravine reconstruction intersects race protection or water"
        )
    return plan


def _fraction(plan: BaseGeometry, collar: float, x: float, y: float) -> float:
    t = (
        min(1.0, plan.boundary.distance(ShapePoint(x, y)) / collar)
        if plan.covers(ShapePoint(x, y))
        else 0.0
    )
    return t * t * (3 - 2 * t)


def _height(
    source: SurfaceFace,
    grid: TerrainGrid,
    plan: BaseGeometry,
    collar: float,
    x: float,
    y: float,
) -> float:
    old = interpolate(source, x, y)[2] / 100
    fraction = _fraction(plan, collar, x, y)
    return old + (source_height(grid, x, y) - old) * fraction if fraction > 0 else old


def _points(vertices: tuple[NativeVertex, ...]) -> tuple[Point, ...]:
    return tuple((-v[1] / 100, -v[0] / 100, v[2] / 100) for v in vertices)


def _ulp(value: float) -> float:
    positive = abs(value)
    bits = struct.unpack("<I", struct.pack("<f", positive))[0]
    return struct.unpack("<f", struct.pack("<I", bits + 1))[0] - positive


def _precision(
    offset: int, vertices: tuple[NativeVertex, ...], intended: Point, inside: bool
) -> RavineFace:
    packed = tuple(
        cast(NativeVertex, struct.unpack("<8f", struct.pack("<8f", *v)))
        for v in vertices
    )
    original_points, packed_points = _points(vertices), _points(packed)
    polygon = Polygon([p[:2] for p in original_points])
    longest = max(
        math.dist(a[:2], b[:2])
        for a, b in zip(original_points, original_points[1:] + original_points[:1])
    )
    width = 2 * polygon.area / longest if longest else 0.0
    xy_bound = max(math.hypot(_ulp(v[0]), _ulp(v[1])) / 100 for v in packed)
    xy_error = max(
        math.dist(a[:2], b[:2]) for a, b in zip(original_points, packed_points)
    )
    z_error = max(abs(a[2] - b[2]) for a, b in zip(original_points, packed_points))
    if xy_error > 0.501 * xy_bound or any(
        abs(a[2] - b[2]) > 0.501 * _ulp(v[2]) / 100
        for a, b, v in zip(original_points, packed_points, packed)
    ):
        raise ValueError("Ravine packing exceeded its float32 position bound")
    return RavineFace(
        offset, intended, vertices, packed, width, xy_bound, xy_error, z_error, inside
    )


def _project_outside(source: RavineFace) -> tuple[RavineFace, float]:
    # Quantized XY can move a tiny fragment off its sloping parent plane.
    normal = source.intended_normal
    if abs(normal[2]) < 1e-12:
        raise ValueError("Outside Ground requires a nonvertical parent plane")
    vertices: list[NativeVertex] = []
    maximum_shift = 0.0
    for vertex, packed in zip(source.original_vertices, source.packed_vertices):
        dx = (-packed[1] + vertex[1]) / 100
        dy = (-packed[0] + vertex[0]) / 100
        shift = -(normal[0] * dx + normal[1] * dy) / normal[2]
        vertices.append((packed[0], packed[1], vertex[2] + shift * 100, *vertex[3:]))
        maximum_shift = max(maximum_shift, abs(shift))
    projected = _precision(source.offset, tuple(vertices), normal, False)
    return replace(
        projected,
        minimum_altitude_m=source.minimum_altitude_m,
        maximum_xy_error_m=max(source.maximum_xy_error_m, projected.maximum_xy_error_m),
        maximum_z_error_m=max(source.maximum_z_error_m, projected.maximum_z_error_m),
    ), maximum_shift


def _smooth_normals(payload: bytearray, offsets: list[int], plan: BaseGeometry) -> None:
    sums: dict[tuple[float, float], Point] = {}
    adjacent: dict[tuple[float, float], list[Point]] = {}
    anchored: set[tuple[float, float]] = set()
    for offset in offsets:
        values = struct.unpack_from("<24f", payload, offset + 4)
        vertices = tuple(cast(NativeVertex, values[k : k + 8]) for k in (0, 8, 16))
        points = _points(vertices)
        normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        area = math.sqrt(sum(x * x for x in normal))
        normal = norm(normal)
        native = (-normal[1], -normal[0], normal[2])
        for vertex, point in zip(vertices, points):
            key = vertex[0], vertex[1]
            total = sums.get(key, (0.0, 0.0, 0.0))
            sums[key] = cast(Point, tuple(a + area * b for a, b in zip(total, native)))
            adjacent.setdefault(key, []).append(native)
            if plan.boundary.distance(ShapePoint(point[:2])) < 0.0001:
                anchored.add(key)
    normals: dict[tuple[float, float], Point] = {}
    for key, total in sums.items():
        normal = norm(total)
        if key in anchored:
            continue
        for i in range(101):
            t = i / 100
            candidate = norm(
                ((1 - t) * normal[0], (1 - t) * normal[1], (1 - t) * normal[2] + t)
            )
            if all(
                sum(a * b for a, b in zip(candidate, face)) >= 0.02 * max(0.01, face[2])
                for face in adjacent[key]
            ):
                break
        normals[key] = candidate
    for offset in offsets:
        for k in range(3):
            start = offset + 4 + k * 32
            vertex = struct.unpack_from("<8f", payload, start)
            replacement_normal = normals.get((vertex[0], vertex[1]))
            if replacement_normal is not None:
                struct.pack_into("<3f", payload, start + 12, *replacement_normal)


def _normal_check(
    tile: str, payload: bytearray, sources: list[RavineFace]
) -> tuple[float, float, tuple[RavinePrecisionFace, ...]]:
    minimum = resolved_minimum = 1.0
    unresolved = []
    for source in sources:
        values = struct.unpack_from("<24f", payload, source.offset + 4)
        vertices = tuple(cast(NativeVertex, values[k : k + 8]) for k in (0, 8, 16))
        points = _points(vertices)
        geometric = norm(cross(sub(points[1], points[0]), sub(points[2], points[0])))
        normals = [(-v[4], -v[3], v[5]) for v in vertices]
        alignment = min(sum(a * b for a, b in zip(geometric, n)) for n in normals)
        intended = min(
            sum(a * b for a, b in zip(source.intended_normal, n)) for n in normals
        )
        if alignment < 0:
            if (
                not source.inside
                or source.minimum_altitude_m > 2 * source.xy_ulp_bound_m
            ):
                raise ValueError("A resolved ravine face has an inward stored normal")
            unresolved.append(
                RavinePrecisionFace(
                    tile,
                    source.offset // 100,
                    Polygon([p[:2] for p in points]).area,
                    source.minimum_altitude_m,
                    source.xy_ulp_bound_m,
                    source.maximum_xy_error_m,
                    source.maximum_z_error_m,
                    alignment,
                    intended,
                    points,
                )
            )
            # Sub-ULP inside slivers keep their geometry; only their offending normals align to the packed face.
            native = (-geometric[1], -geometric[0], geometric[2])
            repaired = []
            for k, normal in enumerate(normals):
                if sum(a * b for a, b in zip(geometric, normal)) < 0:
                    struct.pack_into(
                        "<3f", payload, source.offset + 4 + k * 32 + 12, *native
                    )
                    packed = struct.unpack_from(
                        "<3f", payload, source.offset + 4 + k * 32 + 12
                    )
                    normal = (-packed[1], -packed[0], packed[2])
                repaired.append(sum(a * b for a, b in zip(geometric, normal)))
            alignment = min(repaired)
        else:
            resolved_minimum = min(resolved_minimum, alignment)
        minimum = min(minimum, alignment)
    return minimum, resolved_minimum, tuple(unresolved)


def replace_ground(
    scene: MeshScene, grid: TerrainGrid, plan: BaseGeometry, config: RavineSource,
    *, reproject_outside: bool = False,
) -> RavineChange:
    wanted: Counter[tuple[str, str, bytes]] = Counter()
    for witness in config.original_ground_rows:
        wanted[
            witness.tile, witness.material, bytes.fromhex(witness.attributes_hex)
        ] += witness.copies
    selected: Counter[tuple[str, str, bytes]] = Counter()
    staged: dict[str, MeshTile] = {}
    outside_rows = emitted = collapsed_faces = reoriented = 0
    old_area = new_area = collapsed_area = maximum_width = xy_error = z_error = 0.0
    minimum_delta = math.inf
    maximum_delta = -math.inf
    minimum_alignment = minimum_resolved = 1.0
    maximum_projection = 0.0
    unresolved: list[RavinePrecisionFace] = []
    for name, tile in scene.tiles.items():
        if not name.startswith("Tile_Street_"):
            continue
        bounds = box(
            -tile.maximum[1] / 100,
            -tile.maximum[0] / 100,
            -tile.minimum[1] / 100,
            -tile.minimum[0] / 100,
        )
        if not bounds.intersects(plan):
            outside_rows += len(tile.triangles) // 100
            continue
        replacement = MeshTile(materials=list(tile.materials))
        output = bytearray()
        checks: list[RavineFace] = []
        smoothed = []
        count = 0
        for offset in range(0, len(tile.triangles), 100):
            raw = bytes(tile.triangles[offset : offset + 100])
            material = tile.materials[struct.unpack_from("<I", raw)[0]]
            if material not in GROUND_MATERIALS:
                output.extend(raw)
                outside_rows += 1
                continue
            source = face(tile, offset)
            if (
                source.plan.area < 1e-8
                or min(v[5] for v in source.vertices) < 0.05
                or source.plan.intersection(plan).area < 1e-8
            ):
                output.extend(raw)
                outside_rows += 1
                continue
            selected[name, material, raw[4:]] += 1
            count += 1
            old_area += source.plan.area
            original_normal = norm(
                cross(
                    sub(_points(source.vertices)[1], _points(source.vertices)[0]),
                    sub(_points(source.vertices)[2], _points(source.vertices)[0]),
                )
            )
            if original_normal[2] < 0:
                original_normal = cast(
                    Point, tuple(-value for value in original_normal)
                )
            fragments: list[tuple[tuple[NativeVertex, ...], bool, Point, float]] = []
            for vertices in fragment_rows(
                source, source.plan.difference(plan), material
            ):
                fragments.append(
                    (
                        vertices,
                        False,
                        original_normal,
                        Polygon([p[:2] for p in _points(vertices)]).area,
                    )
                )
            intersection = source.plan.intersection(plan)
            xmin, ymin, xmax, ymax = intersection.bounds
            for row in range(
                math.floor(ymin / config.render_step_m),
                math.ceil(ymax / config.render_step_m),
            ):
                for column in range(
                    math.floor(xmin / config.render_step_m),
                    math.ceil(xmax / config.render_step_m),
                ):
                    part = intersection.intersection(
                        box(
                            column * config.render_step_m,
                            row * config.render_step_m,
                            (column + 1) * config.render_step_m,
                            (row + 1) * config.render_step_m,
                        )
                    )
                    if part.area < 1e-10:
                        continue
                    for triangle in constrained_delaunay_triangles(part).geoms:
                        coordinates = list(triangle.exterior.coords)[:3]
                        if not triangle.exterior.is_ccw:
                            coordinates.reverse()
                        vertices_list = []
                        for x, y in coordinates:
                            old = interpolate(source, x, y)
                            fraction = _fraction(plan, config.collar_width_m, x, y)
                            z = _height(source, grid, plan, config.collar_width_m, x, y)
                            minimum_delta = min(minimum_delta, z - old[2] / 100)
                            maximum_delta = max(maximum_delta, z - old[2] / 100)
                            if fraction == 0:
                                vertices_list.append(old)
                                continue
                            epsilon = 0.005
                            dx = (
                                _height(
                                    source,
                                    grid,
                                    plan,
                                    config.collar_width_m,
                                    x + epsilon,
                                    y,
                                )
                                - _height(
                                    source,
                                    grid,
                                    plan,
                                    config.collar_width_m,
                                    x - epsilon,
                                    y,
                                )
                            ) / (2 * epsilon)
                            dy = (
                                _height(
                                    source,
                                    grid,
                                    plan,
                                    config.collar_width_m,
                                    x,
                                    y + epsilon,
                                )
                                - _height(
                                    source,
                                    grid,
                                    plan,
                                    config.collar_width_m,
                                    x,
                                    y - epsilon,
                                )
                            ) / (2 * epsilon)
                            normal = norm((dy, dx, 1.0))
                            vertices_list.append(
                                cast(
                                    NativeVertex, (*old[:2], z * 100, *normal, *old[6:])
                                )
                            )
                        center = triangle.centroid
                        epsilon = 0.005
                        dx = (
                            _height(
                                source,
                                grid,
                                plan,
                                config.collar_width_m,
                                center.x + epsilon,
                                center.y,
                            )
                            - _height(
                                source,
                                grid,
                                plan,
                                config.collar_width_m,
                                center.x - epsilon,
                                center.y,
                            )
                        ) / (2 * epsilon)
                        dy = (
                            _height(
                                source,
                                grid,
                                plan,
                                config.collar_width_m,
                                center.x,
                                center.y + epsilon,
                            )
                            - _height(
                                source,
                                grid,
                                plan,
                                config.collar_width_m,
                                center.x,
                                center.y - epsilon,
                            )
                        ) / (2 * epsilon)
                        fragments.append(
                            (
                                tuple(vertices_list),
                                True,
                                norm((-dx, -dy, 1.0)),
                                triangle.area,
                            )
                        )
            for vertices, inside, intended, area in fragments:
                check = _precision(len(output), vertices, intended, inside)
                if reproject_outside and not inside:
                    check, shift = _project_outside(check)
                    maximum_projection = max(maximum_projection, shift)
                xy_error = max(xy_error, check.maximum_xy_error_m)
                z_error = max(z_error, check.maximum_z_error_m)
                points = _points(check.packed_vertices)
                orientation = cross(
                    sub(points[1], points[0]), sub(points[2], points[0])
                )[2]
                if orientation == 0:
                    if check.minimum_altitude_m > 2 * check.xy_ulp_bound_m:
                        raise ValueError(
                            "A resolved ravine face collapsed in native encoding"
                        )
                    collapsed_faces += 1
                    collapsed_area += area
                    maximum_width = max(maximum_width, check.minimum_altitude_m)
                    continue
                if orientation < 0:
                    vertices = vertices[0], vertices[2], vertices[1]
                    check = _precision(len(output), vertices, intended, inside)
                    if reproject_outside and not inside:
                        check, shift = _project_outside(check)
                        maximum_projection = max(maximum_projection, shift)
                    reoriented += 1
                if inside:
                    smoothed.append(len(output))
                append(output, replacement, material, check.packed_vertices)
                checks.append(check)
                emitted += 1
                new_area += area
        if count:
            _smooth_normals(output, smoothed, plan)
            raw_min, resolved_min, precision_faces = _normal_check(name, output, checks)
            minimum_alignment = min(minimum_alignment, raw_min)
            minimum_resolved = min(minimum_resolved, resolved_min)
            unresolved.extend(precision_faces)
            replacement.triangles = output
            for offset in range(0, len(output), 100):
                for k in range(3):
                    point = struct.unpack_from("<3f", output, offset + 4 + k * 32)
                    for axis, value in enumerate(point):
                        replacement.minimum[axis] = min(
                            replacement.minimum[axis], value
                        )
                        replacement.maximum[axis] = max(
                            replacement.maximum[axis], value
                        )
            staged[name] = replacement
    if selected != wanted or abs(old_area - new_area - collapsed_area) > 1e-5:
        raise ValueError(
            "Ravine original planes changed or its fragments lost unresolved area"
        )
    scene.tiles.update(staged)
    return RavineChange(
        tuple(staged),
        sum(selected.values()),
        emitted,
        outside_rows,
        plan.area,
        minimum_delta,
        maximum_delta,
        collapsed_area,
        collapsed_faces,
        maximum_width,
        xy_error,
        z_error,
        minimum_alignment,
        minimum_resolved,
        tuple(unresolved),
        reoriented,
        maximum_projection,
    )


def finish_terrain(scene: CircuitScene) -> RavineChange:
    config = TypeAdapter(RavineSource).validate_json(
        (scene.sources / "architecture/ravine-source.json").read_bytes()
    )
    datum = (
        TypeAdapter(RetainedTerrainSource)
        .validate_json((scene.sources / "scenery-ground.json").read_bytes())
        .relative_datum_m
    )
    if (
        scene.slug != "monaco"
        or max(
            abs(scene.provenance.origin.latitude - config.origin_lat_lon[0]),
            abs(scene.provenance.origin.longitude - config.origin_lat_lon[1]),
            abs(scene.provenance.route.uniform_scale - config.uniform_scale),
            abs(datum - config.relative_datum_m),
        )
        > 1e-9
    ):
        raise ValueError("The retained Monaco ravine frame or datum changed")
    for relative, expected in config.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Monaco ravine protected input changed: {relative}")
    path = scene.sources / config.grid_file
    if hashlib.sha256(path.read_bytes()).hexdigest() != config.grid_sha256:
        raise ValueError("The retained Monaco ravine IGN grid changed")
    grid = TypeAdapter(TerrainGrid).validate_json(path.read_bytes())
    if (
        grid.step != 2
        or len(grid.heights) != grid.rows * grid.columns
        or not all(math.isfinite(z) for z in grid.heights)
    ):
        raise ValueError(
            "The retained ravine grid is incomplete or no longer uses2m source queries"
        )
    result = replace_ground(scene, grid, domain(scene, config), config)
    scene.landmarks.append(
        {
            "name": "Source-observed open west ravine terrain form",
            "changed_ground_area_m2": result.domain_area_m2,
            "source": "architecture/ravine-source.json",
            "dimensions_status": "0.5m mesh tessellation of retained2m IGN queries with3m old-plane collar. Source outline has1–2m uncertainty; query spacing is not survey accuracy. Existing materials and all outside planes/attributes remain; roads, contact, buildings, paths and belvedere stay fixed.",
        }
    )
    return result
