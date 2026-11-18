"""Occupied terrace volumes, inset glazing and closed projecting EDITION decks."""

from __future__ import annotations

import math
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient

from venues.jeddah_edition_dataclasses import EditionDetail, EditionFrame


def point(frame: EditionFrame, u: float, v: float, z: float) -> Point:
    return (
        frame.center[0] + frame.axis[0] * u + frame.normal[0] * v,
        frame.center[1] + frame.axis[1] * u + frame.normal[1] * v,
        frame.base_z + z,
    )


def terrace(frame: EditionFrame, setback: float, inset: float) -> Polygon:
    left, low, right, high = frame.footprint.bounds
    front = low + setback if frame.facing < 0 else low + 0.6
    back = high - setback if frame.facing > 0 else high - 0.6
    shape = frame.footprint.intersection(box(left + inset, front, right - inset, back))
    if not isinstance(shape, Polygon) or shape.is_empty:
        raise ValueError("The EDITION deck must remain a connected occupied polygon")
    return orient(shape)


def shortened(
    frame: EditionFrame, shape: Polygon, span: tuple[float, float]
) -> Polygon:
    left, low, right, high = frame.footprint.bounds
    length = right - left
    result = shape.intersection(
        box(left + length * span[0], low, left + length * span[1], high)
    )
    if not isinstance(result, Polygon) or result.is_empty:
        raise TypeError("The shortened EDITION upper wing must stay connected")
    return orient(result)


def raised_fin(scene: MeshScene, frame: EditionFrame, source: EditionDetail) -> None:
    left, low, right, high = frame.footprint.bounds
    u0, u1 = (left + (right - left) * f for f in source.fin_span_fraction)
    v = high - 7.0 if frame.facing > 0 else low + 7.0
    v0, v1 = v - source.fin_thickness_m / 2, v + source.fin_thickness_m / 2
    base = source.tiers[-1].floor_m + 0.28
    profile = ((u0, base), (u1, base), (u0, source.fin_peak_m))
    front = [point(frame, u, v0, z) for u, z in profile]
    back = [point(frame, u, v1, z) for u, z in profile]
    kind = "Building_EditionRaisedWingFin"
    scene.triangle(kind, "JeddahEditionStone", front[0], front[1], front[2])
    scene.triangle(kind, "JeddahEditionStone", back[2], back[1], back[0])
    for index in range(3):
        following = (index + 1) % 3
        scene.quad(
            kind,
            "JeddahEditionStone",
            front[index],
            back[index],
            back[following],
            front[following],
        )


def shell(
    scene: MeshScene,
    frame: EditionFrame,
    shape: Polygon,
    top: float,
    thickness: float,
    kind: str,
    source: EditionDetail,
) -> None:
    inner = shape.buffer(-source.fascia_recess_m, join_style="mitre")
    if not isinstance(inner, Polygon) or inner.is_empty:
        raise TypeError("The recessed EDITION slab must retain one closed body")
    inner = orient(inner)
    lip_bottom = top - source.fascia_lip_m
    bottom = top - thickness
    for surface, level, upward, suffix in (
        (shape, top, True, "Top"),
        (shape.difference(inner), lip_bottom, False, "LipSoffit"),
        (inner, bottom, False, "Soffit"),
    ):
        for triangle in constrained_delaunay_triangles(surface).geoms:
            coordinates = list(orient(triangle).exterior.coords)[:3]
            if not upward:
                coordinates.reverse()
            points = [point(frame, u, v, level) for u, v in coordinates]
            scene.triangle(
                kind + suffix,
                "JeddahEditionStone",
                points[0],
                points[1],
                points[2],
                tuple((u / 4, v / 4) for u, v in coordinates),
            )
    for contour, low, high, suffix in (
        (shape, lip_bottom, top, "FasciaLip"),
        (inner, bottom, lip_bottom, "FasciaRecess"),
    ):
        for a, b in pairwise(contour.exterior.coords):
            scene.quad(
                kind + suffix,
                "JeddahEditionStone",
                point(frame, a[0], a[1], low),
                point(frame, b[0], b[1], low),
                point(frame, b[0], b[1], high),
                point(frame, a[0], a[1], high),
            )


def facade_edge(
    scene: MeshScene,
    frame: EditionFrame,
    a: tuple[float, float],
    b: tuple[float, float],
    low: float,
    high: float,
    source: EditionDetail,
) -> None:
    span = math.dist(a, b)
    count = max(1, round(span / source.facade_bay_m))
    tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    nx, ny = ty, -tx

    def panel(
        start: float,
        end: float,
        bottom: float,
        top: float,
        material: str,
        kind: str,
        inset: float = 0,
    ) -> None:
        first = a[0] + tx * start - nx * inset, a[1] + ty * start - ny * inset
        last = a[0] + tx * end - nx * inset, a[1] + ty * end - ny * inset
        scene.quad(
            kind,
            material,
            point(frame, *first, bottom),
            point(frame, *last, bottom),
            point(frame, *last, top),
            point(frame, *first, top),
        )

    sill, lintel = low + source.window_sill_m, high - source.window_head_m
    panel(
        0, span, low, sill, "JeddahEditionCharcoal", "Building_EditionOpaqueSpandrels"
    )
    panel(
        0,
        span,
        lintel,
        high,
        "JeddahEditionCharcoal",
        "Building_EditionOpaqueSpandrels",
    )
    for bay in range(count):
        start, end = span * bay / count, span * (bay + 1) / count
        pier = min(source.opaque_pier_m / 2, (end - start) / 5)
        first, last = start + pier, end - pier
        panel(
            start,
            first,
            sill,
            lintel,
            "JeddahEditionCharcoal",
            "Building_EditionRoomPiers",
        )
        panel(
            last,
            end,
            sill,
            lintel,
            "JeddahEditionCharcoal",
            "Building_EditionRoomPiers",
        )
        panel(
            first,
            last,
            sill,
            lintel,
            "JeddahEditionRoomGlass",
            "Building_EditionInsetRoomGlazing",
            source.glazing_recess_m,
        )
        if source.room_back_depth_m <= source.glazing_recess_m:
            raise ValueError("EDITION room backs must lie behind their glazing")
        panel(
            first,
            last,
            sill,
            lintel,
            "JeddahEditionCharcoal",
            "Building_EditionSolidRoomBacks",
            source.room_back_depth_m,
        )
        depth_a, depth_b = source.glazing_recess_m, source.room_back_depth_m
        for distance, reverse in ((first, False), (last, True)):
            near = point(
                frame,
                a[0] + tx * distance - nx * depth_a,
                a[1] + ty * distance - ny * depth_a,
                sill,
            )
            far = point(
                frame,
                a[0] + tx * distance - nx * depth_b,
                a[1] + ty * distance - ny * depth_b,
                sill,
            )
            vertices = [
                near,
                far,
                (far[0], far[1], frame.base_z + lintel),
                (near[0], near[1], frame.base_z + lintel),
            ]
            if reverse:
                vertices.reverse()
            scene.quad(
                "Building_EditionRoomReturns",
                "JeddahEditionCharcoal",
                vertices[0],
                vertices[1],
                vertices[2],
                vertices[3],
            )
        for height, reverse in ((sill, False), (lintel, True)):
            vertices = [
                point(
                    frame,
                    a[0] + tx * distance - nx * depth,
                    a[1] + ty * distance - ny * depth,
                    height,
                )
                for distance, depth in (
                    (first, depth_a),
                    (last, depth_a),
                    (last, depth_b),
                    (first, depth_b),
                )
            ]
            if reverse:
                vertices.reverse()
            scene.quad(
                "Building_EditionRoomReturns",
                "JeddahEditionCharcoal",
                vertices[0],
                vertices[1],
                vertices[2],
                vertices[3],
            )
        # Exposed reveals close the recess; the opaque facade is not hidden behind a glass card.
        for distance, reverse in ((first, False), (last, True)):
            u, v = a[0] + tx * distance, a[1] + ty * distance
            outside = point(frame, u, v, sill), point(frame, u, v, lintel)
            inside = (
                point(
                    frame,
                    u - nx * source.glazing_recess_m,
                    v - ny * source.glazing_recess_m,
                    sill,
                ),
                point(
                    frame,
                    u - nx * source.glazing_recess_m,
                    v - ny * source.glazing_recess_m,
                    lintel,
                ),
            )
            quad = outside[0], inside[0], inside[1], outside[1]
            if reverse:
                quad = quad[3], quad[2], quad[1], quad[0]
            scene.quad("Building_EditionWindowReveals", "JeddahEditionCharcoal", *quad)
        for z, reverse in ((sill, False), (lintel, True)):
            pts = [
                point(frame, a[0] + tx * d - nx * inset, a[1] + ty * d - ny * inset, z)
                for d, inset in (
                    (first, 0),
                    (last, 0),
                    (last, source.glazing_recess_m),
                    (first, source.glazing_recess_m),
                )
            ]
            if reverse:
                pts.reverse()
            scene.quad(
                "Building_EditionWindowReveals",
                "JeddahEditionCharcoal",
                pts[0],
                pts[1],
                pts[2],
                pts[3],
            )
        for distance in (first, (first + last) / 2, last):
            u = a[0] + tx * distance - nx * (source.glazing_recess_m - 0.025)
            v = a[1] + ty * distance - ny * (source.glazing_recess_m - 0.025)
            scene.beam(
                "Building_EditionDoorFrames",
                "JeddahEditionCharcoal",
                point(frame, u, v, sill),
                point(frame, u, v, lintel),
                0.055,
                0.055,
            )
        if ny * frame.facing > 0.6:
            for fraction in (0.25, 0.5, 0.75):
                z = sill + (lintel - sill) * fraction
                inset = source.glazing_recess_m - 0.1
                scene.beam(
                    "Building_EditionHorizontalSunshades",
                    "JeddahEditionCharcoal",
                    point(
                        frame,
                        a[0] + tx * first - nx * inset,
                        a[1] + ty * first - ny * inset,
                        z,
                    ),
                    point(
                        frame,
                        a[0] + tx * last - nx * inset,
                        a[1] + ty * last - ny * inset,
                        z,
                    ),
                    0.12,
                    0.055,
                )


def balustrade(
    scene: MeshScene, frame: EditionFrame, shape: Polygon, floor: float, height: float
) -> None:
    ring = orient(shape.buffer(-0.16, join_style="mitre"))
    for a, b in pairwise(ring.exterior.coords):
        span = math.dist(a, b)
        tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
        count = max(1, math.ceil(span / 3.2))
        for index in range(count):
            first, last = (
                span * index / count + 0.025,
                span * (index + 1) / count - 0.025,
            )
            scene.beam(
                "Building_EditionGlassBalustrades",
                "JeddahEditionGuardGlass",
                point(frame, a[0] + tx * first, a[1] + ty * first, floor + height / 2),
                point(frame, a[0] + tx * last, a[1] + ty * last, floor + height / 2),
                0.035,
                height,
            )
        scene.beam(
            "Building_EditionBalustradeCaps",
            "JeddahEditionCharcoal",
            point(frame, a[0], a[1], floor + height),
            point(frame, b[0], b[1], floor + height),
            0.035,
            0.045,
        )


def build(scene: MeshScene, frame: EditionFrame, source: EditionDetail) -> None:
    for level, tier in enumerate(source.tiers):
        deck = terrace(
            frame, max(0.5, tier.front_recess_m - 2.4), tier.end_inset_m - 0.6
        )
        body = terrace(frame, tier.front_recess_m, tier.end_inset_m)
        if level == len(source.tiers) - 1:
            body = shortened(frame, body, source.upper_room_span_fraction)
        shell(
            scene,
            frame,
            deck,
            tier.floor_m + 0.28,
            source.slab_thickness_m,
            "Building_EditionOccupiedDeck",
            source,
        )
        for a, b in pairwise(orient(body).exterior.coords):
            facade_edge(
                scene,
                frame,
                a[:2],
                b[:2],
                tier.floor_m + 0.28,
                tier.ceiling_m,
                source,
            )
        if level + 1 < len(source.tiers):
            following = source.tiers[level + 1]
            overhead = terrace(
                frame,
                max(0.5, following.front_recess_m - 2.4),
                following.end_inset_m - 0.6,
            )
            exposed_roof = body.difference(overhead)
            for triangle in constrained_delaunay_triangles(exposed_roof).geoms:
                uv = list(orient(triangle).exterior.coords)[:3]
                vertices = [point(frame, u, v, tier.ceiling_m) for u, v in uv]
                scene.triangle(
                    "Building_EditionClosedRoomRoofs",
                    "JeddahEditionCharcoal",
                    vertices[0],
                    vertices[1],
                    vertices[2],
                    tuple((u / 4, v / 4) for u, v in uv),
                )
        if level:
            balustrade(
                scene, frame, deck, tier.floor_m + 0.3, source.balustrade_height_m
            )
    roof = shortened(frame, terrace(frame, 0.45, 0.45), source.canopy_span_fraction)
    shell(
        scene,
        frame,
        roof,
        source.canopy_top_m,
        source.canopy_thickness_m,
        "Building_EditionProjectingCanopy",
        source,
    )
    left, low, right, high = frame.footprint.bounds
    front = high - 1.1 if frame.facing > 0 else low + 1.1
    width = right - left
    for u in (-width * 0.34, 0.0, width * 0.34):
        scene.beam(
            "Building_EditionAngledWhiteFrame",
            "JeddahEditionStone",
            point(frame, u + 4, front - frame.facing * 0.2, source.brace_bottom_m),
            point(frame, u - 4, front - frame.facing * 0.2, source.brace_top_m),
            0.7,
            0.58,
        )
    for u in (roof.bounds[0] + 1.2, roof.bounds[2] - 1.2):
        scene.beam(
            "Building_EditionCanopyColumns",
            "JeddahEditionStone",
            point(frame, u, front - frame.facing * 0.25, 0.35),
            point(frame, u, front - frame.facing * 0.25, 24.1),
            0.55,
        )
    raised_fin(scene, frame, source)
