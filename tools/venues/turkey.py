"""Istanbul Park's sloping spectator banks and angular pit hospitality."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.east_architecture import layered_pit_roofs, trees
from venues.west_architecture import apron_band


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((315, 405, -1), (500, 580, 1), (1040, 1130, -1), (1200, 1290, 1), (1350, 1445, -1), (1950, 2050, 1), (2310, 2450, -1), (2520, 2650, -1), (2720, 2860, -1), (3330, 3420, -1), (3440, 3540, 1), (3940, 4080, 1), (4720, 4820, -1), (4840, 4920, 1), (4940, 5045, -1)):
        scene.kerb(start, end, side, width=1.2)
    for start, end, side, width, material in ((275, 440, 1, 18, 'Gravel'), (1000, 1160, 1, 15, 'Gravel'), (1910, 2080, -1, 14, 'Gravel'), (2260, 2910, 1, 18, 'Gravel'), (3280, 3440, 1, 14, 'RunoffGreen'), (3910, 4110, -1, 13, 'RunoffGreen'), (4660, 4840, 1, 18, 'Gravel'), (4910, 5070, 1, 13, 'RunoffGreen')):
        scene.runoff(start, end, side, width, material)

    for start, end, side in ((500, 580, 1), (1040, 1130, -1), (1200, 1290, 1), (1350, 1445, -1), (1950, 2050, 1), (2310, 2860, -1), (3330, 3420, -1), (3440, 3540, 1), (3940, 4080, 1)):
        scene.runoff(start, end, side, 2.6, 'RunoffGreen')

    for apex, side, distances in (
        (363, 1, (150, 100, 50)),
        (2004, -1, (150, 100, 50)),
        (3385, 1, (150, 100, 50)),
        (4775, 1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (5130, 5338, -1, 'PanelPurple'),
        (0, 230, -1, 'PanelPurple'),
        (5130, 5338, 1, 'PanelPurple'),
        (0, 230, 1, 'PanelPurple'),
        (4730, 5060, 1, 'PanelPurple'),
        (3550, 3770, 1, 'PanelGreen'),
    ):
        scene.branding(start, end, side, material)


    apron_band(scene, 2310, 2860, -1, 2.35, 2.55, 'White')
    apron_band(scene, 3440, 3540, 1, 2.35, 2.55, 'White')

def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.modeled_buildings.add(295742112)
    scene.pit_building(5130, 230, -1, depth=30, height=16, levels=3)
    layered_pit_roofs(scene, 5130, 230, -1, levels=3, height=19, bay=55)
    scene.stand(5180, 270, 1, rows=29, setback=7, roofed=True, seat_material='SeatRed')
    scene.stand(4600, 4820, 1, rows=21, setback=14, roofed=True, seat_material='SeatRed')
    scene.stand(1100, 1250, 1, rows=16, setback=18, roofed=False, seat_material='SeatRed')
    scene.stand(2860, 3010, 1, rows=16, setback=25, roofed=False, seat_material='SeatRed')
    for station in (5210, 5300, 80):
        p = scene.at(station)
        a, b = scene.at(station-24), scene.at(station+24)
        near_a, near_b = -(a.half_width+16), -(b.half_width+16)
        far_a, far_b = near_a-32, near_b-32
        scene.quad('Building_IstanbulHospitality', 'Glass', a.point(near_a, 13), b.point(near_b, 13), b.point(near_b, 22), a.point(near_a, 22))
        scene.quad('Building_IstanbulHospitality', 'White', a.point(near_a+4, 22), b.point(near_b+4, 22), b.point(far_b, 25), a.point(far_a, 25))
        scene.quad('Building_IstanbulHospitality', 'Concrete', a.point(far_a, 24.7), b.point(far_b, 24.7), b.point(near_b+4, 21.7), a.point(near_a+4, 21.7))
        scene.beam('Building_IstanbulHospitality', 'White', p.point(-(p.half_width+16)), p.point(-(p.half_width+16), 22), .65)
    scene.landmarks.append({'name': 'Istanbul Park pit and control terraces', 'start_m': 5130, 'end_m': 230, 'roof': 'Three stacked cantilevered slabs with raised angular glazed hospitality volumes', 'dimensions': 'Visual estimate registered to native pit straight; OSM compound excluded from duplicate extrusion.'})
    for start, end, side, setback, spacing in ((500, 1200, -1, 75, 38), (850, 1500, 1, 90, 42), (1500, 2000, -1, 90, 44), (2100, 2800, 1, 105, 43), (2900, 3400, -1, 80, 38), (3550, 4200, 1, 90, 40), (4200, 4550, -1, 80, 42)):
        trees(scene, start, end, side, setback, spacing, 10)
