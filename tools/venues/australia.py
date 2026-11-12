"""Albert Park: temporary race architecture inside a mature lakeside city park."""
from __future__ import annotations

from circuit_dataclasses import SurfaceProjection
from circuit_scene import CircuitScene
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from venues.west_architecture import apron_band, mapped_building, mast, trees, water


def build_venue(scene: CircuitScene) -> None:
    circuit_edges(scene)
    scene.branding(4928.796, 5270.269, 1, 'PanelPurple')
    scene.branding(4928.796, 5270.269, -1, 'PanelPurple')
    scene.branding(652.663, 1033.437, 1, 'PanelYellow')
    scene.branding(652.663, 1033.437, -1, 'PanelYellow')
    scene.braking_boards(287.352, -1)  # T1 / Jones
    scene.braking_boards(1022.484, -1)  # T3 / Whiteford
    scene.braking_boards(3231.100, 1, distances=(100, 50))  # T9 high-speed chicane approach
    scene.braking_boards(4062.230, -1)  # T11
    scene.braking_boards(4575.083, 1)  # T13
    water(scene)
    scene.pit_building(4939.105, 5229.679, side=1, depth=21, height=13, levels=3)
    scene.stand(4898.515, 5270.269, -1, rows=20, setback=6, roofed=True, seat_material='Concrete')
    scene.stand(80.536, 230.655, -1, rows=18, setback=9, roofed=True, seat_material='Concrete')
    scene.stand(1053.409, 1133.301, -1, rows=12, setback=24, seat_material='Concrete')
    scene.stand(1073.382, 1143.610, 1, rows=12, setback=26, seat_material='Concrete')
    scene.stand(3899.226, 4020, -1, rows=13, setback=16, seat_material='Concrete')
    mapped_building(scene, 26811587, 7, floors=2, roof='pitched')
    mapped_building(scene, 154529390, 7, floors=2, roof='pitched')
    mapped_building(scene, 45384591, 70, floors=21, balconies=True)
    mapped_building(scene, 306782098, 16, floors=4, roof='canopy')
    mapped_building(scene, 1081955937, 77.8, floors=23, balconies=True)
    for start, end, side, setback in [(240.963, 1048.255, 1, 6), (301.526, 1048.255, -1, 6),
                                      (1123.637, 1704.784, 1, 18), (1163.583, 1724.757, -1, 17),
                                      (1801.427, 2855.480, -1, 18), (2936.016, 3859.280, -1, 14),
                                      (3879.253, 4798.006, 1, 18), (4095.089, 4758.061, -1, 22)]:
        avenue = start in (240.963, 301.526)
        trees(scene, start, end, side, setback=setback, height=17 if avenue else 13,
              spacing=11 if avenue else 13, rows=3 if avenue else 2)
    trees(scene, 1892.271, 2810, 1, setback=24, spacing=39, height=12, rows=1, palms=True)
    for station in [120.482, 983.826, 1785.320, 2434.117, 3186.644, 4049.989, 4617.605, 5119.505]:
        mast(scene, station, -1, 18)


def circuit_edges(scene: CircuitScene) -> None:
    for start, end, side in [(255.782, 321.499, 1), (362.089, 441.981, -1), (990.269, 1063.074, 1), (1128.791, 1193.864, -1), (1343.983, 1419.364, 1), (1775.011, 1847.171, 1), (1892.271, 1982.471, -1), (2092.645, 2243.408, 1), (3176.980, 3287.153, -1), (3317.434, 3402.480, 1), (4014.553, 4104.753, 1), (4270.335, 4355.381, 1), (4531.271, 4612.451, -1), (4687.833, 4778.033, 1)]:
        scene.kerb(start, end, side, material='SeatYellow', alternate_material='Green',
                   height=-.02 if start == 1892.271 else .055)
    for start, end, side, width, material in [(246.118, 356.935, -1, 9, 'Runoff'), (969.008, 1113.328, -1, 12, 'Runoff'), (1745.374, 1887.117, -1, 12, 'Runoff'), (3969.453, 4155.008, -1, 16, 'Runoff'), (4647.887, 4828.288, -1, 11, 'Runoff')]:
        scene.runoff(start, end, side, width, material)

    for start, end, side in [(246.118, 356.935, -1), (969.008, 1113.328, -1),
                              (1745.374, 1887.117, -1), (3969.453, 4155.008, -1), (4647.887, 4828.288, -1)]:
        apron_band(scene, start, end, side, 1.2, 3.2, 'RunoffGreen')
    t3_apex_lip(scene)
    t3_infield_paint(scene)


def t3_apex_lip(scene: CircuitScene) -> None:
    samples = [scene.at(station) for station in range(1021, 1042)]
    sector = LineString([(p.x, p.y) for p in samples]).buffer(
        -15, single_sided=True, cap_style='flat', join_style='round'
    )
    kerb = unary_union([shape for shape in scene.terrain_cutouts if shape.intersects(sector)])
    lip = kerb.difference(scene.road_mask.buffer(.62)).intersection(sector)
    scene.polygon_surface(lip, 'Red', .08, scene.at(1030.859))
    scene.landmarks.append({
        'name': 'T3 raised red inner apex lip', 'start_m': 1020.551, 'end_m': 1041.168,
        'side': 1, 'area_m2': lip.area,
        'registration': 'Direct 335 s T3 apex, lap 16.017 s, shows red inner lip behind the yellow/green kerb. Outer 0.47 m of the exact corrected kerb footprint, short station span and 8 cm top height are bounded estimates. Raised above the existing kerb; no coplanar duplicate paving or native collision change.',
    })


def t3_infield_paint(scene: CircuitScene) -> None:
    samples = [scene.at(station) for station in range(1000, 1068)]
    sector = LineString([(p.x, p.y) for p in samples]).buffer(
        -25, single_sided=True, cap_style='flat', join_style='round'
    )
    island = scene.road_mask.buffer(12).difference(scene.road_mask.buffer(1.2)).intersection(sector)
    island = island.intersection(scene.corridor_mask.buffer(-0.25))
    pieces = [island] if isinstance(island, Polygon) else list(island.geoms)
    for piece in pieces:
        if isinstance(piece, Polygon):
            scene.terrain_cutouts.append(piece)
    scene.polygon_surface(island, 'RunoffBlack', .001, paved=True, smooth_ground=True)
    road = scene.at(1041.168)
    anchor = road.point(road.half_width + 3.2)
    projection = SurfaceProjection(anchor, (road.tx, road.ty, 0.0), 18, 4.5)
    rectangle = Polygon([
        (anchor[0] + road.tx * u - road.ty * v,
         anchor[1] + road.ty * u + road.tx * v)
        for u, v in ((-9, -2.25), (9, -2.25), (9, 2.25), (-9, 2.25))
    ])
    scene.paint_surface(rectangle.intersection(island), 'GroundPirelli', projection=projection)
    scene.landmarks.append({
        'name': 'T3 black Pirelli paved infield', 'start_m': 999.934, 'end_m': 1067.584,
        'side': 1, 'area_m2': island.area,
        'registration': 'Direct supplied 332–334 s T3 approach/apex, lap 13.032–15.016 s, shows black paving with yellow Pirelli lettering inside the right kerb. Exact footprint depth and lettering dimensions are bounded estimates; native road union constrains the edge.',
        'physical_contract': 'Visual-only paving; no runoff range or extra corridor. Native racing XYZ, banking, shoulders, drive surface and collision unchanged.',
    })
