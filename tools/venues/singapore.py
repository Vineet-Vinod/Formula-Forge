"""Marina Bay's night skyline, civic buildings, durian shells and observation wheel."""
from __future__ import annotations

import math

from circuit_mesh import add, mul
from circuit_scene import CircuitScene

from venues.east_architecture import cylinder, facade, frame, mapped, trees
from venues.pit_compounds import SINGAPORE, mapped_pit
from venues.singapore_bridge import anderson_bridge
from venues.singapore_raffles import (
    build_context,
    flyer_terminal,
    frontage_trees,
    ground_parcels,
)
from venues.singapore_stamford import build_stamford, stamford_tree_band
from venues.singapore_viaduct import build_viaduct
from venues.singapore_waterfront import build_waterfront, skypark, tower


def esplanade(scene: CircuitScene, osm_id: int) -> None:
    building = mapped(scene, osm_id)
    if building is None:
        return
    c, axis, side, length, width = frame(building)
    z = scene.ground(c[0], c[1])
    cylinder(scene, (c[0], c[1], z), length*.5, width*.5, 7, 'Cream', heading=math.atan2(axis[1], axis[0]))
    def point(angle: float, latitude: float) -> tuple[float, float, float]:
        return add((c[0], c[1], z+7+28*math.sin(latitude)), add(mul(axis, length*.51*math.cos(latitude)*math.cos(angle)), mul(side, width*.51*math.cos(latitude)*math.sin(angle))))
    for row in range(10):
        for column in range(48):
            a0, a1, t0, t1 = column*math.tau/48, (column+1)*math.tau/48, row*math.pi/20, (row+1)*math.pi/20
            a, b, d, e = point(a0, t0), point(a1, t0), point(a1, t1), point(a0, t1)
            scene.quad('Building_Esplanade', 'Glass', a, b, d, e)
            center = point((a0+a1)/2, (t0+t1)/2)
            peak = add(center, (math.cos((a0+a1)/2)*1.1, math.sin((a0+a1)/2)*1.1, 1.15))
            scene.triangle('Building_EsplanadeShades', 'Cream', a, b, peak)
            scene.triangle('Building_EsplanadeShades', 'White', b, d, peak)
            scene.triangle('Building_EsplanadeShades', 'Concrete', d, e, peak)
            scene.triangle('Building_EsplanadeShades', 'Cream', e, a, peak)
            scene.beam('Building_EsplanadeRibs', 'Steel', a, d, .11)
    scene.modeled_buildings.add(osm_id)
    scene.landmarks.append({'name': building.name, 'osm_id': osm_id, 'height_m': 35, 'roof': 'Ellipsoidal glass shell with individual projecting triangular sunshades'})


def flyer(scene: CircuitScene) -> None:
    building = mapped(scene, 230082125)
    if building is None:
        return
    c, axis, normal, _, _ = frame(building)
    ground = scene.ground(c[0], c[1])
    hub = c[0], c[1], ground + 165 - 75 - 2.04
    for face in (-1, 1):
        center = add(hub, mul(normal, face*3))
        for step in range(112):
            a, b = step*math.tau/112, (step+1)*math.tau/112
            pa = add(center, add(mul(axis, 75*math.cos(a)), (0, 0, 75*math.sin(a))))
            pb = add(center, add(mul(axis, 75*math.cos(b)), (0, 0, 75*math.sin(b))))
            scene.beam('Building_FlyerRim', 'FlyerSteel', pa, pb, .65)
            if step % 4 == 0:
                scene.beam('Building_FlyerSpokes', 'FlyerSteel', center, pa, .12)
        for side in (-1, 1):
            foot = add((c[0], c[1], ground), add(mul(axis, side*42), mul(normal, face*24)))
            scene.beam('Building_FlyerLegs', 'White', foot, center, 2.4)
    for capsule in range(28):
        angle = capsule*math.tau/28
        p = add(hub, add(mul(axis, 75*math.cos(angle)), (0, 0, 75*math.sin(angle))))
        cylinder(scene, add(p, (0, 0, -2)), 3.5, 2, 4, 'Glass', 16, math.atan2(axis[1], axis[0]))
        scene.box('Building_FlyerCapsule', 'White', add(p, (0, 0, 1.9)), 6, 3.5, .28, math.atan2(axis[1], axis[0]))
    flyer_terminal(scene)
    scene.modeled_buildings.add(230082125)
    scene.landmarks.append({'name': 'Singapore Flyer', 'osm_id': 230082125, 'diameter_m': 150, 'height_m': 165, 'capsules': 28, 'source': 'Singapore Flyer operator fun facts; wheel orientation estimated from mapped base.'})


def sands(scene: CircuitScene) -> None:
    for osm_id in (116801004, 172307472, 172307471):
        tower(scene, scene.footprint(osm_id))
    skypark(scene, scene.footprint(116800998))




def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((292.310953, 347.513185, -1), (377.737782, 428.059639, 1), (453.227322, 513.586810, -1), (851.213587, 911.644731, 1), (1299.673799, 1370.223443, 1), (1687.731011, 1737.103121, -1), (1898.377329, 1948.274616, 1), (2079.294084, 2139.601088, -1), (2537.731602, 2602.976801, -1), (2658.413769, 2718.177348, 1), (2763.594638, 2824.021025, -1), (2924.779077, 3004.310770, -1), (3473.011870, 3529.264329, 1), (3720.777376, 3786.284915, -1), (4199.549801, 4275.026950, 1), (4310.287205, 4370.693376, -1), (4567.246657, 4647.739375, -1), (4667.898788, 4753.527739, -1)):
        scene.kerb(start, end, side, width=.72)
    for start, end, side, width, material in ((267.111744, 357.591562, 1, 8, 'Runoff'), (443.168519, 528.691351, 1, 8, 'Runoff'), (1657.491802, 1757.261687, 1, 8, 'Runoff'), (2049.068716, 2159.748244, 1, 6, 'Runoff'), (2904.634192, 3034.549723, 1, 6, 'Runoff'), (4537.007576, 4677.978262, 1, 7, 'Runoff')):
        scene.runoff(start, end, side, width, material)

    for apex, side, distances in (
        (325.505959, 1, (150, 100, 50)),
        (489.422627, 1, (100, 50)),
        (883.434250, -1, (150, 100, 50)),
        (1712.478558, 1, (150, 100, 50)),
        (2574.929437, 1, (150, 100, 50)),
        (2964.961013, 1, (100, 50)),
        (3506.283961, -1, (150, 100, 50)),
        (4240.869811, -1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (4708.211713, 4940, -1, 'PanelSingapore'),
        (0, 171.354734, -1, 'PanelSingapore'),
        (4708.211713, 4940, 1, 'PanelSingapore'),
        (0, 171.354734, 1, 'PanelSingapore'),
        (785.700774, 926.761387, -1, 'PanelYellow'),
    ):
        scene.branding(start, end, side, material)
    for side in (-1, 1):
        scene.branding(3892.119939, 4335.435917, side, 'PanelGreen')



def build_venue(scene: CircuitScene) -> None:
    ground_parcels(scene)
    circuit_edges(scene)
    build_waterfront(scene)
    build_viaduct(scene)
    anderson_bridge(scene)
    build_context(scene)
    stamford = build_stamford(scene)
    scene.modeled_buildings.add(97582570)
    esplanade(scene, 256163011)
    esplanade(scene, 256163012)
    flyer(scene)
    sands(scene)
    civic = {46595597, 170960936, 46595395, 46594820, 46594819, 46595390, 243427705, 243427888, 172931401}
    heights = {46595395: 25, 46595597: 25, 170960936: 25, 46594820: 15, 46594819: 15, 48035153: 223, 155988210: 158, 46595145: 115, 46595146: 181, 46595147: 181, 46595148: 181, 102938119: 181, 742205653: 65, 46594816: 80}
    for building in scene.buildings:
        if building.osm_id in scene.modeled_buildings or building.osm_id == 49890775 or building.use == 'grandstand':
            continue
        c, _, _, _, _ = frame(building)
        _, distance = scene.nearest(c[0], c[1])
        if distance < 170 or building.osm_id in heights:
            facade(scene, building.osm_id, heights.get(building.osm_id, max(10, building.height)), 'classical' if building.osm_id in civic else 'modern', 'Cream' if building.osm_id in civic else 'Concrete')
    dome = mapped(scene, 170960936)
    if dome is not None:
        c, _, _, _, _ = frame(dome)
        base = c[0], c[1], scene.ground(c[0], c[1])+25
        cylinder(scene, base, 10, 10, 4.5, 'Cream')
        for layer in range(16):
            angle = layer*math.pi/32
            radius = 10*math.cos(angle)
            cylinder(scene, add(base, (0, 0, 4.5+10*math.sin(angle))), radius, radius, .8, 'Roof', 32)
    mapped_pit(scene, SINGAPORE)
    scene.stand(4718.266285, 120.956315, 1, rows=23, setback=5, roofed=True, seat_material='SeatRed')
    scene.stand(2200.061823, 2532.691906, -1, rows=14, setback=5, roofed=False, seat_material='SeatRed')
    scene.stand(3205.904624, 3447.812678, -1, rows=14, setback=6, roofed=False, seat_material='SeatRed')
    for start, end, side, setback, spacing in ((503.510135, 1128.320683, -1, 5, 18), (654.667603, 1158.559456, 1, 7, 21), (1948.274616, 2602.976801, -1, 6, 16), (2250.460027, 2753.506502, 1, 4, 17), (2753.506502, 3115.187419, 1, 6, 18), (3145.426532, 3740.932435, -1, 6, 16), (3145.426532, 3740.932435, 1, 8, 20)):
        trees(scene, start, end, side, setback, spacing, 13)
    stamford_tree_band(scene, stamford)
    frontage_trees(scene)
    for start, end, side in ((453.227322, 805.860027, 1), (1208.957514, 1612.133386, -1), (3992.916696, 4345.495629, 1)):
        trees(scene, start, end, side, 8, 45, 11, palm=True)
