"""Reproducible Monza survey, independent of the gameplay coordinate contract.

Run with uv run python tools/blender/tracks/survey_monza.py.
OSM coordinates are observations, not a cadastral or laser survey.
"""

from __future__ import annotations

import bisect
import hashlib
import itertools
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from import_osm_centerline import stitch_segments

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "assets/tracks/monza/reconstruction"
TARGET = 5793.0
RELATION = 284565
START_NODE = 1828499259


def cumulative(points, closed=False):
    result = [0.0]
    for a, b in zip(points, points[1:] + points[:1] if closed else points[1:]):
        result.append(result[-1] + math.dist(a, b))
    return result


def smooth(points, closed=True, spacing=0.75):
    """Distance-aware Hermite interpolation, preserving every observed vertex."""
    n = len(points)
    result = []
    for i in range(n if closed else n - 1):
        p0, p1 = points[i], points[(i + 1) % n]
        prev = points[(i - 1) % n] if closed or i else p0
        nex = points[(i + 2) % n] if closed or i + 2 < n else p1
        d = math.dist(p0, p1)
        a, b = math.dist(prev, p0), math.dist(p1, nex)
        t0 = [(p1[k] - prev[k]) * d / max(a + d, 1e-9) for k in range(2)]
        t1 = [(nex[k] - p0[k]) * d / max(b + d, 1e-9) for k in range(2)]
        for j in range(max(2, math.ceil(d / spacing))):
            t = j / max(2, math.ceil(d / spacing))
            result.append(
                [
                    (2 * t**3 - 3 * t * t + 1) * p0[k]
                    + (t**3 - 2 * t * t + t) * t0[k]
                    + (-2 * t**3 + 3 * t * t) * p1[k]
                    + (t**3 - t * t) * t1[k]
                    for k in range(2)
                ]
            )
    if not closed:
        result.append(list(points[-1]))
    return result


def resample(points, count):
    station = cumulative(points, True)
    result = []
    for j in range(count):
        s = j * station[-1] / count
        i = min(bisect.bisect_right(station, s) - 1, len(points) - 1)
        t = (s - station[i]) / (station[i + 1] - station[i])
        result.append(
            [
                points[i][k] * (1 - t) + points[(i + 1) % len(points)][k] * t
                for k in range(2)
            ]
        )
    return result


def main():
    path = OUT / "references/monza.osm"
    root = ET.parse(path).getroot()
    nodes = {
        int(n.get("id")): [float(n.get("lon")), float(n.get("lat"))]
        for n in root.findall("node")
    }
    ways = {int(w.get("id")): w for w in root.findall("way")}
    rel = next(r for r in root.findall("relation") if int(r.get("id")) == RELATION)
    ids = [
        int(m.get("ref"))
        for m in rel.findall("member")
        if m.get("type") == "way" and not m.get("role")
    ]
    route = stitch_segments(
        [[int(nd.get("ref")) for nd in ways[i].findall("nd")] for i in ids]
    )
    origin = nodes[START_NODE]
    lat = math.radians(origin[1])
    # WGS84 local tangent-plane scale at the control line; X east, Y north, Z up.
    east = (
        math.pi
        / 180
        * 6378137
        / math.sqrt(1 - 0.00669437999014 * math.sin(lat) ** 2)
        * math.cos(lat)
    )
    north = (
        math.pi
        / 180
        * 6378137
        * (1 - 0.00669437999014)
        / (1 - 0.00669437999014 * math.sin(lat) ** 2) ** 1.5
    )

    def project(node):
        lon, latitude = nodes[node]
        return [(lon - origin[0]) * east, (latitude - origin[1]) * north]

    xy = [project(n) for n in route]
    if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(xy, xy[1:] + xy[:1])) > 0:
        route.reverse()
    k = route.index(START_NODE)
    route = route[k:] + route[:k]
    raw = [project(n) for n in route]
    pts = resample(smooth(raw), 7724)
    unscaled = cumulative(pts, True)[-1]
    factor = TARGET / unscaled
    pts = [[p[0] * factor, p[1] * factor] for p in pts]
    stations = cumulative(pts, True)

    def nearest(p):
        return min(range(len(pts)), key=lambda i: math.dist(pts[i], p))

    features = []
    for wid, way in ways.items():
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        refs = [int(n.get("ref")) for n in way.findall("nd")]
        if not all(n in nodes for n in refs) or len(refs) < 2:
            continue
        relevant = (
            wid in ids
            or tags.get("highway") in {"raceway", "service", "path", "footway", "track"}
            or "building" in tags
            or "barrier" in tags
            or tags.get("landuse") in {"forest", "grass", "meadow"}
            or tags.get("natural") in {"wood", "sand", "scrub", "water"}
            or tags.get("amenity") == "parking"
        )
        if not relevant:
            continue
        coords = [[v * factor for v in project(n)] for n in refs]
        # Include the venue and park, exclude the surrounding city streets.
        cx, cy = [sum(p[j] for p in coords) / len(coords) for j in range(2)]
        if not (-300 < cx < 1550 and -1200 < cy < 1650):
            continue
        features.append(
            {
                "osm_way": wid,
                "tags": tags,
                "points": coords,
                "closed": refs[0] == refs[-1],
            }
        )

    # Woods around Monza are mostly multipolygons. Preserve inner clearings.
    def rings(members):
        segments = []
        for member in members:
            way = ways.get(int(member.get("ref")))
            if way is not None:
                ns = [int(n.get("ref")) for n in way.findall("nd")]
                if all(n in nodes for n in ns):
                    segments.append(ns)
        finished = []
        while segments:
            chain = segments.pop(0)
            while chain[0] != chain[-1]:
                found = False
                for i, part in enumerate(segments):
                    if chain[-1] == part[0]:
                        chain.extend(part[1:])
                    elif chain[-1] == part[-1]:
                        chain.extend(part[-2::-1])
                    elif chain[0] == part[-1]:
                        chain = part[:-1] + chain
                    elif chain[0] == part[0]:
                        chain = part[:0:-1] + chain
                    else:
                        continue
                    segments.pop(i)
                    found = True
                    break
                if not found:
                    break
            if chain[0] == chain[-1]:
                finished.append([[v * factor for v in project(n)] for n in chain])
        return finished

    for relation in root.findall("relation"):
        tags = {t.get("k"): t.get("v") for t in relation.findall("tag")}
        if tags.get("landuse") != "forest" and tags.get("natural") != "wood":
            continue
        members = relation.findall("member")
        outer = rings(
            [m for m in members if m.get("role") == "outer" and m.get("type") == "way"]
        )
        inner = rings(
            [m for m in members if m.get("role") == "inner" and m.get("type") == "way"]
        )
        for index, ps in enumerate(outer):
            features.append(
                {
                    "osm_way": -int(relation.get("id")) * 10 - index,
                    "osm_relation": int(relation.get("id")),
                    "tags": tags,
                    "points": ps,
                    "holes": inner,
                    "closed": True,
                }
            )
    way_stations = {}
    for wid in ids:
        way = ways[wid]
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        refs = [int(n.get("ref")) for n in way.findall("nd")]
        vals = [stations[nearest([v * factor for v in project(n)])] for n in refs]
        way_stations[str(wid)] = {
            "name": tags.get("name", "connecting straight"),
            "start_m": min(vals),
            "end_m": max(vals),
        }
    pit = next(f for f in features if f["osm_way"] == 38168747)
    pit["points"] = smooth(pit["points"], False, 1.5)
    # Named transitions follow mapped ways; section boundaries include their approaches.
    anchors = {int(k): v for k, v in way_stations.items()}
    bounds = [
        0,
        anchors[179968242]["start_m"] - 130,
        anchors[179968242]["end_m"] + 40,
        anchors[179968245]["start_m"] - 160,
        anchors[179968229]["start_m"] - 100,
        anchors[179968230]["start_m"] - 110,
        anchors[179968230]["end_m"] + 70,
        anchors[179968226]["start_m"] - 150,
        anchors[179968239]["end_m"] + 70,
        anchors[179968234]["start_m"] - 180,
        TARGET,
    ]
    names = [
        "Start_finish",
        "Rettifilo",
        "Curva_Grande",
        "Roggia",
        "Lesmo_1",
        "Lesmo_2",
        "Serraglio",
        "Ascari",
        "Back_straight",
        "Alboreto",
    ]
    assert all(a < b for a, b in itertools.pairwise(bounds)), bounds
    sections = [
        {"name": n, "start_m": bounds[i], "end_m": bounds[i + 1]}
        for i, n in enumerate(names)
    ]
    survey = {
        "schema": 1,
        "origin_wgs84_lon_lat": origin,
        "axes": "X east, Y north, Z up; metres",
        "source_osm_relation": RELATION,
        "source_start_node": START_NODE,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "raw_projected_length_m": cumulative(raw, True)[-1],
        "smoothed_unscaled_length_m": unscaled,
        "uniform_plan_scale": factor,
        "plan_length_m": stations[-1],
        "sample_spacing_m": TARGET / len(pts),
        "centerline_xy": pts,
        "stations_m": stations[:-1],
        "raw_observations_xy": [[v * factor for v in p] for p in raw],
        "way_stations": way_stations,
        "sections": sections,
        "features": features,
        "confidence": {
            "plan": "OSM observed nodes, locally projected and uniformly normalized to official lap length",
            "vertical": "inferred smooth park grade; no measured elevation data available",
            "camber": "inferred restrained crossfall, not surveyed",
            "width": "10-12 m official range; local transitions inferred",
            "footprints": "OSM observations; dates and completeness vary",
            "barriers_runoff": "mapped where present; other offsets inferred from plans and imagery",
            "event_configuration": "2025 FIA map and 2026 F1 specification; not a verified 2026 event installation",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "survey.json").write_text(json.dumps(survey, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in survey.items()
                if k
                not in {
                    "features",
                    "centerline_xy",
                    "stations_m",
                    "raw_observations_xy",
                }
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
