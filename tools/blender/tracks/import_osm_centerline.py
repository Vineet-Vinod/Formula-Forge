#!/usr/bin/env python3
"""Snapshot selected OpenStreetMap circuit centerlines as C++ catalog arrays.

The generated coordinates are a reproducible, meter-based derivative of OSM
raceway geometry. FIA/circuit sources remain authoritative for lap length,
direction, start placement, elevation, width, banking, and runoff.
"""

from __future__ import annotations

import argparse
import math
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
OUTPUT = REPO / "src" / "track_data"
USER_AGENT = "FormulaForgeTrackImporter/1.0"

TRACKS = {
    "shanghai": {
        "symbol": "kShanghaiCenterline",
        "bbox": (121.205, 31.328, 121.235, 31.352),
        "way": 156328670,
        "clockwise": True,
        # FIA race start is 190 m beyond the control line toward Turn 1.
        "start": (31.3390674, 121.2168157),
        "source": "https://www.openstreetmap.org/way/156328670",
        "sample_spacing_m": 35.0,
    },
    "bahrain": {
        "symbol": "kBahrainCenterline",
        "bbox": (50.500, 26.015, 50.530, 26.045),
        "ways": (4818385, 881756729, 881756728),
        "clockwise": True,
        "start": (26.0320851, 50.5124434),
        "source": "https://www.openstreetmap.org/relation/284538",
        "smoothing_iterations": 3,
    },
    "jeddah": {
        "symbol": "kJeddahCenterline",
        "bbox": (39.095, 21.615, 39.125, 21.650),
        "ways": (
            1007989410, 1359884757, 1257884699, 1359884761,
            1359884760, 1359884759, 1359884758, 1359884756,
            1359884762,
        ),
        "clockwise": False,
        "start": (21.6369468, 39.1027829),
        "source": "https://www.openstreetmap.org/way/1007989410",
        "smoothing_iterations": 2,
    },
    "sepang": {
        "symbol": "kSepangCenterline",
        "bbox": (101.715, 2.745, 101.755, 2.775),
        "relation": 284496,
        "clockwise": True,
        "start_node": 1578189278,
        "source": "https://www.openstreetmap.org/relation/284496",
        "smoothing_iterations": 2,
    },
    "cota": {
        "symbol": "kCotaCenterline",
        "bbox": (-97.660, 30.110, -97.605, 30.160),
        "relation": 6537729,
        "clockwise": False,
        "start_node": 7909207460,
        "source": "https://www.openstreetmap.org/relation/6537729",
        "smoothing_iterations": 2,
    },
    "istanbul": {
        "symbol": "kIstanbulCenterline",
        "bbox": (29.390, 40.940, 29.430, 40.975),
        "way": 179048507,
        "clockwise": False,
        "start_node": 1893855303,
        "source": "https://www.openstreetmap.org/way/179048507",
        "smoothing_iterations": 2,
    },
    "hockenheim": {
        "symbol": "kHockenheimCenterline",
        "bbox": (8.555, 49.315, 8.595, 49.345),
        "relation": 284588,
        "clockwise": True,
        "start_node": 395005281,
        "source": "https://www.openstreetmap.org/relation/284588",
    },
    "buddh": {
        "symbol": "kBuddhCenterline",
        "bbox": (77.520, 28.330, 77.550, 28.365),
        "relation": 2532569,
        "clockwise": True,
        "start_node": 1986414860,
        "source": "https://www.openstreetmap.org/relation/2532569",
    },
}


def fetch_map(spec):
    bbox = ",".join(str(value) for value in spec["bbox"])
    request = urllib.request.Request(
        f"https://api.openstreetmap.org/api/0.6/map?bbox={bbox}",
        headers={"User-Agent": USER_AGENT},
    )
    root = ET.fromstring(urllib.request.urlopen(request, timeout=90).read())
    nodes = {
        int(node.attrib["id"]): (float(node.attrib["lat"]), float(node.attrib["lon"]))
        for node in root.findall("node")
    }
    ways = {
        int(way.attrib["id"]): [int(node.attrib["ref"]) for node in way.findall("nd")]
        for way in root.findall("way")
    }
    relations = {int(relation.attrib["id"]): relation for relation in root.findall("relation")}
    return nodes, ways, relations


def route_way_ids(spec, relations):
    if "way" in spec:
        return [spec["way"]]
    if "ways" in spec:
        return list(spec["ways"])
    relation = relations[spec["relation"]]
    return [
        int(member.attrib["ref"])
        for member in relation.findall("member")
        if member.attrib["type"] == "way"
        and member.attrib.get("role", "") not in {"pit_lane", "pitlane"}
    ]


def stitch_segments(segments):
    """Join member ways by shared endpoints without changing lap direction."""
    unused = list(range(len(segments)))
    route = list(segments[unused.pop(0)])
    while unused:
        joined = False
        for offset, index in enumerate(unused):
            segment = segments[index]
            if route[-1] == segment[0]:
                route.extend(segment[1:])
            elif route[-1] == segment[-1]:
                route.extend(reversed(segment[:-1]))
            elif route[0] == segment[-1]:
                route = list(segment[:-1]) + route
            elif route[0] == segment[0]:
                route = list(reversed(segment[1:])) + route
            else:
                continue
            unused.pop(offset)
            joined = True
            break
        if not joined:
            raise ValueError("OSM circuit members no longer form one connected loop")
    if route[0] == route[-1]:
        route.pop()
    return route


def project_to_meters(route, nodes):
    latitude_origin = sum(nodes[node][0] for node in route) / len(route)
    longitude_origin = sum(nodes[node][1] for node in route) / len(route)
    longitude_scale = 111_320.0 * math.cos(math.radians(latitude_origin))
    return [
        ((nodes[node][1] - longitude_origin) * longitude_scale,
         (nodes[node][0] - latitude_origin) * 111_320.0)
        for node in route
    ]


def signed_area(points):
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


def point_line_distance(point, first, second):
    dx, dy = second[0] - first[0], second[1] - first[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1.0e-12:
        return math.dist(point, first)
    blend = max(
        0.0,
        min(
            1.0,
            ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy)
            / length_squared,
        ),
    )
    projection = (first[0] + dx * blend, first[1] + dy * blend)
    return math.dist(point, projection)


def simplify_open(points, tolerance):
    if len(points) <= 2:
        return points
    farthest_distance = -1.0
    farthest_index = 0
    for index in range(1, len(points) - 1):
        distance = point_line_distance(points[index], points[0], points[-1])
        if distance > farthest_distance:
            farthest_distance = distance
            farthest_index = index
    if farthest_distance <= tolerance:
        return [points[0], points[-1]]
    first = simplify_open(points[: farthest_index + 1], tolerance)
    second = simplify_open(points[farthest_index:], tolerance)
    return first[:-1] + second


def simplify_closed(points, tolerance):
    # The start/finish datum remains the first control point. Split the loop at
    # its most distant point so RDP never shortcuts across the closing arc.
    split = max(range(1, len(points)), key=lambda index: math.dist(points[0], points[index]))
    first = simplify_open(points[: split + 1], tolerance)
    second = simplify_open(points[split:] + [points[0]], tolerance)
    return first[:-1] + second[:-1]


def resample_closed(points, spacing):
    cumulative = [0.0]
    for index, point in enumerate(points):
        cumulative.append(
            cumulative[-1] + math.dist(point, points[(index + 1) % len(points)])
        )
    count = max(4, int(round(cumulative[-1] / spacing)))
    result = []
    segment = 0
    for sample in range(count):
        distance = cumulative[-1] * sample / count
        while cumulative[segment + 1] < distance:
            segment += 1
        span = max(1.0e-9, cumulative[segment + 1] - cumulative[segment])
        blend = (distance - cumulative[segment]) / span
        first = points[segment]
        second = points[(segment + 1) % len(points)]
        result.append(
            (
                first[0] + (second[0] - first[0]) * blend,
                first[1] + (second[1] - first[1]) * blend,
            )
        )
    return result


def smooth_closed(points, iterations):
    """Round mapper-node corners without changing ordering or adding shortcuts."""
    smoothed = list(points)
    for _ in range(iterations):
        smoothed = [
            (
                smoothed[(index - 1) % len(smoothed)][0] * 0.25
                + point[0] * 0.50
                + smoothed[(index + 1) % len(smoothed)][0] * 0.25,
                smoothed[(index - 1) % len(smoothed)][1] * 0.25
                + point[1] * 0.50
                + smoothed[(index + 1) % len(smoothed)][1] * 0.25,
            )
            for index, point in enumerate(smoothed)
        ]
    return smoothed


def controls_for(spec):
    nodes, ways, relations = fetch_map(spec)
    way_ids = route_way_ids(spec, relations)
    route = stitch_segments([ways[way] for way in way_ids])
    points = project_to_meters(route, nodes)
    if (signed_area(points) < 0.0) != spec["clockwise"]:
        route.reverse()
        points.reverse()

    if spec.get("start_node") in route:
        start = route.index(spec["start_node"])
    else:
        latitude, longitude = spec["start"]
        start = min(
            range(len(route)),
            key=lambda index: (
                nodes[route[index]][0] - latitude
            ) ** 2
            + (nodes[route[index]][1] - longitude) ** 2,
        )
    route = route[start:] + route[:start]
    points = points[start:] + points[:start]

    center_x = 0.5 * (min(point[0] for point in points) + max(point[0] for point in points))
    center_y = 0.5 * (min(point[1] for point in points) + max(point[1] for point in points))
    points = [(point[0] - center_x, point[1] - center_y) for point in points]
    # Uniform stationing prevents Catmull-Rom from amplifying clusters of
    # survey nodes into tiny hooks while preserving the mapped racing line.
    controls = resample_closed(points, spec.get("sample_spacing_m", 20.0))
    controls = smooth_closed(controls, spec.get("smoothing_iterations", 0))
    return way_ids, points, controls


def render(slug, spec, way_ids, source_points, controls):
    raw_length = sum(
        math.dist(source_points[index], source_points[(index + 1) % len(source_points)])
        for index in range(len(source_points))
    )
    lines = [
        "// Derived from OpenStreetMap raceway geometry; © OpenStreetMap contributors.",
        f"// Source: {spec['source']}",
        f"// OSM way sequence: {', '.join(str(way) for way in way_ids)}.",
        f"// Raw projected loop length: {raw_length:.3f} m. Runtime normalizes to the FIA length.",
        f"// Uniform source sampling: {spec.get('sample_spacing_m', 20.0):.1f} m.",
        f"// Circular smoothing passes: {spec.get('smoothing_iterations', 0)}.",
        f"constexpr TrackControlPoint {spec['symbol']}[] = {{",
    ]
    for start in range(0, len(controls), 3):
        chunk = controls[start : start + 3]
        lines.append(
            "    "
            + ", ".join(f"{{{x:.3f}f, {y:.3f}f}}" for x, y in chunk)
            + ","
        )
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track", choices=tuple(TRACKS), required=True)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    spec = TRACKS[args.track]
    way_ids, source_points, controls = controls_for(spec)
    content = render(args.track, spec, way_ids, source_points, controls)
    if args.stdout:
        print(content, end="")
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"{args.track}_centerline.inc"
    path.write_text(content, encoding="utf-8")
    print(
        f"generated {path.relative_to(REPO)}: "
        f"{len(source_points)} OSM nodes -> {len(controls)} controls"
    )


if __name__ == "__main__":
    main()
