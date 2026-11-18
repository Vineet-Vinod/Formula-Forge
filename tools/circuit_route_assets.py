"""Build finite pit and escape overlays without replaying a venue scene."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from dataclasses import asdict
from pathlib import Path

from circuit_dataclasses import Point
from circuit_escapes_dataclasses import EscapeOverlay
from circuit_mesh import MeshScene, add
from circuit_portals_dataclasses import Barrier, Portal
from circuit_route_assets_dataclasses import RouteAssets, RouteMesh
from pit_routes import encode_barriers, encode_route
from pit_routes_dataclasses import PitRoute, PitSection
from pydantic import TypeAdapter
from shapely.geometry import LineString, Polygon


def clip_foreign_protection(walls: list[Barrier], portals: list[Portal]) -> list[Barrier]:
    result = walls.copy()
    for portal in portals:
        opening = Polygon(portal.polygon_xy_m)
        clipped = []
        for wall in result:
            if wall.top <= portal.bottom_m or wall.bottom >= portal.top_m:
                clipped.append(wall)
                continue
            line = LineString([(wall.ax, wall.ay), (wall.bx, wall.by)])
            mask = opening.buffer(wall.radius, join_style="mitre")
            if not line.intersects(mask):
                clipped.append(wall)
                continue
            remainder = line.difference(mask)
            parts = [remainder] if isinstance(remainder, LineString) else list(remainder.geoms)
            for part in parts:
                if not isinstance(part, LineString) or part.length < 0.001:
                    continue
                first, last = part.coords[0], part.coords[-1]
                clipped.append(Barrier(first[0], first[1], last[0], last[1], wall.bottom, wall.top, wall.radius))
        result = clipped
    return result


def pit_point(section: PitSection, lateral: float, lift: float = 0.0) -> Point:
    return (
        section.x + section.normal_x * lateral,
        section.y + section.normal_y * lateral,
        section.z + section.cross_slope * lateral + lift,
    )


def emit_pit(scene: MeshScene, route: PitRoute) -> None:
    for first, last in zip(route.sections, route.sections[1:]):
        points = (
            pit_point(first, -first.half_width),
            pit_point(last, -last.half_width),
            pit_point(last, last.half_width),
            pit_point(first, first.half_width),
        )
        for indices in ((0, 1, 2), (0, 2, 3)):
            face = points[indices[0]], points[indices[1]], points[indices[2]]
            scene.triangle("Tile_Route", "Runoff", *face, uv=tuple((p[0] / 4, p[1] / 4) for p in face))
        for side in (-1, 1):
            scene.quad(
                "Tile_Route", "White",
                pit_point(first, side * (first.half_width - 0.12), 0.006),
                pit_point(last, side * (last.half_width - 0.12), 0.006),
                pit_point(last, side * last.half_width, 0.006),
                pit_point(first, side * first.half_width, 0.006),
                up=True,
            )


def emit_protection(scene: MeshScene, walls: list[Barrier], street: bool) -> None:
    for index, wall in enumerate(walls):
        first = wall.ax, wall.ay, wall.bottom
        last = wall.bx, wall.by, wall.bottom
        height = wall.top - wall.bottom
        if street:
            scene.beam("Tile_Route", "Concrete", add(first, (0, 0, height / 2)),
                add(last, (0, 0, height / 2)), wall.radius * 2, height)
        else:
            for lift in (0.27, 0.58, min(0.88, height)):
                scene.beam("Tile_Route", "Steel", add(first, (0, 0, lift)), add(last, (0, 0, lift)), 0.13, 0.25)
        scene.banner(add(first, (0, 0, height)), add(last, (0, 0, height)), 2.2, "Fence")
        if index % 4 == 0:
            scene.beam("Tile_Route", "Steel", first, add(first, (0, 0, height + 2.2)), 0.08)


def prepare(circuit: str, destination: Path, pit_path: Path | None, escape_path: Path | None) -> RouteAssets:
    route = TypeAdapter(PitRoute).validate_json(pit_path.read_bytes()) if pit_path else None
    escapes = TypeAdapter(EscapeOverlay).validate_json(escape_path.read_bytes()) if escape_path else None
    if (route is not None and route.slug != circuit) or (escapes is not None and escapes.circuit != circuit):
        raise ValueError("Route overlay belongs to a different circuit")
    if route is None and escapes is None:
        raise ValueError("A route overlay requires a qualified pit or escape input")
    if any(path.resolve().is_relative_to(destination.resolve()) for path in (pit_path, escape_path) if path is not None):
        raise ValueError("Generated overlay output must not contain its source inputs")
    destination.mkdir(parents=True, exist_ok=True)
    scene = MeshScene()
    portals = list(route.portals) if route else []
    pit_walls = list(route.barriers) if route else []
    escape_walls = list(escapes.barriers) if escapes else []
    walls = clip_foreign_protection(pit_walls, list(escapes.portals)) if escapes else pit_walls
    walls += clip_foreign_protection(escape_walls, list(route.portals)) if route else escape_walls
    if route:
        emit_pit(scene, route)
    cosmetic_portals: list[Portal] = []
    if circuit == "jeddah" and route is not None:
        from venues.jeddah_pit_protection import emit_exit_paving, exit_floor_portals

        emit_exit_paving(scene, route)
        cosmetic_portals = exit_floor_portals(route)
    if escapes:
        portals.extend(escapes.portals)
        for triangle in escapes.paving:
            points = triangle.a, triangle.b, triangle.c
            scene.triangle("Tile_Route", triangle.material, *points,
                uv=tuple((p[0] / 4, p[1] / 4) for p in points))
    if circuit == "jeddah" and route is not None:
        from venues.jeddah_pit_approach import (
            approach_floor_portals,
            emit_approach_paving,
            entry_extra_barriers,
        )

        walls.extend(entry_extra_barriers(route))
        emit_approach_paving(scene, route)
        cosmetic_portals.extend(approach_floor_portals(route))
    walkway_rails: set[Barrier] = set()
    graded_walls: set[Barrier] = set()
    if circuit == "jeddah" and route is not None:
        from venues.jeddah_early_pit import emit_details as early_details
        from venues.jeddah_early_pit import load_recipe as early_recipe

        early = early_recipe(route)
        openings = [*early.portals, *early.separator_portals]
        walls = clip_foreign_protection(walls, openings)
        portals.extend(openings)
        cosmetic_portals.extend(early.floor_portals)
        walls.extend(record.barrier for record in early.walls)
        graded_walls.update(record.barrier for record in early.walls)
        early_details(scene, early)
        from venues.jeddah_pit_walkway import build_walkway, walkway_recipe

        reference = Path(__file__).resolve().parents[1] / "build/circuits/jeddah/barriers.csv"
        with reference.open() as handle:
            base_walls = TypeAdapter(list[Barrier]).validate_python(list(csv.DictReader(handle)))
        retained_base = clip_foreign_protection(base_walls, portals)
        walkway = build_walkway(scene, route, [*retained_base, *walls], walkway_recipe())
        walkway_rails.update(walkway.extra_barriers)
        walls.extend(walkway.extra_barriers)
        cosmetic_portals.extend(walkway.floor_portals)
        if len(cosmetic_portals) > 512:
            raise ValueError("Jeddah cosmetic openings exceed the native editor limit")
        (destination / "pit-walkway-proof.json").write_text(json.dumps(asdict(walkway.proof), indent=2) + "\n")
    street = circuit in {"baku", "jeddah", "monaco", "singapore", "lasvegas", "australia", "canada"}
    emit_protection(scene, [wall for wall in walls if wall not in walkway_rails | graded_walls], street)
    if circuit == "jeddah" and route is not None:
        from venues.jeddah_pit_approach import (
            emit_approach_gantry,
            emit_approach_panels,
        )
        from venues.jeddah_pit_entry_panels import emit_entry_panels
        from venues.jeddah_pit_protection import emit_panels

        emit_panels(scene, route)
        emit_entry_panels(scene, route)
        emit_approach_panels(scene, route)
        emit_approach_gantry(scene, route)
    records = []
    for original_name, tile in sorted(scene.tiles.items()):
        name = original_name.replace("Tile_Street", "Tile_Route").replace("Building_City", "Tile_Route_Structure")
        if not name.startswith("Tile_Route_"):
            raise ValueError("Route overlay would overwrite a base scene asset: " + name)
        count = len(tile.triangles) // 100
        if count > 500_000 or count * 100 != len(tile.triangles):
            raise ValueError("Route mesh exceeds the native import bound")
        raw = struct.pack("<8sI", b"FFLVM1\0\0", count) + tile.triangles
        path = destination / (name + ".mesh")
        path.write_bytes(raw)
        records.append(RouteMesh(name, path.name, tile.materials, tile.minimum + tile.maximum,
            count, hashlib.sha256(raw).hexdigest()))
    lane_file = "pit_lane.bin" if route else None
    if route:
        (destination / "pit_lane.bin").write_bytes(encode_route(route))
    (destination / "pit_barriers.bin").write_bytes(encode_barriers(portals, walls))
    escape_file = None
    if escapes and escapes.paving:
        escape_file = "escape_surface.bin"
        raw_surface = bytearray(struct.pack("<8sI", b"FFSURF1\0", len(escapes.paving)))
        for triangle in escapes.paving:
            raw_surface.extend(struct.pack("<9f", *triangle.a, *triangle.b, *triangle.c))
        (destination / escape_file).write_bytes(raw_surface)
    root = Path(__file__).resolve().parents[1]
    inputs = [p for p in (pit_path, escape_path) if p is not None]
    if circuit == "jeddah" and route is not None:
        inputs.extend(root / path for path in (
            "Attribution/Sources/jeddah/pit-exit-protection.json",
            "tools/venues/jeddah_pit_protection.py",
            "tools/venues/jeddah_pit_protection_dataclasses.py",
            "Attribution/Sources/jeddah/pit-approach-corridor.json",
            "tools/venues/jeddah_pit_approach.py",
            "tools/venues/jeddah_pit_approach_dataclasses.py",
            "Attribution/Sources/jeddah/pit-entry-panels.json",
            "tools/venues/jeddah_pit_entry_panels.py",
            "tools/venues/jeddah_pit_entry_panels_dataclasses.py",
            "Attribution/Sources/jeddah/pit-personnel-walkway.json",
            "Attribution/Sources/jeddah/pit-early-corridor.json",
            "tools/venues/jeddah_early_pit.py",
            "tools/venues/jeddah_early_pit_dataclasses.py",
            "tools/venues/jeddah_early_pit_material.py",
            "tools/venues/jeddah_pit_walkway.py",
            "tools/venues/jeddah_pit_walkway_dataclasses.py",
            "build/circuits/jeddah/barriers.csv",
            "build/circuits/jeddah/manifest.json",
        ))
    result = RouteAssets(circuit, 1, "Source east/north/Z metres; packed meshes use Unreal world centimetres",
        records, portals, list(escapes.paint_domains) if escapes else [],
        {str(p.relative_to(root) if p.is_relative_to(root) else p): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in inputs}, lane_file, "pit_barriers.bin",
        "Finite route overlay. Original venue meshes remain the base. Native clipping/reclassification, exact physical clearance, source review and fresh live validation are required before acceptance.", escape_file, cosmetic_portals)
    (destination / "manifest.json").write_text(json.dumps(asdict(result), indent=2) + "\n")
    (destination / "portals.json").write_text(json.dumps({"portals": [asdict(p) for p in portals]}, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("circuit")
    parser.add_argument("--pit", type=Path)
    parser.add_argument("--escapes", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.circuit, args.output, args.pit, args.escapes)
    print(f"{result.circuit}: {len(result.tiles)} route meshes, {sum(p.triangles for p in result.tiles)} faces")


if __name__ == "__main__":
    main()
