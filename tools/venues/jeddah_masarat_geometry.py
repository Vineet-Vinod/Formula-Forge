"""Original Masarat architecture reconstructed from registered primary photos."""
from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise

from circuit_dataclasses import Point
from circuit_mesh import MeshScene
from shapely.geometry import Point as ShapePoint
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import transform

from venues.jeddah_context_shapes import skin, slab, walls
from venues.jeddah_masarat_dataclasses import MasaratArchitecture, Wing


def xy(config: MasaratArchitecture, u: float, v: float) -> tuple[float, float]:
    return (config.origin[0] + u * config.axis[0] + v * config.normal[0],
            config.origin[1] + u * config.axis[1] + v * config.normal[1])


def native(config: MasaratArchitecture, plan: Polygon) -> Polygon:
    result = transform(lambda u, v: xy(config, u, v), plan)
    if not isinstance(result, Polygon):
        raise TypeError('A component plan must remain a polygon')
    return result


def rounded(u: float, v: float, width: float, depth: float, radius: float) -> Polygon:
    return box(u - width / 2 + radius, v + radius,
               u + width / 2 - radius, v + depth - radius).buffer(radius, quad_segs=8)


def plans(config: MasaratArchitecture) -> tuple[tuple[str, Polygon, float], ...]:
    components = []
    for wing in config.wings:
        outer = rounded(wing.center, wing.front, wing.width, wing.depth, 1.6)
        left = wing.center - wing.width / 2
        stack = rounded(left + 3.1, wing.front, 6.2, 7.5, 2.6)
        # Reuse the actual edge: equivalent sums can leave a sub-picometre slit at this join.
        recess = box(left - .1, wing.front - .1, stack.bounds[2], stack.bounds[3])
        exposed = outer.difference(recess).union(stack)
        if not isinstance(exposed, Polygon):
            raise TypeError('The rounded corner stack must attach to its stone finger')
        components.append((wing.name, native(config, exposed), wing.height))
    high = native(config, rounded(125, 24.5, 25, 30, 1.0).difference(
        box(131.75, 24.3, 138.5, 25.45)))
    core = native(config, ShapePoint(135, 28).buffer(3.2, quad_segs=12))
    high = high.union(core)
    high_corner = native(config, box(112.4, 24.4, 118.7, 32.0))
    high_stack = native(config, rounded(115.6, 24.5, 6.2, 7.5, 2.6))
    high = high.difference(high_corner).union(high_stack)
    if not isinstance(high, Polygon):
        raise TypeError('The tall core must attach to the main wing')
    outer_return = native(config, rounded(132, 10.5, 14, 20, 5.2))
    lower_return = outer_return.difference(high)
    if not isinstance(lower_return, Polygon):
        raise TypeError('The lower rounded loggia must remain one attached return')
    components.extend((('DominantHighWing', high, config.high_height_m),
                       ('LowerRoundedReturn', lower_return, config.return_height_m)))
    return tuple(components)


def point(config: MasaratArchitecture, u: float, v: float, z: float) -> Point:
    return (*xy(config, u, v), z)


def panel(scene: MeshScene, config: MasaratArchitecture, a: tuple[float, float],
          b: tuple[float, float], low: float, high: float, material: str, kind: str) -> None:
    scene.quad(kind, material, point(config, *a, low), point(config, *b, low),
               point(config, *b, high), point(config, *a, high))


def framed_windows(scene: MeshScene, config: MasaratArchitecture, a: tuple[float, float],
                   b: tuple[float, float], base: float, height: float, floors: int,
                   count: int, seed: int, narrow: bool = False) -> None:
    span = math.dist(a, b)
    tx, ty = (b[0] - a[0]) / span, (b[1] - a[1]) / span
    pitch = height / floors
    for floor in range(floors):
        low, high = base + floor * pitch + .7, base + (floor + 1) * pitch - .4
        for bay in range(count):
            f = (bay + .5) / count
            center = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            width = min(1.25 if narrow else 2.1, span / count * .63)
            first = center[0] - tx * width / 2, center[1] - ty * width / 2
            last = center[0] + tx * width / 2, center[1] + ty * width / 2
            material = 'WarmGlass' if (floor * 19 + bay * 11 + seed) % 53 == 0 else 'Glass'
            panel(scene, config, first, last, low, high, material, 'Building_MasaratInsetWindows')
            scene.beam('Building_MasaratWindowSills', 'White', point(config, *first, low - .06),
                       point(config, *last, low - .06), .08, .1)


def balcony_stack(scene: MeshScene, config: MasaratArchitecture, shape: Polygon,
                  base: float, height: float, floors: int, name: str,
                  excluded: Polygon | None = None) -> None:
    outer = native(config, shape)
    if excluded is not None:
        outer = outer.difference(excluded)
        if not isinstance(outer, Polygon):
            raise TypeError('A rounded stack must remain connected after its high-wing partition')
    inner = outer.buffer(-1.35, join_style='round')
    if not isinstance(inner, Polygon) or inner.is_empty:
        raise ValueError('The estimated loggia depth consumes its entire floorplate')
    pitch = height / floors
    thickness = .38 if excluded is not None else .28
    pier_width = .55 if excluded is not None else .36
    boundary = list(orient(outer, sign=1).exterior.coords)
    for floor in range(floors + 1):
        slab(scene, outer, base + floor * pitch, thickness, 'Building_MasaratRoundedFloorSlabs')
    walls(scene, inner, base + .1, base + height - thickness,
          'Building_MasaratRecessedLoggias', 'Glass')
    for floor in range(floors):
        low = base + floor * pitch + .15
        high = base + (floor + 1) * pitch - thickness
        for i, (a, b) in enumerate(pairwise(boundary)):
            if excluded is not None and excluded.buffer(.02).covers(ShapePoint((a[0]+b[0])/2, (a[1]+b[1])/2)):
                continue
            span = math.dist(a, b)
            scene.quad('Building_MasaratPaleBalconyRails', 'Cream', (*a[:2], low + .65),
                       (*b[:2], low + .65), (*b[:2], low + 1.05), (*a[:2], low + 1.05))
            scene.beam('Building_MasaratRailCaps', 'Steel', (*a[:2], low + 1.07),
                       (*b[:2], low + 1.07), .035, .045)
            if i % 8 == 0 or span > 2:
                scene.beam('Building_MasaratLoggiaPiers', 'White', (*a[:2], low),
                           (*a[:2], high), pier_width, .45)
    skin(scene, outer, base + height, 'Building_MasaratLoggiaRoof', 'Concrete')


def lower_wing(scene: MeshScene, config: MasaratArchitecture, wing: Wing, plan: Polygon) -> None:
    base = wing.entry_relative_m
    # The narrow rounded return is distinct from the broad stone wall in both primary photos.
    stack_local = rounded(wing.center - wing.width / 2 + 3.1, wing.front, 6.2, 7.5, 2.6)
    stack = native(config, stack_local)
    solid = plan.difference(stack)
    if not isinstance(solid, Polygon):
        raise TypeError('The lower wing body must stay connected beside its rounded loggia')
    walls(scene, solid, base, base + wing.height, 'Building_MasaratStoneFingers', wing.material)
    skin(scene, solid, base + wing.height, 'Building_MasaratFingerRoof', 'Roof')
    balcony_stack(scene, config, stack_local, base, wing.height - .45, wing.floors, wing.name)
    left, right = wing.center - wing.width / 2, wing.center + wing.width / 2
    # Broad side walls have small recessed windows; the deep slots remain actual open air.
    for side, sign in ((left - .018, -1), (right + .018, 1)):
        framed_windows(scene, config, (side, wing.front + 8), (side, wing.front + wing.depth - 2),
                       base, wing.height - .7, wing.floors, 7, int(wing.center) + sign, True)
        for v in (wing.front + 8, wing.front + wing.depth - 2):
            scene.beam('Building_MasaratStonePilasters', 'Cream', point(config, side, v, base),
                       point(config, side, v, base + wing.height), .46, .35)
    framed_windows(scene, config, (left + 6.6, wing.front - .018), (right - 1.5, wing.front - .018),
                   base, wing.height, wing.floors, 3, int(wing.center))
    framed_windows(scene, config, (left + 1.5, wing.front + wing.depth + .018),
                   (right - 1.5, wing.front + wing.depth + .018), base, wing.height, wing.floors, 5, 17)
    walls(scene, solid, base + wing.height - .3, base + wing.height + .5,
          'Building_MasaratModestRoofParapets', 'Cream')


def high_wing(scene: MeshScene, config: MasaratArchitecture, plan: Polygon, lower: Polygon) -> None:
    base, height = config.entrance_relative_m, config.high_height_m
    tall_stack_local = rounded(115.6, 24.5, 6.2, 7.5, 2.6)
    tall_stack = native(config, tall_stack_local)
    solid = plan.difference(tall_stack)
    if not isinstance(solid, Polygon):
        raise TypeError('The tall rounded loggia must attach to a connected high wing')
    for a, b in pairwise(orient(solid, sign=1).exterior.coords):
        dx = (a[0] + b[0]) / 2 - config.origin[0]
        dy = (a[1] + b[1]) / 2 - config.origin[1]
        front_coordinate = dx * config.normal[0] + dy * config.normal[1]
        material = 'Cream' if abs(front_coordinate - 24.5) < .01 else 'White'
        scene.quad('Building_MasaratHighEnvelope', material, (*a[:2], base), (*b[:2], base),
                   (*b[:2], base + height), (*a[:2], base + height))
    # Glazing is confined to vertical bands, with a large pale wall between them.
    for u in (112.48, 137.52):
        for first, last in ((34, 40), (43, 52)):
            framed_windows(scene, config, (u, first), (u, last), base, height - 2,
                           config.high_floors, 2 if first == 34 else 3, first)
    for v in (24.48, 54.52):
        start = 119.1 if v < 30 else 114
        count = 3 if v < 30 else 5
        framed_windows(scene, config, (start, v), (132, v), base,
                       height - 2, config.high_floors, count, int(v), narrow=v < 30)
    for u in (113.4, 132.2):
        for v in (24.45, 54.55):
            scene.beam('Building_MasaratHighStonePilasters', 'Cream', point(config, u, v, base),
                       point(config, u, v, base + height - 1), 1.05, .4)
    core = native(config, ShapePoint(135, 28).buffer(3.2, quad_segs=12))
    balcony_stack(scene, config, tall_stack_local, base, height - 1.1, config.high_floors,
                  'TallWingNarrowStack')
    main_roof = solid.difference(core)
    roof_parts = [main_roof] if isinstance(main_roof, Polygon) else list(main_roof.geoms)
    for part in roof_parts:
        if not isinstance(part, Polygon):
            raise TypeError('The roof beside the distinct core must contain only surface polygons')
        skin(scene, part, base + height, 'Building_MasaratHighRoof', 'Concrete')
    walls(scene, core, base + height, base + height + 1.1,
          'Building_MasaratRoundedPaleCoreCapSides', 'White')
    skin(scene, core, base + height + 1.1, 'Building_MasaratCoreCap', 'White')
    return_local = rounded(132, 10.5, 14, 20, 5.2)
    balcony_stack(scene, config, return_local, base, config.return_height_m,
                  config.return_floors, 'LowerRoundedReturn', plan)
    assert lower.area > 0


def build(scene: MeshScene, config: MasaratArchitecture,
          ground: Callable[[float, float], float]) -> tuple[tuple[str, Polygon, float], ...]:
    components = plans(config)
    for wing, (_, plan, _) in zip(config.wings, components[:4], strict=True):
        lower_wing(scene, config, wing, plan)
    high_wing(scene, config, components[4][1], components[5][1])
    # Only the observed southern fence is reconstructed; unknown rear/site boundaries stay open.
    for i in range(75):
        u = 4 + i * 2.0
        if 122 < u < 137:
            continue
        a, b = xy(config, u, 1.0), xy(config, u + 1.8, 1.0)
        za, zb = ground(*a), ground(*b)
        scene.quad('Building_MasaratEntrancePlinth', 'White', (*a, za - .12), (*b, zb - .12),
                   (*b, zb + .45), (*a, za + .45))
        for j in range(4):
            f = j / 4
            x, y = a[0] + (b[0]-a[0])*f, a[1] + (b[1]-a[1])*f
            z = za + (zb-za)*f
            scene.beam('Building_MasaratBlackPicketFence', 'Black', (x,y,z+.35), (x,y,z+2.0), .055)
        scene.beam('Building_MasaratFenceTopRail', 'Black', (*a, za+1.8), (*b, zb+1.8), .055)
    return components
