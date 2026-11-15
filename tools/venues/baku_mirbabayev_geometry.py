"""Photo-led Mirbabayev frontage; vertical schedule and edge intervals are estimates."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles, set_precision
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry import Point as GeoPoint
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_khagani_dataclasses import FrontWall
from venues.baku_khagani_geometry import band, lathe, masonry, relief, rosette
from venues.baku_mirbabayev_dataclasses import (
    XY,
    CapBand,
    PalaceGeometry,
    PalacePavilion,
    PalaceSource,
)
from venues.baku_museum_geometry import _panel

KIND = "Building_Mirbabayev"
STONE = "BakuStone"
TRIM = "Cream"


def face(a: XY, b: XY, base: float) -> CourtFace:
    length = math.dist(a, b)
    tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length, 0.0)
    return CourtFace(
        (*a, base), tangent, (tangent[1], -tangent[0], 0.0), length, length
    )


def pieces(shape: Polygon | MultiPolygon) -> tuple[Polygon, ...]:
    return tuple(shape.geoms) if isinstance(shape, MultiPolygon) else (shape,)


def rail(scene: CircuitScene, wall: CourtFace, a: float, b: float, z: float) -> None:
    depth = 0.73
    scene.box(
        KIND,
        TRIM,
        _point(wall, (a + b) / 2, z - 0.11, depth / 2),
        b - a + 0.28,
        depth + 0.12,
        0.22,
        math.atan2(wall.tangent[1], wall.tangent[0]),
    )
    for aa, dd, bb, ee in (
        (a, depth, b, depth),
        (a, 0.0, a, depth),
        (b, 0.0, b, depth),
    ):
        for level in (0.12, 0.88):
            scene.beam(
                KIND,
                "Black",
                _point(wall, aa, z + level, dd),
                _point(wall, bb, z + level, ee),
                0.045,
            )
        count = max(1, math.ceil(math.hypot(bb - aa, ee - dd) / 0.18))
        for i in range(count + 1):
            t = i / count
            x, d = aa + (bb - aa) * t, dd + (ee - dd) * t
            scene.beam(
                KIND,
                "Black",
                _point(wall, x, z + 0.08, d),
                _point(wall, x, z + 0.91, d),
                0.025,
            )
            if i % 3 == 1:
                for j in range(8):
                    angle0, angle1 = j * math.tau / 8, (j + 1) * math.tau / 8
                    scene.beam(
                        KIND,
                        "Black",
                        _point(
                            wall,
                            x + 0.11 * math.cos(angle0),
                            z + 0.48 + 0.21 * math.sin(angle0),
                            d,
                        ),
                        _point(
                            wall,
                            x + 0.11 * math.cos(angle1),
                            z + 0.48 + 0.21 * math.sin(angle1),
                            d,
                        ),
                        0.018,
                    )
    for x in (a + 0.35, b - 0.35):
        relief(
            scene,
            wall,
            Polygon(
                [
                    (x - 0.12, z - 0.70),
                    (x + 0.12, z - 0.70),
                    (x + 0.25, z - 0.12),
                    (x - 0.25, z - 0.12),
                ]
            ),
            0.51,
            -0.02,
            TRIM,
        )


def segmental(x: float, width: float, low: float, height: float) -> CourtOpening:
    half, rise = width / 2, 0.28
    radius = (half * half + rise * rise) / (2 * rise)
    alpha = math.asin(half / radius)
    center_z = low + height - radius
    arch = [
        (
            x + radius * math.cos(math.pi / 2 - alpha + 2 * alpha * i / 16),
            center_z + radius * math.sin(math.pi / 2 - alpha + 2 * alpha * i / 16),
        )
        for i in range(17)
    ]
    return CourtOpening(
        Polygon([(x - half, low), (x + half, low), *arch]), True, low + height - rise
    )


def glazing(
    scene: CircuitScene,
    surface: CourtFace,
    opening: CourtOpening,
    depth: float = -0.25,
    material: str = "Glass",
    stone: bool = True,
) -> None:
    _panel(scene, surface, opening.shape, depth, material)
    frame_material = "Trunk" if opening.door else "White"
    for a, b in pairwise(opening.shape.exterior.coords):
        scene.quad(
            KIND,
            TRIM,
            _point(surface, a[0], a[1]),
            _point(surface, b[0], b[1]),
            _point(surface, b[0], b[1], depth),
            _point(surface, a[0], a[1], depth),
        )
        scene.beam(
            KIND,
            frame_material,
            _point(surface, a[0], a[1], depth + 0.025),
            _point(surface, b[0], b[1], depth + 0.025),
            0.055,
        )
    if stone:
        trim = opening.shape.buffer(0.115, join_style="mitre").difference(opening.shape)
        if isinstance(trim, (Polygon, MultiPolygon)):
            relief(scene, surface, trim, 0.09, -0.01, TRIM)
    x0, z0, x1, z1 = opening.shape.bounds
    x = (x0 + x1) / 2
    scene.beam(
        KIND,
        frame_material,
        _point(surface, x, z0, depth + 0.03),
        _point(surface, x, z1, depth + 0.03),
        0.05,
    )
    transom = (
        opening.arch_spring_m
        if opening.arch_spring_m is not None
        else z0 + (z1 - z0) * 0.72
    )
    scene.beam(
        KIND,
        frame_material,
        _point(surface, x0, transom, depth + 0.03),
        _point(surface, x1, transom, depth + 0.03),
        0.05,
    )


def framed(
    scene: CircuitScene, wall: CourtFace, opening: CourtOpening, pediment: bool = False
) -> None:
    glazing(scene, wall, opening, -0.25, "Glass")
    x0, z0, x1, z1 = opening.shape.bounds
    x = (x0 + x1) / 2
    if pediment:
        hood = Polygon([(x0 - 0.35, z1 + 0.15), (x, z1 + 0.83), (x1 + 0.35, z1 + 0.15)])
        relief(scene, wall, hood, 0.19, -0.02, TRIM)
        relief(scene, wall, hood.buffer(-0.14), 0.215, 0.19, STONE)
    else:
        strip = opening.shape.buffer(0.27).difference(opening.shape.buffer(0.16))
        if isinstance(strip, (Polygon, MultiPolygon)):
            relief(scene, wall, strip, 0.14, 0.02, TRIM)
    if z0 > 5:
        for side in (x0 - 0.26, x1 + 0.26):
            relief(
                scene,
                wall,
                box(side - 0.09, z0 - 0.18, side + 0.09, z1 + 0.18),
                0.12,
                0.01,
                TRIM,
            )


def wall(
    scene: CircuitScene, source: PalaceSource, edge: int, rear: bool = False
) -> float:
    ring = source.ring_xy_m
    bands = source.bands
    # Literal source ring is clockwise; reverse each face for outward source winding.
    surface = face(ring[(edge + 1) % len(ring)], ring[edge], source.floor_relative_m)
    if edge == 4:
        centers = tuple(surface.length_m * (1 - f) for f in source.main_fractions)
    elif edge == 3:
        centers = (surface.length_m * 0.5,)
    else:
        count = max(1, round(surface.length_m / (4.3 if not rear else 4.8)))
        centers = tuple(surface.length_m * (i + 0.5) / count for i in range(count))
    holes: list[CourtOpening] = []
    if edge == 4:
        for ground in source.main_ground:
            x = surface.length_m * (1 - ground.fraction)
            holes.append(
                _opening(
                    x,
                    ground.width_m,
                    bands.ground_bottom_m,
                    bands.ground_head_m - bands.ground_bottom_m,
                    True,
                    True,
                )
                if ground.round_head
                else segmental(
                    x,
                    ground.width_m,
                    bands.ground_bottom_m,
                    bands.ground_head_m - bands.ground_bottom_m,
                )
            )
        for index, x in enumerate(centers):
            ordinary = index in (*range(1, 6), *range(9, 14))
            middle_width = 1.85 if ordinary else 3.0 if index in (0, 7, 14) else 2.25
            holes.append(
                _opening(
                    x,
                    middle_width,
                    bands.middle_bottom_m,
                    bands.middle_head_m - bands.middle_bottom_m,
                    not ordinary,
                    False,
                )
            )
            if index in (0, 7, 14):
                holes.extend(
                    (
                        _opening(
                            x - 1.65,
                            0.70,
                            bands.upper_bottom_m,
                            bands.upper_head_m - bands.upper_bottom_m,
                            False,
                            False,
                        ),
                        _opening(
                            x,
                            2.05,
                            bands.upper_bottom_m,
                            bands.upper_head_m - bands.upper_bottom_m,
                            False,
                            False,
                        ),
                        _opening(
                            x + 1.65,
                            0.70,
                            bands.upper_bottom_m,
                            bands.upper_head_m - bands.upper_bottom_m,
                            False,
                            False,
                        ),
                    )
                )
            else:
                holes.append(
                    _opening(
                        x,
                        1.80 if ordinary else 2.15,
                        bands.upper_bottom_m,
                        bands.upper_head_m - bands.upper_bottom_m,
                        False,
                        False,
                    )
                )
    else:
        for x in centers:
            width = min(
                2.25 if rear else 2.45 if edge == 3 else 1.90, surface.length_m * 0.42
            )
            holes.extend(
                (
                    (
                        _opening(
                            x,
                            width + 0.18,
                            bands.ground_bottom_m,
                            bands.ground_head_m - bands.ground_bottom_m,
                            False,
                            True,
                        )
                        if rear
                        else segmental(
                            x,
                            width + 0.18,
                            bands.ground_bottom_m,
                            bands.ground_head_m - bands.ground_bottom_m,
                        )
                    ),
                    _opening(
                        x,
                        width,
                        bands.middle_bottom_m,
                        bands.middle_head_m - bands.middle_bottom_m,
                        edge == 3,
                        False,
                    ),
                    _opening(
                        x,
                        width - 0.12,
                        bands.upper_bottom_m,
                        bands.upper_head_m - bands.upper_bottom_m,
                        False,
                        False,
                    ),
                )
            )
    masonry(
        scene,
        FrontWall(
            133160749,
            edge,
            surface,
            ((0.0, -0.65), (surface.length_m, -0.65)),
            (0.0, surface.length_m),
        ),
        source.cornice_m,
        holes,
        STONE,
        0.42,
    )
    for h in holes:
        if rear:
            glazing(scene, surface, h, -0.25, "Glass", stone=False)
        else:
            framed(
                scene,
                surface,
                h,
                edge != 3
                and abs(h.shape.bounds[1] - bands.middle_bottom_m) < 1e-6
                and h.arch_spring_m is None,
            )
    for low, thick, depth in (
        (0.0, 0.22, 0.07),
        (bands.first_belt_m - 0.30, 0.22, 0.13),
        (bands.first_belt_m, 0.22, 0.19),
        (bands.second_belt_m, 0.20, 0.17),
        (source.cornice_m - 0.95, 0.19, 0.15),
        (source.cornice_m - 0.65, 0.24, 0.28),
        (source.cornice_m - 0.35, 0.35, 0.40),
    ):
        band(scene, surface, low, thick, depth, TRIM)
    if rear:
        return 0.0
    joint_curve_change = 0.0
    band(scene, surface, source.cornice_m, 0.20, 0.16, TRIM)
    for i in range(max(1, round(surface.length_m / 4.8))):
        x = surface.length_m * (i + 0.5) / max(1, round(surface.length_m / 4.8))
        relief(
            scene,
            surface,
            box(x - 0.21, source.cornice_m, x + 0.21, source.cornice_m + 0.53),
            0.22,
            -0.20,
            TRIM,
        )
    aperture_union = unary_union([h.shape.buffer(0.15) for h in holes])
    for z in (0.8, 1.4, 2.0, 2.6, 3.2, 3.8, 4.4, 5.0, 5.6, 6.2):
        strip = box(0.0, z, surface.length_m, z + 0.035).difference(aperture_union)
        if isinstance(strip, (Polygon, MultiPolygon)):
            snapped = set_precision(strip, 0.001)
            simplified = snapped.simplify(0.0005, preserve_topology=True)
            joint_curve_change = max(
                joint_curve_change, snapped.hausdorff_distance(simplified)
            )
            if isinstance(simplified, (Polygon, MultiPolygon)):
                relief(scene, surface, simplified, 0.025, 0.005, TRIM)
    for x in (0.23, surface.length_m - 0.23):
        relief(
            scene,
            surface,
            box(x - 0.16, bands.first_belt_m + 0.15, x + 0.16, source.cornice_m - 1.10),
            0.13,
            -0.01,
            TRIM,
        )
        for z in (
            bands.first_belt_m + 0.25,
            bands.second_belt_m - 0.55,
            bands.second_belt_m + 0.60,
            source.cornice_m - 1.50,
        ):
            relief(
                scene, surface, box(x - 0.28, z, x + 0.28, z + 0.26), 0.23, 0.02, TRIM
            )
    sorted_centers = sorted(centers)
    for left, right in pairwise(sorted_centers):
        x = (left + right) / 2
        relief(
            scene,
            surface,
            box(
                x - 0.10,
                bands.middle_bottom_m - 0.90,
                x + 0.10,
                bands.second_belt_m - 0.40,
            ),
            0.09,
            -0.01,
            TRIM,
        )
    for x in centers:
        rosette(scene, surface, x, bands.second_belt_m - 0.30, 0.23)
    for i in range(max(1, round(surface.length_m / 0.65))):
        x = surface.length_m * (i + 0.5) / max(1, round(surface.length_m / 0.65))
        relief(
            scene,
            surface,
            box(x - 0.10, source.cornice_m - 0.68, x + 0.10, source.cornice_m - 0.44),
            0.28,
            0.12,
            TRIM,
        )
    if edge == 4:
        c = list(centers)
        for ia, ib, width in (
            (0, 0, 1.15),
            (2, 4, 1.0),
            (6, 6, 1.15),
            (7, 7, 2.0),
            (8, 8, 1.15),
            (10, 12, 1.0),
            (14, 14, 1.15),
            (15, 15, 1.15),
        ):
            rail(
                scene,
                surface,
                min(c[ia], c[ib]) - width,
                max(c[ia], c[ib]) + width,
                bands.upper_bottom_m - 0.1,
            )
        for i in (0, 7, 14):
            width = 1.65 if i == 7 else 1.45
            rail(
                scene, surface, c[i] - width, c[i] + width, bands.middle_bottom_m - 0.17
            )
        cx = surface.length_m * (1 - source.main_fractions[7])
        for delta in (-3.3, 3.3):
            relief(
                scene,
                surface,
                box(
                    cx + delta - 0.17,
                    bands.first_belt_m + 0.05,
                    cx + delta + 0.17,
                    source.cornice_m - 0.85,
                ),
                0.27,
                0.10,
                TRIM,
            )
        crown = Polygon(
            [
                (cx - 4.6, source.cornice_m - 0.1),
                (cx, source.cornice_m + 1.85),
                (cx + 4.6, source.cornice_m - 0.1),
            ]
        )
        relief(scene, surface, crown, 0.27, -0.02, TRIM)
        relief(scene, surface, crown.buffer(-0.26), 0.30, 0.27, STONE)
        rosette(scene, surface, cx, source.cornice_m + 0.65, 0.55)
        crest = Polygon(
            [
                (cx - 0.85, source.cornice_m + 1.65),
                (cx - 0.67, source.cornice_m + 3.8),
                (cx - 0.35, source.cornice_m + 4.1),
                (cx + 0.35, source.cornice_m + 4.1),
                (cx + 0.67, source.cornice_m + 3.8),
                (cx + 0.85, source.cornice_m + 1.65),
            ]
        )
        relief(scene, surface, crest, 0.30, -0.05, TRIM)
        rosette(scene, surface, cx, source.cornice_m + 3.0, 0.42)
        lathe(
            scene,
            _point(surface, cx, source.cornice_m + 4.1, 0.1),
            ((0.0, 0.18), (0.28, 0.26), (0.52, 0.10), (0.95, 0.025)),
            "Steel",
            10,
        )
    elif edge in (0, 1, 2):
        for i, x in enumerate(centers):
            if i % 2 == 0:
                rail(scene, surface, x - 1.15, x + 1.15, bands.middle_bottom_m - 0.17)
            if i % 3 == 1:
                rail(scene, surface, x - 1.15, x + 1.15, bands.upper_bottom_m - 0.1)
    elif edge == 3:
        rail(
            scene,
            surface,
            surface.length_m / 2 - 1.65,
            surface.length_m / 2 + 1.65,
            bands.upper_bottom_m - 0.1,
        )
        for x in (surface.length_m * 0.18, surface.length_m * 0.82):
            relief(
                scene,
                surface,
                box(
                    x - 0.75,
                    bands.middle_bottom_m - 0.8,
                    x + 0.75,
                    bands.middle_head_m + 0.3,
                ),
                0.07,
                0.01,
                TRIM,
            )
            rosette(
                scene,
                surface,
                x,
                (bands.middle_bottom_m + bands.middle_head_m) / 2,
                0.48,
            )

    return joint_curve_change


def roof(scene: CircuitScene, source: PalaceSource, shape: Polygon) -> None:
    # Nested literal occupied rings leave the U-shaped courtyard open. The rear roof is estimated.
    rings = [
        shape,
        *(shape.buffer(-d, join_style="mitre") for d in (1.0, 2.0, 3.0, 4.0)),
    ]
    for i, outer in enumerate(rings):
        region = outer.difference(rings[i + 1]) if i + 1 < len(rings) else outer
        if not isinstance(region, (Polygon, MultiPolygon)):
            raise TypeError("The occupied roof ceased to be polygonal")
        for part in pieces(region):
            for tri in constrained_delaunay_triangles(part).geoms:
                coords = list(orient(tri, sign=1).exterior.coords)[:3]
                p = [
                    (
                        x,
                        y,
                        source.floor_relative_m
                        + source.cornice_m
                        + min(4.0, shape.boundary.distance(GeoPoint(x, y)))
                        * source.roof_rise_m
                        / 4,
                    )
                    for x, y in coords
                ]
                scene.triangle(KIND, "Roof", p[0], p[1], p[2])
    wall_front = face(source.ring_xy_m[5], source.ring_xy_m[4], source.floor_relative_m)
    for f in (
        0.065,
        0.115,
        0.168,
        0.224,
        0.292,
        0.342,
        0.396,
        0.455,
        0.545,
        0.603,
        0.66,
        0.718,
        0.774,
        0.826,
        0.881,
        0.934,
    ):
        x, y, _ = _point(wall_front, wall_front.length_m * f, 0.0, -4.6)
        z = (
            source.floor_relative_m
            + source.cornice_m
            + min(4.0, shape.boundary.distance(GeoPoint(x, y))) * source.roof_rise_m / 4
        )
        if shape.buffer(-0.65).covers(GeoPoint(x, y)):
            scene.box(
                KIND,
                TRIM,
                (x, y, z + 0.7),
                0.62,
                0.62,
                1.4,
                math.atan2(wall_front.tangent[1], wall_front.tangent[0]),
            )
            scene.box(
                KIND,
                TRIM,
                (x, y, z + 1.38),
                0.78,
                0.78,
                0.12,
                math.atan2(wall_front.tangent[1], wall_front.tangent[0]),
            )


def cap_point(band: CapBand, u: float, z: float, depth: float = 0.0) -> Point:
    radius = band.r0 + (band.r1 - band.r0) * (z - band.z0) / (band.z1 - band.z0)
    return (
        band.center[0] + band.tangent[0] * u + band.normal[0] * (radius + depth),
        band.center[1] + band.tangent[1] * u + band.normal[1] * (radius + depth),
        band.center[2] + z,
    )


def pavilion(scene: CircuitScene, source: PalaceSource, item: PalacePavilion) -> None:
    cx, cy, _ = item.center
    profiles = (
        (0.0, item.radius_m),
        (0.66, item.radius_m * 0.97),
        (1.80, item.radius_m * 0.78),
        (3.06, item.radius_m * 0.50),
        (3.84, item.radius_m * 0.22),
    )
    base = source.floor_relative_m + source.cornice_m
    start = math.atan2(item.front_normal[1], item.front_normal[0])
    for i in range(8):
        angle = start + i * math.tau / 8
        normal = math.cos(angle), math.sin(angle)
        tangent = -normal[1], normal[0]
        half = math.tan(math.pi / 8)
        # The eight cap facets have oval apertures on photographed street-facing sides only.
        oval = Polygon(
            [
                (
                    math.cos(j * math.tau / 40) * 0.48,
                    1.73 + math.sin(j * math.tau / 40) * 0.78,
                )
                for j in range(40)
            ]
        )
        hole = oval if i in item.oval_facets else Polygon()
        for (z0, r0), (z1, r1) in pairwise(profiles):
            surface_band = CapBand((cx, cy, base), normal, tangent, z0, r0, z1, r1)
            patch = Polygon(
                [(-r0 * half, z0), (r0 * half, z0), (r1 * half, z1), (-r1 * half, z1)]
            )
            exposed = patch.difference(hole)
            for tri in constrained_delaunay_triangles(exposed).geoms:
                q = [
                    cap_point(surface_band, float(u), float(z))
                    for u, z in list(orient(tri, sign=1).exterior.coords)[:3]
                ]
                scene.triangle(KIND, "Roof", q[0], q[1], q[2])
            if not hole.is_empty:
                glass = patch.intersection(hole)
                for tri in constrained_delaunay_triangles(glass).geoms:
                    q = [
                        cap_point(surface_band, float(u), float(z), -0.12)
                        for u, z in list(orient(tri, sign=1).exterior.coords)[:3]
                    ]
                    scene.triangle(KIND, "Glass", q[0], q[1], q[2])
                trim = patch.intersection(hole.buffer(0.14).difference(hole))
                for tri in constrained_delaunay_triangles(trim).geoms:
                    q = [
                        cap_point(surface_band, float(u), float(z), 0.075)
                        for u, z in list(orient(tri, sign=1).exterior.coords)[:3]
                    ]
                    scene.triangle(KIND, TRIM, q[0], q[1], q[2])
                for a, b in pairwise(oval.exterior.coords):
                    segment = LineString([a, b]).intersection(box(-10.0, z0, 10.0, z1))
                    if isinstance(segment, LineString) and segment.length > 1e-8:
                        aa, bb = segment.coords[0], segment.coords[-1]
                        scene.quad(
                            KIND,
                            TRIM,
                            cap_point(surface_band, aa[0], aa[1]),
                            cap_point(surface_band, bb[0], bb[1]),
                            cap_point(surface_band, bb[0], bb[1], -0.12),
                            cap_point(surface_band, aa[0], aa[1], -0.12),
                        )
        for (z0, r0), (z1, r1) in pairwise(profiles):
            a = (
                cx + normal[0] * r0 + tangent[0] * r0 * half,
                cy + normal[1] * r0 + tangent[1] * r0 * half,
                base + z0,
            )
            b = (
                cx + normal[0] * r1 + tangent[0] * r1 * half,
                cy + normal[1] * r1 + tangent[1] * r1 * half,
                base + z1,
            )
            scene.beam(KIND, "Steel", a, b, 0.045)
    for (z, radius), reverse in ((profiles[0], True), (profiles[-1], False)):
        for i in range(8):
            a = start + i * math.tau / 8 - math.pi / 8
            b = start + (i + 1) * math.tau / 8 - math.pi / 8
            rr = radius / math.cos(math.pi / 8)
            pa = (cx + rr * math.cos(a), cy + rr * math.sin(a), base + z)
            pb = (cx + rr * math.cos(b), cy + rr * math.sin(b), base + z)
            scene.triangle(
                KIND,
                "Roof",
                (cx, cy, base + z),
                pb if reverse else pa,
                pa if reverse else pb,
            )
    # Small open-looking lantern above the slate cap, not a transplanted civic dome.
    lathe(
        scene,
        (cx, cy, base),
        (
            (3.84, item.radius_m * 0.22),
            (3.99, item.radius_m * 0.22),
            (3.99, 0.48),
            (4.54, 0.48),
            (4.64, 0.68),
            (4.94, 0.08),
            (5.88, 0.025),
        ),
        TRIM,
        16,
    )
    for i in range(8):
        angle = start + i * math.tau / 8
        normal = math.cos(angle), math.sin(angle)
        tangent = -normal[1], normal[0]
        a = (
            cx + normal[0] * 0.485 + tangent[0] * 0.16,
            cy + normal[1] * 0.485 + tangent[1] * 0.16,
            base + 4.10,
        )
        b = (
            cx + normal[0] * 0.485 - tangent[0] * 0.16,
            cy + normal[1] * 0.485 - tangent[1] * 0.16,
            base + 4.10,
        )
        scene.banner(a, b, 0.28, "Black", KIND)


def build(scene: CircuitScene, source: PalaceSource) -> PalaceGeometry:
    shape = orient(Polygon(source.ring_xy_m), sign=1)
    joint_curve_change = max(
        wall(scene, source, edge, edge not in (0, 1, 2, 3, 4))
        for edge in range(len(source.ring_xy_m))
    )
    roof(scene, source, shape)
    main = face(source.ring_xy_m[5], source.ring_xy_m[4], source.floor_relative_m)
    corner = face(source.ring_xy_m[4], source.ring_xy_m[3], source.floor_relative_m)
    inside = shape.buffer(-4.8, join_style="mitre")
    centers = []
    for surface, fraction, facets in ((corner, 0.5, (0, 2)), (main, 0.055, (0, 6))):
        seed = _point(surface, surface.length_m * fraction, 0.0, -4.8)
        nearest = nearest_points(inside, GeoPoint(*seed[:2]))[0]
        center = (nearest.x, nearest.y, source.floor_relative_m + source.cornice_m)
        radius = min(
            4.1, shape.boundary.distance(nearest) * math.cos(math.pi / 8) - 0.06
        )
        pavilion(
            scene, source, PalacePavilion(center, radius, main.outward[:2], facets)
        )
        centers.append(center)
    return PalaceGeometry(
        source.cornice_m,
        source.pavilion_top_m,
        tuple(centers),
        source.main_fractions,
        shape.convex_hull.difference(shape).area,
        joint_curve_change,
    )
