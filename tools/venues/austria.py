"""Red Bull Ring: steep pasture amphitheatre, red stands and enclosing conifer ridges."""
from __future__ import annotations

from circuit_scene import CircuitScene

from venues.west_architecture import apron_band, mapped_building, mast
from venues.woodland import mapped_woodland, stand_with_clearing


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4040, 4310, 1, 'PanelLenovo')
    scene.branding(4040, 4310, -1, 'PanelLenovo')
    scene.branding(0, 260, 1, 'PanelLenovo')
    scene.branding(0, 260, -1, 'PanelLenovo')
    scene.branding(1930, 2110, -1, 'PanelWhite')
    scene.braking_boards(285, -1)  # Niki Lauda / T1
    scene.braking_boards(1228, -1)  # Remus / T3
    scene.braking_boards(2047, -1)  # Schlossgold / T4
    scene.braking_boards(2584, 1, distances=(100, 50))  # Rauch / T6
    steel_bull(scene)
    mapped_building(scene, 118364939, 12, facade='Concrete', floors=3, roof='canopy', garage_front=True)
    scene.stand(3990, 4310, -1, rows=20, setback=5, roofed=True, seat_material='SeatRed')
    scene.stand(70, 250, -1, rows=19, setback=9, roofed=True, seat_material='SeatRed')
    scene.stand(330, 580, -1, rows=19, setback=12, roofed=True, seat_material='SeatRed')
    remus_stand = stand_with_clearing(scene, 1110, 1300, -1, rows=20, setback=26,
                                     seat_material='SeatRed')
    scene.stand(1900, 2110, -1, rows=19, setback=29, seat_material='SeatRed')
    scene.stand(2670, 2890, 1, rows=14, setback=25, seat_material='SeatRed')
    mapped_woodland(scene, (remus_stand,))
    for station in [180, 1170, 1990, 2520, 2880, 3550, 3920, 4190]:
        mast(scene, station, -1, 24)


def steel_bull(scene: CircuitScene) -> None:
    import math

    from circuit_mesh import add

    x, y = scene.geo(47.2232459, 14.7611031)
    base = (x, y, scene.ground(x, y))
    scene.landmarks.append({'name': 'Der Bulle vom Spielberg', 'osm_id': 5443064309,
                            'height_m': 17.2, 'dimensions_status': 'OSM position, official17.2moverallheight; bull anatomy, ring span and orientation reconstructed from reference432.54s and sculptor photographs.'})
    previous = None
    for segment in range(97):
        angle = math.tau * segment / 96
        point = add(base, (12.5 * math.cos(angle), 0, 8.6 + 8.6 * math.sin(angle)))
        if previous is not None:
            scene.beam('Building_Bull', 'Steel', previous, point, .5, .7)
        previous = point
    # Angular welded volumes preserve the sculpture's leaping silhouette.
    scene.box('Building_Bull', 'Steel', add(base, (0, 0, 11)), 9, 3.5, 4, -.15)
    scene.box('Building_Bull', 'Steel', add(base, (5, 0, 11.8)), 3.3, 3, 3, -.25)
    for side in [-1, 1]:
        hip = add(base, (-3.3, side * 1.2, 10))
        knee = add(base, (-6.5, side * 1.6, 7))
        hoof = add(base, (-9.5, side * 1.7, 7.8))
        scene.beam('Building_Bull', 'Steel', hip, knee, .9)
        scene.beam('Building_Bull', 'Steel', knee, hoof, .55)
        scene.beam('Building_Bull', 'Steel', add(base, (2.5, side * 1.3, 10)), add(base, (6, side * 1.5, 6.8)), .85)
        scene.beam('Building_Bull', 'Steel', add(base, (6, side * 1.5, 6.8)), add(base, (8, side * 1.8, 8)), .5)
        scene.beam('Building_Bull', 'White', add(base, (5.5, side * 1.4, 12.5)), add(base, (6.2, side * 2.8, 14.6)), .3)
    scene.beam('Building_Bull', 'Steel', add(base, (-4.5, 0, 11.8)), add(base, (-7.5, 0, 14)), .35)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(245, 340, 1), (1180, 1300, 1), (1995, 2115, 1), (2510, 2625, -1), (2810, 2925, -1), (3575, 3675, 1), (3795, 3900, 1)]:
        scene.kerb(start, end, side, material='Red', alternate_material='White')
    for start, end, side, width, material in [(220, 380, -1, 20, 'Runoff'), (1140, 1360, -1, 22, 'Runoff'), (1940, 2160, -1, 24, 'Gravel'), (2460, 2690, 1, 20, 'Gravel'), (2770, 2990, 1, 20, 'Gravel'), (3520, 3730, -1, 18, 'Gravel'), (3750, 3940, -1, 17, 'Runoff')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side, width in [(220, 380, -1, 20), (1140, 1360, -1, 22),
                                     (3750, 3940, -1, 17)]:
        apron_band(scene, start, end, side, 1.2, 2.8, 'RunoffGreen')
        apron_band(scene, start, end, side, 2.8, width - .2, 'RunoffRed')
    for start, end, side in [(1940, 2160, -1), (2460, 2690, 1),
                              (2770, 2990, 1), (3520, 3730, -1)]:
        apron_band(scene, start, end, side, 1.2, 2.8, 'RunoffGreen')
