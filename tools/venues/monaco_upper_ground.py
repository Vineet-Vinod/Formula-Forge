"""Refine the qualified upper bank and retain its mapped tree on actual Ground."""

from __future__ import annotations

import hashlib
import struct
from collections import Counter

from circuit_dataclasses import Point, RetainedTerrainSource, TerrainGrid
from circuit_mesh import MeshScene
from circuit_scene import ROOT, CircuitScene
from pydantic import TypeAdapter
from shapely import from_wkt
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from venues.monaco_groves import GroundTriangle, ground_height, packed_point
from venues.monaco_natural_ground import classify
from venues.monaco_ravine import replace_ground
from venues.monaco_ravine_dataclasses import RavineChange
from venues.monaco_surfaces import GROUND_MATERIALS, face
from venues.monaco_upper_ground_dataclasses import UpperBankSource


def tree_rows(scene: MeshScene) -> Counter[tuple[str, bytes]]:
    rows: Counter[tuple[str, bytes]] = Counter()
    for tile in scene.tiles.values():
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
            rows[material, bytes(tile.triangles[offset + 4 : offset + 100])] += 1
    return rows


def old_tree(source: UpperBankSource) -> MeshScene:
    scene = MeshScene()
    scene.broadleaf(source.old_tree_base, source.tree_height_m, source.tree_seed)
    if sum(len(tile.triangles) // 100 for tile in scene.tiles.values()) != source.tree_row_count:
        raise ValueError("The retained mapped tree recipe changed")
    return scene


def tree_matches(scene: MeshScene, wanted: Counter[tuple[str, bytes]]) -> dict[str, set[int]]:
    found: Counter[tuple[str, bytes]] = Counter()
    matches: dict[str, set[int]] = {}
    for name, tile in scene.tiles.items():
        if not name.startswith("Building_City_"):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
            if material not in {"Trunk", "TreeCanopy"}:
                continue
            key = material, bytes(tile.triangles[offset + 4 : offset + 100])
            if key in wanted:
                found[key] += 1
                matches.setdefault(name, set()).add(offset)
    if found != wanted:
        raise ValueError("The mapped upper-bank tree no longer matches its exact102 source rows")
    return matches


def supporting_ground(scene: MeshScene, plan: BaseGeometry) -> tuple[GroundTriangle, ...]:
    faces: list[GroundTriangle] = []
    for name, tile in scene.tiles.items():
        if not name.startswith("Tile_Street_"):
            continue
        for offset in range(0, len(tile.triangles), 100):
            material = tile.materials[struct.unpack_from("<I", tile.triangles, offset)[0]]
            if material not in GROUND_MATERIALS | {"MonacoNaturalGround"}:
                continue
            surface = face(tile, offset)
            if (
                surface.plan.area < 1e-9
                or min(v[5] for v in surface.vertices) < 0.05
                or not surface.plan.intersects(plan)
            ):
                continue
            points = [(-v[1] / 100, -v[0] / 100, v[2] / 100) for v in surface.vertices]
            faces.append((points[0], points[1], points[2]))
    return tuple(faces)


def apply(scene: MeshScene, grid: TerrainGrid, source: UpperBankSource) -> tuple[RavineChange, Point]:
    wanted = tree_rows(old_tree(source))
    matches = tree_matches(scene, wanted)
    plan = from_wkt(source.terrain.expected_domain_wkt)
    result = replace_ground(scene, grid, plan, source.terrain)
    support = supporting_ground(scene, plan)
    x, y, _old_z = source.old_tree_base
    corners = [packed_point((x + dx, y + dy, 0)) for dx in (-0.125, 0.125) for dy in (-0.125, 0.125)]
    new_z = min(ground_height(support, a, b) for a, b, _ in corners) - source.tree_burial_m
    base = x, y, new_z
    for name, offsets in matches.items():
        tile = scene.tiles[name]
        tile.triangles = bytearray().join(
            tile.triangles[offset : offset + 100]
            for offset in range(0, len(tile.triangles), 100)
            if offset not in offsets
        )
    scene.broadleaf(base, source.tree_height_m, source.tree_seed)
    classify(scene, plan)
    return result, base


def finish(scene: CircuitScene) -> None:
    source = TypeAdapter(UpperBankSource).validate_json(
        (scene.sources / "architecture/upper-bank-source.json").read_bytes()
    )
    config = source.terrain
    datum = TypeAdapter(RetainedTerrainSource).validate_json(
        (scene.sources / "scenery-ground.json").read_bytes()
    ).relative_datum_m
    if scene.slug != "monaco" or max(
        abs(scene.provenance.origin.latitude - config.origin_lat_lon[0]),
        abs(scene.provenance.origin.longitude - config.origin_lat_lon[1]),
        abs(scene.provenance.route.uniform_scale - config.uniform_scale),
        abs(datum - config.relative_datum_m),
    ) > 1e-9:
        raise ValueError("The upper-bank frame or datum changed")
    for relative, expected in config.protected_source_sha256.items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Upper-bank protected source changed: {relative}")
    plan = from_wkt(config.expected_domain_wkt)
    protected = unary_union([
        scene.corridor_mask.buffer(2),
        *[area.buffer(2) for area in scene.extra_corridors],
        *scene.water_shapes,
        *[Polygon(building.ring).buffer(2.5) for building in scene.buildings],
    ])
    if not plan.is_valid or plan.intersection(protected).area > 1e-8:
        raise ValueError("The upper bank overlaps a protected structure or corridor")
    path = scene.sources / config.grid_file
    if hashlib.sha256(path.read_bytes()).hexdigest() != config.grid_sha256:
        raise ValueError("The retained upper-bank IGN source changed")
    grid = TypeAdapter(TerrainGrid).validate_json(path.read_bytes())
    result, base = apply(scene, grid, source)
    scene.landmarks.append({
        "name": "Finite upper garden and bank with mapped tree",
        "source": "architecture/upper-bank-source.json",
        "changed_ground_area_m2": result.domain_area_m2,
        "mapped_tree_id": source.mapped_tree_id,
        "tree_base_delta_m": base[2] - source.old_tree_base[2],
        "dimensions_status": config.source_note,
    })
