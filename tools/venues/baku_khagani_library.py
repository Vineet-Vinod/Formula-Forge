from __future__ import annotations

from dataclasses import replace

from circuit_scene import CircuitScene
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from venues.baku_civic import _opening, _point
from venues.baku_civic_dataclasses import CourtFace, CourtOpening
from venues.baku_hotel_geometry import stone_balcony
from venues.baku_khagani_dataclasses import FrontWall, LibrarySource
from venues.baku_khagani_geometry import (
    band,
    glazing,
    masonry,
    pointed,
    relief,
    roof_step,
    statue,
    wall_shape,
)


def library_pier(scene: CircuitScene, wall: FrontWall, x: float) -> None:
    face = wall.face
    relief(scene, face, box(x - 0.21, 7.0, x + 0.21, 11.28), 0.25, -0.18, "Cream")
    relief(scene, face, box(x - 0.34, 11.25, x + 0.34, 11.57), 0.35, -0.18)
    relief(scene, face, box(x - 0.28, 6.98, x + 0.28, 7.22), 0.33, -0.18)
    for shift in (-0.21, 0, 0.21):
        diamond = Polygon(
            [
                (x + shift, 11.32),
                (x + shift + 0.10, 11.41),
                (x + shift, 11.50),
                (x + shift - 0.10, 11.41),
            ]
        )
        relief(scene, face, diamond, 0.38, 0.34, "Cream")


def library_front(scene: CircuitScene, source: LibrarySource) -> None:
    wall = source.front
    face, top = wall.face, source.wing_height_m
    length = face.length_m
    bays = source.bays
    step = length / bays
    depth = source.gallery_depth_m
    lower: list[CourtOpening] = []
    upper: list[CourtOpening] = []
    for i in range(bays):
        x = (i + 0.5) * step
        for low, high in ((0.65, 2.65), (3.5, 5.65)):
            lower.append(_opening(x, 1.55, low, high - low, False, False))
        upper.append(pointed(x, step * 0.78, 7.05, 11.5, 2.35))
    masonry(scene, wall, top, [*lower, *upper], depth=0.45)
    mask = wall_shape(wall, top)
    for opening in lower:
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
                glazing(scene, face, replace(opening, shape=piece), -0.25)
    for opening in upper:
        trim = opening.shape.buffer(0.14, join_style="mitre").difference(opening.shape)
        if not isinstance(trim, (Polygon, MultiPolygon)):
            raise TypeError("Library pointed archivolt lost its shape")
        relief(scene, face, trim, 0.12, -0.02)
        for a, b in zip(
            opening.shape.exterior.coords, list(opening.shape.exterior.coords)[1:]
        ):
            scene.quad(
                "Building_LibraryOpenGalleryReveals",
                "Cream",
                _point(face, a[0], a[1]),
                _point(face, b[0], b[1]),
                _point(face, b[0], b[1], -0.45),
                _point(face, a[0], a[1], -0.45),
            )
    back_face = CourtFace(
        _point(face, 0, 0, -depth), face.tangent, face.outward, length, length
    )
    inner_windows = [
        _opening((i + 0.5) * step, 1.75, 7.8, 4.6, False, False) for i in range(bays)
    ]
    inner_wall = box(0, 6.8, length, top).difference(
        unary_union([opening.shape for opening in inner_windows])
    )
    if not isinstance(inner_wall, (Polygon, MultiPolygon)):
        raise TypeError("Library inner gallery wall lost its masonry")
    relief(scene, back_face, inner_wall, 0, -0.3, "Cream")
    for opening in inner_windows:
        glazing(scene, back_face, opening, -0.2)
    for i in range(bays + 1):
        library_pier(scene, wall, i * step)
    for i in range(bays):
        x = (i + 0.5) * step
        stone_balcony(scene, face, x - step * 0.35, x + step * 0.35, 7.02, 0.05)
        if i in (1, 3, 5, 8, 10, 12, 15, 18, 20):
            statue(scene, face, x, 7.18, 2.35, -0.7, i)
    for low, thick, outward in (
        (3.1, 0.12, 0.12),
        (6.62, 0.20, 0.20),
        (14.3, 0.18, 0.20),
        (15.0, 0.28, 0.36),
        (top - 0.16, 0.16, 0.48),
    ):
        band(scene, face, low, thick, outward)
    occupied = Polygon(scene.footprint(wall.osm_id).ring)
    roof_step(scene, face, 0, length, top, 13.6, depth, occupied)
    roof_step(scene, face, 0, length, 7.0, 6.8, depth, occupied)
