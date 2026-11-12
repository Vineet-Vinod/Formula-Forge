"""Zandvoort: layered pit roofs and scattered scrub on exposed North Sea dunes."""
from __future__ import annotations

import math

from circuit_dataclasses import Point
from circuit_mesh import cross, sub
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon
from shapely.ops import unary_union

from venues.west_architecture import apron_band, mapped_building, mast
from venues.zandvoort_water import water_bodies


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    water_bodies(scene)
    scene.branding(4050, 4250, 1, 'PanelWhite')
    scene.branding(4050, 4250, -1, 'PanelWhite')
    scene.branding(0, 280, 1, 'PanelWhite')
    scene.branding(0, 280, -1, 'PanelWhite')
    scene.branding(330, 530, -1, 'PanelDHL')
    scene.branding(790, 970, 1, 'PanelDHL')
    scene.branding(2380, 2610, 1, 'PanelDHL')
    scene.branding(2380, 2480, -1, 'PanelDHL')
    scene.branding(2950, 3160, 1, 'PanelYellow')
    scene.branding(2950, 3160, -1, 'PanelYellow')
    scene.braking_boards(400, -1)  # Tarzan
    scene.braking_boards(873, 1, distances=(100, 50))  # Hugenholtz
    scene.braking_boards(2538, 1)  # T10
    scene.braking_boards(3186, -1)  # Hans Ernst first apex
    mapped_building(scene, 52473177, 13, facade='Concrete', floors=3, roof='canopy', garage_front=True)
    scene.stand(3990, 4240, -1, rows=21, setback=6, roofed=True, seat_material='SeatBlue')
    scene.stand(0, 250, -1, rows=21, setback=6, roofed=True, seat_material='SeatBlue')
    scene.stand(300, 480, -1, rows=21, setback=22, seat_material='SeatBlue')
    scene.stand(680, 820, -1, rows=18, setback=25, seat_material='SeatBlue')
    scene.stand(930, 1050, -1, rows=15, setback=26, seat_material='SeatBlue')
    scene.stand(3000, 3140, -1, rows=16, setback=21, seat_material='SeatBlue')
    scene.stand(3500, 3690, -1, rows=20, setback=23, seat_material='SeatBlue')
    for start, end, side in [(1100, 1510, 1), (1120, 1460, -1), (1790, 2050, 1),
                              (1800, 2040, -1), (2160, 2770, 1), (2150, 2780, -1),
                              (3270, 3460, 1)]:
        dune_scrub(scene, start, end, side)
    dune_scrub(scene, 3650, 3960, 1)
    for station in [220, 720, 1050, 1700, 2230, 2990, 3560, 3910]:
        mast(scene, station, -1, 20)


def dune_scrub(scene: CircuitScene, start: float, end: float, side: int) -> None:
    blocked = unary_union([scene.corridor_mask.buffer(1.5), *scene.extra_corridors,
                           *scene.water_shapes, *[Polygon(b.ring).buffer(2) for b in scene.buildings]])
    shrubs, rocks = 0, 0
    count = max(1, math.ceil((end - start) / 11))
    for i in range(count):
        sample = scene.at(start + (end - start) * (i + .35) / count)
        shoulder = sample.left_shoulder if side > 0 else sample.right_shoulder
        for row in range(3):
            lane = side * (sample.half_width + scene.kerb_margin(sample.station) + shoulder + 3 + row * 6)
            p = sample.point(lane)
            x, y = p[0] + math.sin(i * 2.3 + row) * 1.8, p[1] + math.cos(i * 1.7 + row) * 1.8
            if blocked.covers(ShapePoint(x, y)):
                continue
            height = 2.4 + .7 * math.sin(i * 1.4 + row * .8)
            ground = scene.ground(x, y)
            # Start the low crown at terrain level; exposed trunks made former tiny trees read as palms.
            scene.broadleaf((x, y, ground - height * .45), height, i + row * 37)
            shrubs += 1
            if (i + row) % 3:
                continue
            ring: list[Point] = []
            for face in range(7):
                angle = math.tau * face / 7
                rx, ry = x + math.cos(angle) * 1.1, y + math.sin(angle) * .7
                ring.append((rx, ry, scene.ground(rx, ry) + .025))
            peak = (x, y, ground + .26)
            for a, b in zip(ring, ring[1:] + ring[:1]):
                scene.triangle('Building_DuneRocks', 'Concrete', a, b, peak)
            rocks += 1
    scene.vegetation.append({'start_m': start, 'end_m': end, 'side': side,
                             'species_form': 'Low windswept scrub with small exposed stone patches',
                             'shrubs': shrubs, 'rock_patches': rocks,
                             'placement_status': 'Reference865/866.5/868s middle dune and872s final bank vegetation character; individual footprints reconstructed beyond protection/buildings/water. Low crowns start at sampled ground; small rock facets follow sampled terrain rather than fixed-Z tiles.'})


def t10_gravel_pocket(scene: CircuitScene) -> None:
    start, end = 2500.0, 2610.0
    scene.surface_ranges.append({'type': 'runoff', 'start_m': start, 'end_m': end,
                                 'side': 1, 'requested_width_m': 4, 'material': 'Gravel'})
    def outer(station: float) -> float:
        t = max(0, min(1, (station - start) / 15, (end - station) / 15))
        return 1 + 3 * t * t * (3 - 2 * t)
    for i in range(55):
        a, b = scene.at(start + i * 2), scene.at(start + (i + 1) * 2)
        pa, pb = a.point(a.half_width + 1), b.point(b.half_width + 1)
        qa, qb = a.point(a.half_width + outer(a.station)), b.point(b.half_width + outer(b.station))
        shape = Polygon([pa[:2], pb[:2], qb[:2], qa[:2]])
        if not shape.is_valid or shape.area < 1e-8:
            continue
        remaining = shape.difference(scene.road_mask)
        components = [remaining] if isinstance(remaining, Polygon) else list(getattr(remaining, 'geoms', []))
        for component in components:
            if isinstance(component, Polygon) and component.area > 1e-8:
                scene.extra_corridors.append(component)
                scene.polygon_surface(component, 'Gravel', .001, a)
    scene.landmarks.append({'name': 'T10 bounded outside gravel band', 'start_m': start, 'end_m': end,
                            'side': 1, 'grass_lip_m': 1, 'maximum_gravel_band_width_m': 3,
                            'dimensions_status': 'Continuous866.5/868s apex sequence and operatorT10 photographs establish grass lip, gravel and close wall. Original1m grass/3m gravel/15m end tapers estimated, not surveyed. Separate typed3.55m native right-shoulder correction plus.95margin brings wall to4.5m outside road; road and bank unchanged.'})


def t10_infield_paint(scene: CircuitScene) -> None:
    cells = []
    for station in range(2480, 2590, 2):
        a, b = scene.at(station), scene.at(station + 2)

        def width(distance: float) -> float:
            t = max(0.0, min(1.0, (distance - 2480) / 15, (2590 - distance) / 15))
            return 2.05 + 10 * t * t * (3 - 2 * t)

        cell = Polygon([
            a.point(-a.half_width - 2.05)[:2],
            b.point(-b.half_width - 2.05)[:2],
            b.point(-b.half_width - width(b.station))[:2],
            a.point(-a.half_width - width(a.station))[:2],
        ])
        if cell.is_valid and cell.area > 1e-8:
            cells.append(cell)
    island = unary_union(cells).difference(scene.road_mask.buffer(0.15))
    if not isinstance(island, Polygon) or island.is_empty:
        raise ValueError('T10 infield paint must remain a connected island')
    first_surface = len(scene.surface_points)
    scene.terrain_cutouts.append(island)
    scene.polygon_surface(island, 'RunoffNavy', .001, paved=True, smooth_ground=True)
    heading = scene.at(2560)
    label_anchor = heading.point(-heading.half_width - 7)
    center = ShapePoint(label_anchor[:2])
    axis = heading.tx, heading.ty
    across = -heading.ty, heading.tx
    length, depth = 30.4, 3.8
    rectangle = Polygon([
        (center.x + axis[0] * u + across[0] * v,
         center.y + axis[1] * u + across[1] * v)
        for u, v in ((-length / 2, -depth / 2), (length / 2, -depth / 2),
                     (length / 2, depth / 2), (-length / 2, depth / 2))
    ])
    for base_a, base_b, base_c in scene.surface_points[first_surface:]:
        piece = rectangle.intersection(Polygon([base_a[:2], base_b[:2], base_c[:2]]))
        denominator = (base_b[1] - base_c[1]) * (base_a[0] - base_c[0]) + (base_c[0] - base_b[0]) * (base_a[1] - base_c[1])
        for triangle in constrained_delaunay_triangles(piece).geoms:
            points: list[Point] = []
            for x, y in list(triangle.exterior.coords)[:3]:
                u = ((base_b[1] - base_c[1]) * (x - base_c[0]) + (base_c[0] - base_b[0]) * (y - base_c[1])) / denominator
                v = ((base_c[1] - base_a[1]) * (x - base_c[0]) + (base_a[0] - base_c[0]) * (y - base_c[1])) / denominator
                points.append((x, y, u * base_a[2] + v * base_b[2] + (1 - u - v) * base_c[2] + .005))
            if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                points.reverse()
            uv = tuple(
                (.5 + ((p[0] - center.x) * axis[0] + (p[1] - center.y) * axis[1]) / length,
                 .5 - ((p[0] - center.x) * across[0] + (p[1] - center.y) * across[1]) / depth)
                for p in points
            )
            scene.triangle('Tile_T10GroundLettering', 'GroundMSC', points[0], points[1], points[2], uv)
    scene.landmarks.append({'name': 'T10 inside navy MSC paved advertising island',
                            'start_m': 2480, 'end_m': 2590, 'side': -1,
                            'area_m2': island.area, 'grass_rim_beyond_kerb_m': .81,
                            'paint_lift_m': .005,
                            'physical_contract': 'Visual-only island: no runoff range or extra_corridors registration; native shoulder, limits, drive surface and walls unchanged.',
                            'registration': 'Supplied 866.5/868 s continuous T10 left turn-in/apex shows dark navy paving and large white MSC lettering inside the left kerb. Native 2490–2590 m inside kerb and road-local cells constrain the footprint; 2.05 m edge setback, 10 m maximum paved width and 15 m tapers are bounded estimates, not surveyed advertising dimensions. Existing original typeset MSC texture follows exact paved triangles, with no copied reference pixels.'})


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(340, 480, 1), (680, 770, 1), (805, 950, -1), (1670, 1795, 1), (2030, 2130, 1), (2230, 2340, 1), (2490, 2590, -1), (3130, 3210, 1), (3220, 3290, -1), (3500, 3610, 1), (3720, 3940, 1)]:
        scene.kerb(start, end, side, material='RunoffOrange' if start in (340, 805) else 'Red', alternate_material='White')
    for start, end, side, width, material in [(290, 510, -1, 24, 'Gravel'), (780, 995, 1, 20, 'Gravel'), (1630, 1840, -1, 24, 'Gravel'), (1990, 2170, -1, 22, 'Gravel'), (2190, 2380, -1, 20, 'Gravel'), (3080, 3320, -1, 18, 'Gravel'), (3460, 3650, -1, 20, 'Gravel')]:
        scene.runoff(start, end, side, width, material)
    t10_gravel_pocket(scene)
    t10_infield_paint(scene)

    for start, end, side in [(290, 510, -1), (3080, 3320, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.1, 'RunoffGreen')
