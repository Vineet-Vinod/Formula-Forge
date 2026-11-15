"""Private south facade and source-qualified mansard/hip roof reconstruction."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene, cross, sub
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

from venues.monaco_rome_dataclasses import XY, RomeFrame, RomeSpec, RoofObjectSource

KIND = 'Building_PrivateVillaDeRome'
STUCCO = 'MonacoRomeStucco'
MARBLE = 'MonacoRomePinkMarble'
MOULDING = 'MonacoRomeMoulding'
METAL = 'MonacoRomeIron'
ROOF = 'MonacoRomeSlate'
ROOF_KIND = KIND+'_MainRoof'
SOFFIT_KIND = KIND+'_Soffit'
SOIL = 'MonacoRomeRoofSoil'
PLANT = 'MonacoRomeRoofPlant'
OBJECT_KIND = KIND+'_RoofObject'
SHUTTER = 'MonacoRomeShutter'
GLASS = 'Glass'


def prism(scene: MeshScene, shape: Polygon, low: float, high: float,
          material: str, kind: str = KIND) -> None:
    shape = orient(shape, sign=1)
    for triangle in constrained_delaunay_triangles(shape).geoms:
        xy = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            xy.reverse()
        a, b, c = [(x, y, high) for x, y in xy]
        scene.triangle(kind, material, a, b, c)
        a, b, c = [(x, y, low) for x, y in xy]
        scene.triangle(kind, material, c, b, a)
    for ring in (shape.exterior, *shape.interiors):
        for a, b in pairwise(ring.coords):
            scene.quad(kind, material, (*a, low), (*b, low), (*b, high), (*a, high))


def block(scene: MeshScene, spec: RomeSpec, u: float, d: float, z: float,
          width: float, depth: float, height: float, material: str) -> None:
    frame = spec.frame
    shape = Polygon([frame.point(u+du, d+dd, z)[:2]
                     for du, dd in ((-width/2, -depth/2), (width/2, -depth/2),
                                    (width/2, depth/2), (-width/2, depth/2))])
    prism(scene, shape, z-frame.datum_m-height/2, z-frame.datum_m+height/2, material)


def column(scene: MeshScene, spec: RomeSpec, u: float, d: float,
           bottom: float, top: float) -> None:
    frame = spec.frame
    ring = Polygon([frame.point(u+spec.column_radius_m*math.cos(i*math.tau/12),
                                d+spec.column_radius_m*math.sin(i*math.tau/12), bottom)[:2]
                    for i in range(12)])
    prism(scene, ring, bottom-frame.datum_m, top-frame.datum_m, MARBLE)
    for z in (bottom+.08, top-.08):
        block(scene, spec, u, d, z, spec.column_capital_width_m, .58, .16, MOULDING)
    block(scene, spec, u, d, top-.23, .43, .43, .17, MARBLE)


def wall_panel(scene: MeshScene, spec: RomeSpec, u0: float, u1: float,
               d: float, bottom: float, top: float, material: str) -> None:
    frame = spec.frame
    scene.quad(KIND, material, frame.point(u0, d, bottom), frame.point(u1, d, bottom),
               frame.point(u1, d, top), frame.point(u0, d, top))


def arch_opening(scene: MeshScene, spec: RomeSpec, u: float, d: float,
                 bottom: float, top: float, width: float, material: str = GLASS) -> None:
    frame = spec.frame
    radius = width/2
    spring = top-radius
    points = [(u-radius, bottom), (u+radius, bottom),
              *[(u+radius*math.cos(i*math.pi/16), spring+radius*math.sin(i*math.pi/16))
                for i in range(17)]]
    center = frame.point(u, d, (bottom+spring)/2)
    for a, b in pairwise([*points, points[0]]):
        scene.triangle(KIND, material, center, frame.point(a[0], d, a[1]),
                       frame.point(b[0], d, b[1]))
    for a, b in pairwise(points[2:]):
        scene.beam(KIND, MARBLE, frame.point(a[0], d-.035, a[1]),
                   frame.point(b[0], d-.035, b[1]), .10, .13)
    for sign in (-1, 1):
        block(scene, spec, u+sign*(radius+.06), d-.035, (bottom+spring)/2,
              .12, .13, spring-bottom, MARBLE)
    block(scene, spec, u, d-.05, bottom-.07, width+.22, .24, .13, MOULDING)
    block(scene, spec, u, d-.07, (bottom+spring)/2, .055, .09, spring-bottom, SHUTTER)


def rail(scene: MeshScene, spec: RomeSpec, u0: float, u1: float,
         depth: float, bottom: float, stone: bool) -> None:
    frame = spec.frame
    material = MOULDING if stone else METAL
    for z in (bottom+.13, bottom+.92):
        scene.beam(KIND, material, frame.point(u0, depth, z),
                   frame.point(u1, depth, z), .13 if stone else .045, .13 if stone else .045)
    count = max(1, round((u1-u0)/(.30 if stone else .23)))
    for index in range(count+1):
        u = u0+(u1-u0)*index/count
        if stone:
            for low, high, radius in ((.19, .29, .055), (.29, .45, .085),
                                      (.45, .64, .055), (.64, .83, .075)):
                ring = Polygon([frame.point(u+radius*math.cos(i*math.tau/8),
                                            depth+radius*math.sin(i*math.tau/8), bottom)[:2]
                                for i in range(8)])
                prism(scene, ring, bottom+low-frame.datum_m,
                      bottom+high-frame.datum_m, MARBLE)
        else:
            scene.beam(KIND, material, frame.point(u, depth, bottom+.15),
                       frame.point(u, depth, bottom+.91), .024)
            center = bottom+.53
            radius = .095
            for step in range(8):
                a, b = step*math.tau/8, (step+1)*math.tau/8
                scene.beam(KIND, material,
                           frame.point(u+radius*math.cos(a), depth, center+.21*math.sin(a)),
                           frame.point(u+radius*math.cos(b), depth, center+.21*math.sin(b)), .018)


def facade(scene: MeshScene, spec: RomeSpec) -> None:
    frame = spec.frame
    width = frame.width_m
    for level in range(spec.normal_levels):
        bottom = spec.base_absolute_m+level*spec.floor_height_m
        top = bottom+spec.floor_height_m
        # The unlocated lowest tier stays in the shell instead of inventing an entrance.
        if level == 0:
            continue
        block(scene, spec, width/2, 1.2, bottom, width-.14, 2.4, .24, MOULDING)
        block(scene, spec, width/2, .14, bottom-.18, width-.14, .26, .12, MARBLE)
        for index in range(spec.main_bays+1):
            u = .38+(width-.76)*index/spec.main_bays
            column(scene, spec, u, .42, bottom+.16, top-.18)
        for bay in range(spec.main_bays):
            u = .38+(width-.76)*(bay+.5)/spec.main_bays
            if level % 2:
                arch_opening(scene, spec, u, spec.loggia_depth_m-.025,
                             bottom+.39, top-.47, 1.8)
            else:
                wall_panel(scene, spec, u-.9, u+.9, spec.loggia_depth_m-.025,
                           bottom+.35, top-.45, GLASS)
                block(scene, spec, u, spec.loggia_depth_m-.09, top-.38, 2.05, .15, .15, MOULDING)
                for sign in (-1, 1):
                    block(scene, spec, u+sign*1.04, spec.loggia_depth_m-.06,
                          (bottom+top)/2, .16, .13, 2.45, MARBLE)
            a = .72+(width-.76)*bay/spec.main_bays
            b = -.04+(width-.76)*(bay+1)/spec.main_bays
            rail(scene, spec, a, b, .22, bottom+.13, stone=(level % 2 == 0))
    cornice = spec.terrace_absolute_m
    block(scene, spec, width/2, 1.25, cornice-.12, width-.10, 2.5, .27, MOULDING)
    rail(scene, spec, .45, width-.45, .25, cornice+.03, stone=True)


def roof_point(spec: RomeSpec, u: float, v: float, z: float) -> Point:
    nw, sw, se, ne = spec.roof_xy_absolute_z_m
    x = (1-v)*((1-u)*sw[0]+u*se[0])+v*((1-u)*nw[0]+u*ne[0])
    y = (1-v)*((1-u)*sw[1]+u*se[1])+v*((1-u)*nw[1]+u*ne[1])
    return x, y, z-spec.frame.datum_m


def roof_envelope(spec: RomeSpec) -> tuple[XY, ...]:
    if spec.north_eave_uv is None:
        raise ValueError('A revised roof envelope needs the independent north eave')
    nw, ne = spec.north_eave_uv
    return tuple(roof_point(spec, u, v, 0)[:2] for u, v in
                 ((0., 0.), (1., 0.), (1., spec.terrace_depth_fraction),
                  ne, nw, (0., spec.terrace_depth_fraction)))


def roof_triangle(scene: MeshScene, material: str, a: Point, b: Point, c: Point,
                  kind: str = ROOF_KIND, thickness: float = .12) -> None:
    if cross(sub(b, a), sub(c, a))[2] < 0:
        b, c = c, b
    top = (a, b, c)
    low = tuple((p[0], p[1], p[2]-thickness) for p in top)
    scene.triangle(kind, material, *top)
    scene.triangle(kind, material, low[2], low[1], low[0])
    for i in range(3):
        j = (i+1)%3
        scene.quad(kind, material, low[i], low[j], top[j], top[i])


def roof_quad(scene: MeshScene, material: str, a: Point, b: Point, c: Point, d: Point,
              *, kind: str = ROOF_KIND, thickness: float = .12) -> None:
    roof_triangle(scene, material, a, b, c, kind, thickness)
    roof_triangle(scene, material, a, c, d, kind, thickness)


def roof_skin(scene: MeshScene, faces: list[tuple[str, tuple[Point, Point, Point]]]) -> None:
    counts: Counter[tuple[Point, Point]] = Counter()
    edges: dict[tuple[Point, Point], tuple[str, Point, Point]] = {}
    for material, points in faces:
        a, b, c = points
        if cross(sub(b, a), sub(c, a))[2] < 0:
            b, c = c, b
        scene.triangle(ROOF_KIND, material, a, b, c)
        low = tuple((p[0], p[1], p[2]-.12) for p in (a, b, c))
        scene.triangle(ROOF_KIND, material, low[2], low[1], low[0])
        for p, q in ((a, b), (b, c), (c, a)):
            key = (p, q) if p < q else (q, p)
            counts[key] += 1
            edges[key] = material, p, q
    if max(counts.values()) > 2:
        raise ValueError('Main roof has a non-manifold top join')
    for key, count in counts.items():
        if count != 1:
            continue
        material, p, q = edges[key]
        scene.quad(ROOF_KIND, material, (p[0], p[1], p[2]-.12),
                   (q[0], q[1], q[2]-.12), q, p)


def dormer(scene: MeshScene, spec: RomeSpec, u: float, depth: float) -> None:
    frame = spec.frame
    outer = Polygon([(u-.88, 82.95), (u+.88, 82.95),
                     *[(u+.88*math.cos(i*math.pi/20), 85.06+.88*math.sin(i*math.pi/20))
                       for i in range(21)]])
    inner = Polygon([(u-.60, 83.12), (u+.60, 83.12),
                     *[(u+.60*math.cos(i*math.pi/20), 85.05+.60*math.sin(i*math.pi/20))
                       for i in range(21)]])
    hood = orient(outer.difference(inner), sign=1)
    for triangle in constrained_delaunay_triangles(hood).geoms:
        xy = list(triangle.exterior.coords)[:3]
        if not triangle.exterior.is_ccw:
            xy.reverse()
        p, q, r = [frame.point(x, depth, z) for x, z in xy]
        scene.triangle(KIND, MOULDING, p, q, r)
        p, q, r = [frame.point(x, depth+.95, z) for x, z in xy]
        scene.triangle(KIND, MOULDING, r, q, p)
    for ring in (hood.exterior, *hood.interiors):
        for a, b in pairwise(ring.coords):
            scene.quad(KIND, ROOF, frame.point(a[0], depth, a[1]),
                       frame.point(a[0], depth+.95, a[1]),
                       frame.point(b[0], depth+.95, b[1]), frame.point(b[0], depth, b[1]))
    arch_opening(scene, spec, u, depth+.025, 83.12, 85.65, 1.20, SHUTTER)


def elevation_spec(spec: RomeSpec, a: XY, b: XY) -> RomeSpec:
    p, q = roof_point(spec, *a, spec.terrace_absolute_m), roof_point(spec, *b, spec.terrace_absolute_m)
    span = math.dist(p[:2], q[:2])
    axis = (q[0]-p[0])/span, (q[1]-p[1])/span
    frame = RomeFrame(p[:2], axis, (-axis[1], axis[0]), span, 3., spec.frame.datum_m)
    return replace(spec, frame=frame)


def roof_sections(spec: RomeSpec) -> tuple[tuple[Point, Point, Point], ...]:
    u = spec.mansard_inner_u_fraction
    near, rear = spec.mansard_inner_front_v_fraction, spec.mansard_inner_rear_v_fraction
    low = spec.terrace_absolute_m
    high = spec.shoulder_absolute_m
    t = spec.terrace_depth_fraction
    # UV coordinates share the same bilinear plan as the literal source roof ring.
    outer = [(0., t, low), (1., t, low), (1., 1., low), (0., 1., low)]
    inner = [(u, near, high), (1-u, near, high), (1-u, rear, high), (u, rear, high)]
    if spec.north_upper_uv is not None:
        nw, ne = spec.north_upper_uv
        inner[2], inner[3] = (*ne, high), (*nw, high)
    if spec.north_eave_uv is not None:
        nw, ne = spec.north_eave_uv
        outer[2], outer[3] = (*ne, low), (*nw, low)
    apex = (*spec.hip_apex_uv, spec.hip_apex_absolute_m)
    sections: list[tuple[Point, Point, Point]] = []
    for i in range(4):
        j = (i+1)%4
        sections.extend(((outer[i], outer[j], inner[j]), (outer[i], inner[j], inner[i])))
        sections.append((inner[i], inner[j], apex))
    return tuple(sections)


def roof_height(spec: RomeSpec, u: float, v: float) -> float:
    point = roof_point(spec, u, v, 0)
    for section in roof_sections(spec):
        a, b, c = [roof_point(spec, *p) for p in section]
        den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        p = ((b[1]-c[1])*(point[0]-c[0])+(c[0]-b[0])*(point[1]-c[1]))/den
        q = ((c[1]-a[1])*(point[0]-c[0])+(a[0]-c[0])*(point[1]-c[1]))/den
        if min(p, q, 1-p-q) >= -1e-8:
            return p*a[2]+q*b[2]+(1-p-q)*c[2]+spec.frame.datum_m
    raise ValueError('Roof feature escaped the qualified mansard/hip plan')


def roof_object_point(spec: RomeSpec, u: float, v: float, lift: float) -> Point:
    return roof_point(spec, u, v, roof_height(spec, u, v)+lift)


def north_hip(scene_spec: RomeSpec) -> tuple[Point, Point, Point]:
    if scene_spec.north_upper_uv is None:
        raise ValueError('Register the observed northern upper shoulder before roof objects')
    nw, ne = scene_spec.north_upper_uv
    return (roof_point(scene_spec, *ne, scene_spec.shoulder_absolute_m),
            roof_point(scene_spec, *nw, scene_spec.shoulder_absolute_m),
            roof_point(scene_spec, *scene_spec.hip_apex_uv, scene_spec.hip_apex_absolute_m))


def source_object_point(spec: RomeSpec, source: RoofObjectSource,
                        u: float, v: float, lift: float) -> Point:
    sw, se, ne, nw = source.footprint_xy_m
    x = (1-v)*((1-u)*sw[0]+u*se[0])+v*((1-u)*nw[0]+u*ne[0])
    y = (1-v)*((1-u)*sw[1]+u*se[1])+v*((1-u)*nw[1]+u*ne[1])
    a, b, c = north_hip(spec)
    denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    p = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
    q = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
    return x, y, p*a[2]+q*b[2]+(1-p-q)*c[2]+lift


def roof_objects(scene: MeshScene, spec: RomeSpec) -> None:
    if len(spec.source_objects) != 3:
        raise ValueError('All three roof objects need direct source registrations')
    light = next(p for p in spec.source_objects if p.kind == 'rooflight')
    fans = next(p for p in spec.source_objects if p.kind == 'fans')
    plant = next(p for p in spec.source_objects if p.kind == 'plant')
    for row in range(3):
        for col in range(2):
            u0, u1, v0, v1 = col/2, (col+1)/2, row/3, (row+1)/3
            pane = [source_object_point(spec, light, u, v, .09)
                    for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
            roof_quad(scene, GLASS, *pane, kind=OBJECT_KIND, thickness=.025)
            for a, b in pairwise([*pane, pane[0]]):
                scene.beam(KIND, MOULDING, a, b, .055)
    tray = [source_object_point(spec, fans, u, v, .10)
            for u, v in ((0., 0.), (1., 0.), (1., 1.), (0., 1.))]
    roof_quad(scene, METAL, *tray, kind=OBJECT_KIND, thickness=.06)
    for a, b in pairwise([*tray, tray[0]]):
        scene.beam(KIND, MOULDING, a, b, .09)
    for fraction in (.25, .75):
        center = source_object_point(spec, fans, fraction, .5, .30)
        scene.box(KIND, MOULDING, (center[0], center[1], center[2]-.10), .95, .95, .20)
        ring = [(center[0]+.36*math.cos(i*math.tau/20),
                 center[1]+.36*math.sin(i*math.tau/20), center[2]+.015) for i in range(21)]
        for a, b in pairwise(ring):
            scene.triangle(KIND, METAL, (center[0], center[1], center[2]+.015), a, b)
        for i in range(4):
            angle = i*math.tau/4
            scene.beam(KIND, STUCCO, (center[0], center[1], center[2]+.035),
                       (center[0]+.28*math.cos(angle), center[1]+.28*math.sin(angle), center[2]+.035), .055)
    bed = [source_object_point(spec, plant, u, v, .12)
           for u, v in ((0., 0.), (1., 0.), (1., 1.), (0., 1.))]
    roof_quad(scene, SOIL, *bed, kind=OBJECT_KIND, thickness=.08)
    for a, b in pairwise([*bed, bed[0]]):
        scene.beam(KIND, METAL, a, b, .10)
    for u, v in ((.25, .25), (.75, .25), (.25, .75), (.75, .75)):
        p = source_object_point(spec, plant, u, v, .14)
        top = (p[0], p[1], p[2]+.32)
        ring = [(p[0]+.39*math.cos(i*math.tau/8), p[1]+.39*math.sin(i*math.tau/8), p[2])
                for i in range(9)]
        for a, b in pairwise(ring):
            scene.triangle(KIND, PLANT, a, b, top)
            scene.triangle(KIND, PLANT, b, a, p)


def roofs(scene: MeshScene, spec: RomeSpec) -> None:
    frame = spec.frame
    _nw, sw, se, _ne = spec.roof_xy_absolute_z_m
    t = spec.terrace_depth_fraction
    outer = [roof_point(spec, 0, t, spec.terrace_absolute_m),
             roof_point(spec, 1, t, spec.terrace_absolute_m),
             roof_point(spec, 1, 1, spec.terrace_absolute_m), roof_point(spec, 0, 1, spec.terrace_absolute_m)]
    north_nw, north_ne = (spec.north_eave_uv if spec.north_eave_uv is not None
                          else ((0., 1.), (1., 1.)))
    outer[2] = roof_point(spec, *north_ne, spec.terrace_absolute_m)
    outer[3] = roof_point(spec, *north_nw, spec.terrace_absolute_m)
    front = [roof_point(spec, 0, 0, sw[2]), roof_point(spec, 1, 0, se[2]), outer[1], outer[0]]
    faces: list[tuple[str, tuple[Point, Point, Point]]] = [
        (MOULDING, (front[0], front[1], front[2])), (MOULDING, (front[0], front[2], front[3]))]
    for section in roof_sections(spec):
        points = [roof_point(spec, *p) for p in section]
        faces.append((ROOF, (points[0], points[1], points[2])))
    roof_skin(scene, faces)
    # A thin horizontal soffit joins the observed overhang to the unchanged body.
    prism(scene, Polygon([p[:2] for p in outer]),
          spec.terrace_absolute_m-frame.datum_m-.24,
          spec.terrace_absolute_m-frame.datum_m-.12, MOULDING, SOFFIT_KIND)
    for i in range(4):
        scene.beam(KIND, METAL, outer[i], outer[(i+1)%4], .04)
    u = spec.mansard_inner_u_fraction
    near, rear = spec.mansard_inner_front_v_fraction, spec.mansard_inner_rear_v_fraction
    inner = [(u, near), (1-u, near), (1-u, rear), (u, rear)]
    if spec.north_upper_uv is not None:
        inner[2], inner[3] = spec.north_upper_uv[1], spec.north_upper_uv[0]
    apex = roof_point(spec, *spec.hip_apex_uv, spec.hip_apex_absolute_m+.02)
    for hip_uv in inner:
        scene.beam(KIND, METAL, roof_point(spec, *hip_uv, spec.shoulder_absolute_m+.02), apex, .025)
    front_spec = elevation_spec(spec, (0, t), (1, t))
    frame = front_spec.frame
    depth = .06
    for fraction in (.20, .80):
        u = frame.width_m*fraction
        dormer(scene, front_spec, u, depth)
    for a, b, fractions in (
        ((1., t), north_ne, (.14, .38, .62, .86)),
        (north_nw, (0., t), (.14, .38, .62, .86)),
        (north_ne, north_nw, (.18, .50, .82)),
    ):
        side_spec = elevation_spec(spec, a, b)
        for fraction in fractions:
            dormer(scene, side_spec, side_spec.frame.width_m*fraction, .13)
    center = frame.width_m/2
    peak = 86.65
    left, right = center-2.65, center+2.65
    p, q, r = frame.point(left, depth-.08, 83.6), frame.point(right, depth-.08, 83.6), frame.point(center, depth-.08, peak)
    scene.triangle(KIND, STUCCO, p, q, r)
    for x, y in ((p, q), (q, r), (r, p)):
        scene.beam(KIND, MOULDING, x, y, .16)
    circle = []
    for i in range(25):
        angle = i*math.tau/24
        circle.append(frame.point(center+.40*math.cos(angle), depth-.11, 84.65+.40*math.sin(angle)))
    c = frame.point(center, depth-.115, 84.65)
    for x, y in pairwise(circle):
        scene.triangle(KIND, GLASS, c, x, y)
        scene.beam(KIND, MOULDING, x, y, .065)
    roof_objects(scene, spec)


def emit(scene: MeshScene, spec: RomeSpec) -> dict[str, int]:
    frame = spec.frame
    owner = orient(Polygon(spec.owner_xy_m), sign=1)
    inset = Polygon([frame.point(u, d, spec.base_absolute_m)[:2]
                     for u, d in ((-2, spec.loggia_depth_m),
                                  (frame.width_m+2, spec.loggia_depth_m),
                                  (frame.width_m+2, frame.depth_m+2), (-2, frame.depth_m+2))])
    core = owner.intersection(inset)
    if not isinstance(core, Polygon):
        raise TypeError('Rome recessed body must stay in one literal owner')
    prism(scene, core, spec.base_absolute_m-frame.datum_m,
          spec.terrace_absolute_m-frame.datum_m, STUCCO)
    # Close the low south foundation. Upper south space is a real recessed loggia.
    foundation = Polygon([frame.point(u, d, spec.base_absolute_m)[:2]
                          for u, d in ((0, 0), (frame.width_m, 0),
                                       (frame.width_m, spec.loggia_depth_m), (0, spec.loggia_depth_m))]).intersection(owner)
    if not isinstance(foundation, Polygon):
        raise TypeError('Rome foundation escaped its literal owner')
    prism(scene, foundation, spec.base_absolute_m-frame.datum_m,
          spec.base_absolute_m+spec.floor_height_m-frame.datum_m, STUCCO)
    # Plain secondary elevations are deliberately sparse estimates.
    ring = list(owner.exterior.coords)
    for a, b in pairwise(ring):
        span = math.dist(a, b)
        if (a[1]+b[1])/2 < frame.origin[1]+2:
            continue
        tx, ty = (b[0]-a[0])/span, (b[1]-a[1])/span
        nx, ny = ty, -tx
        for level in range(3, spec.normal_levels):
            bottom = spec.base_absolute_m+level*spec.floor_height_m+.85
            for bay in range(max(1, round(span/5.5))):
                u = (bay+.5)*span/max(1, round(span/5.5))
                x, y = a[0]+tx*u+nx*.025, a[1]+ty*u+ny*.025
                p = (x-tx*.48, y-ty*.48, bottom-frame.datum_m)
                q = (x+tx*.48, y+ty*.48, bottom-frame.datum_m)
                scene.quad(KIND, GLASS, p, q, (q[0], q[1], q[2]+1.65), (p[0], p[1], p[2]+1.65))
    facade(scene, spec)
    body_ends = {name: len(tile.triangles) for name, tile in scene.tiles.items()}
    roofs(scene, spec)
    return body_ends
