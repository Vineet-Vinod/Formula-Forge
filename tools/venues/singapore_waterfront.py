"""Mapped Marina Bay water and the resort's low waterfront architecture."""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Building, Point
from circuit_mesh import add, cross, mul, norm, sub
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapePoint
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from venues.east_architecture import frame

MARINA_BASE = 2.5
WATER_HEIGHT = -4.811936793826295


def roof_mesh(scene: CircuitScene, shape: BaseGeometry,
              height: Callable[[float, float], float], material: str,
              kind: str, step: float = 5.) -> None:
    left, bottom, right, top = shape.bounds
    for row in range(max(1, math.ceil((top-bottom)/step))):
        y = bottom + row*step
        for column in range(max(1, math.ceil((right-left)/step))):
            x = left + column*step
            piece = shape.intersection(box(x, y, x+step, y+step))
            for triangle in constrained_delaunay_triangles(piece).geoms:
                points = [(px, py, height(px, py)) for px, py in list(triangle.exterior.coords)[:3]]
                if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                    points.reverse()
                scene.triangle(kind, material, points[0], points[1], points[2],
                               tuple((p[0]/8, p[1]/8) for p in points))


def roof_line(scene: CircuitScene, shape: BaseGeometry, start: Point, end: Point,
              height: Callable[[float, float], float], width: float,
              material: str, kind: str) -> None:
    clipped = shape.intersection(LineString([start[:2], end[:2]]))
    paths = [clipped] if isinstance(clipped, LineString) else list(getattr(clipped, 'geoms', []))
    for path in paths:
        if not isinstance(path, LineString) or path.length < .1:
            continue
        count = max(1, math.ceil(path.length/3))
        previous = path.interpolate(0)
        a = previous.x, previous.y, height(previous.x, previous.y)+.08
        for step in range(1, count+1):
            point = path.interpolate(path.length*step/count)
            b = point.x, point.y, height(point.x, point.y)+.08
            scene.beam(kind, material, a, b, width)
            a = b


def waterfront_water(scene: CircuitScene) -> None:
    grid = scene.grid
    bounds = box(grid.x, grid.y, grid.x+(grid.columns-1)*grid.step,
                 grid.y+(grid.rows-1)*grid.step)
    for ring in scene.area_polygons({'natural': 'water'}):
        if len(ring) < 3:
            continue
        shape = Polygon(ring).intersection(bounds)
        parts = [shape] if isinstance(shape, Polygon) else list(getattr(shape, 'geoms', []))
        for polygon in parts:
            if not isinstance(polygon, Polygon) or polygon.is_empty:
                continue
            scene.water_shapes.append(polygon)
            for triangle in constrained_delaunay_triangles(polygon).geoms:
                points = [(x, y, WATER_HEIGHT) for x, y in list(triangle.exterior.coords)[:3]]
                if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                    points.reverse()
                scene.triangle('Tile_MarinaWater', 'Water', points[0], points[1], points[2])
    scene.landmarks.append({'name': 'Marina Reservoir and Singapore River',
                            'water_height_m': WATER_HEIGHT,
                            'area_m2': sum(p.area for p in scene.water_shapes),
                            'source': 'Complete retained OSM relations 9542146 and 9569901. The PUB map corroborates the shoreline. Water uses the flattened DSM water datum and lies below the existing bridges. This changes scenery only.'})


def podium(scene: CircuitScene) -> None:
    building = scene.footprint(2298319)
    shape = orient(Polygon(building.ring))
    scene.terrain_cutouts.append(shape)
    ring = list(shape.exterior.coords)
    for a, b in pairwise(ring):
        scene.quad('Building_SandsPodium', 'Glass',
                   (*a, MARINA_BASE), (*b, MARINA_BASE),
                   (*b, MARINA_BASE+15), (*a, MARINA_BASE+15))
        length = math.dist(a, b)
        for column in range(max(1, math.ceil(length/6))):
            t = (column+.5)/max(1, math.ceil(length/6))
            p = a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, MARINA_BASE
            scene.beam('Building_SandsPodiumPiers', 'Cream', p, add(p, (0, 0, 15)), .18)
        for floor in (5., 10., 15.):
            scene.beam('Building_SandsPodiumFascia', 'Cream', (*a, MARINA_BASE+floor),
                       (*b, MARINA_BASE+floor), .22)
    roof_mesh(scene, shape, lambda x, y: MARINA_BASE+15, 'Cream', 'Building_SandsPodiumRoof')
    for osm_id in (1056849313, 1056849314, 1056849315):
        part = scene.footprint(osm_id)
        roof_shape = Polygon(part.ring)
        scene.terrain_cutouts.append(roof_shape)
        center, axis, normal, length, width = frame(part)

        def height(x: float, y: float, c: Point = center,
                   n: Point = normal, w: float = width) -> float:
            across = ((x-c[0])*n[0]+(y-c[1])*n[1])/(w*.5)
            return MARINA_BASE+15+10*math.sqrt(max(0., 1-across*across))

        for a, b in pairwise(list(orient(roof_shape).exterior.coords)):
            scene.quad('Building_SandsGalleriaWalls', 'Glass',
                       (*a, MARINA_BASE), (*b, MARINA_BASE),
                       (*b, height(*b)), (*a, height(*a)))
            scene.beam('Building_SandsGalleriaFascia', 'Cream',
                       (*a, MARINA_BASE+15), (*b, MARINA_BASE+15), .22)
        roof_mesh(scene, roof_shape, height, 'Glass', 'Building_SandsGalleriaRoof')
        count = max(1, math.ceil(length/7))
        for index in range(count+1):
            c = add(center, mul(axis, length*(index/count-.5)))
            roof_line(scene, roof_shape, add(c, mul(normal, -width)),
                      add(c, mul(normal, width)), height, .22, 'Cream', 'Building_SandsGalleriaRibs')
        for fraction in (-.75, -.5, -.25, 0., .25, .5, .75):
            c = add(center, mul(normal, width*.5*fraction))
            roof_line(scene, roof_shape, add(c, mul(axis, -length)),
                      add(c, mul(axis, length)), height, .09, 'Steel', 'Building_SandsGalleriaGrid')
        scene.modeled_buildings.add(osm_id)
    scene.modeled_buildings.update((2298319, 12633419))
    scene.landmarks.append({'name': 'The Shoppes waterfront podium and gallerias',
                            'osm_id': 2298319, 'foundation_m': MARINA_BASE,
                            'podium_height_m': 15, 'roof_crest_height_m': 25,
                            'source': 'Mapped outer footprint and round-roof parts 1056849313, 1056849314 and 1056849315. Safdie photographs show curved glazed gallerias and cream ribs. Heights come from OSM tags; the section is a visual reconstruction.'})


def flower_dome(scene: CircuitScene) -> None:
    building = scene.footprint(171142595)
    shape = Polygon(building.ring)
    scene.terrain_cutouts.append(shape)
    center, axis, normal, length, width = frame(building)
    base = .9

    def height(x: float, y: float) -> float:
        along = ((x-center[0])*axis[0]+(y-center[1])*axis[1])/(length*.5)
        across = ((x-center[0])*normal[0]+(y-center[1])*normal[1])/(width*.5)
        return base+38*math.sqrt(max(.006, 1-along*along-across*across))

    roof_mesh(scene, shape, height, 'Glass', 'Building_FlowerDomeGlass', 4.)
    ring = list(orient(shape).exterior.coords)
    for a, b in pairwise(ring):
        scene.quad('Building_FlowerDomeBase', 'Glass', (*a, base), (*b, base),
                   (*b, height(*b)), (*a, height(*a)))
    for index in range(25):
        c = add(center, mul(axis, length*(index/24-.5)))
        roof_line(scene, shape, add(c, mul(normal, -width)),
                  add(c, mul(normal, width)), height, .28 if index%3 == 0 else .12,
                  'Cream', 'Building_FlowerDomeArches')
    for index in range(17):
        c = add(center, mul(normal, width*(index/16-.5)))
        roof_line(scene, shape, add(c, mul(axis, -length)),
                  add(c, mul(axis, length)), height, .1, 'Steel', 'Building_FlowerDomeGrid')
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'name': building.name, 'osm_id': building.osm_id,
                            'height_m': 38, 'foundation_m': base,
                            'source': 'Mapped footprint. Project engineer Atelier Ten specifies a 170 m by 86 m by 38 m glass gridshell, which overrides the coarse 30 m OSM height. Shell curvature and rib spacing are visual estimates.'})


def tower(scene: CircuitScene, building: Building) -> None:
    shape = orient(Polygon(building.ring))
    scene.terrain_cutouts.append(shape)
    center, axis, normal, length, width = frame(building)
    ring = list(shape.exterior.coords)[:-1]

    def point(p: tuple[float, float], fraction: float) -> Point:
        along = (p[0]-center[0])*axis[0]+(p[1]-center[1])*axis[1]
        across = (p[0]-center[0])*normal[0]+(p[1]-center[1])*normal[1]
        taper = min(1., fraction/.45)
        along *= 1-(1-min(1., 48/length))*taper
        across *= 1-(1-min(1., 30/width))*taper
        return add((center[0], center[1], MARINA_BASE+193*fraction),
                   add(mul(axis, along), mul(normal, across)))

    for floor in range(55):
        low, high = floor/55, (floor+1)/55
        for index, (a, b) in enumerate(zip(ring, ring[1:]+ring[:1])):
            pa, pb, ta, tb = point(a, low), point(b, low), point(a, high), point(b, high)
            scene.quad('Building_SandsTowers', 'Glass', pa, pb, tb, ta)
            scene.quad('Building_SandsBalconies', 'Cream',
                       add(ta, (0, 0, -.15)), add(tb, (0, 0, -.15)), tb, ta)
            tangent = norm(sub(pb, pa))
            outward = tangent[1], -tangent[0], 0.
            columns = max(1, math.ceil(math.dist(pa, pb)/3.3))
            for column in range(columns):
                if (floor*13+index*7+column*17)%7 > 1:
                    continue
                middle = add(add(pa, mul(sub(pb, pa), (column+.5)/columns)),
                             add(mul(outward, .025), (0, 0, 1.1)))
                left, right = sub(middle, mul(tangent, .85)), add(middle, mul(tangent, .85))
                scene.quad('Building_SandsWindows', 'WarmGlass', left, right,
                           add(right, (0, 0, 1.25)), add(left, (0, 0, 1.25)))
    scene.modeled_buildings.add(building.osm_id)


def build_waterfront(scene: CircuitScene) -> None:
    waterfront_water(scene)
    podium(scene)
    flower_dome(scene)


def skypark(scene: CircuitScene, building: Building) -> None:
    shape = orient(Polygon(building.ring))
    center, axis, normal, length, width = frame(building)
    deck = MARINA_BASE+200
    underside: list[tuple[Point, Point, Point]] = []
    boundary_edges: Counter[tuple[tuple[float, float], tuple[float, float]]] = Counter()
    boundary_direction: dict[tuple[tuple[float, float], tuple[float, float]],
                             tuple[tuple[float, float], tuple[float, float]]] = {}

    def belly(x: float, y: float) -> float:
        t = min(1., shape.boundary.distance(ShapePoint(x, y))/8)
        return deck-6-2*t*t*(3-2*t)

    left, bottom, right, top = shape.bounds
    for row in range(math.ceil((top-bottom)/5)):
        y = bottom+row*5
        for column in range(math.ceil((right-left)/5)):
            x = left+column*5
            piece = shape.intersection(box(x, y, x+5, y+5))
            for triangle in constrained_delaunay_triangles(piece).geoms:
                points = [(px, py, belly(px, py)) for px, py in list(triangle.exterior.coords)[:3]]
                if cross(sub(points[1], points[0]), sub(points[2], points[0]))[2] < 0:
                    points.reverse()
                underside.append((points[0], points[2], points[1]))
                scene.triangle('Building_SandsSkyparkDeck', 'Cream',
                               (*points[0][:2], deck), (*points[1][:2], deck), (*points[2][:2], deck))
                scene.triangle('Building_SandsSkypark', 'Grass',
                               (*points[0][:2], deck+.15), (*points[1][:2], deck+.15), (*points[2][:2], deck+.15))
                for a, b in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
                    pa = round(a[0], 7), round(a[1], 7)
                    pb = round(b[0], 7), round(b[1], 7)
                    key = tuple(sorted((pa, pb)))
                    edge = key[0], key[1]
                    boundary_edges[edge] += 1
                    boundary_direction[edge] = pa, pb
    for a, b, c in underside:
        scene.triangle('Building_SandsSkyparkSoffit', 'Cream', a, b, c)
    for edge, count in boundary_edges.items():
        if count != 1:
            continue
        edge_a, edge_b = boundary_direction[edge]
        scene.quad('Building_SandsSkypark', 'Cream',
                   (*edge_a, deck), (*edge_a, deck-6), (*edge_b, deck-6), (*edge_b, deck))
        scene.beam('Building_SandsSkypark', 'White', (*edge_a, deck+.5), (*edge_b, deck+.5), .35)

    index = STRtree([Polygon([p[:2] for p in triangle]) for triangle in underside])

    def height(x: float, y: float) -> float:
        for triangle_index in index.query(ShapePoint(x, y), predicate='intersects'):
            a, b, c = underside[triangle_index]
            denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
            v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
            return u*a[2]+v*b[2]+(1-u-v)*c[2]-.12
        return belly(x, y)-.12

    for number in range(-5, 6):
        c = add(center, mul(normal, width*.075*number))
        roof_line(scene, shape, add(c, mul(axis, -length)),
                  add(c, mul(axis, length)), height, .11, 'Steel', 'Building_SandsSkyparkRibs')
    scene.modeled_buildings.add(building.osm_id)
    scene.landmarks.append({'name': 'Sands SkyPark', 'osm_id': building.osm_id,
                            'deck_height_m': 200, 'mapped_length_m': length,
                            'mapped_maximum_width_m': width, 'mapped_area_m2': shape.area,
                            'source': 'Retained OSM outline 116800998. Arup specifies 340 m length, 38 m nominal width and 200 m height. Mapped length is 340.16 m and area is 12,454.9 m²; the operator reports 12,400 m². The mapped maximum bounding width of 57.72 m differs from the nominal width. The model follows the mapped outline. The closed belly and longitudinal ribs follow the JFE photograph.'})
