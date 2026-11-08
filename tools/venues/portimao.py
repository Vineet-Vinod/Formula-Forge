"""Portimão: faceted grandstand blades and a circular glazed control tower on dry hills."""
from __future__ import annotations

from circuit_dataclasses import Point
from circuit_mesh import add
from circuit_scene import CircuitScene
from shapely.geometry import Polygon

from venues.west_architecture import apron_band, mapped_building, mast, trees


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(560, 930, 1, 'PanelWhite')
    scene.branding(560, 930, -1, 'PanelWhite')
    scene.branding(2230, 2400, 1, 'PanelWhite')
    scene.branding(2900, 3020, -1, 'PanelWhite')
    scene.braking_boards(1254, -1)  # Opening right-hander
    scene.braking_boards(1602, -1)  # Curva Lagos
    scene.braking_boards(2332, 1)  # Curva da Torre VIP
    scene.braking_boards(2952, -1)  # Curva Samsung
    scene.braking_boards(3327, 1, distances=(100, 50))  # Curva Craig Jones
    mapped_building(scene, 38167081, 12, facade='White', floors=3, roof='canopy', garage_front=True)
    mapped_building(scene, 38166697, 17, facade='Concrete', floors=1, roof='blades', enclosed=False)
    scene.stand(470, 1060, -1, rows=23, setback=7, seat_material='SeatRed')
    torre_vip(scene)
    scene.stand(1430, 1540, -1, rows=12, setback=24, seat_material='SeatRed')
    scene.stand(3480, 3570, -1, rows=12, setback=27, seat_material='SeatRed')
    for start, end, side in [(1450, 2120, 1), (1650, 2120, -1), (2430, 2880, 1),
                              (2480, 2860, -1), (3080, 3450, 1), (3220, 3420, -1),
                              (3650, 4100, 1), (3700, 4120, -1)]:
        trees(scene, start, end, side, setback=40, spacing=38, height=5.5, rows=1)
    for station in [400, 1120, 1570, 2320, 2940, 3590, 4260]:
        mast(scene, station, -1, 18)


def torre_vip(scene: CircuitScene) -> None:
    building = scene.footprint(157736297)
    polygon = Polygon(building.ring)
    center = polygon.centroid
    base = scene.nearest(center.x, center.y)[0].z
    ring = list(building.ring)
    if not polygon.exterior.is_ccw:
        ring.reverse()

    def point(p: tuple[float, float], scale: float, z: float) -> Point:
        return center.x + (p[0] - center.x) * scale, center.y + (p[1] - center.y) * scale, base + z

    kind = 'Building_TorreVIP'
    for a, b in zip(ring, ring[1:] + ring[:1]):
        for level in range(5):
            z = level * 3.6
            pa, pb = point(a, .84, z), point(b, .84, z)
            scene.banner(add(pa, (0, 0, .25)), add(pb, (0, 0, .25)), 3.1, 'Glass', kind)
            scene.beam(kind, 'White', pa, add(pa, (0, 0, 3.6)), .18)
            if level:
                ia, ib, oa, ob = point(a, .84, z), point(b, .84, z), point(a, .95, z), point(b, .95, z)
                scene.quad(kind, 'White', ia, ib, ob, oa, up=True)
                scene.quad(kind, 'Concrete', add(oa, (0, 0, -.24)), add(ob, (0, 0, -.24)),
                           add(ib, (0, 0, -.24)), add(ia, (0, 0, -.24)), up=False)
                scene.banner(add(oa, (0, 0, -.24)), add(ob, (0, 0, -.24)), .28, 'White', kind)
                scene.banner(add(oa, (0, 0, .15)), add(ob, (0, 0, .15)), .8, 'Glass', kind)
                scene.beam(kind, 'Steel', add(oa, (0, 0, .98)), add(ob, (0, 0, .98)), .055)
        ra, rb = point(a, 1.02, 18), point(b, 1.02, 18)
        scene.triangle(kind, 'White', (center.x, center.y, base + 18), ra, rb)
        scene.triangle(kind, 'Concrete', add(rb, (0, 0, -.3)), add(ra, (0, 0, -.3)), (center.x, center.y, base + 17.7))
        scene.banner(add(ra, (0, 0, -.3)), add(rb, (0, 0, -.3)), .35, 'White', kind)
        scene.beam(kind, 'White', point(a, .95, 14.4), point(a, .95, 17.7), .14)
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'name': 'Torre VIP layered circular terraces', 'osm_id': building.osm_id,
                            'height_m': 18, 'levels': 5,
                            'dimensions_status': 'Mapped24-point circular outline and5OSMlevels. Glazed shaft inset to84%, terraces95%, crown102% of outline reconstruct observed projecting profile in173.63/615.30s;18mheight and exact overhang depths are unmeasured.'})


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(4560, 4650, 1), (0, 170, 1), (1210, 1295, 1), (1300, 1360, -1), (1380, 1480, 1), (1560, 1650, 1), (1700, 1800, -1), (2260, 2400, -1), (2750, 2870, 1), (2890, 3000, 1), (3280, 3370, -1), (3500, 3680, 1), (3810, 3920, -1), (4020, 4130, -1), (4230, 4380, 1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    for start, end, side, width, material in [(1170, 1520, -1, 23, 'Gravel'), (1510, 1690, -1, 20, 'Gravel'), (2220, 2450, 1, 22, 'Gravel'), (2700, 3040, -1, 24, 'Gravel'), (3450, 3730, -1, 24, 'Gravel'), (3770, 4170, 1, 23, 'Gravel'), (4180, 4430, -1, 25, 'Gravel')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(1170, 1520, -1), (1510, 1690, -1),
                              (2220, 2450, 1), (2700, 3040, -1),
                              (3450, 3730, -1), (3770, 4170, 1), (4180, 4430, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.8, 'RunoffGreen')
    for start, end, side in [(2220, 2450, 1), (3450, 3730, -1)]:
        apron_band(scene, start, end, side, 3.8, 5.2, 'RunoffRed')
