"""Two photo-registered Neftchilar fronts and finite mapped-park tree context."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, add, norm
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_khagani_canopy import CROPS
from venues.baku_khagani_canopy import tree as broad_tree
from venues.baku_khagani_dataclasses import FrontWall, StreetTree
from venues.baku_khagani_geometry import band, glazing, lathe, masonry, relief
from venues.baku_mirbabayev import project_stone_uvs
from venues.baku_mirbabayev_geometry import rail
from venues.baku_waterfront_dataclasses import (
    FinalContextSource,
    ParkTree,
    WaterfrontFront,
)

KIND = "Building_NeftchilarContext"


def face(a: tuple[float, float], b: tuple[float, float], floor: float) -> CourtFace:
    length = math.dist(a, b)
    tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.0)
    return CourtFace(
        (*a, floor), tangent, (tangent[1], -tangent[0], 0.0), length, length
    )


def primary(source: WaterfrontFront) -> CourtFace:
    ring = source.ring_xy_m
    a, b = ring[source.main_edge], ring[(source.main_edge + 1) % len(ring)]
    if not Polygon(ring).exterior.is_ccw:
        a, b = b, a
    return face(a, b, source.floor_relative_m)


def pieces(shape: Polygon | MultiPolygon) -> tuple[Polygon, ...]:
    return tuple(shape.geoms) if isinstance(shape, MultiPolygon) else (shape,)


def wall(
    scene: CircuitScene,
    source: WaterfrontFront,
    frame: CourtFace,
    openings: list[CourtOpening],
) -> None:
    definition = FrontWall(
        source.osm_id,
        source.main_edge,
        frame,
        ((0.0, -source.foundation_drop_m), (frame.length_m, -source.foundation_drop_m)),
        (0.0, frame.length_m),
    )
    masonry(scene, definition, source.cornice_m, openings, "BakuStone", 0.36)
    for opening in openings:
        glazing(scene, frame, opening, stone=False)
        border = opening.shape.buffer(0.14, join_style="mitre").difference(
            opening.shape
        )
        if isinstance(border, (Polygon, MultiPolygon)):
            relief(scene, frame, border, 0.14, -0.02, "Cream")
    for z, thick, depth in (
        (5.55, 0.28, 0.16),
        (11.0, 0.20, 0.15),
        (16.45, 0.18, 0.16),
        (16.65, 0.18, 0.27),
        (16.83, 0.17, 0.40),
    ):
        if source.osm_id == 465003806 and z > 16.0:
            for interval in (
                (0.0, frame.length_m / 2 - 2.8),
                (frame.length_m / 2 + 2.8, frame.length_m),
            ):
                band(scene, frame, z, thick, depth, "Cream", interval)
        else:
            band(scene, frame, z, thick, depth, "Cream")


def rectangular_roof(
    scene: CircuitScene, source: WaterfrontFront, dormers: bool
) -> None:
    shape = orient(Polygon(source.ring_xy_m), sign=1)
    ring = list(shape.exterior.coords)[:-1]
    inset = shape.buffer(-4.5, join_style="mitre")
    if not isinstance(inset, Polygon) or len(inset.exterior.coords) != 5:
        raise ValueError(
            "Qualified waterfront hip roof must retain its four-sided owner"
        )
    inner = list(orient(inset, sign=1).exterior.coords)[:-1]
    pairs = [min(inner, key=lambda q: math.dist(p, q)) for p in ring]
    main = primary(source)
    for i, a in enumerate(ring):
        b = ring[(i + 1) % len(ring)]
        aa, bb = pairs[i], pairs[(i + 1) % len(ring)]
        near = (
            math.dist(a, main.start[:2]) < 1e-7
            and math.dist(b, _point(main, main.length_m, 0)[:2]) < 1e-7
        )
        z0 = source.cornice_m
        z1 = source.roof_top_m if dormers else source.cornice_m + 1.4
        if near and dormers:
            rise = z1 - z0
            u0 = (aa[0] - a[0]) * main.tangent[0] + (aa[1] - a[1]) * main.tangent[1]
            u1 = (bb[0] - a[0]) * main.tangent[0] + (bb[1] - a[1]) * main.tangent[1]
            depth = -(
                (aa[0] - a[0]) * main.outward[0] + (aa[1] - a[1]) * main.outward[1]
            )
            roof = Polygon([(0, z0), (main.length_m, z0), (u1, z1), (u0, z1)])
            holes = [
                _opening(
                    5.4 + (main.length_m - 10.8) * j / 10,
                    1.65,
                    z0 + 1.30,
                    1.90,
                    True,
                    False,
                )
                for j in range(11)
            ]
            surface = roof.difference(unary_union([o.shape for o in holes]))
            if not isinstance(surface, (Polygon, MultiPolygon)):
                raise TypeError("Neftchilar roof lost its sloped polygon")

            def mapped(
                x: float,
                z: float,
                recess: float = 0.0,
                zbase: float = z0,
                climb: float = rise,
                inset_m: float = depth,
            ) -> Point:
                return _point(main, x, z, -(z - zbase) / climb * inset_m + recess)

            for part in pieces(surface):
                for t in constrained_delaunay_triangles(part).geoms:
                    coords = list(t.exterior.coords)[:3]
                    if not t.exterior.is_ccw:
                        coords.reverse()
                    points = [mapped(x, z) for x, z in coords]
                    scene.triangle(KIND, "Steel", points[0], points[1], points[2])
            for opening in holes:
                for t in constrained_delaunay_triangles(opening.shape).geoms:
                    coords = list(t.exterior.coords)[:3]
                    if not t.exterior.is_ccw:
                        coords.reverse()
                    points = [mapped(x, z, -0.08) for x, z in coords]
                    scene.triangle(KIND, "Glass", points[0], points[1], points[2])
                for a2, b2 in pairwise(opening.shape.exterior.coords):
                    scene.quad(
                        KIND,
                        "Cream",
                        mapped(a2[0], a2[1]),
                        mapped(b2[0], b2[1]),
                        mapped(b2[0], b2[1], -0.08),
                        mapped(a2[0], a2[1], -0.08),
                    )
                    scene.beam(
                        KIND,
                        "Cream",
                        mapped(a2[0], a2[1], 0.08),
                        mapped(b2[0], b2[1], 0.08),
                        0.13,
                    )
                x0, l, x1, h = opening.shape.bounds
                scene.beam(
                    KIND,
                    "Trunk",
                    mapped((x0 + x1) / 2, l, -0.05),
                    mapped((x0 + x1) / 2, h, -0.05),
                    0.06,
                )
        else:
            points = [
                (*a, source.floor_relative_m + z0),
                (*b, source.floor_relative_m + z0),
                (*bb, source.floor_relative_m + z1),
                (*aa, source.floor_relative_m + z1),
            ]
            scene.quad(
                KIND,
                "Steel" if dormers else "Roof",
                points[0],
                points[1],
                points[2],
                points[3],
                up=True,
            )
    z = source.floor_relative_m + (
        source.roof_top_m if dormers else source.cornice_m + 1.4
    )
    for t in constrained_delaunay_triangles(inset).geoms:
        coords = list(t.exterior.coords)[:3]
        if not t.exterior.is_ccw:
            coords.reverse()
        points = [(float(x), float(y), z) for x, y in coords]
        scene.triangle(
            KIND, "Steel" if dormers else "Roof", points[0], points[1], points[2]
        )


def crown(scene: CircuitScene, frame: CourtFace, source: WaterfrontFront) -> None:
    x = frame.length_m / 2
    width = 4.4
    opening = _opening(x, width, 11.65, source.roof_top_m - 11.65, True, False)
    border = opening.shape.buffer(0.34, join_style="round").difference(opening.shape)
    if isinstance(border, (Polygon, MultiPolygon)):
        relief(scene, frame, border, 0.26, -0.05, "Cream")
    for radius, depth in ((0.48, 0.11), (0.62, 0.01)):
        trim = opening.shape.buffer(radius, join_style="round").difference(
            opening.shape.buffer(radius - 0.11, join_style="round")
        )
        if isinstance(trim, (Polygon, MultiPolygon)):
            relief(scene, frame, trim, depth, depth - 0.09, "Cream")
    top = source.roof_top_m
    spring = top - width / 2
    for j in range(24):
        a, b = j * math.pi / 24, (j + 1) * math.pi / 24
        p = _point(
            frame, x + width / 2 * math.cos(a), spring + width / 2 * math.sin(a), -0.10
        )
        q = _point(
            frame, x + width / 2 * math.cos(b), spring + width / 2 * math.sin(b), -0.10
        )
        pp = _point(
            frame, x + width / 2 * math.cos(a), spring + width / 2 * math.sin(a), -4.5
        )
        qq = _point(
            frame, x + width / 2 * math.cos(b), spring + width / 2 * math.sin(b), -4.5
        )
        scene.quad(KIND, "Roof", p, pp, qq, q, up=True)
    rail(scene, frame, x - 1.9, x + 1.9, 11.55)


def balustrade(scene: CircuitScene, frame: CourtFace, z: float) -> None:
    for low, thick, depth in ((z, 0.17, 0.26), (z + 0.94, 0.15, 0.29)):
        band(scene, frame, low, thick, depth, "Cream")
    for j in range(math.ceil(frame.length_m / 0.43)):
        x = frame.length_m * (j + 0.5) / math.ceil(frame.length_m / 0.43)
        lathe(
            scene,
            _point(frame, x, z + 0.17, 0.16),
            (
                (0.0, 0.07),
                (0.09, 0.09),
                (0.27, 0.055),
                (0.52, 0.09),
                (0.73, 0.065),
                (0.77, 0.08),
            ),
            "Cream",
            6,
        )
    for x in (0.0, frame.length_m / 2, frame.length_m):
        relief(
            scene,
            frame,
            box(max(0, x - 0.16), z, min(frame.length_m, x + 0.16), z + 1.09),
            0.40,
            0.02,
            "Cream",
        )


def build_front(scene: CircuitScene, source: WaterfrontFront) -> None:
    frame = primary(source)
    length = frame.length_m
    openings = []
    if source.osm_id == 465003806:
        # Fourteen observed arches flank a separate broad central glazed crown.
        centers = [1.3 + j * (length / 2 - 4.6) / 6 for j in range(7)]
        centers += [length - x for x in reversed(centers)]
        for low, high in ((6.15, 10.55), (11.65, 16.1)):
            for x in centers:
                openings.append(_opening(x, 1.65, low, high - low, True, low < 1))
        # Traffic and trees hide much of the shop band; this sparse working
        # schedule keeps its broader openings separate from the upper count.
        for x, width in (
            (1.3, 1.65),
            (4.0, 1.65),
            (6.7, 1.65),
            (length * 0.30, 2.8),
            (length * 0.46, 2.8),
            (length * 0.64, 2.8),
            (length - 4.2, 2.0),
            (length - 1.3, 1.65),
        ):
            openings.append(_opening(x, width, 0.35, 4.5, True, True))
        central = _opening(
            length / 2, 4.4, 11.65, source.roof_top_m - 11.65, True, False
        )
        openings.append(central)
    else:
        centers = [length * (j + 0.5) / 17 for j in range(17)]
        for row, (low, high) in enumerate(((0.35, 4.75), (6.2, 10.2), (11.65, 15.8))):
            for j, x in enumerate(centers):
                if row == 0 and j % 2 == 1:
                    continue
                openings.append(
                    _opening(
                        x, 1.65 if row else 2.0, low, high - low, row == 0, row == 0
                    )
                )
    wall(scene, source, frame, openings)
    for x in (0.35, length - 0.35):
        relief(scene, frame, box(x - 0.25, 0, x + 0.25, 16.4), 0.13, -0.02, "Cream")
        for dx in (-0.14, 0.0, 0.14):
            relief(
                scene,
                frame,
                box(x + dx - 0.023, 0.4, x + dx + 0.023, 16.25),
                0.18,
                0.13,
                "Cream",
            )
        for z in (5.3, 10.8, 16.1):
            band(
                scene,
                frame,
                z,
                0.25,
                0.28,
                "Cream",
                (max(0, x - 0.5), min(length, x + 0.5)),
            )
    if source.osm_id == 465003806:
        # Small repeated cornice teeth are visible beneath the original eaves.
        for j in range(math.ceil(length / 0.48)):
            x = length * (j + 0.5) / math.ceil(length / 0.48)
            if abs(x - length / 2) < 2.8:
                continue
            relief(
                scene,
                frame,
                box(x - 0.075, 16.39, x + 0.075, 16.58),
                0.32,
                0.06,
                "Cream",
            )
    if source.osm_id == 465003806:
        for a, b, z in (
            (0.6, 8.5, 11.55),
            (length - 8.5, length - 0.6, 11.55),
            (0.6, 8.5, 6.05),
        ):
            rail(scene, frame, a, b, z)
        crown(scene, frame, source)
    else:
        rail(scene, frame, length * 0.62, length * 0.80, 11.55)
        scene.box(
            KIND,
            "Black",
            _point(frame, length * 0.71, 15.72, 0.70),
            length * 0.19,
            1.4,
            0.06,
            math.atan2(frame.tangent[1], frame.tangent[0]),
        )
        for fraction in (0.63, 0.79):
            scene.beam(
                KIND,
                "Black",
                _point(frame, length * fraction, 11.58, 0.90),
                _point(frame, length * fraction, 15.72, 0.90),
                0.035,
            )
        balustrade(scene, frame, 17.02)
    ring = list(orient(Polygon(source.ring_xy_m), sign=1).exterior.coords)[:-1]
    for a, b in pairwise([*ring, ring[0]]):
        if (
            math.dist(a, frame.start[:2]) < 1e-8
            and math.dist(b, _point(frame, length, 0)[:2]) < 1e-8
        ):
            continue
        rear = face(a, b, source.floor_relative_m)
        definition = FrontWall(
            source.osm_id,
            -1,
            rear,
            (
                (0.0, -source.foundation_drop_m),
                (rear.length_m, -source.foundation_drop_m),
            ),
            (0.0, rear.length_m),
        )
        masonry(scene, definition, 17.0, [], "BakuStone", 0.36)
        band(scene, rear, 16.8, 0.20, 0.15, "Cream")
    rectangular_roof(scene, source, source.osm_id == 152191301)


def evergreen(scene: MeshScene, pose: ParkTree) -> None:
    base, height, width = pose.base, pose.height_m, pose.crown_width_m
    scene.beam(KIND, "Trunk", base, add(base, (0, 0, height * 0.82)), 0.27)
    for layer in range(6):
        fraction = 0.24 + layer * 0.125
        span = width * (1 - layer * 0.14)
        center = add(base, (0, 0, height * fraction))
        crop = CROPS[(pose.seed + layer) % len(CROPS)]
        u0, u1 = (
            (crop.column * 256 + crop.left_px) / 1536,
            (crop.column * 256 + crop.right_px) / 1536,
        )
        v0, v1 = (
            (crop.row * 256 + crop.top_px) / 1536,
            (crop.row * 256 + crop.bottom_px) / 1536,
        )
        for plane in range(3):
            angle = plane * math.pi / 3 + pose.seed * 0.21 + layer * 0.31
            dx, dy = math.cos(angle) * span / 2, math.sin(angle) * span / 2
            points = (
                (center[0] - dx, center[1] - dy, center[2] + height * 0.14),
                (center[0] + dx, center[1] + dy, center[2] + height * 0.14),
                (center[0] + dx, center[1] + dy, center[2] - height * 0.14),
                (center[0] - dx, center[1] - dy, center[2] - height * 0.14),
            )
            for indices, uv in [
                ((0, 1, 2), ((u0, v0), (u1, v0), (u1, v1))),
                ((0, 2, 3), ((u0, v0), (u1, v1), (u0, v1))),
            ]:
                chosen = tuple(points[i] for i in indices)
                normals = tuple(
                    norm(
                        (
                            (p[0] - base[0]) / (width * 0.5) ** 2,
                            (p[1] - base[1]) / (width * 0.5) ** 2,
                            (p[2] - base[2] - height * 0.08) / (height * 0.85) ** 2,
                        )
                    )
                    for p in chosen
                )
                scene.triangle(
                    KIND,
                    "BakuSahilCanopy",
                    chosen[0],
                    chosen[1],
                    chosen[2],
                    uv,
                    normals=normals,
                )


def build(scene: CircuitScene, source: FinalContextSource) -> None:
    if scene.tiles:
        raise ValueError("Waterfront geometry requires an isolated candidate scene")
    for front in source.fronts:
        build_front(scene, front)
    for item in source.trees:
        if item.form == "evergreen":
            evergreen(scene, item)
        else:
            broad_tree(
                scene,
                StreetTree(
                    item.base,
                    item.height_m,
                    item.crown_width_m,
                    item.seed,
                    "sahil",
                    "Source-fit visual park density estimate; individual root position not surveyed",
                ),
                0.0,
            )

    for tile in scene.tiles.values():
        project_stone_uvs(tile)
