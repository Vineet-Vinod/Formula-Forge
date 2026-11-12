"""White lens fascias and oval openings observed on the Shanghai crossing wings."""

from __future__ import annotations

from circuit_dataclasses import Point, RoadStation
from circuit_mesh import add, mul
from circuit_scene import CircuitScene
from shapely import constrained_delaunay_triangles
from shapely.affinity import scale, translate
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapePoint
from shapely.geometry.polygon import orient


def lens_outline() -> Polygon:
    return translate(
        scale(ShapePoint(0, 0).buffer(1, quad_segs=48), 67.5, 3.5), yoff=27
    )


def lens_shape() -> Polygon:
    openings = [
        translate(
            scale(ShapePoint(0, 0).buffer(1, quad_segs=32), 7, 1.15),
            xoff=lane,
            yoff=27.2,
        )
        for lane in (-45.0, 45.0)
    ]
    return lens_outline().difference(openings[0]).difference(openings[1])


def front_point(
    scene: CircuitScene,
    wing: Polygon,
    sample: RoadStation,
    lane: float,
    height: float,
    depth: float = 0.0,
) -> Point:
    center = sample.point(lane)
    along = sample.tx, sample.ty, 0.0
    line = LineString(
        [add(center, mul(along, -45))[:2], add(center, mul(along, 45))[:2]]
    )
    crossing = wing.intersection(line)
    parts = (
        [crossing]
        if isinstance(crossing, LineString)
        else list(getattr(crossing, "geoms", []))
    )
    coordinates = [
        p for part in parts if isinstance(part, LineString) for p in part.coords
    ]
    if not coordinates:
        raise ValueError("Shanghai lens extends outside its mapped crossing wing")
    x, y = min(
        coordinates,
        key=lambda p: (p[0] - sample.x) * sample.tx + (p[1] - sample.y) * sample.ty,
    )
    mapped_offset = (x - sample.x) * sample.tx + (y - sample.y) * sample.ty
    front_offset = -14.5 if sample.station < 3500 else -15.0
    advance = max(0.0, front_offset - mapped_offset)
    x += sample.tx * advance
    y += sample.ty * advance
    x += sample.tx * (0.25 + depth)
    y += sample.ty * (0.25 + depth)
    return x, y, scene.nearest(x, y)[0].z + height


def wing_side(
    scene: CircuitScene, sample: RoadStation, a: Point, b: Point, c: Point, d: Point
) -> None:
    along_a = (a[0] - sample.x) * sample.tx + (a[1] - sample.y) * sample.ty
    along_b = (b[0] - sample.x) * sample.tx + (b[1] - sample.y) * sample.ty
    lane_a = (a[0] - sample.x) * sample.ty - (a[1] - sample.y) * sample.tx
    lane_b = (b[0] - sample.x) * sample.ty - (b[1] - sample.y) * sample.tx
    if (along_a + along_b) / 2 > -5 or abs(along_a - along_b) > abs(
        lane_a - lane_b
    ) * 0.25:
        scene.quad("Building_ShanghaiMappedWingRoofEdges", "Glass", a, b, c, d)
        return
    polygon = Polygon(
        [
            (
                (p[0] - sample.x) * sample.ty - (p[1] - sample.y) * sample.tx,
                p[2] - scene.nearest(*p[:2])[0].z,
            )
            for p in (a, b, c, d)
        ]
    )
    remaining = polygon.difference(lens_outline())
    for triangle in constrained_delaunay_triangles(remaining).geoms:
        points = []
        for lane, height in list(orient(triangle).exterior.coords)[:3]:
            t = (lane - lane_a) / (lane_b - lane_a)
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            points.append((x, y, scene.nearest(x, y)[0].z + height))
        # Match the outward-facing original boundary quad.
        normal = (b[1] - a[1], a[0] - b[0])
        cross = (points[1][0] - points[0][0]) * (points[2][2] - points[0][2]) - (
            points[1][2] - points[0][2]
        ) * (points[2][0] - points[0][0])
        if cross * normal[1] > 0:
            points[1], points[2] = points[2], points[1]
        scene.triangle(
            "Building_ShanghaiMappedWingFrontGlass",
            "Glass",
            points[0],
            points[1],
            points[2],
        )
        scene.triangle(
            "Building_ShanghaiMappedWingFrontGlass",
            "Glass",
            points[2],
            points[1],
            points[0],
        )


def wing_nose(scene: CircuitScene, wing: Polygon, sample: RoadStation) -> None:
    shape = orient(lens_shape())
    for triangle in constrained_delaunay_triangles(shape).geoms:
        coordinates = list(orient(triangle).exterior.coords)[:3]
        first = [
            front_point(scene, wing, sample, lane, height)
            for lane, height in coordinates
        ]
        last = [
            front_point(scene, wing, sample, lane, height, 0.55)
            for lane, height in coordinates
        ]
        scene.triangle(
            "Building_ShanghaiWingLensFront", "White", first[0], first[1], first[2]
        )
        scene.triangle(
            "Building_ShanghaiWingLensBack", "White", last[2], last[1], last[0]
        )
    for ring_index, ring in enumerate([shape.exterior, *shape.interiors]):
        for a, b in zip(ring.coords, list(ring.coords)[1:]):
            first_a = front_point(scene, wing, sample, a[0], a[1])
            first_b = front_point(scene, wing, sample, b[0], b[1])
            last_a = front_point(scene, wing, sample, a[0], a[1], 0.55)
            last_b = front_point(scene, wing, sample, b[0], b[1], 0.55)
            scene.quad(
                "Building_ShanghaiWingLensRim"
                if ring_index == 0
                else "Building_ShanghaiWingPortholeTunnel",
                "White" if ring_index == 0 else "Glass",
                last_a,
                last_b,
                first_b,
                first_a,
            )
    label = translate(
        scale(ShapePoint(0, 0).buffer(1, quad_segs=32), 21, 1.9), yoff=27.2
    )
    for triangle in constrained_delaunay_triangles(label).geoms:
        coordinates = list(orient(triangle).exterior.coords)[:3]
        points = [
            front_point(scene, wing, sample, lane, height, -0.005)
            for lane, height in coordinates
        ]
        uv = tuple(
            (lane / 42 + 0.5, 0.5 - (height - 27.2) / 3.8)
            for lane, height in coordinates
        )
        scene.triangle(
            "Building_ShanghaiWingVenueLabel",
            "VenueSign",
            points[0],
            points[1],
            points[2],
            uv,
        )
    scene.landmarks.append(
        {
            "name": "Shanghai crossing-wing white lens fascia and oval openings",
            "native_center_station_m": sample.station,
            "fascia_width_estimate_m": 135,
            "fascia_height_estimate_m": 7,
            "porthole_width_estimate_m": 14,
            "porthole_height_estimate_m": 2.3,
            "nose_depth_estimate_m": 0.55,
            "source_note": "Direct continuous707/708s entry wing and626/682s exit wing show pointed white lens fronts with two dark oval openings. Width±5m,height±1.5m,portholewidth±3m/height±.7m are visual estimates. The nose lies inside the actual mapped crossing envelope and above the preserved23.3m clearance. No supplied pixels or game logos are shipped.",
        }
    )
