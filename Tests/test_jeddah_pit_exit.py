"""The pit-exit terrace shell must close without extending over the fast lane."""

from __future__ import annotations

import math
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, sub
from shapely.geometry import Polygon
from venues.jeddah_pit_exit_geometry import solid


def test_clipped_exit_slabs_are_closed_and_outward_after_native_packing() -> None:
    shape = Polygon([(0, 0), (20, 0), (20, 6), (11, 8), (7, 6), (0, 6)])
    scene = MeshScene()
    solid(scene, shape, 2.3, 2.78, "JeddahEditionStone", "Building_Roof")
    edges: Counter[tuple[Point, Point]] = Counter()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            values = struct.unpack_from("<I24f", tile.triangles, offset)
            points = [
                (-values[2 + i * 8] / 100, -values[1 + i * 8] / 100,
                 values[3 + i * 8] / 100)
                for i in range(3)
            ]
            normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
            length = math.sqrt(sum(value * value for value in normal))
            assert length > 0
            stored = (-values[5], -values[4], values[6])
            assert sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .99999
            center = tuple(sum(p[axis] for p in points) / 3 for axis in range(3))
            if abs(normal[2]) > length * .9:
                assert normal[2] * (center[2] - 2.54) > 0
            else:
                outside = (center[0] + normal[0] / length * .001,
                           center[1] + normal[1] / length * .001)
                from shapely.geometry import Point as ShapePoint

                assert not shape.contains(ShapePoint(*outside))
            for a, b in zip(points, points[1:] + points[:1], strict=True):
                edges[(a, b)] += 1
    assert edges
    assert all(count == 1 and edges[(b, a)] == 1 for (a, b), count in edges.items())


def test_actual_t22_frontage_keeps_south_face_roof_and_road_gap() -> None:
    import json

    from circuit_dataclasses import MeshTile
    from circuit_scene import CircuitScene
    from pydantic import TypeAdapter
    from shapely.geometry import LineString, MultiPoint
    from shapely.ops import unary_union
    from venues.jeddah_pit_exit import exit_tip_mask
    from venues.jeddah_pit_exit import source_record as exit_source
    from venues.jeddah_pit_exit_dataclasses import PitExitFrontage
    from venues.jeddah_pit_exit_geometry import build
    from venues.jeddah_t22_frontage import build as build_arcade
    from venues.jeddah_t22_frontage import coordinate, front_mask, source_record
    from venues.jeddah_t22_frontage_dataclasses import ArcadeOpening

    class RoadMaskScene(CircuitScene):
        def triangle(self, kind: str, material: str, a: Point, b: Point, c: Point,
                     uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                     normals: tuple[Point, ...] | None = None) -> None:
            pass

    class TaggedMesh(MeshScene):
        def tile(self, kind: str, point: Point) -> MeshTile:
            return self.tiles.setdefault(kind, MeshTile())

    def faces(mesh: MeshScene) -> list[tuple[str, str, list[Point], Point, bytes]]:
        result = []
        for kind, tile in mesh.tiles.items():
            for offset in range(0, len(tile.triangles), 100):
                values = struct.unpack_from('<I24f', tile.triangles, offset)
                points = [(-values[2 + 8 * i] / 100, -values[1 + 8 * i] / 100,
                           values[3 + 8 * i] / 100) for i in range(3)]
                result.append((kind, tile.materials[values[0]], points,
                               (-values[5], -values[4], values[6]), bytes(tile.triangles[offset + 4:offset + 100])))
        return result

    scene = RoadMaskScene('jeddah')
    before = list(scene.road), scene.grid, list(scene.buildings)
    scene.road_surfaces('Runoff')
    source = source_record()
    old_footprint = Polygon(scene.footprint(source.osm_id).ring)
    retained = old_footprint.difference(exit_tip_mask(exit_source()))
    available = retained.difference(scene.road_mask.buffer(1.2))
    parts = list(available.geoms)
    assert len(parts) == 2
    detail = TypeAdapter(PitExitFrontage).validate_json((scene.sources / 'pit-exit-frontage.json').read_bytes())
    base = min(scene.ground(x, y) for x, y in retained.exterior.coords)
    old, new = TaggedMesh(), TaggedMesh()
    for part in parts:
        build(old, part, base, detail)
        build(new, part, base, detail, source)
    assert before == (scene.road, scene.grid, scene.buildings)
    old_faces, new_faces = faces(old), faces(new)
    old_roof = Counter((m, raw) for kind, m, _p, _n, raw in old_faces if kind == 'Building_Roof')
    new_roof = Counter((m, raw) for kind, m, _p, _n, raw in new_faces if kind == 'Building_Roof')
    assert old_roof == new_roof
    cut = source.outer_coordinate_m - source.stand_depth_m
    protected = Counter((kind, m, raw) for kind, m, p, n, raw in old_faces
                        if abs(n[2]) < .5 and all(coordinate(v[0], v[1], source) < cut - .02 for v in p))
    actual = Counter((kind, m, raw) for kind, m, _p, _n, raw in new_faces)
    missing = protected - actual
    assert protected and not missing, dict(Counter(kind for kind, _material, _raw in missing))
    allowed = available.buffer(.0003)
    fresh = [row for row in new_faces if row[0].startswith('Building_T22')]
    assert fresh
    closed_edges: Counter[tuple[str, Point, Point]] = Counter()
    for _kind, _material, points, stored, _raw in fresh:
        normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
        length = math.sqrt(sum(v * v for v in normal))
        assert length > 1e-10
        assert sum(a * b for a, b in zip(normal, stored, strict=True)) / length > .999
        projected = MultiPoint([p[:2] for p in points]).convex_hull
        assert projected.difference(allowed).length < .0001
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            closed_edges[(_kind, a, b)] += 1
    assert all(count == closed_edges[(kind, b, a)] for (kind, a, b), count in closed_edges.items())
    coverage = unary_union([Polygon([p[:2] for p in points]) for _k, _m, points, _n, _r in fresh])
    assert coverage.intersection(scene.road_mask).area == 0
    openings: list[ArcadeOpening] = []
    for part in parts:
        openings.extend(build_arcade(TaggedMesh(), part, base, detail.roof_height_m, source))
    assert openings
    sections = []
    height = openings[0].center[2]
    for _kind, _material, points, _n, _raw in new_faces:
        intersections = []
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            if (a[2] < height < b[2]) or (b[2] < height < a[2]):
                t = (height - a[2]) / (b[2] - a[2])
                intersections.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        if len(intersections) == 2:
            sections.append(LineString(intersections))
    for opening in openings:
        x, y, _z = opening.center
        nx, ny = opening.inward_xy
        ray = LineString([(x - nx * .3, y - ny * .3), (x + nx * 2, y + ny * 2)])
        assert not any(ray.intersects(section) for section in sections)
    print(json.dumps({'occupied_parts': len(parts), 'new_triangles': len(new_faces),
                      'protected_south_vertical_faces_exact': sum(protected.values()),
                      'roof_faces_exact': sum(old_roof.values()), 'open_arcade_bays': len(openings),
                      'road_overlap_m2': coverage.intersection(scene.road_mask).area,
                      'new_plan_coverage_m2': coverage.area, 'north_recess_depth_m': source.stand_depth_m,
                      'maximum_field_above_arch_floor_m': max(scene.ground(p.center[0], p.center[1]) - base for p in openings),
                      'removed_upper_north_slab_m2': available.intersection(front_mask(source)).area}))
