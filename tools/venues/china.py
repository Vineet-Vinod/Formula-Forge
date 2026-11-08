"""Shanghai lotus canopy terraces and open parkland with the pit roof bridge."""
from __future__ import annotations

from circuit_mesh import add
from circuit_scene import CircuitScene

from venues.east_architecture import cylinder, footprint_stand, trees


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((165, 285, 1), (390, 465, -1), (960, 1040, -1), (1070, 1155, 1), (1180, 1270, 1), (2610, 2750, 1), (2990, 3110, -1), (3930, 4140, 1), (4180, 4300, -1), (4590, 4700, 1), (4865, 4960, 1), (5320, 5430, -1)):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in ((130, 300, -1, 12, 'Gravel'), (920, 1050, 1, 14, 'RunoffGreen'), (1060, 1320, -1, 15, 'Gravel'), (2580, 2780, -1, 16, 'RunoffGreen'), (2960, 3150, 1, 14, 'Gravel'), (3850, 4190, -1, 18, 'Gravel'), (4160, 4330, 1, 13, 'RunoffGreen'), (4840, 5000, -1, 15, 'Gravel')):
        scene.runoff(start, end, side, width, material)

    for start, end, side in ((165, 285, 1), (390, 465, -1), (1070, 1270, 1), (2990, 3110, -1), (3930, 4140, 1), (4180, 4300, -1), (4865, 4960, 1)):
        scene.runoff(start, end, side, 2.6, 'RunoffGreen')

    for apex, side, distances in (
        (3950, -1, (150, 100, 50)),
        (4920, -1, (150, 100, 50)),
        (1006, 1, (150, 100, 50)),
        (2680, -1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (2530, 2730, -1, 'PanelYellow'),
        (2760, 2940, -1, 'PanelGreen'),
        (2760, 2940, 1, 'PanelGreen'),
    ):
        scene.branding(start, end, side, material)


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    for osm_id in (156341844, 156341848, 156341851):
        footprint_stand(scene, osm_id, 22, seat_material='SeatRed')
    for osm_id in (1372223261, 1372223262):
        footprint_stand(scene, osm_id, 19, 'lotus', seat_material='SeatRed')
    # Section A includes the bridge and roof footprint across the straight.
    scene.modeled_buildings.add(107371135)
    scene.stand(3240, 3690, -1, rows=34, setback=7, roofed=True, seat_material='SeatRed')
    scene.pit_building(3230, 3740, 1, depth=28, height=16, levels=3)
    for station in range(3230, 3740, 30):
        a, b = scene.at(station), scene.at(station+30)
        scene.beam('Building_ShanghaiPits', 'SeatYellow', a.point(a.half_width+13, 9), b.point(b.half_width+13, 9), .55, .65)
        scene.quad('Building_ShanghaiPits', 'Roof', a.point(a.half_width+10, 18), b.point(b.half_width+10, 18), b.point(b.half_width+44, 18.7), a.point(a.half_width+44, 18.7))
    for station in (3280, 3650):
        p = scene.at(station)
        for side in (-1, 1):
            c = p.point(side*(p.half_width+45))
            base = c[0], c[1], scene.ground(c[0], c[1])
            cylinder(scene, base, 15, 18, 27, 'Glass', heading=0.25)
            for floor in range(1, 7):
                cylinder(scene, add(base, (0, 0, floor*4)), 15.3, 18.3, .28, 'White', heading=.25)
        a, b = scene.at(station-25), scene.at(station+25)
        scene.quad('Building_ShanghaiBridge', 'White', a.point(-83, 29), b.point(-83, 29), b.point(83, 29), a.point(83, 29))
        scene.quad('Building_ShanghaiBridge', 'Concrete', a.point(83, 28.6), b.point(83, 28.6), b.point(-83, 28.6), a.point(-83, 28.6))
        scene.beam('Building_ShanghaiBridge', 'Glass', p.point(-80, 25.6), p.point(80, 25.6), 24, 4.5)
    scene.landmarks.append({'name': 'Shanghai Section A roof bridges', 'start_m': 3230, 'end_m': 3740, 'clearance_m': 23.3, 'dimensions': 'Reference-estimated roof volumes; mapped compound excluded from solid extrusion.'})
    for start, end, side, setback in ((0, 550, -1, 65), (600, 1400, 1, 90), (1450, 2550, 1, 75), (1700, 2500, -1, 110), (4400, 5000, -1, 80), (5000, 5440, 1, 95)):
        trees(scene, start, end, side, setback, 34, 10)
