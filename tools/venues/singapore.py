"""Marina Bay's night skyline, civic buildings, durian shells and observation wheel."""
from __future__ import annotations

import math

from circuit_mesh import add, mul
from circuit_scene import CircuitScene

from venues.east_architecture import cylinder, facade, frame, mapped, trees


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
    hub = c[0], c[1], ground+90
    for face in (-1, 1):
        center = add(hub, mul(normal, face*3))
        for step in range(112):
            a, b = step*math.tau/112, (step+1)*math.tau/112
            pa = add(center, add(mul(axis, 75*math.cos(a)), (0, 0, 75*math.sin(a))))
            pb = add(center, add(mul(axis, 75*math.cos(b)), (0, 0, 75*math.sin(b))))
            scene.beam('Building_FlyerRim', 'White', pa, pb, .65)
            if step % 4 == 0:
                scene.beam('Building_FlyerSpokes', 'Steel', center, pa, .12)
        for side in (-1, 1):
            foot = add((c[0], c[1], ground), add(mul(axis, side*42), mul(normal, face*24)))
            scene.beam('Building_FlyerLegs', 'White', foot, center, 2.4)
    for capsule in range(28):
        angle = capsule*math.tau/28
        p = add(hub, add(mul(axis, 75*math.cos(angle)), (0, 0, 75*math.sin(angle))))
        cylinder(scene, add(p, (0, 0, -2)), 3.5, 2, 4, 'Glass', 16, math.atan2(axis[1], axis[0]))
        scene.box('Building_FlyerCapsule', 'White', add(p, (0, 0, 1.9)), 6, 3.5, .28, math.atan2(axis[1], axis[0]))
    facade(scene, 51761904, 12, 'modern', 'White')
    scene.modeled_buildings.add(230082125)
    scene.landmarks.append({'name': 'Singapore Flyer', 'osm_id': 230082125, 'diameter_m': 150, 'height_m': 165, 'capsules': 28, 'source': 'Singapore Flyer operator fun facts; wheel orientation estimated from mapped base.'})


def sands(scene: CircuitScene) -> None:
    # Distant skyline coordinates are estimated; they are outside the corridor footprint extract.
    xy = scene.geo(1.28375, 103.86055)
    base_z = scene.ground(*xy)
    axis = .73, .683, 0.
    normal = -axis[1], axis[0], 0.
    heading = math.atan2(axis[1], axis[0])
    for along in (-90, 0, 90):
        center = add((xy[0], xy[1], base_z), mul(axis, along))
        for leg in (-1, 1):
            for floor in range(55):
                rise = floor*200/55
                lean = leg*(10+13*(1-floor/55)**2)
                c = add(center, add(mul(normal, lean), (0, 0, rise+1.65)))
                scene.box('Building_SandsTowers', 'Glass', c, 48, 19, 3.6, heading)
                scene.box('Building_SandsBalconies', 'Cream', add(c, (0, 0, 1.8)), 49, 20, .22, heading)
                if floor % 4 == 0:
                    scene.box('Building_SandsWindows', 'WarmGlass', add(c, mul(normal, leg*9.55)), 36, .12, 1.4, heading)
    center = xy[0], xy[1], base_z+200
    for segment in range(80):
        a, b = segment*math.tau/80, (segment+1)*math.tau/80
        def rim(angle: float, z: float, scale: float = 1.) -> tuple[float, float, float]:
            return add(center, add(add(mul(axis, 170*math.cos(angle)*scale), mul(normal, 19*math.sin(angle)*scale)), (0, 0, z)))
        scene.quad('Building_SandsSkypark', 'Cream', rim(a, 0), rim(b, 0), rim(b, -6, .95), rim(a, -6, .95))
        scene.triangle('Building_SandsSkypark', 'Grass', add(center, (0, 0, .15)), rim(a, .15), rim(b, .15))
        scene.beam('Building_SandsSkypark', 'White', rim(a, .5), rim(b, .5), .35)
    scene.landmarks.append({'name': 'Marina Bay Sands', 'latitude': 1.28375, 'longitude': 103.86055, 'height_m': 200, 'skypark_length_m': 340, 'skypark_width_m': 38, 'source': 'Arup project description; geographic position and tower plan are visual estimates.'})

from venues.west_architecture import apron_band


def circuit_edges(scene: CircuitScene) -> None:
    # Native-station intervals are reference estimates, independent of auto turn labels.
    for start, end, side in ((290, 345, -1), (375, 425, 1), (450, 510, -1), (845, 905, 1), (1290, 1360, 1), (1675, 1730, -1), (1890, 1950, 1), (2080, 2140, -1), (2535, 2600, -1), (2655, 2715, 1), (2760, 2820, -1), (2920, 3010, -1), (3475, 3540, 1), (3730, 3795, -1), (4205, 4280, 1), (4315, 4375, -1), (4570, 4650, -1), (4670, 4755, -1)):
        scene.kerb(start, end, side, width=.72)
    for start, end, side, width, material in ((265, 355, 1, 8, 'Runoff'), (440, 525, 1, 8, 'Runoff'), (1645, 1750, 1, 8, 'Runoff'), (2050, 2160, 1, 6, 'Runoff'), (2900, 3040, 1, 6, 'Runoff'), (4540, 4680, 1, 7, 'Runoff')):
        scene.runoff(start, end, side, width, material)

    for apex, side, distances in (
        (323, 1, (150, 100, 50)),
        (486, 1, (100, 50)),
        (877, -1, (150, 100, 50)),
        (1702, 1, (150, 100, 50)),
        (2572, 1, (150, 100, 50)),
        (2966, 1, (100, 50)),
        (3513, -1, (150, 100, 50)),
        (4246, -1, (150, 100, 50)),
    ):
        scene.braking_boards(apex, side, distances=distances)

    for start, end, side, material in (
        (4710, 4940, -1, 'PanelSingapore'),
        (0, 170, -1, 'PanelSingapore'),
        (4710, 4940, 1, 'PanelSingapore'),
        (0, 170, 1, 'PanelSingapore'),
        (780, 920, -1, 'PanelYellow'),
    ):
        scene.branding(start, end, side, material)


    apron_band(scene, 4710, 4940, -1, 1.2, 5.8, 'Yellow')
    apron_band(scene, 0, 170, -1, 1.2, 5.8, 'Yellow')

def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
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
    scene.modeled_buildings.add(49890775)
    scene.pit_building(4710, 170, -1, depth=22, height=15, levels=3)
    scene.stand(4720, 120, 1, rows=23, setback=5, roofed=True, seat_material='SeatRed')
    scene.stand(2200, 2530, -1, rows=14, setback=5, roofed=False, seat_material='SeatRed')
    scene.stand(3210, 3450, -1, rows=14, setback=6, roofed=False, seat_material='SeatRed')
    for start, end, side, setback, spacing in ((500, 1120, -1, 5, 18), (650, 1150, 1, 7, 21), (1380, 1950, 1, 5, 18), (1950, 2600, -1, 6, 16), (2250, 2750, 1, 4, 17), (2750, 3120, 1, 6, 18), (3150, 3750, -1, 6, 16), (3150, 3750, 1, 8, 20), (3900, 4450, -1, 12, 23)):
        trees(scene, start, end, side, setback, spacing, 13)
    for start, end, side in ((450, 800, 1), (1200, 1600, -1), (4000, 4350, 1)):
        trees(scene, start, end, side, 8, 45, 11, palm=True)
