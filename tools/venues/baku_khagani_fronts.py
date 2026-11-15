from __future__ import annotations

from dataclasses import replace

from circuit_scene import CircuitScene
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_geometry import stone_balcony
from venues.baku_khagani_dataclasses import HistoricFront
from venues.baku_khagani_geometry import (
    band,
    corinthian,
    glazing,
    lathe,
    mansard,
    masonry,
    pediment,
    projected_oriel,
    relief,
    rosette,
    statue,
    wall_shape,
)
from venues.baku_university import iron_balcony


def windows(
    scene: CircuitScene,
    source: HistoricFront,
    openings: list[CourtOpening],
    depth: float = -0.28,
) -> None:
    mask = wall_shape(source.wall, source.cornice_m)
    for opening in openings:
        shape = opening.shape.intersection(mask)
        pieces = (
            [shape]
            if isinstance(shape, Polygon)
            else list(shape.geoms)
            if isinstance(shape, MultiPolygon)
            else []
        )
        for piece in pieces:
            if piece.area > 0.01:
                glazing(
                    scene,
                    source.wall.face,
                    replace(opening, shape=piece),
                    depth,
                    "Trunk" if opening.door else "Glass",
                )
                if opening.door:
                    x0, _z0, x1, _z1 = piece.bounds
                    for side in range(2):
                        low_x = x0 + 0.16 + side * (x1 - x0) / 2
                        high_x = x0 - 0.16 + (side + 1) * (x1 - x0) / 2
                        for low_z, high_z in ((0.55, 1.6), (1.85, 2.85), (3.1, 3.8)):
                            outer = box(low_x, low_z, high_x, high_z).intersection(
                                piece
                            )
                            border = outer.difference(
                                box(
                                    low_x + 0.10,
                                    low_z + 0.10,
                                    high_x - 0.10,
                                    high_z - 0.10,
                                )
                            )
                            if isinstance(border, (Polygon, MultiPolygon)):
                                relief(
                                    scene,
                                    source.wall.face,
                                    border,
                                    -0.12,
                                    -0.23,
                                    "Trunk",
                                )


def composers(scene: CircuitScene, source: HistoricFront) -> None:
    wall, top = source.wall, source.cornice_m
    face, length = wall.face, wall.face.length_m
    middle = tuple(length * t for t in (0.405, 0.595, 0.785))
    wings = tuple(length * t for t in (0.055, 0.16, 0.265, 0.945))
    openings: list[CourtOpening] = []
    for x in middle:
        openings.extend(
            (
                _opening(x, 2.75, 0.3, 4.1, True, False),
                _opening(x, 2.5, 5.9, 4.5, True, False),
                _opening(x, 2.6, 11.7, 3.85, False, False),
            )
        )
    for x in wings:
        for low, high in ((0.3, 4.4), (6.0, 10.4), (11.7, 15.6)):
            openings.append(
                _opening(
                    x,
                    1.75 if abs(x / length - 0.16) < 0.01 else 0.95,
                    low,
                    high - low,
                    low < 1,
                    False,
                )
            )
    masonry(scene, wall, top, openings)
    windows(scene, source, openings)
    for t in (0.31, 0.50, 0.69, 0.88):
        corinthian(scene, face, length * t, 5.45, top - 0.65, 0.45, 0.65)
    stone_balcony(scene, face, length * 0.29, length * 0.90, 5.45, 1.15)
    iron_balcony(scene, face, length * 0.555, length * 0.635, 11.4)
    for a, b in ((0.015, 0.29), (0.90, 0.99)):
        iron_balcony(scene, face, length * a, length * b, 11.4)
    for z, thick, depth in (
        (5.05, 0.28, 0.30),
        (top - 0.8, 0.24, 0.45),
        (top - 0.3, 0.3, 0.68),
    ):
        band(scene, face, z, thick, depth)
    pediment(scene, face, length * 0.26, length * 0.93, top - 0.1, source.roof_rise_m)
    vase = _point(face, length * 0.595, top + 0.18, 0.52)
    lathe(
        scene,
        vase,
        (
            (0, 0.24),
            (0.12, 0.3),
            (0.25, 0.16),
            (0.85, 0.23),
            (1.05, 0.12),
            (1.22, 0.22),
        ),
    )
    for side in (-1, 1):
        x = length * 0.595 + side * 0.82
        centre = _point(face, x, top + 0.18, 0.45)
        lathe(scene, centre, ((0.22, 0.24), (0.46, 0.28), (0.95, 0.25), (1.05, 0.12)))
        lathe(
            scene,
            (centre[0], centre[1], centre[2] + 1.02),
            ((0, 0.1), (0.08, 0.18), (0.28, 0.16), (0.36, 0.03)),
        )
        scene.beam(
            "Building_ComposersSeatedFigure",
            "White",
            _point(face, x, top + 0.65, 0.55),
            _point(face, x + side * 0.62, top + 0.22, 0.65),
            0.23,
        )
        scene.beam(
            "Building_ComposersSeatedFigure",
            "White",
            _point(face, x - side * 0.12, top + 1.0, 0.5),
            _point(face, length * 0.595 + side * 0.22, top + 0.93, 0.62),
            0.15,
        )
    for t in (0.30, 0.89):
        statue(scene, face, length * t, 5.6, 2.4, 0.65)
    for x in middle:
        rosette(scene, face, x, 11.1, 0.38)
    for i in range(round(length / 0.36)):
        x = (i + 0.5) * length / round(length / 0.36)
        relief(scene, face, box(x - 0.07, top - 0.55, x + 0.07, top - 0.34), 0.54, 0.31)
    if source.return_wall is not None:
        return_wall = source.return_wall
        return_openings = [
            _opening(
                return_wall.face.length_m / 2, 1.65, low, high - low, low < 1, False
            )
            for low, high in ((0.3, 4.4), (6.0, 10.4), (11.7, 15.6))
        ]
        masonry(scene, return_wall, top, return_openings)
        for opening in return_openings:
            glazing(scene, return_wall.face, opening)
        for z, thick, depth in (
            (5.05, 0.28, 0.30),
            (top - 0.8, 0.24, 0.45),
            (top - 0.3, 0.3, 0.5),
        ):
            band(scene, return_wall.face, z, thick, depth)


def writers(scene: CircuitScene, source: HistoricFront) -> None:
    wall, top = source.wall, source.cornice_m
    face, length = wall.face, wall.face.length_m
    oriels = (0.085 * length, 0.915 * length)
    plain = tuple(length * t for t in (0.25, 0.38, 0.51))
    gallery = tuple(length * t for t in (0.66, 0.79))
    openings: list[CourtOpening] = []
    for x in plain:
        openings.extend(
            (
                _opening(x, 1.9, 0.35, 4.15, False, False),
                _opening(x, 1.85, 6.1, 3.8, False, False),
                _opening(x, 1.9, 11.55, 3.55, False, False),
            )
        )
    openings[0] = _opening(plain[0], 2.8, 0.22, 4.5, True, True)
    for x in gallery:
        openings.extend(
            (
                _opening(x, 2.0, 0.35, 4.15, False, False),
                _opening(x, 2.4, 6.0, 4.0, False, False),
                _opening(x, 3.0, 11.3, 4.35, True, False),
            )
        )
    voids = [opening.shape for opening in openings]
    voids.extend(box(x - 1.8, 5.2, x + 1.8, top - 0.55) for x in oriels)
    shape = wall_shape(wall, top).difference(unary_union(voids))
    if not isinstance(shape, (Polygon, MultiPolygon)):
        raise TypeError("Writers Union must retain its individual facade")
    relief(scene, face, shape, 0, -0.35, "Cream")
    plain_openings = [
        opening
        for opening in openings
        if not (
            opening.shape.bounds[1] > 11
            and 0.59 * length < opening.shape.centroid.x < 0.86 * length
        )
    ]
    windows(scene, source, plain_openings)
    for opening in openings:
        if opening in plain_openings:
            continue
        x0, _z0, x1, _z1 = opening.shape.bounds
        back_face = CourtFace(
            _point(face, 0, 0, -0.95), face.tangent, face.outward, length, length
        )
        inner = _opening((x0 + x1) / 2, 1.85, 11.55, 2.65, False, False)
        backing = opening.shape.difference(inner.shape)
        if not isinstance(backing, (Polygon, MultiPolygon)):
            raise TypeError("Writers gallery must retain its inner masonry")
        relief(scene, back_face, backing, 0, -0.22, "Cream")
        glazing(scene, back_face, inner, -0.2)
        trim = opening.shape.buffer(0.12, join_style="mitre").difference(opening.shape)
        if not isinstance(trim, (Polygon, MultiPolygon)):
            raise TypeError("Writers gallery archivolt must retain its shape")
        relief(scene, face, trim, 0.10, -0.02)
        for a, b in zip(
            opening.shape.exterior.coords, list(opening.shape.exterior.coords)[1:]
        ):
            scene.quad(
                "Building_WritersGalleryReveals",
                "Cream",
                _point(face, *a),
                _point(face, *b),
                _point(face, b[0], b[1], -0.95),
                _point(face, a[0], a[1], -0.95),
            )

    for x in oriels:
        projected_oriel(
            scene, face, x, 3.6, 5.2, top - 0.55, ((6.2, 9.7), (11.4, 14.7)), 1.0
        )
        rosette(scene, face, x, 10.4, 0.55)
        rosette(scene, face, x, 15.5, 0.6)
    iron_balcony(scene, face, length * 0.19, length * 0.5956, 5.85)
    for x in plain:
        iron_balcony(scene, face, x - 1.1, x + 1.1, 11.2)
        rosette(scene, face, x, 10.55, 0.43)
        rosette(scene, face, x, 15.7, 0.5)
    stone_balcony(scene, face, length * 0.59595, length * 0.855, 5.85, 1.0)
    stone_balcony(scene, face, length * 0.59595, length * 0.855, 11.0, 0.85)
    corinthian(scene, face, length * 0.725, 6.0, 10.8, 0.22, 0.62, "ionic")
    for z, thick, depth in (
        (5.25, 0.22, 0.28),
        (10.6, 0.18, 0.22),
        (top - 0.75, 0.20, 0.32),
        (top - 0.25, 0.25, 0.55),
    ):
        band(scene, face, z, thick, depth)
    mansard(
        scene,
        face,
        top,
        source.roof_rise_m,
        tuple((2.0, length * t) for t in (0.08, 0.22, 0.36, 0.5, 0.64, 0.78, 0.92)),
        "BakuOxideRoof",
        False,
    )
    for i in range(round(length / 0.42)):
        x = (i + 0.5) * length / round(length / 0.42)
        relief(scene, face, box(x - 0.10, top - 0.67, x + 0.10, top - 0.36), 0.50, 0.22)
    for a, b in ((0.36, 0.55), (0.56, 0.76), (0.77, 0.97)):
        scene.quad(
            "Building_WritersShopAwning",
            "BakuOxideRoof",
            _point(face, a * length, 4.55, 1.0),
            _point(face, b * length, 4.55, 1.0),
            _point(face, b * length, 4.95, 0.08),
            _point(face, a * length, 4.95, 0.08),
            up=True,
        )
        band(scene, face, 4.40, 0.15, 1.0, "BakuOxideRoof", (a * length, b * length))


def house23(scene: CircuitScene, source: HistoricFront) -> None:
    wall, top = source.wall, source.cornice_m
    face, length = wall.face, wall.face.length_m
    left = tuple(length * t for t in (0.13, 0.32))
    centre, right = length * 0.5956, length * 0.84
    openings: list[CourtOpening] = []
    levels = ((0.55, 3.4), (5.0, 8.1), (9.4, 12.3), (13.6, 15.9))
    for row, (low, high) in enumerate(levels):
        for x in left:
            openings.append(
                _opening(x, 1.65, low, high - low, row == 0 and x == left[1], False)
            )
        openings.append(
            _opening(right, 3.0 if row == 1 else 2.8, low, high - low, row == 3, False)
        )
    openings.extend(
        _opening(centre + d, 1.15, 13.65, 2.25, False, False) for d in (-1.5, 0, 1.5)
    )
    openings.extend(
        _opening(centre + d, 1.5, 0.55, 2.85, False, False) for d in (-0.95, 0.95)
    )
    voids = [opening.shape for opening in openings]
    voids.append(box(centre - 2.05, 4.35, centre + 2.05, 13.6))
    shape = wall_shape(wall, top).difference(unary_union(voids))
    if not isinstance(shape, (Polygon, MultiPolygon)):
        raise TypeError("House23 must retain its asymmetric facade")
    relief(scene, face, shape, 0, -0.35, "Concrete")
    windows(scene, source, openings)
    projected_oriel(
        scene,
        face,
        centre,
        4.1,
        4.35,
        13.55,
        ((5.1, 8.05), (9.45, 12.35)),
        1.15,
        "Concrete",
    )
    for row, (low, _) in enumerate(levels):
        if row == 0:
            stone_balcony(scene, face, length * 0.06, length * 0.94, low - 0.05, 0.7)
        elif row == 1:
            stone_balcony(scene, face, left[1] - 1.35, left[1] + 1.35, low - 0.12, 0.6)
            stone_balcony(scene, face, right - 2.0, right + 2.0, low - 0.12, 1.1)
            corinthian(scene, face, right - 1.0, low, low + 3.5, 0.16, 0.68, "doric")
            corinthian(scene, face, right + 1.0, low, low + 3.5, 0.16, 0.68, "doric")
        elif row == 2:
            stone_balcony(scene, face, right - 1.7, right + 1.7, low - 0.1, 0.95)
        else:
            stone_balcony(scene, face, right - 1.4, right + 1.4, low - 0.08, 0.65)
    for x in left:
        for z in (8.65, 12.9, 16.4):
            rosette(scene, face, x, z, 0.48 if z < 16 else 0.3)
    for z, thick, depth in (
        (4.1, 0.24, 0.35),
        (8.7, 0.12, 0.15),
        (13.0, 0.12, 0.16),
        (top - 0.28, 0.28, 0.45),
    ):
        band(scene, face, z, thick, depth)
    rosette(scene, face, centre, 4.5, 0.85)
    rosette(scene, face, centre, 13.35, 0.75)
    mansard(
        scene,
        face,
        top,
        source.roof_rise_m,
        tuple(
            (1.2 if i in (0, 2) else 2.15, length * t)
            for i, t in enumerate((0.095, 0.23, 0.355, 0.50, 0.67, 0.835))
        ),
    )
