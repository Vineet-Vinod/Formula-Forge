"""Unite the racing deck and escape roads before generating their shared protection."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Attribution/Sources/lasvegas"
SCRATCH = ROOT / "build/lasvegas"
INCLUDE = ROOT / "Source/FormulaForge/Native/track_data/lasvegas_boundaries.inc"


def main() -> None:
    road_path = SCRATCH / "road.csv"
    digest = hashlib.sha256(
        road_path.read_bytes()
        + (SOURCE / "escape-areas.json").read_bytes()
        + Path(__file__).read_bytes()
    ).hexdigest()
    record_path = SOURCE / "boundaries.json"
    if (
        record_path.exists()
        and INCLUDE.exists()
        and (SOURCE / "terrain_mesh.bin").exists()
        and (SOURCE / "barrier_heights.bin").exists()
        and json.loads(record_path.read_text()).get("input_sha256") == digest
    ):
        return
    try:
        import shapely
        from shapely.geometry import Point as QueryPoint
        from shapely.geometry import Polygon, box
    except ImportError as error:
        raise RuntimeError(
            "Install tools/requirements-lasvegas.txt and set LASVEGAS_PYTHON to that Python for changed Vegas geometry"
        ) from error
    from lasvegas_geometry import Scenery

    scenery = Scenery()
    road = scenery.road
    recipe = json.loads((SOURCE / "escape-areas.json").read_text())
    anchors = json.loads((SOURCE / "layout-corrections.json").read_text())["turns"]
    turns = {}
    for anchor in anchors:
        x, y = (value * scenery.scale for value in anchor["near_source_xy_m"])
        turns[anchor["number"]] = min(
            road, key=lambda p: (p.x - x) ** 2 + (p.y - y) ** 2
        )
    right = [p.point(p.half_width + 0.95)[:2] for p in road]
    left = [p.point(-p.half_width - 0.95)[:2] for p in road]
    deck = Polygon(right, [left])
    racing = Polygon(
        [p.point(p.half_width + 0.35)[:2] for p in road],
        [[p.point(-p.half_width - 0.35)[:2] for p in road]],
    )
    if not deck.is_valid or not racing.is_valid:
        raise ValueError(
            "Offset road edges intersect: correct the centreline curvature before forming the deck"
        )
    regions = []
    for escape in recipe["escape_roads"]:
        apex = turns[escape["turn"]]
        entry = min(
            road, key=lambda p: abs(p.station - apex.station + escape["approach_m"])
        )
        length = escape["approach_m"] + escape["beyond_apex_m"]
        half = escape["width_m"] / 2
        start = entry.point(half)[:2], entry.point(-half)[:2]
        end = [(x + entry.tx * length, y + entry.ty * length) for x, y in start]
        polygon = Polygon([start[0], start[1], end[1], end[0]])
        regions.append(
            {
                "name": f"Turn {escape['turn']} escape road",
                "turn": escape["turn"],
                "paint": "Runoff",
                "ring": list(polygon.exterior.coords)[:-1],
                "origin": [entry.x, entry.y, entry.z],
                "direction": [entry.tx, entry.ty],
                "grade": 0.0,
            }
        )
    for apron in recipe["painted_aprons"]:
        apron_sample = turns[apron["turn"]]
        regions.append(
            {
                "name": apron["name"],
                "turn": apron["turn"],
                "paint": apron["paint"],
                "ring": [
                    [x * scenery.scale, y * scenery.scale]
                    for x, y in apron["source_xy_m"]
                ],
                "origin": [apron_sample.x, apron_sample.y, apron_sample.z],
                "direction": [apron_sample.tx, apron_sample.ty],
                "grade": 0.0,
            }
        )
    region_polygons = [Polygon(region["ring"]) for region in regions]
    for polygon in region_polygons:
        if not polygon.is_valid:
            raise ValueError("Invalid authored escape region")
    paved = shapely.union_all([deck, *region_polygons]).simplify(
        0.002, preserve_topology=True
    )
    if paved.geom_type != "Polygon" or not paved.is_valid:
        raise ValueError("The paved deck must remain one connected, valid polygon")
    shapely.prepare(paved)

    def floor(x: float, y: float) -> float:
        for region, polygon in zip(regions, region_polygons, strict=True):
            # Interpolated edge points can fall a few ulps outside their polygon.
            if polygon.distance(QueryPoint(x, y)) <= 0.00001:
                sample, distance = scenery.nearest(x, y)
                # Keep the mouth flush with the road and transition to the entry deck.
                t = max(0.0, min(1.0, (distance - sample.half_width) / 10))
                blend = t * t * (3 - 2 * t)
                return sample.z * (1 - blend) + region["origin"][2] * blend
        return scenery.nearest(x, y)[0].z

    def terrain(x: float, y: float) -> float:
        z = scenery.ground(x, y)
        point = QueryPoint(x, y)
        for region, polygon in zip(regions, region_polygons, strict=True):
            distance = polygon.distance(point)
            if distance < 14:
                t = max(0.0, min(1.0, distance / 14))
                blend = t * t * (3 - 2 * t)
                z = (region["origin"][2] - 0.055) * (1 - blend) + z * blend
        return z

    walls = []
    wall_heights = bytearray()
    for ring in [paved.exterior, *paved.interiors]:
        points = list(ring.coords)
        for a, b in itertools.pairwise(points):
            count = max(1, math.ceil(math.dist(a, b)))
            for i in range(count):
                p = (a[0] + (b[0] - a[0]) * i / count, a[1] + (b[1] - a[1]) * i / count)
                q = (
                    a[0] + (b[0] - a[0]) * (i + 1) / count,
                    a[1] + (b[1] - a[1]) * (i + 1) / count,
                )
                za, zb = floor(*p), floor(*q)
                z = min(za, zb)
                wall_heights.extend(struct.pack("<2f", za, zb))
                walls.append(
                    (
                        p[0] * 17,
                        -p[1] * 17,
                        q[0] * 17,
                        -q[1] * 17,
                        z * 17,
                        (max(za, zb) + 0.95) * 17,
                        0.15 * 17,
                    )
                )
    paving = []
    for triangle in shapely.constrained_delaunay_triangles(
        shapely.segmentize(paved.difference(racing), 8)
    ).geoms:
        vertices = list(triangle.exterior.coords)[:3]
        paving.append(
            tuple(value for x, y in vertices for value in (x, y, floor(x, y)))
        )
    lines = [
        "// Generated by tools/lasvegas_boundaries.py; source east/north metres for paving, simulation units for walls.",
        f"const std::array<AuthoredBarrierSegment, {len(walls)}> kLasVegasWalls{{{{",
    ]
    for ax, ay, bx, by, z, top, radius in walls:
        lines.append(
            f"    {{{{{ax:.5f}f,{ay:.5f}f}},{{{bx:.5f}f,{by:.5f}f}},{z:.5f}f,{top:.5f}f,{radius:.5f}f}},"
        )
    lines.extend(
        [
            "}};",
            f"constexpr std::array<std::array<float,9>, {len(paving)}> kLasVegasPaving{{{{",
        ]
    )
    for triangle in paving:
        lines.append("    {" + ",".join(f"{v:.6f}f" for v in triangle) + "},")
    lines.append("}};")
    payload = "\n".join(lines) + "\n"
    if not INCLUDE.exists() or INCLUDE.read_text() != payload:
        INCLUDE.write_text(payload)
    (SOURCE / "barrier_heights.bin").write_bytes(
        b"FFWALL1\0" + struct.pack("<I", len(walls)) + wall_heights
    )
    (SCRATCH / "escape_regions.json").write_text(json.dumps(regions, indent=2) + "\n")
    ground = bytearray()
    grid = scenery.terrain
    for row in range(math.ceil((grid.rows - 1) * grid.step / 12)):
        y = grid.y + row * 12
        for col in range(math.ceil((grid.columns - 1) * grid.step / 12)):
            x = grid.x + col * 12
            cell = box(x, y, x + 12, y + 12)
            if paved.covers(cell):
                continue
            clipped = cell.difference(paved) if paved.intersects(cell) else cell
            for tri in shapely.constrained_delaunay_triangles(clipped).geoms:
                vertices = list(tri.exterior.coords)[:3]
                ground.extend(
                    struct.pack(
                        "<9f",
                        *(v for px, py in vertices for v in (px, py, terrain(px, py))),
                    )
                )
    (SOURCE / "terrain_mesh.bin").write_bytes(ground)
    record = {
        "input_sha256": digest,
        "recipe": "tools/lasvegas_boundaries.py",
        "paving_triangles": len(paving),
        "collision_segments": len(walls),
        "paved_area_m2": paved.area,
        "regions": regions,
        "method": "Planar union of the narrow track deck and individually authored escape roads/apron. A single boundary supplies native collision and visible protection. Paved floors and clipped terrain meet that boundary.",
    }
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(
        f"Vegas deck: {len(walls)} walls, {len(paving)} extra contact triangles, {paved.area:.0f} square metres"
    )


if __name__ == "__main__":
    main()
