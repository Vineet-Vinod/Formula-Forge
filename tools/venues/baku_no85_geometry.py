"""Photo-registered loggia/oriel No85; floor pitches and rear mass are estimates."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_geometry import frame
from venues.baku_khagani_geometry import band, glazing, lathe, relief, rosette
from venues.baku_mirbabayev import project_stone_uvs
from venues.baku_no85_dataclasses import No85Model, No85Source
from venues.baku_philharmonic_geometry import column

KIND = "Building_Neftchilar85"


def main_face(source: No85Source) -> CourtFace:
    a, b = (
        source.ring_xy_m[source.main_edge],
        source.ring_xy_m[(source.main_edge + 1) % len(source.ring_xy_m)],
    )
    if not Polygon(source.ring_xy_m).exterior.is_ccw:
        a, b = b, a
    return frame((*a, source.floor_relative_m), (*b, source.floor_relative_m))


def local_shape(face: CourtFace, shape: BaseGeometry) -> BaseGeometry:
    def ring(points):
        return [_point(face, float(u), 0.0, -float(v))[:2] for u, v in points]

    if not isinstance(shape, Polygon):
        raise TypeError("No85 authoring domains must be polygonal")
    return Polygon(
        ring(shape.exterior.coords), [ring(hole.coords) for hole in shape.interiors]
    )


def parts(shape: BaseGeometry) -> tuple[Polygon, ...]:
    if isinstance(shape, Polygon):
        return (shape,)
    return (
        tuple(p for p in shape.geoms if isinstance(p, Polygon))
        if hasattr(shape, "geoms")
        else ()
    )


def slab(
    scene: CircuitScene,
    frame: CourtFace,
    plan: tuple[tuple[float, float], ...],
    z: float,
    thick: float = 0.16,
) -> None:
    shape = orient(Polygon([_point(frame, u, 0.0, d)[:2] for u, d in plan]), sign=1)
    for t in constrained_delaunay_triangles(shape).geoms:
        xy = list(t.exterior.coords)[:3]
        if not t.exterior.is_ccw:
            xy.reverse()
        for h, reverse in ((z, False), (z - thick, True)):
            points = [(float(x), float(y), frame.start[2] + h) for x, y in xy]
            if reverse:
                points.reverse()
            scene.triangle(KIND, "Cream", points[0], points[1], points[2])
    for a, b in pairwise(shape.exterior.coords):
        scene.quad(
            KIND,
            "Cream",
            (*a, frame.start[2] + z - thick),
            (*b, frame.start[2] + z - thick),
            (*b, frame.start[2] + z),
            (*a, frame.start[2] + z),
        )


def iron(
    scene: CircuitScene,
    face: CourtFace,
    points: tuple[tuple[float, float], ...],
    z: float,
) -> None:
    for a, b in pairwise(points):
        for h in (0.12, 0.95):
            scene.beam(
                KIND,
                "Black",
                _point(face, a[0], z + h, a[1]),
                _point(face, b[0], z + h, b[1]),
                0.035,
            )
    for j, (u, d) in enumerate(points):
        scene.beam(
            KIND,
            "Black",
            _point(face, u, z + 0.08, d),
            _point(face, u, z + 0.99, d),
            0.023,
        )
        if j % 4 == 1:
            for k in range(8):
                angle0, angle1 = k * math.tau / 8, (k + 1) * math.tau / 8
                scene.beam(
                    KIND,
                    "Black",
                    _point(
                        face,
                        u + 0.085 * math.cos(angle0),
                        z + 0.5 + 0.18 * math.sin(angle0),
                        d,
                    ),
                    _point(
                        face,
                        u + 0.085 * math.cos(angle1),
                        z + 0.5 + 0.18 * math.sin(angle1),
                        d,
                    ),
                    0.018,
                )


def bow(scene: CircuitScene, face: CourtFace, x: float, width: float, z: float) -> None:
    points = tuple(
        (
            x + width / 2 * math.cos(math.pi * j / 24),
            0.08 + 0.82 * math.sin(math.pi * j / 24),
        )
        for j in range(25)
    )
    slab(scene, face, points, z)
    iron(scene, face, points, z)


def back_wall(
    scene: CircuitScene,
    face: CourtFace,
    u: float,
    width: float,
    low: float,
    high: float,
    levels: tuple[float, ...],
    bays: int = 1,
) -> None:
    surface = box(u - width / 2, low, u + width / 2, high)
    windows = [
        _opening(
            u - width / 2 + width * (j + 0.5) / bays,
            width / bays * 0.64,
            z + 0.25,
            min(2.7, high - z - 0.3),
            False,
            False,
        )
        for j in range(bays)
        for z in levels
        if low - 0.1 <= z < high - 1.0
    ]
    masonry = surface.difference(unary_union([o.shape for o in windows]))
    if not isinstance(masonry, (Polygon, MultiPolygon)):
        raise TypeError("No85 loggia backing lost its masonry")
    relief(scene, face, masonry, -1.42, -1.65, "BakuStone")
    for opening in windows:
        glazing(scene, face, opening, -1.50, stone=False)
    for opening in windows:
        a, b, c, d = opening.shape.bounds
        for x in (a, (a + c) / 2, c):
            scene.beam(
                KIND,
                "White",
                _point(face, x, b, -1.47),
                _point(face, x, d, -1.47),
                0.065,
            )


def oriel(
    scene: CircuitScene,
    face: CourtFace,
    u: float,
    rows: tuple[tuple[float, float], ...],
) -> None:
    width = 3.2
    low = 4.1
    top = 23.5
    depth = 0.95
    plan = (
        (u - width / 2, 0.0),
        (u - width * 0.30, depth),
        (u + width * 0.30, depth),
        (u + width / 2, 0.0),
    )
    for a, b in pairwise(plan):
        side = frame(_point(face, a[0], low, a[1]), _point(face, b[0], low, b[1]))
        holes = [
            _opening(
                side.length_m / 2, side.length_m * 0.77, za - low, zb - za, False, False
            )
            for za, zb in rows
        ]
        masonry = box(0, 0, side.length_m, top - low).difference(
            unary_union([o.shape for o in holes])
        )
        if not isinstance(masonry, (Polygon, MultiPolygon)):
            raise TypeError("No85 oriel lost its outer wall")
        relief(scene, side, masonry, 0.0, -0.18, "Cream")
        for opening in holes:
            glazing(scene, side, opening, -0.12, stone=False)
            x0, z0, x1, z1 = opening.shape.bounds
            for x in (x0, (x0 + x1) / 2, x1):
                scene.beam(
                    KIND,
                    "White",
                    _point(side, x, z0, -0.08),
                    _point(side, x, z1, -0.08),
                    0.075,
                )
            for z in (z0, z1 - 0.60, z1):
                scene.beam(
                    KIND,
                    "White",
                    _point(side, x0, z, -0.08),
                    _point(side, x1, z, -0.08),
                    0.065,
                )
        for za, zb in rows:
            z = zb - low + 0.12
            band(scene, side, z, 0.15, 0.17, "Cream")
            if z + 0.65 < top - low:
                relief(
                    scene,
                    side,
                    box(0.10, z + 0.17, side.length_m - 0.10, z + 0.65),
                    0.08,
                    0.0,
                    "Cream",
                )
                if side.length_m > 0.8:
                    rosette(scene, side, side.length_m / 2, z + 0.4, 0.20)
        band(scene, side, top - low - 0.16, 0.16, 0.25, "Cream")
    slab(scene, face, plan, top, 0.20)
    slab(scene, face, plan, low, 0.24)


def front(scene: CircuitScene, source: No85Source) -> None:
    face = main_face(source)
    length = face.length_m
    a, b = source.main_core_interval_m
    silhouette = Polygon(
        [
            (0, -source.foundation_drop_m),
            (length, -source.foundation_drop_m),
            (length, source.wing_cornice_m),
            (b, source.wing_cornice_m),
            (b, source.cornice_m),
            (a, source.cornice_m),
            (a, source.wing_cornice_m),
            (0, source.wing_cornice_m),
        ]
    )
    group_centers = (length / 2 - 4.2, length / 2, length / 2 + 4.2)
    lower = [_opening(x, 3.55, 4.25, 15.0, True, False) for x in group_centers]
    flanks = [_opening(x, 3.85, 8.0, 11.25, True, False) for x in (6.3, length - 6.3)]
    upper = CourtOpening(
        box(length / 2 - 6.25, 19.65, length / 2 + 6.25, 26.65), False, None
    )
    plain = []
    for x in (10.25, length - 10.25):
        for z in (*source.lower_floor_m, *source.upper_floor_m):
            plain.append(_opening(x, 1.35, z + 0.3, 2.65, False, False))
    # The shops are source-occluded: these five broad apertures are a working
    # lower-band estimate, with no invented entrance stairs or signage.
    for x in (10.25, *group_centers, length - 10.25):
        plain.append(_opening(x, 2.7, 0.35, 3.45, False, True))
    masonry = silhouette.difference(
        unary_union([o.shape for o in [*lower, *flanks, upper, *plain]])
    )
    if not isinstance(masonry, (Polygon, MultiPolygon)):
        raise TypeError("No85 street wall lost its shape")
    relief(scene, face, masonry, 0.0, -1.65, "BakuStone")
    for opening in [*lower, *flanks]:
        border = opening.shape.buffer(0.20, join_style="round").difference(
            opening.shape
        )
        if isinstance(border, (Polygon, MultiPolygon)):
            relief(scene, face, border, 0.18, -0.02, "Cream")
        x0, z0, x1, z1 = opening.shape.bounds
        back_wall(scene, face, (x0 + x1) / 2, x1 - x0, z0, z1, source.lower_floor_m)
    for opening in plain:
        glazing(scene, face, opening, stone=True)
    for x in group_centers:
        for z in source.lower_floor_m:
            bow(scene, face, x, 3.38, z)
    for x in (6.3, length - 6.3):
        for z in source.lower_floor_m[1:]:
            slab(
                scene,
                face,
                (
                    (x - 1.77, -1.48),
                    (x + 1.77, -1.48),
                    (x + 1.77, 0.02),
                    (x - 1.77, 0.02),
                ),
                z,
            )
            iron(
                scene, face, tuple((x - 1.7 + j * 3.4 / 18, 0.04) for j in range(19)), z
            )
    back_wall(scene, face, length / 2, 12.5, 19.65, 26.65, source.upper_floor_m, bays=3)
    for z in source.upper_floor_m:
        slab(
            scene,
            face,
            (
                (length / 2 - 6.2, -1.48),
                (length / 2 + 6.2, -1.48),
                (length / 2 + 6.2, 0.02),
                (length / 2 - 6.2, 0.02),
            ),
            z,
        )
        iron(
            scene,
            face,
            tuple((length / 2 - 6.2 + j * 12.4 / 62, 0.05) for j in range(63)),
            z,
        )
    for x in (length / 2 - 6.1, length / 2 - 2.05, length / 2 + 2.05, length / 2 + 6.1):
        for dx in (-0.15, 0.15):
            column(scene, _point(face, x + dx, 19.45, 0.12), 0.12, 7.30, "Cream", KIND)
    rows = tuple((z + 0.15, min(z + 2.85, 23.1)) for z in (*source.lower_floor_m, 19.1))
    for x in (1.82, length - 1.82):
        oriel(scene, face, x, rows)
    for z, thickness, depth in (
        (4.05, 0.18, 0.15),
        (19.25, 0.28, 0.28),
        (23.65, 0.24, 0.28),
    ):
        band(scene, face, z, thickness, depth, "Cream")
    for interval, top in (
        ((0.0, a), source.wing_cornice_m),
        ((a, b), source.cornice_m),
        ((b, length), source.wing_cornice_m),
    ):
        for z, t, d in (
            (top - 0.65, 0.20, 0.26),
            (top - 0.45, 0.18, 0.38),
            (top - 0.27, 0.27, 0.52),
        ):
            band(scene, face, z, t, d, "Cream", interval)
        for j in range(max(1, math.ceil((interval[1] - interval[0]) / 0.52))):
            x = interval[0] + (interval[1] - interval[0]) * (j + 0.5) / max(
                1, math.ceil((interval[1] - interval[0]) / 0.52)
            )
            relief(
                scene,
                face,
                box(x - 0.09, top - 0.85, x + 0.09, top - 0.58),
                0.30,
                0.05,
                "Cream",
            )
    for z, interval in ((source.cornice_m, (a, b)),):
        band(scene, face, z, 0.18, 0.32, "Cream", interval)
        band(scene, face, z + 0.88, 0.15, 0.34, "Cream", interval)
        for j in range(math.ceil((b - a) / 0.42)):
            x = a + (b - a) * (j + 0.5) / math.ceil((b - a) / 0.42)
            lathe(
                scene,
                _point(face, x, z + 0.18, 0.20),
                (
                    (0.0, 0.065),
                    (0.1, 0.085),
                    (0.28, 0.05),
                    (0.52, 0.08),
                    (0.68, 0.06),
                    (0.71, 0.07),
                ),
                "Cream",
                6,
            )


def roof_domains(source: No85Source) -> tuple[tuple[BaseGeometry, float], ...]:
    face = main_face(source)
    owner = Polygon(source.ring_xy_m)
    a, b = source.main_core_interval_m
    core = local_shape(face, box(a, -0.01, b, 14.0)).intersection(owner)
    front_block = (
        local_shape(face, box(-100, -1, 100, 15.5)).intersection(owner).difference(core)
    )
    middle = local_shape(face, box(-100, 15.5, 100, 32.0)).intersection(owner)
    back = owner.difference(unary_union([core, front_block, middle]))
    return (
        (core, source.cornice_m),
        (front_block, source.wing_cornice_m),
        (middle, source.middle_return_m),
        (back, source.back_return_m),
    )


def build(scene: CircuitScene, source: No85Source) -> No85Model:
    if scene.tiles:
        raise ValueError("No85 geometry requires isolated candidate tiles")
    owner = orient(Polygon(source.ring_xy_m), sign=1)
    domains = roof_domains(source)
    main = main_face(source)
    front(scene, source)
    main_line = LineString([main.start[:2], _point(main, main.length_m, 0.0)[:2]])
    for domain, top in domains:
        for polygon in parts(domain):
            polygon = orient(polygon, sign=1)
            for t in constrained_delaunay_triangles(polygon).geoms:
                points = [
                    (float(x), float(y), source.floor_relative_m + top)
                    for x, y in list(t.exterior.coords)[:3]
                ]
                if not t.exterior.is_ccw:
                    points.reverse()
                scene.triangle(KIND, "Roof", points[0], points[1], points[2])
            for ring in (polygon.exterior, *polygon.interiors):
                for a, b in pairwise(ring.coords):
                    edge = LineString([a, b])
                    outside = edge.difference(owner.boundary.buffer(1e-7)).length < 1e-6
                    if edge.length < 1e-8:
                        continue
                    if outside and main_line.buffer(1e-7).covers(edge):
                        continue
                    lower = -source.foundation_drop_m
                    if not outside:
                        middle = edge.interpolate(0.5, normalized=True)
                        adjacent = [
                            height
                            for other, height in domains
                            if other is not domain and other.buffer(1e-7).covers(middle)
                        ]
                        if not adjacent or max(adjacent) >= top - 0.001:
                            continue
                        lower = max(adjacent)
                    wall = frame(
                        (*a, source.floor_relative_m), (*b, source.floor_relative_m)
                    )
                    openings = []
                    if (
                        outside
                        and edge.difference(
                            LineString(
                                [source.ring_xy_m[10], source.ring_xy_m[11]]
                            ).buffer(1e-7)
                        ).length
                        < 1e-6
                    ):
                        count = max(1, round(wall.length_m / 5.0))
                        for j in range(count):
                            x = wall.length_m * (j + 0.5) / count
                            for z in (4.3, 8.0, 11.7, 15.4, 19.1):
                                if z + 2.7 < top - 0.6:
                                    openings.append(
                                        _opening(
                                            x,
                                            1.45,
                                            z + 0.25,
                                            2.6,
                                            top < 21.0 and z > top - 5.0,
                                            False,
                                        )
                                    )
                    shape = box(0, lower, wall.length_m, top).difference(
                        unary_union([o.shape for o in openings])
                    )
                    if not isinstance(shape, (Polygon, MultiPolygon)):
                        raise TypeError("No85 return lost its masonry")
                    relief(scene, wall, shape, 0.0, -0.34, "BakuStone")
                    for opening in openings:
                        glazing(scene, wall, opening, stone=False)
                    band(scene, wall, top - 0.3, 0.3, 0.24, "Cream")
    for tile in scene.tiles.values():
        project_stone_uvs(tile)
    return No85Model(
        main.length_m,
        owner.area,
        sum(domain.area for domain, _ in domains),
        3,
        len(source.lower_floor_m),
        5,
    )
