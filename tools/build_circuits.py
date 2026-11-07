#!/usr/bin/env python3
"""Build Formula Forge circuits from OpenStreetMap and Copernicus GLO-90.

Reads public raceway geometry and point elevations, then writes the native
survey includes, provenance and building footprints. Contact binaries are
written afterwards by build/tests/export-surfaces so they share the runtime
sampler. Cached downloads live under Attribution/Sources/<slug>/.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "Attribution" / "Sources"
TRACK_DATA = ROOT / "Source" / "FormulaForge" / "Native" / "track_data"
CONTENT = ROOT / "Content" / "Generated"
REVIEWS = ROOT / "build" / "reviews"
RETRIEVED = "2026-11-04"
EARTH = 6378137.0
USER_AGENT = "FormulaForge/track-authoring (ODbL circuit reconstruction)"

# lengths are published Grand Prix figures used to choose a layout and, when
# the mapped loop is already within 1.5%, to apply one recorded scale.
CIRCUITS = [
    dict(slug="bahrain", enum="Bahrain", folder="Bahrain", title="Bahrain",
         venue="Bahrain International Circuit", country="Bahrain",
         lat=26.0325, lon=50.5106, radius=2200, lengths=[5412], turns=15,
         clockwise=True, street=False, shoulder=12.0, base=12.0, straight=15.0,
         names=["Grand Prix"], crossings=0, environment="desert-circuit",
         description="Sakhir Grand Prix loop, with the long pit straight and the tight opening complex."),
    dict(slug="jeddah", enum="Jeddah", folder="Jeddah", title="Jeddah",
         venue="Jeddah Corniche Circuit", country="Saudi Arabia",
         lat=21.6319, lon=39.1044, radius=4500, lengths=[6174], turns=27,
         clockwise=False, street=True, shoulder=5.0, base=12.0, straight=15.0,
         names=["Jeddah", "Corniche"], crossings=0, environment="corniche",
         description="The Jeddah Corniche street loop along the Red Sea, anti-clockwise."),
    dict(slug="australia", enum="Australia", folder="Australia", title="Australia",
         venue="Albert Park Circuit", country="Australia",
         lat=-37.8497, lon=144.9680, radius=2200, lengths=[5278], turns=16,
         clockwise=True, street=True, shoulder=5.0, base=12.0, straight=14.0,
         names=["Albert Park", "Australian"], crossings=0, environment="park-street",
         description="Albert Park's Grand Prix loop around the lake in Melbourne."),
    dict(slug="japan", enum="Japan", folder="Japan", title="Japan",
         venue="Suzuka International Racing Course", country="Japan",
         lat=34.8431, lon=136.5408, start=(34.8433, 136.5409), radius=2200, lengths=[5807], turns=18,
         clockwise=True, street=False, shoulder=6.0, base=12.0, straight=15.0,
         names=["Suzuka", "Grand Prix"], crossings=1, deck=True, environment="figure-eight",
         description="Suzuka's figure-eight Grand Prix course. The back straight crosses above the Degner curves."),
    dict(slug="china", enum="China", folder="China", title="China",
         venue="Shanghai International Circuit", country="China",
         lat=31.3389, lon=121.2198, radius=2200, lengths=[5451], turns=16,
         clockwise=True, street=False, shoulder=10.0, base=13.0, straight=16.0,
         names=["Shanghai", "Grand Prix"], crossings=0, environment="parkland",
         description="Shanghai International Circuit, including the long opening right-hander."),
    dict(slug="canada", enum="Canada", folder="Canada", title="Canada",
         venue="Circuit Gilles Villeneuve", country="Canada",
         lat=45.5006, lon=-73.5225, radius=1800, lengths=[4361], turns=14,
         clockwise=True, street=True, shoulder=4.0, base=12.0, straight=13.5,
         names=["Gilles Villeneuve", "Montreal"], crossings=0, environment="island",
         description="Circuit Gilles Villeneuve on Ile Notre-Dame in Montreal."),
    dict(slug="monaco", enum="Monaco", folder="Monaco", title="Monaco",
         venue="Circuit de Monaco", country="Monaco",
         lat=43.7347, lon=7.4216, radius=1400, lengths=[3337], turns=19,
         clockwise=True, street=True, shoulder=2.2, base=10.5, straight=12.0,
         names=["Monaco"], crossings=0, environment="harbour",
         description="Circuit de Monaco, a narrow harbour and street lap."),
    dict(slug="austria", enum="Austria", folder="Austria", title="Austria",
         venue="Red Bull Ring", country="Austria",
         lat=47.2197, lon=14.7647, radius=1800, lengths=[4318, 4326], turns=10,
         clockwise=True, street=False, shoulder=8.0, base=12.0, straight=15.0,
         names=["Red Bull", "Grand Prix", "A1-Ring"], crossings=0, environment="alpine",
         description="The Red Bull Ring in Spielberg, a short lap with steep alpine grades."),
    dict(slug="spa", enum="Spa", folder="Spa", title="Spa",
         venue="Circuit de Spa-Francorchamps", country="Belgium",
         lat=50.4372, lon=5.9714, radius=3500, lengths=[7004], turns=19,
         clockwise=True, street=False, shoulder=10.0, base=12.0, straight=15.0,
         names=["Spa", "Grand Prix", "Francorchamps"], crossings=0, environment="forest",
         description="Spa-Francorchamps, from La Source through Eau Rouge and Blanchimont."),
    dict(slug="zandvoort", enum="Zandvoort", folder="Zandvoort", title="Zandvoort",
         venue="Circuit Zandvoort", country="Netherlands",
         lat=52.3888, lon=4.5409, radius=1600, lengths=[4259, 4307], turns=14,
         clockwise=True, street=False, shoulder=7.0, base=12.0, straight=14.0,
         names=["Zandvoort", "Grand Prix"], crossings=0, environment="dunes",
         banks=[("Hugenholtz", 18.0, 3), ("Arie Luyendyk", 18.0, 16)],
         corner_names=["Tarzan", "Gerlach", "Hugenholtz", "Hunserug", "Slotemaker",
                       "Scheivlak", "Masters", "Hugenholtz entrance", "Van Dorp",
                       "Hans Ernst", "Kumho", "Arie Luyendyk entry", "Arie Luyendyk",
                       "Turn 14"],
         description="Circuit Zandvoort in the dunes, with banked Hugenholtz and Arie Luyendyk corners."),
    dict(slug="baku", enum="Baku", folder="Baku", title="Baku",
         venue="Baku City Circuit", country="Azerbaijan",
         lat=40.3725, lon=49.8533, radius=3500, lengths=[6003, 6006], turns=20,
         clockwise=False, street=True, shoulder=4.0, base=12.0, straight=14.0,
         names=["Baku"], crossings=0, environment="city",
         description="Baku City Circuit, from the castle section down the long pit straight."),
    dict(slug="malaysia", enum="Malaysia", folder="Malaysia", title="Malaysia",
         venue="Sepang International Circuit", country="Malaysia",
         lat=2.7606, lon=101.7375, radius=2000, lengths=[5543], turns=15,
         clockwise=True, street=False, shoulder=10.0, base=12.0, straight=16.0,
         names=["Sepang", "Grand Prix"], crossings=0, environment="tropical",
         description="Sepang's Grand Prix circuit, with the two long straights and the back-straight kink."),
    dict(slug="singapore", enum="Singapore", folder="Singapore", title="Singapore",
         venue="Marina Bay Street Circuit", country="Singapore",
         lat=1.2914, lon=103.8640, radius=2200, lengths=[4940, 5065], turns=19,
         clockwise=False, street=True, shoulder=3.5, base=12.0, straight=14.0,
         names=["Marina Bay", "Singapore"], crossings=0, environment="marina",
         description="Marina Bay Street Circuit around the Singapore waterfront."),
    dict(slug="cota", enum="Cota", folder="COTA", title="COTA",
         venue="Circuit of the Americas", country="United States",
         lat=30.1328, lon=-97.6411, radius=2200, lengths=[5513, 5470], turns=20,
         clockwise=False, street=False, shoulder=12.0, base=12.0, straight=16.0,
         names=["Americas", "Grand Prix"], crossings=0, environment="hill-country",
         description="Circuit of the Americas in Austin, anti-clockwise from the uphill first corner."),
    dict(slug="lasvegas", enum="LasVegas", folder="LasVegas", title="Las Vegas",
         venue="Las Vegas Strip Circuit", country="United States",
         lat=36.1147, lon=-115.1728, radius=3000, lengths=[6201, 6120], turns=17,
         clockwise=False, street=True, shoulder=4.0, base=12.0, straight=16.0,
         names=["Las Vegas", "Strip"], crossings=0, environment="strip",
         description="The Las Vegas Strip Circuit."),
    dict(slug="turkey", enum="Turkey", folder="Turkey", title="Turkey",
         venue="Istanbul Park", country="Turkey",
         lat=40.9517, lon=29.4050, radius=2200, lengths=[5338], turns=14,
         clockwise=False, street=False, shoulder=10.0, base=12.0, straight=15.0,
         names=["Istanbul", "Grand Prix"], crossings=0, environment="parkland",
         description="Istanbul Park, an anti-clockwise lap built around the long Turn 8."),
    dict(slug="portimao", enum="Portimao", folder="Portimao", title="Portimao",
         venue="Autodromo Internacional do Algarve", country="Portugal",
         lat=37.2270, lon=-8.6266, radius=1800, lengths=[4653], turns=15,
         clockwise=True, street=False, shoulder=8.0, base=12.0, straight=14.0,
         names=["Algarve", "Portimao", "Grand Prix"], crossings=0, environment="algarve",
         description="Portimao's Algarve circuit, a blind-crest lap over rolling hills."),
    dict(slug="buddh", enum="Buddh", folder="Buddh", title="Buddh",
         venue="Buddh International Circuit", country="India",
         lat=28.3487, lon=77.5331, radius=2200, lengths=[5125, 5141], turns=16,
         clockwise=True, street=False, shoulder=10.0, base=12.0, straight=15.0,
         names=["Buddh", "Grand Prix", "India"], crossings=0, environment="plain",
         description="Buddh International Circuit near Greater Noida."),
    dict(slug="hanoi", enum="Hanoi", folder="Hanoi", title="Hanoi",
         venue="Hanoi Street Circuit", country="Vietnam",
         lat=21.0166, lon=105.7660, radius=2500, lengths=[5607, 5613, 5559], turns=23,
         clockwise=True, street=True, shoulder=4.0, base=12.0, straight=14.0,
         names=["Hanoi"], crossings=0, environment="capital",
         description="The Hanoi street circuit designed for the Vietnamese Grand Prix."),
    dict(slug="hockenheim", enum="Hockenheim", folder="Hockenheim", title="Hockenheim",
         venue="Hockenheimring", country="Germany",
         lat=49.3278, lon=8.5658, radius=2200, lengths=[4574], turns=17,
         clockwise=True, street=False, shoulder=8.0, base=12.0, straight=15.0,
         names=["Hockenheim", "Grand Prix"], crossings=0, environment="forest",
         description="The current Hockenheimring Grand Prix loop, not the old forest circuit."),
]


def log(message: str) -> None:
    print(message, flush=True)


def request(url: str, data: bytes | None = None, limit: int = 14_000_000, timeout: int = 180) -> bytes:
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                chunks = []
                total = 0
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise RuntimeError(f"response exceeded {limit} bytes")
                    chunks.append(chunk)
                return b"".join(chunks)
        except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
            last = error
            time.sleep(2.0 + attempt * 3.0)
    raise RuntimeError(f"request failed: {url[:80]} ({last})")


def overpass(query: str) -> dict:
    payload = urllib.parse.urlencode({"data": query}).encode()
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    last = None
    for endpoint in endpoints:
        try:
            body = request(endpoint, payload, timeout=200)
            return json.loads(body)
        except (RuntimeError, json.JSONDecodeError) as error:
            last = error
            log(f"  overpass fallback after {error}")
            time.sleep(2)
    raise RuntimeError(last)


def haversine(a, b) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH * math.asin(min(1.0, math.sqrt(h)))


def length_of(coords) -> float:
    return sum(haversine(a, b) for a, b in zip(coords, coords[1:]))


def dedupe(coords, minimum=0.35):
    if not coords:
        return []
    output = [coords[0]]
    for point in coords[1:]:
        if haversine(output[-1], point) >= minimum:
            output.append(point)
    return output


def project(lat, lon, origin) -> tuple[float, float]:
    lat0, lon0 = origin
    x = math.radians(lon - lon0) * math.cos(math.radians(lat0)) * EARTH
    y = math.radians(lat - lat0) * EARTH
    return x, y


def heading(a, b) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def wrap(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi


def signed_area(points) -> float:
    area = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        area += a[0] * b[1] - b[0] * a[1]
    return 0.5 * area


def heading_sum(points) -> float:
    total = 0.0
    count = len(points)
    for index in range(count):
        previous = points[index - 1]
        current = points[index]
        nxt = points[(index + 1) % count]
        total += wrap(heading(current, nxt) - heading(previous, current))
    return total


def resample(coords, spacing=4.0):
    coords = dedupe(coords)
    if len(coords) < 3:
        raise RuntimeError("centerline has too few points")
    gap = haversine(coords[0], coords[-1])
    if gap > 140:
        raise RuntimeError("centerline does not close")
    if gap > 25:
        arrive = heading(coords[max(0, len(coords) - 6)], coords[-1])
        depart = heading(coords[0], coords[min(5, len(coords) - 1)])
        chord = heading(coords[-1], coords[0])
        if abs(wrap(arrive - chord)) > math.radians(35) or abs(wrap(depart - chord)) > math.radians(35):
            raise RuntimeError("closure would cut a corner")
    if haversine(coords[0], coords[-1]) < 1.0:
        coords = coords[:-1]
    cumulative = [0.0]
    for a, b in zip(coords, coords[1:]):
        cumulative.append(cumulative[-1] + haversine(a, b))
    cumulative.append(cumulative[-1] + haversine(coords[-1], coords[0]))
    closed = coords + [coords[0]]
    total = cumulative[-1]
    count = max(12, int(round(total / spacing)))
    samples = []
    cursor = 0
    for index in range(count):
        distance = total * index / count
        while cursor + 1 < len(cumulative) and cumulative[cursor + 1] < distance:
            cursor += 1
        span = max(0.001, cumulative[cursor + 1] - cumulative[cursor])
        blend = (distance - cumulative[cursor]) / span
        a = closed[cursor]
        b = closed[cursor + 1]
        samples.append((a[0] + (b[0] - a[0]) * blend, a[1] + (b[1] - a[1]) * blend))
    return samples, total


def crossings(points) -> int:
    count = len(points)
    found = 0
    for i in range(count):
        a = points[i]
        b = points[(i + 1) % count]
        rx, ry = b[0] - a[0], b[1] - a[1]
        for j in range(i + 1, count):
            separation = j - i
            if separation <= 2 or separation >= count - 2:
                continue
            c = points[j]
            d = points[(j + 1) % count]
            sx, sy = d[0] - c[0], d[1] - c[1]
            denominator = rx * sy - ry * sx
            if abs(denominator) < 1e-8:
                continue
            qx, qy = c[0] - a[0], c[1] - a[1]
            t = (qx * sy - qy * sx) / denominator
            u = (qx * ry - qy * rx) / denominator
            if 0.0001 < t < 0.9999 and 0.0001 < u < 0.9999:
                found += 1
    return found


def way_points(element) -> list[tuple[float, float]] | None:
    geometry = element.get("geometry")
    if not geometry or len(geometry) < 2:
        return None
    return [(node["lat"], node["lon"]) for node in geometry]


def rejected(name: str) -> bool:
    text = name.lower()
    return any(word in text for word in ("kart", "drag", "oval", "paddock", "pit", "test layout", "rally"))


def stitch_ordered(segments):
    chain = None
    for segment in segments:
        segment = dedupe(segment)
        if len(segment) < 2:
            continue
        if chain is None:
            chain = segment
            continue
        forward = haversine(chain[-1], segment[0])
        backward = haversine(chain[-1], segment[-1])
        if min(forward, backward) > 80:
            return None
        if backward < forward:
            segment = list(reversed(segment))
        chain.extend(segment[1:])
    if not chain or haversine(chain[0], chain[-1]) > 25:
        return None
    if haversine(chain[0], chain[-1]) < 3:
        chain = chain[:-1]
    return chain if length_of(chain + [chain[0]]) > 800 else None


def stitch_greedy(segments):
    segments = [dedupe(segment) for segment in segments if len(dedupe(segment)) >= 2]
    if not segments:
        return None
    used = [False] * len(segments)
    start = max(range(len(segments)), key=lambda index: length_of(segments[index]))
    used[start] = True
    chain = list(segments[start])
    for _ in range(len(segments)):
        if haversine(chain[0], chain[-1]) < 8 and sum(used) == len(used):
            break
        best = None
        for index, segment in enumerate(segments):
            if used[index]:
                continue
            for flipped in (False, True):
                candidate = list(reversed(segment)) if flipped else segment
                distance = haversine(chain[-1], candidate[0])
                if best is None or distance < best[0]:
                    best = (distance, index, candidate)
        if best is None or best[0] > 80:
            break
        used[best[1]] = True
        chain.extend(best[2][1:])
    if haversine(chain[0], chain[-1]) > 80:
        return None
    if haversine(chain[0], chain[-1]) < 3:
        chain = chain[:-1]
    return chain


def node_key(point):
    return (round(point[0], 5), round(point[1], 5))


def best_cycle(segments, targets):
    edges = []
    for segment in segments:
        segment = dedupe(segment, 0.8)
        if len(segment) < 2:
            continue
        if length_of(segment) < 8:
            continue
        edges.append(segment)
    if len(edges) > 140:
        edges.sort(key=length_of, reverse=True)
        edges = edges[:140]
    endpoints = []
    for segment in edges:
        endpoints.append(segment[0])
        endpoints.append(segment[-1])
    parent = list(range(len(endpoints)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(len(endpoints)):
        for right in range(left + 1, len(endpoints)):
            if haversine(endpoints[left], endpoints[right]) <= 8.0:
                parent[find(right)] = find(left)
    adjacency = {}
    for index, segment in enumerate(edges):
        adjacency.setdefault(find(index * 2), []).append(index)
        adjacency.setdefault(find(index * 2 + 1), []).append(index)
    best = None

    def consider(loop, measured):
        nonlocal best
        published = min(targets, key=lambda value: abs(value - measured))
        error = abs(measured - published) / published
        if best is None or error < best[0]:
            best = (error, loop)

    visits = 0

    def search(start, node, used, chain, measured):
        nonlocal visits
        visits += 1
        if visits > 250000 or measured > max(targets) * 1.25:
            return
        for index in adjacency.get(node, []):
            if used[index]:
                continue
            start_id = find(index * 2)
            end_id = find(index * 2 + 1)
            if node == start_id:
                ordered = edges[index]
                nxt = end_id
            elif node == end_id:
                ordered = list(reversed(edges[index]))
                nxt = start_id
            else:
                continue
            added = length_of(ordered)
            used[index] = True
            if nxt == start and measured + added > min(targets) * 0.7:
                consider(chain + ordered[1:], measured + added)
            elif nxt != start:
                search(start, nxt, used, chain + ordered[1:], measured + added)
            used[index] = False

    for index, segment in enumerate(edges):
        used = [False] * len(edges)
        used[index] = True
        search(find(index * 2), find(index * 2 + 1), used, list(segment), length_of(segment))
        if best and best[0] < 0.012:
            break
    return None if best is None or best[0] > 0.1 else best[1]


def name_of(tags, fallback=""):
    return tags.get("name:en") or tags.get("name") or fallback


def matches_hint(name: str, hints) -> bool:
    text = name.lower()
    return any(hint.lower() in text for hint in hints)


def collect_candidates(payload, spec):
    candidates = []
    ways = []
    for element in payload.get("elements", []):
        if element.get("type") != "way":
            continue
        points = way_points(element)
        if not points:
            continue
        tags = element.get("tags", {})
        if tags.get("highway") != "raceway" and "circuit" not in tags and tags.get("sport") not in ("motor", "motor_racing"):
            continue
        name = name_of(tags)
        ways.append((name, points, tags))
        if rejected(name):
            continue
        if haversine(points[0], points[-1]) < 12 and length_of(points) > 1000:
            candidates.append({"name": name, "coords": points[:-1] if haversine(points[0], points[-1]) < 2 else points, "source": f"way/{element.get('id')}"})

    grouped = {}
    for name, points, tags in ways:
        if not name or rejected(name):
            continue
        grouped.setdefault(name, []).append(points)
    for name, segments in grouped.items():
        stitched = stitch_greedy(segments)
        if stitched:
            candidates.append({"name": name, "coords": stitched, "source": f"name:{name}"})

    for element in payload.get("elements", []):
        if element.get("type") != "relation":
            continue
        tags = element.get("tags", {})
        name = name_of(tags)
        segments = []
        for member in element.get("members", []):
            if member.get("type") != "way" or member.get("role") in ("pit", "pit_lane"):
                continue
            points = way_points(member)
            if points:
                segments.append(points)
        stitched = stitch_ordered(segments) or stitch_greedy(segments)
        if stitched and not rejected(name):
            candidates.append({"name": name or f"relation {element.get('id')}", "coords": stitched, "source": f"relation/{element.get('id')}"})
        cycled = best_cycle(segments, spec["lengths"])
        if cycled:
            candidates.append({"name": name or f"relation {element.get('id')}", "coords": cycled, "source": f"relation-cycle/{element.get('id')}"})
    pool = []
    for name, points, tags in ways:
        if rejected(name):
            continue
        pool.append(points)
    cycled = best_cycle(pool, spec["lengths"])
    if cycled:
        candidates.append({"name": "joined raceway", "coords": cycled, "source": "cycle"})
    return candidates


def rank(candidates, spec):
    ranked = []
    for candidate in candidates:
        try:
            samples, measured = resample(candidate["coords"], 8.0)
        except RuntimeError:
            continue
        published = min(spec["lengths"], key=lambda value: abs(value - measured))
        error = abs(measured - published) / published
        local = [project(lat, lon, samples[0]) for lat, lon in samples]
        cross = crossings(local)
        hint = matches_hint(candidate["name"], spec["names"])
        if cross > spec["crossings"] + 1:
            continue
        if error > 0.12 and not hint:
            continue
        ranked.append({**candidate, "samples": samples, "measured": measured, "published": published, "error": error, "crossings": cross, "hint": hint})
    ranked.sort(key=lambda item: (0 if item["hint"] else 1, item["error"], abs(item["crossings"] - spec["crossings"])))
    return ranked


def rotate_to_start(samples, spec):
    origin = spec.get("start") or (spec["lat"], spec["lon"])
    start = min(range(len(samples)), key=lambda index: haversine(samples[index], origin))
    return samples[start:] + samples[:start]


def orient(samples, spec):
    local = [project(lat, lon, samples[0]) for lat, lon in samples]
    clockwise = heading_sum(local) < 0
    if clockwise != spec["clockwise"]:
        samples = [samples[0]] + list(reversed(samples[1:]))
        clockwise = not clockwise
    return samples, clockwise


def circular_smooth(values, passes):
    current = list(values)
    for _ in range(passes):
        nxt = []
        count = len(current)
        for index in range(count):
            nxt.append((current[index - 1] + 2 * current[index] + current[(index + 1) % count]) / 4)
        current = nxt
    return current


def load_bare_earth(source: Path):
    path = source / "elevation" / "bare_earth.bin"
    if not path.exists():
        return None
    data = path.read_bytes()
    if data[:8] != b"FFDEM1\0\0":
        return None
    origin_x, origin_y, step, cols, rows = struct.unpack_from("<ddfII", data, 8)
    count = cols * rows
    if len(data) != 36 + count * 4:
        raise ValueError("Invalid bare-earth grid size")
    heights = struct.unpack_from(f"<{count}f", data, 36)
    return {"origin_x": origin_x, "origin_y": origin_y, "step": step, "cols": cols, "rows": rows, "heights": heights}


def load_gsi(source: Path, geographic_origin, scale: float):
    path = source / "elevation" / "gsi_ground.bin"
    if not path.exists():
        return None
    data = path.read_bytes()
    if data[:8] != b"FFGSI1\0\0":
        return None
    origin_lat, origin_lon, min_x, min_y, step, cols, rows = struct.unpack_from("<ddfffII", data, 8)
    count = cols * rows
    if len(data) != 44 + count * 4:
        raise ValueError("Invalid GSI ground grid size")
    shift_x, shift_y = project(origin_lat, origin_lon, geographic_origin)
    heights = struct.unpack_from(f"<{count}f", data, 44)
    return {
        "origin_x": (shift_x + min_x) * scale,
        "origin_y": (shift_y + min_y) * scale,
        "step": step * scale,
        "cols": cols,
        "rows": rows,
        "heights": heights,
    }


def sample_bare(grid, x: float, y: float):
    col = (x - grid["origin_x"]) / grid["step"]
    row = (y - grid["origin_y"]) / grid["step"]
    if col < 0 or row < 0 or col >= grid["cols"] - 1 or row >= grid["rows"] - 1:
        return None
    c0, r0 = int(math.floor(col)), int(math.floor(row))
    tx, ty = col - c0, row - r0
    cols = grid["cols"]
    heights = grid["heights"]

    def at(c, r):
        return heights[r * cols + c]

    return (at(c0, r0) * (1 - tx) * (1 - ty) + at(c0 + 1, r0) * tx * (1 - ty)
            + at(c0, r0 + 1) * (1 - tx) * ty + at(c0 + 1, r0 + 1) * tx * ty)


def write_terrain(folder: str, grid, datum: float) -> None:
    import array
    path = CONTENT / folder / "Data"
    path.mkdir(parents=True, exist_ok=True)
    values = array.array("f", (value - datum for value in grid["heights"]))
    blob = bytearray(b"FFTRN1\0\0")
    blob += struct.pack("<ddfII", grid["origin_x"], grid["origin_y"], grid["step"], grid["cols"], grid["rows"])
    blob += values.tobytes()
    (path / "terrain.bin").write_bytes(blob)


def elevations(samples):
    step = max(1, len(samples) // 180)
    picked = list(range(0, len(samples), step))
    if picked[-1] != len(samples) - 1:
        picked.append(len(samples) - 1)
    heights = []
    for batch in range(0, len(picked), 80):
        group = picked[batch:batch + 80]
        lats = ",".join(f"{samples[index][0]:.6f}" for index in group)
        lons = ",".join(f"{samples[index][1]:.6f}" for index in group)
        url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
        payload = json.loads(request(url, limit=1_000_000, timeout=60))
        heights.extend(payload["elevation"])
        time.sleep(0.35)
    raw = list(heights)
    # A short rise and fall is an overpass or roof in a 90 m surface model.
    for index in range(2, len(raw) - 2):
        neighbors = (raw[index - 2] + raw[index - 1] + raw[index + 1] + raw[index + 2]) / 4
        if raw[index] - neighbors > 6:
            raw[index] = neighbors
    smoothed = circular_smooth(raw, 2)
    return picked, heights, smoothed


def interpolate(stations, values, count):
    output = []
    last = len(stations) - 1
    for index in range(count):
        place = last * index / count
        left = min(int(math.floor(place)), last - 1)
        blend = place - left
        output.append(values[left] + (values[left + 1] - values[left]) * blend)
    return output


def crossing_pair(samples_xy):
    count = len(samples_xy)
    pair = None
    best = 1e9
    for i in range(count):
        a = samples_xy[i]
        b = samples_xy[(i + 1) % count]
        rx, ry = b[0] - a[0], b[1] - a[1]
        for j in range(i + 3, count):
            if min((j - i) % count, (i - j) % count) < 30:
                continue
            c = samples_xy[j]
            d = samples_xy[(j + 1) % count]
            sx, sy = d[0] - c[0], d[1] - c[1]
            denominator = rx * sy - ry * sx
            if abs(denominator) < 1e-6:
                continue
            qx, qy = c[0] - a[0], c[1] - a[1]
            t = (qx * sy - qy * sx) / denominator
            u = (qx * ry - qy * rx) / denominator
            if 0 < t < 1 and 0 < u < 1:
                gap = min((j - i) % count, (i - j) % count)
                if gap < best:
                    best = gap
                    pair = (i, j)
    return pair


def suzuka_deck(samples_xy, elevation, stations):
    # The back straight is the bridge over the Degner curves. A ground model
    # falls into that underpass, so the notch on the straighter branch is
    # filled back up to the embankment. The lower road is left untouched.
    pair = crossing_pair(samples_xy)
    if not pair:
        return elevation, None
    first, second = pair

    def straightness(index):
        total = 0.0
        count = len(samples_xy)
        for offset in range(-40, 40):
            before = samples_xy[(index + offset - 8) % count]
            center = samples_xy[(index + offset) % count]
            after = samples_xy[(index + offset + 8) % count]
            one = (center[0] - before[0], center[1] - before[1])
            two = (after[0] - center[0], after[1] - center[1])
            total += abs(math.atan2(one[0] * two[1] - one[1] * two[0], one[0] * two[0] + one[1] * two[1]))
        return total

    bridge, under = (first, second) if straightness(first) < straightness(second) else (second, first)
    length = stations[-1] + (stations[1] - stations[0] if len(stations) > 1 else 1)

    def apart(a, b):
        delta = abs(a - b)
        return min(delta, length - delta)

    wings = [elevation[index] for index, station in enumerate(stations)
             if 40 < apart(station, stations[bridge]) < 100]
    if not wings:
        return elevation, None
    wings.sort()
    wing = wings[len(wings) // 2]
    notch = [index for index, station in enumerate(stations)
             if apart(station, stations[bridge]) < 80 and elevation[index] < wing - 2.5]
    if notch:
        left = max(0, min(notch) - 1)
        right = min(len(elevation) - 1, max(notch) + 1)
        span = max(1, right - left)
        for index in range(left, right + 1):
            blend = (index - left) / span
            elevation[index] = elevation[left] + (elevation[right] - elevation[left]) * blend
        bridge = min(range(left, right + 1), key=lambda index: apart(stations[index], stations[bridge]))
    clearance = elevation[bridge] - elevation[under]
    if clearance < 5.6 or clearance > 7.4:
        target = 6.2
        deficit = target - clearance
        for index, station in enumerate(stations):
            delta = apart(station, stations[bridge])
            if delta < 50:
                blend = 0.5 * (1 + math.cos(math.pi * delta / 50))
                elevation[index] += deficit * blend
        clearance = elevation[bridge] - elevation[under]
    return elevation, {
        "bridge_station_m": stations[bridge],
        "underpass_station_m": stations[under],
        "modeled_clearance_m": round(clearance, 3),
        "bridge_branch": "back straight",
        "underpass_branch": "Degner",
    }


def fill_notches(elevation, stations, depth=2.5, reach=12):
    # A narrow drop below the surrounding road is a culvert or underpass in the
    # ground model, not the racing surface. Raise only those samples.
    count = len(elevation)
    length = stations[-1] + (stations[1] - stations[0] if len(stations) > 1 else 1.0)
    for _ in range(3):
        updated = elevation[:]
        for index in range(count):
            if min(stations[index], length - stations[index]) < 80:
                continue
            left = (index - reach) % count
            right = (index + reach) % count
            if stations[right] <= stations[left]:
                continue
            blend = (stations[index] - stations[left]) / (stations[right] - stations[left])
            chord = elevation[left] + (elevation[right] - elevation[left]) * blend
            if elevation[index] < chord - depth:
                updated[index] = chord
        elevation[:] = updated


def flatten_spikes(elevation, limit=0.35):
    # One-sample holes make the road quads overlap and the contact surface
    # disagree with the centreline. A steady grade is left alone.
    count = len(elevation)
    for _ in range(8):
        updated = elevation[:]
        changed = False
        for index in range(count):
            chord = (elevation[index - 1] + elevation[(index + 1) % count]) * 0.5
            if elevation[index] < chord - limit:
                updated[index] = chord
                changed = True
        elevation[:] = updated
        if not changed:
            break


def nearest_shoulder(origin_xy, tangent, barriers, default, half_width):
    left = right = None
    tx, ty = tangent
    scale = math.hypot(tx, ty) or 1
    tx, ty = tx / scale, ty / scale
    ox, oy = origin_xy
    for bx, by in barriers:
        dx, dy = bx - ox, by - oy
        distance = math.hypot(dx, dy)
        if distance < half_width + 0.8 or distance > 28:
            continue
        side = tx * dy - ty * dx
        shoulder = distance - half_width - 0.85
        if shoulder < 1.2 or shoulder > 24:
            continue
        if side >= 0:
            left = shoulder if left is None else min(left, shoulder)
        else:
            right = shoulder if right is None else min(right, shoulder)
    return left if left is not None else default, right if right is not None else default


def smooth_series(values, window):
    output = []
    count = len(values)
    for index in range(count):
        bucket = []
        for offset in range(-window, window + 1):
            bucket.append(values[(index + offset) % count])
        bucket.sort()
        output.append(bucket[len(bucket) // 2])
    return output


def suzuka_turns(local, stations, target):
    count = len(local)
    window = max(3, int(0.012 * count))
    scores = []
    for index in range(count):
        before = local[(index - window) % count]
        center = local[index]
        after = local[(index + window) % count]
        first = (center[0] - before[0], center[1] - before[1])
        second = (after[0] - center[0], after[1] - center[1])
        turn = math.atan2(first[0] * second[1] - first[1] * second[0], first[0] * second[0] + first[1] * second[1])
        scores.append(turn)
    peaks = []
    minimum = max(8, count // 100)
    for index, turn in enumerate(scores):
        if abs(turn) < 0.18:
            continue
        if abs(turn) <= abs(scores[(index - 1) % count]) or abs(turn) <= abs(scores[(index + 1) % count]):
            continue
        if peaks and min(abs(index - peaks[-1][0]), count - abs(index - peaks[-1][0])) < minimum:
            if abs(turn) > abs(peaks[-1][1]):
                peaks[-1] = (index, turn)
            continue
        peaks.append((index, turn))
    kept = []
    for index, turn in peaks:
        if kept:
            previous = kept[-1]
            gap = min(abs(index - previous[0]), count - abs(index - previous[0])) * (target / count)
            if turn * previous[1] > 0 and abs(turn) < 0.45 and gap < 400:
                if abs(turn) > abs(previous[1]):
                    kept[-1] = (index, turn)
                continue
        kept.append((index, turn))
    names = ["Turn 1", "Turn 2", "Turn 3", "Turn 4", "Turn 5", "Turn 6",
             "Dunlop", "Degner 1", "Degner 2", "110R", "Hairpin", "200R",
             "Spoon", "Spoon Curve", "130R", "Casio", "Casio Triangle", "Final"]
    if len(kept) != len(names):
        found = ", ".join(f"{stations[index]:.0f}:{'L' if turn > 0 else 'R'}" for index, turn in kept)
        raise RuntimeError(f"Suzuka corner match found {len(kept)} peaks ({found})")
    turns = []
    for (index, turn), name in zip(kept, names):
        turns.append({
            "name": name,
            "fraction": stations[index] / target,
            "direction": 1 if turn > 0 else -1,
            "station": stations[index],
        })
    return turns


def quintic_width(stations, controls):
    controls = sorted(controls)
    width = []
    for station in stations:
        index = max(0, min(len(controls) - 2, next((item - 1 for item, control in enumerate(controls) if control[0] > station), len(controls) - 2)))
        start, end = controls[index], controls[index + 1]
        blend = max(0.0, min(1.0, (station - start[0]) / max(0.001, end[0] - start[0])))
        blend = blend * blend * blend * (10 + blend * (-15 + 6 * blend))
        width.append((station, start[1] + (end[1] - start[1]) * blend))
    return width


def japan_building_height(name):
    named = {
        "V2": 24.0, "VIP": 22.0, "V1": 16.0, "Q2": 14.0, "B2": 14.0, "A1": 12.0,
        "Q1": 10.0, "B1": 10.0, "C": 10.0, "G": 9.0, "S": 10.0,
        "ピットビル": 12.0, "西コントロールタワー": 30.0, "センターハウス": 16.0,
    }
    return named.get(name or "")


def apexes(points):
    count = len(points)
    window = max(2, int(0.018 * count))
    scores = []
    for index in range(count):
        before = points[(index - window) % count]
        center = points[index]
        after = points[(index + window) % count]
        first = (center[0] - before[0], center[1] - before[1])
        second = (after[0] - center[0], after[1] - center[1])
        cross = first[0] * second[1] - first[1] * second[0]
        dot = first[0] * second[0] + first[1] * second[1]
        turn = math.atan2(cross, dot)
        scores.append(turn)
    found = []
    minimum = max(8, count // 80)
    for index, turn in enumerate(scores):
        if abs(turn) < 0.22:
            continue
        if abs(turn) < abs(scores[(index - 1) % count]) or abs(turn) < abs(scores[(index + 1) % count]):
            continue
        if found and min(abs(index - found[-1][0]), count - abs(index - found[-1][0])) < minimum:
            if abs(turn) > abs(found[-1][1]):
                found[-1] = (index, turn)
            continue
        found.append((index, turn))
    return found


def emit_points(kind, rows):
    return "constexpr " + kind + "[] = {\n" + ",\n".join(rows) + "\n};\n"


def write_survey(spec, xy, elevation, width, bank, runoff, turns, shoulders):
    slug = spec["slug"]
    prefix = spec["enum"]
    rows_xy = [f"    {{{x:.4f}f, {y:.4f}f}}" for x, y in xy]
    rows_z = [f"    {{{distance:.3f}f, {height:.4f}f}}" for distance, height in elevation]
    rows_w = [f"    {{{distance:.3f}f, {value:.3f}f}}" for distance, value in width]
    rows_b = [f"    {{{distance:.3f}f, {value:.3f}f}}" for distance, value in bank]
    rows_r = []
    for zone in runoff:
        surface = f"TrackRunoffSurface::{zone['surface']}"
        rows_r.append(f"    {{{zone['start']:.2f}f, {zone['end']:.2f}f, {zone['side']}, {surface}, {zone['width']:.2f}f}}")
    if not rows_r:
        rows_r.append("    {0.0f, 0.0f, 0, TrackRunoffSurface::Grass, 0.0f}")
    rows_t = []
    for turn in turns:
        direction = "Left" if turn["direction"] > 0 else "Right"
        rows_t.append(f'    {{"{turn["name"]}", {turn["fraction"]:.5f}f, TrackTurnDirection::{direction}}}')
    rows_s = [f"    {{{distance:.3f}f, {left:.3f}f, {right:.3f}f}}" for distance, left, right in shoulders]
    text = "\n".join([
        f"// Generated by tools/build_circuits.py. Do not edit by hand.",
        emit_points(f"TrackControlPoint k{prefix}Centerline", rows_xy).rstrip(),
        emit_points(f"TrackElevationPoint k{prefix}Elevation", rows_z).rstrip(),
        emit_points(f"TrackWidthPoint k{prefix}Width", rows_w).rstrip(),
        emit_points(f"TrackBankPoint k{prefix}Bank", rows_b).rstrip(),
        emit_points(f"TrackRunoffZone k{prefix}Runoff", rows_r).rstrip(),
        emit_points(f"TrackTurnExpectation k{prefix}Turns", rows_t).rstrip(),
        emit_points(f"TrackShoulderPoint k{prefix}Shoulder", rows_s).rstrip(),
        "",
    ])
    (TRACK_DATA / f"{slug}_survey.inc").write_text(text)


def write_landmarks(folder, wheels):
    blob = bytearray(b"FFLMK1\0\0")
    blob += struct.pack("<I", len(wheels))
    for x, y, radius, hub in wheels:
        blob += struct.pack("<Iffff", 1, x, y, radius, hub)
    path = CONTENT / folder / "Data"
    path.mkdir(parents=True, exist_ok=True)
    (path / "landmarks.bin").write_bytes(blob)


def write_buildings(folder, footprints):
    import struct
    blob = bytearray(b"FFBLD1\0\0")
    blob += struct.pack("<I", len(footprints))
    for height, ring in footprints:
        blob += struct.pack("<I", len(ring))
        blob += struct.pack("<f", height)
        for x, y in ring:
            blob += struct.pack("<ff", x, y)
    path = CONTENT / folder / "Data"
    path.mkdir(parents=True, exist_ok=True)
    (path / "buildings.bin").write_bytes(blob)


def simplify_ring(ring, limit=16):
    ring = dedupe([(point[0], point[1]) for point in ring], 1.0)
    if len(ring) <= limit:
        return ring
    # Keep every nth vertex, always retaining the first.
    stride = math.ceil(len(ring) / limit)
    reduced = ring[::stride]
    return reduced[:limit]


def footprint_area(ring):
    return abs(signed_area(ring))


def lasvegas_alignment(samples):
    recipe = json.loads((SOURCES / "lasvegas/layout-corrections.json").read_text())
    origin = samples[0]
    local = [project(lat, lon, origin) for lat, lon in samples]
    stations = [0.0]
    for a, b in zip(local, local[1:]):
        stations.append(stations[-1] + math.dist(a, b))
    for correction in reversed(recipe["corrections"]):
        begin, end = correction["replace_original_station_m"]
        first = min(range(len(stations)), key=lambda i: abs(stations[i] - begin))
        last = min(range(len(stations)), key=lambda i: abs(stations[i] - end))
        replacement = []
        for controls in correction["beziers"]:
            steps = max(8, math.ceil(sum(math.dist(a, b) for a, b in zip(controls, controls[1:]))))
            for step in range(steps):
                t = step / steps
                weights = [(1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3]
                replacement.append(tuple(sum(p[axis] * w for p, w in zip(controls, weights)) for axis in (0, 1)))
        replacement.append(tuple(correction["beziers"][-1][-1]))
        local[first:last + 1] = replacement
    def geographic(points):
        return [(origin[0] + math.degrees(y / EARTH),
                 origin[1] + math.degrees(x / (EARTH * math.cos(math.radians(origin[0]))))) for x, y in points]
    regular, _ = resample(geographic(local), 4.0)
    local = [project(lat, lon, origin) for lat, lon in regular]
    smooth = [circular_smooth([p[axis] for p in local], 24) for axis in (0, 1)]
    tight = [circular_smooth([p[axis] for p in local], 2) for axis in (0, 1)]
    # The short, already authored Harmon reversals need a smaller spatial filter.
    filtered = []
    for i, (x, y) in enumerate(local):
        distance = math.hypot(x - 35, y + 710)
        t = max(0.0, min(1.0, (distance - 135) / 75))
        blend = t*t*t*(10 + t*(-15 + 6*t))
        filtered.append(tuple(tight[axis][i] * (1-blend) + smooth[axis][i] * blend for axis in (0, 1)))
    # Filtering the closed loop can move the initial sample by millimetres.
    offset = filtered[0]
    filtered = [(x-offset[0], y-offset[1]) for x, y in filtered]
    return geographic(filtered)


def build(spec, refresh=False):
    source = SOURCES / spec["slug"]
    source.mkdir(parents=True, exist_ok=True)
    cache = source / "circuit.osm.json.gz"
    barrier_cache = source / "barriers.osm.json.gz"
    query = f'''
[out:json][timeout:180];
(
  way["highway"="raceway"](around:{spec["radius"]},{spec["lat"]},{spec["lon"]});
  relation["type"="circuit"](around:{spec["radius"]},{spec["lat"]},{spec["lon"]});
  relation["route"="raceway"](around:{spec["radius"]},{spec["lat"]},{spec["lon"]});
);
out geom;
'''
    if cache.exists() and not refresh:
        payload = json.loads(gzip.decompress(cache.read_bytes()))
        log(f"{spec['slug']}: using cached raceway extract")
    else:
        log(f"{spec['slug']}: downloading raceways")
        payload = overpass(query)
        cache.write_bytes(gzip.compress(json.dumps(payload).encode()))
        time.sleep(1.2)
    ranked = rank(collect_candidates(payload, spec), spec)
    if not ranked or ranked[0]["error"] > 0.08:
        preview = ", ".join(f"{item['name']} {item['measured']:.0f}m/{item['error']:.1%}" for item in ranked[:8])
        raise RuntimeError(f"no layout within 8% of {spec['lengths']}. candidates: {preview or 'none'}")
    chosen = ranked[0]
    samples, clockwise = orient(rotate_to_start(chosen["samples"], spec), spec)
    if spec["slug"] == "lasvegas":
        samples = lasvegas_alignment(samples)
    samples, measured = resample(samples, 4.0)
    local = [project(lat, lon, samples[0]) for lat, lon in samples]
    area = signed_area(local)
    heading_direction = (area < 0) != clockwise
    published = min(spec["lengths"], key=lambda value: abs(value - measured))
    length_error = abs(measured - published) / published
    scale = 1.0
    if length_error <= 0.015:
        scale = published / measured
        local = [(x * scale, y * scale) for x, y in local]
        target = float(published)
    else:
        target = measured
    chosen["error"] = length_error
    chosen["published"] = published
    count = len(local)
    spacing = target / count
    stations = [index * spacing for index in range(count)]
    bare = load_gsi(source, samples[0], scale) if spec["slug"] == "japan" else None
    if bare is None:
        bare = load_bare_earth(source)
    elevation_cache = source / "elevation_samples.json"
    if bare is not None:
        sampled = []
        for x, y in local:
            value = sample_bare(bare, x, y)
            if value is None:
                raise RuntimeError(f"{spec['slug']}: bare-earth grid does not cover the centreline")
            sampled.append(value)
        relative = circular_smooth(sampled, 74 if spec["slug"] == "lasvegas" else 2)
        picked = list(range(count))
        log(f"{spec['slug']}: ground DEM {min(sampled):.1f}..{max(sampled):.1f} m")
    elif elevation_cache.exists() and not refresh:
        saved = json.loads(elevation_cache.read_text())
        picked, raw, smoothed = saved["index"], saved["raw"], saved["smoothed"]
        relative = interpolate(picked, smoothed, count)
    else:
        log(f"{spec['slug']}: sampling Copernicus GLO-90")
        picked, raw, smoothed = elevations(samples)
        elevation_cache.write_text(json.dumps({"index": picked, "raw": raw, "smoothed": smoothed}))
        relative = interpolate(picked, smoothed, count)
    deck_note = None
    if spec.get("deck"):
        relative, deck_note = suzuka_deck(local, relative, stations)
    if spec["slug"] == "japan":
        fill_notches(relative, stations)
        flatten_spikes(relative)
    seam = min(40.0, target * 0.02)
    for index, station in enumerate(stations):
        remaining = target - station
        if 0 < remaining < seam:
            blend = remaining / seam
            relative[index] = relative[index] * blend + relative[0] * (1.0 - blend)
    datum = min(relative)
    relative = [value - datum for value in relative]
    relief = max(relative) - min(relative)
    if bare is not None:
        write_terrain(spec["folder"], bare, datum)

    # Width follows the local heading change. Straights use the wider figure.
    width = []
    window = max(3, int(70 / spacing))
    for index in range(count):
        before = local[(index - window) % count]
        after = local[(index + window) % count]
        center = local[index]
        turn = abs(wrap(heading(center, after) - heading(before, center)))
        blend = min(1.0, turn / 0.55)
        width.append((stations[index], spec["straight"] + (spec["base"] - spec["straight"]) * blend))
    if spec["slug"] == "lasvegas":
        recipe = json.loads((source / "layout-corrections.json").read_text())
        anchor_stations = {}
        for anchor in recipe["turns"]:
            point = tuple(value * scale for value in anchor["near_source_xy_m"])
            index = min(range(count), key=lambda i: math.dist(local[i], point))
            anchor_stations[anchor["number"]] = stations[index]
        controls = [(0., 14.5), (anchor_stations[14]-100, 14.5),
                    (anchor_stations[14], 12.5), (anchor_stations[16], 12.5),
                    (anchor_stations[16]+90, 13.5), (anchor_stations[17], 15.),
                    (1815., 15.), (anchor_stations[1], 13.), (anchor_stations[4], 13.),
                    (anchor_stations[5]-100, 13.), (anchor_stations[5], 12.),
                    (anchor_stations[6], 13.), (anchor_stations[7], 12.),
                    (anchor_stations[9], 12.), (anchor_stations[10], 13.5),
                    (anchor_stations[11], 13.5), (anchor_stations[12], 12.5),
                    (anchor_stations[12]+90, 14.5), (target, 14.5)]
        controls.sort()
        width = []
        for station in stations:
            i = max(0, min(len(controls)-2, next((j-1 for j, c in enumerate(controls) if c[0] > station), len(controls)-2)))
            a, b = controls[i], controls[i+1]
            t = max(0., min(1., (station-a[0]) / max(.001, b[0]-a[0])))
            blend = t*t*t*(10 + t*(-15 + 6*t))
            width.append((station, a[1] + (b[1]-a[1])*blend))
    width.append((target, width[0][1]))

    detected = apexes(local)
    names = spec.get("corner_names") or [f"Turn {index + 1}" for index in range(len(detected))]
    if len(names) != len(detected):
        names = [f"Turn {index + 1}" for index in range(len(detected))]
    turns = []
    for (index, turn), name in zip(detected, names):
        turns.append({"name": name, "fraction": stations[index] / target, "direction": 1 if turn > 0 else -1, "station": stations[index]})
    if spec["slug"] == "japan":
        turns = suzuka_turns(local, stations, target)
        by_name = {turn["name"]: turn["station"] for turn in turns}
        width = quintic_width(stations, [
            (0.0, 15.0), (by_name["Turn 1"] - 80, 15.0), (by_name["Turn 1"], 13.0),
            (by_name["Turn 6"], 12.0), (by_name["Dunlop"], 13.5), (by_name["Degner 1"], 12.0),
            (by_name["Hairpin"], 12.0), (by_name["200R"], 14.0), (by_name["Spoon"], 13.0),
            (by_name["Spoon Curve"] + 80, 15.0), (by_name["130R"] - 40, 15.0), (by_name["130R"], 14.0),
            (by_name["Casio"], 12.0), (by_name["Final"] + 80, 14.5), (target, 15.0),
        ])
        width.append((target, width[0][1]))
    if spec["slug"] == "lasvegas":
        recipe = json.loads((source / "layout-corrections.json").read_text())
        turns = []
        for anchor in recipe["turns"]:
            point = tuple(value * scale for value in anchor["near_source_xy_m"])
            index = min(range(count), key=lambda i: math.dist(local[i], point))
            turns.append({"name": f"Turn {anchor['number']}", "fraction": stations[index] / target,
                          "direction": anchor["direction"], "station": stations[index]})
        turns.sort(key=lambda turn: turn["station"])
    bank = [(0.0, 0.0)]
    bank_notes = []
    for bank_spec in spec.get("banks", []):
        label, angle = bank_spec[0], bank_spec[1]
        fallback = bank_spec[2] if len(bank_spec) > 2 else None
        match = next((turn for turn in turns if label.lower() in turn["name"].lower()), None)
        if match is None and fallback and 1 <= fallback <= len(turns):
            match = turns[fallback - 1]
            label = f"{label} (detected apex {fallback})"
        if not match:
            bank_notes.append(f"{label} not anchored; count was {len(detected)}")
            continue
        sign = -1 if match["direction"] > 0 else 1
        station = match["station"]
        bank.append((max(0.0, station - 80), 0.0))
        bank.append((max(0.0, station - 25), sign * angle))
        bank.append((station, sign * angle))
        bank.append((min(target, station + 25), sign * angle))
        bank.append((min(target, station + 80), 0.0))
        bank_notes.append(f"{label} {angle:.0f} deg at {station:.0f} m, outside raised")
    bank.append((target, 0.0))
    bank.sort()

    runoff = []
    if spec["slug"] == "japan":
        # Driver's left is +1. Gravel sits on the outside of the slow corners.
        for turn in turns:
            if turn["name"] not in {"Turn 2", "Degner 1", "Degner 2", "Hairpin", "Spoon", "Spoon Curve", "Casio", "Casio Triangle"}:
                continue
            side = 1 if turn["direction"] > 0 else -1
            runoff.append({
                "start": max(0.0, turn["station"] - 55),
                "end": min(target, turn["station"] + 40),
                "side": side,
                "surface": "Gravel",
                "width": 14.0 if turn["name"] == "Hairpin" else 11.0,
            })
    else:
        for turn in turns:
            if abs(turn["direction"]) != 1:
                continue
            # Slow corners get the loose surface on the outside.
            outside = 1 if turn["direction"] < 0 else -1
            start = max(0.0, turn["station"] - 70)
            end = min(target, turn["station"] + 45)
            if end - start < 20:
                continue
            surface = "Asphalt" if spec["street"] else "Gravel"
            runoff.append({"start": start, "end": end, "side": outside, "surface": surface, "width": spec["shoulder"]})

    barriers = []
    if barrier_cache.exists() and not refresh:
        barrier_payload = json.loads(gzip.decompress(barrier_cache.read_bytes()))
    else:
        south = min(lat for lat, _ in samples) - 0.0012
        north = max(lat for lat, _ in samples) + 0.0012
        west = min(lon for _, lon in samples) - 0.0012
        east = max(lon for _, lon in samples) + 0.0012
        barrier_query = f'''
[out:json][timeout:120];
way["barrier"~"wall|guard_rail|fence|retaining_wall"]({south},{west},{north},{east});
out geom;
'''
        try:
            log(f"{spec['slug']}: downloading barriers")
            barrier_payload = overpass(barrier_query)
            barrier_cache.write_bytes(gzip.compress(json.dumps(barrier_payload).encode()))
        except RuntimeError as error:
            log(f"{spec['slug']}: barrier query skipped ({error})")
            barrier_payload = {"elements": []}
        time.sleep(1.0)
    origin = samples[0]
    scale_xy = scale
    for element in barrier_payload.get("elements", []):
        points = way_points(element)
        if not points:
            continue
        for lat, lon in points[::2]:
            bx, by = project(lat, lon, origin)
            barriers.append((bx * scale_xy, by * scale_xy))
    left, right = [], []
    for index, (x, y) in enumerate(local):
        previous = local[(index - 1) % count]
        nxt = local[(index + 1) % count]
        tangent = (nxt[0] - previous[0], nxt[1] - previous[1])
        half = width[index][1] * 0.5
        a, b = nearest_shoulder((x, y), tangent, barriers, spec["shoulder"], half)
        left.append(a)
        right.append(b)
    left = smooth_series(left, 6)
    right = smooth_series(right, 6)
    if spec["slug"] == "japan":
        for turn in turns:
            if turn["name"] not in {"Turn 2", "Degner 1", "Degner 2", "Hairpin", "Spoon", "Spoon Curve", "Casio", "Casio Triangle", "130R"}:
                continue
            extra = 16.0 if turn["name"] == "Hairpin" else (12.0 if turn["name"] != "130R" else 9.0)
            for index, station in enumerate(stations):
                gap = min(abs(station - turn["station"]), target - abs(station - turn["station"]))
                if gap > 50:
                    continue
                if turn["direction"] > 0:
                    left[index] = max(left[index], extra)
                else:
                    right[index] = max(right[index], extra)
    if spec["slug"] == "lasvegas":
        left = right = [.10] * count
        runoff = [{"start": 0., "end": target, "side": 0, "surface": "Asphalt", "width": 0.}]
    shoulders = [(stations[index], left[index], right[index]) for index in range(0, count, 2)]
    shoulders.append((target, shoulders[0][1], shoulders[0][2]))

    # Buildings inside a narrow corridor, not the whole city.
    building_cache = source / "buildings.osm.json.gz"
    if building_cache.exists() and not refresh:
        building_payload = json.loads(gzip.decompress(building_cache.read_bytes()))
    else:
        south = min(lat for lat, _ in samples) - 0.0008
        north = max(lat for lat, _ in samples) + 0.0008
        west = min(lon for _, lon in samples) - 0.0008
        east = max(lon for _, lon in samples) + 0.0008
        building_query = f'''
[out:json][timeout:150];
way["building"]({south},{west},{north},{east});
out geom;
'''
        try:
            log(f"{spec['slug']}: downloading building footprints")
            building_payload = overpass(building_query)
            building_cache.write_bytes(gzip.compress(json.dumps(building_payload).encode()))
        except RuntimeError as error:
            log(f"{spec['slug']}: buildings skipped ({error})")
            building_payload = {"elements": []}
        time.sleep(1.0)
    footprints = []
    for element in building_payload.get("elements", []):
        points = way_points(element)
        if not points or len(points) < 4:
            continue
        ring = [(project(lat, lon, origin)[0] * scale_xy, project(lat, lon, origin)[1] * scale_xy) for lat, lon in points]
        if haversine(points[0], points[-1]) < 3:
            ring = ring[:-1]
        ring = simplify_ring(ring)
        if len(ring) < 3 or footprint_area(ring) < 30 or footprint_area(ring) > 12000:
            continue
        centroid = (sum(point[0] for point in ring) / len(ring), sum(point[1] for point in ring) / len(ring))
        distance = min(math.hypot(centroid[0] - x, centroid[1] - y) for x, y in local[::3])
        tags = element.get("tags", {})
        named_height = japan_building_height(tags.get("name")) if spec["slug"] == "japan" else None
        near_limit, far_limit = (8, 130) if named_height else (14, 85)
        if distance < near_limit or distance > far_limit:
            continue
        height = None
        if "height" in tags:
            digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in tags["height"]).split()
            if digits:
                height = float(digits[0])
        elif "building:levels" in tags:
            try:
                height = float(tags["building:levels"]) * 3.2
            except ValueError:
                height = None
        if named_height:
            height = named_height
        if height is None:
            kind = tags.get("building", "")
            height = 14.0 if kind in ("grandstand", "stadium", "hangar") else (11.0 if spec["street"] else 7.0)
        height = min(70.0, max(3.0, height))
        footprints.append((distance, height, ring))
    footprints.sort(key=lambda item: item[0])
    footprints = [(height, ring) for _, height, ring in footprints[:900]]
    write_buildings(spec["folder"], footprints)
    if spec["slug"] == "japan":
        wheel_x, wheel_y = project(34.845979, 136.538821, origin)
        write_landmarks(spec["folder"], [(wheel_x * scale_xy, wheel_y * scale_xy, 24.0, 27.0)])
    write_survey(spec, local, list(zip(stations, relative)) + [(target, relative[0])], width, bank, runoff, turns, shoulders)

    aspect_x = [point[0] for point in local]
    aspect_y = [point[1] for point in local]
    aspect = (max(aspect_x) - min(aspect_x)) / max(0.001, max(aspect_y) - min(aspect_y))
    cross = crossings(local)
    osm_hash = hashlib.sha256(cache.read_bytes()).hexdigest()
    record = {
        "slug": spec["slug"],
        "layout": chosen["name"],
        "source": chosen["source"],
        "measured_m": round(measured, 3),
        "published_m": published,
        "published_candidates_m": spec["lengths"],
        "length_error": round(chosen["error"], 5),
        "uniform_scale": round(scale, 6),
        "target_m": target,
        "clockwise": clockwise,
        "heading_direction_test": heading_direction,
        "crossings": cross,
        "aspect": round(aspect, 5),
        "relief_m": round(relief, 3),
        "elevation_datum_removed_m": round(datum, 3),
        "samples": count,
        "turns_detected": len(turns) if spec["slug"] == "japan" else len(detected),
        "turns_published": spec["turns"],
        "buildings": len(footprints),
        "barrier_vertices": len(barriers),
        "deck": deck_note,
        "banks": bank_notes,
        "osm_sha256": osm_hash,
    }
    if spec["slug"] in {"lasvegas", "japan"}:
        record["turns_registered"] = len(turns)
    (source / "reconstruction.json").write_text(json.dumps(record, indent=2) + "\n")
    provenance = {
        "circuit": spec["venue"],
        "layout": chosen["name"],
        "layout_year_intent": "Current Grand Prix layout where the circuit is live; last Formula 1 layout where it is not. The mapped OpenStreetMap loop was selected by published length.",
        "retrieved": RETRIEVED,
        "origin": {"latitude": samples[0][0], "longitude": samples[0][1], "meaning": "Local source origin at the point on the loop nearest the venue coordinate, after rotation to the start."},
        "projection": "Local tangent plane, x east metres, y north metres. Vertical values are relative to the lowest smoothed sample on the lap.",
        "route": {
            "provider": "OpenStreetMap contributors",
            "licence": "ODbL 1.0",
            "licence_url": "https://opendatacommons.org/licenses/odbl/1-0/",
            "query_radius_m": spec["radius"],
            "file": "circuit.osm.json.gz",
            "sha256": osm_hash,
            "chosen": chosen["source"],
            "measured_plan_m": round(measured, 3),
            "published_m": published,
            "uniform_scale": round(scale, 6),
            "scale_rule": "Applied only when the mapped plan was within 1.5% of a published length. Larger gaps keep the mapped length.",
        },
        "elevation": ({
            "provider": "Geospatial Information Authority of Japan",
            "dataset": "5 m mesh DEM tiles, dem5a at zoom 15",
            "dataset_note": "Ground elevations sampled on the centreline and retained on an 8 m terrain grid. The back-straight notch, where the mesh sees the Degner underpass, is filled to the embankment. This is a processed racing profile, not a GSI product and not a construction survey.",
            "licence": "https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html",
            "service": "https://cyberjapandata.gsi.go.jp/xyz/dem5a/{z}/{x}/{y}.txt",
            "retrieved": "2026-11-07",
            "sample_spacing_m": 4.0,
            "smoothing": "Two circular binomial passes on the 4 m centreline samples. The bridge notch is replaced by the embankment chord. Other drops of more than 2.5 m inside a 48 m window, at the Dunlop crest and before the final chicane, are raised to that chord because they are culverts in the ground model.",
            "relative_datum": "Heights stored after subtracting the lap minimum.",
            "removed_minimum_m": round(datum, 3),
            "relief_m": round(relief, 3),
            "uncertainty_m": 2,
            "file": "elevation/gsi_ground.bin",
            "deck": deck_note,
            "published_relief_crosscheck_m": 40.4,
        } if spec["slug"] == "japan" else {
            "provider": "USGS 3D Elevation Program",
            "dataset": "NV_ClarkCounty_B22 1 m bare-earth DEM",
            "dataset_note": "Lidar bare earth, 1 m, sampled on the centreline and on a 4 m terrain grid. WGS84 was projected to NAD83 UTM zone 11; that datum shift is about a metre.",
            "licence": "Public domain",
            "source_url": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/NV_ClarkCounty_B22/TIFF/USGS_1M_11_x66y400_NV_ClarkCounty_B22.tif",
            "retrieved": "2026-11-05",
            "publication": "2023-10-30",
            "sample_spacing_m": 4.0,
            "smoothing": "74 circular binomial passes on the 4 m samples (24 m standard deviation). Filters short pre-construction ground breaks in the future paddock; broad surveyed grade is retained. This is an estimated racing profile, not a measured post-construction deck.",
            "relative_datum": "Heights stored after subtracting the lap minimum.",
            "removed_minimum_m": round(datum, 3),
            "relief_m": round(relief, 3),
            "uncertainty_m": 1,
            "file": "elevation/bare_earth.bin",
            "deck": deck_note,
        } if bare is not None else {
            "provider": "Open-Meteo Elevation API",
            "dataset": "Copernicus DEM GLO-90",
            "dataset_note": "Surface model, about 90 m, includes roofs and canopy. Not a bare-earth racing survey.",
            "licence": "Copernicus DEM, see https://registry.opendata.aws/copernicus-dem/",
            "retrieved": RETRIEVED,
            "sample_spacing_m": round(target / max(1, len(picked)), 1),
            "smoothing": "Two circular binomial passes on the coarse samples, then linear interpolation onto the 4 m centreline. Isolated samples more than 6 m above their neighbours were treated as overpasses or roofs.",
            "relative_datum": "Heights stored after subtracting the lap minimum.",
            "removed_minimum_m": round(datum, 3),
            "relief_m": round(relief, 3),
            "uncertainty_m": 8 if spec["street"] else 5,
            "deck": deck_note,
        }),
        "width": {
            "base_m": spec["base"],
            "straight_m": spec["straight"],
            "method": "Authored from typical Grade 1 asphalt width, wider on low-curvature sections. Not a traced white-line survey.",
        },
        "shoulders": {
            "default_m": spec["shoulder"],
            "method": "Nearest OSM barrier vertex on each side, median-smoothed, clamped to 1.2-24 m outside the kerb. Missing sides keep the venue default.",
            "barrier_file": "barriers.osm.json.gz" if barrier_cache.exists() else None,
        },
        "banking": bank_notes or "Neutral. No published camber was anchored to a detected corner.",
        "buildings": {
            "count": len(footprints),
            "method": "OSM footprints within 14-85 m of the centreline, extruded to a tagged height or a default. Roof shape is flat.",
            "licence": "ODbL 1.0",
        },
        "protection": "Both sides are walled at the shoulder offset. Pit entry is closed. That closure is a game boundary, not a claim about the real pit lane.",
        "not_claimed": "No orthophoto registration and no cockpit capture in this build. Centimetre storage is not centimetre accuracy."
        if bare is not None else
        "No lidar, no orthophoto registration, no cockpit capture in this build. Centimetre storage is not centimetre accuracy.",
    }
    if spec["slug"] == "lasvegas" and (source / "scenery.json").exists():
        provenance["native_scenery"] = {
            "recipe": "make lasvegas-assets", "manifest": "scenery.json", "source_manifest": "scenery_sources.json",
            "runtime_assets": "Content/Generated/LasVegas", "start_finish_station_m": 1815,
            "validation_reference": "docs/lasvegas_curves_validation.json",
            "note": "Native scenery replaces the initial generic road ribbon only for Las Vegas. The initial footprint count describes the old narrow corridor, not the current native city.",
        }
        provenance["not_claimed"] = "No orthophoto or post-construction engineering registration. Widths are estimates, and the 2022 bare-earth survey predates the racing deck. Cockpit and runtime review are recorded in docs/lasvegas_validation.json. Centimetre storage is not centimetre accuracy."
    if spec["slug"] == "lasvegas":
        provenance["route"]["authored_alignment"] = "layout-corrections.json"
        provenance["route"]["measured_plan_includes_authored_corrections"] = True
        provenance["route"]["horizontal_filter"] = "4 m source sampling; 24 binomial passes away from Harmon, 2 in its authored short reversals, joined with a quintic transition. Dense native samples use local geometric normals."
        provenance["width"] = {"method": "Explicit 12-15 m venue and corner controls, joined with quintic transitions; estimated from the reference, not inferred from instantaneous curvature."}
        provenance["shoulders"] = {"default_m": .10, "method": "Narrow 0.10 m shoulder outside the 0.85 m kerb allowance. Local escapes and the blue Sphere apron are authored separately in escape-areas.json and united with the deck in boundaries.json."}
        provenance["protection"] = "One closed paved-deck union supplies native walls and visible protection, including open escape-road mouths and tire-protected ends. Pit entry remains a closed game boundary. Escape dimensions are bounded visual estimates, not surveyed barrier positions."
        provenance["buildings"]["method"] = "Initial narrow OSM corridor count only. The native scene uses the larger mapped skyline with individual tower, roof and podium reconstructions in landmark-architecture.json and scenery.json."
    if spec["slug"] == "japan":
        provenance["origin"]["meaning"] = "Nearest centreline sample to the published start/finish at 34.8433 N, 136.5409 E."
        provenance["width"] = {"method": "15 m on the two straights and 12-14 m through the corners, joined with quintic transitions. Estimates from the circuit's character, not a white-line survey."}
        provenance["shoulders"]["method"] = "OSM barriers, with the outside of Degner, the hairpin, Spoon, 130R and the final chicane widened to a runoff. Pit entry stays closed for the game."
        provenance["buildings"]["method"] = "OSM footprints. Named grandstands, the pit building and the west control tower use estimated heights. The Circuit Wheel is a separate 48 m wheel placed at 34.845979 N, 136.538821 E; its 51 m top is an estimate of the published viewing height, not a measured diameter."
        provenance["reference_video"] = {
            "file": "Saved/Refs/japan.mp4",
            "use": "Appearance only. The clip is a commercial racing-game Japanese Grand Prix replay, not an onboard survey. Its pixels and meshes are not shipped.",
        }
        provenance["not_claimed"] = "No orthophoto registration and no packaged cockpit capture in this build. Widths, grandstand heights and the wheel diameter are estimates. The GSI mesh is ground, not a racing-deck survey. Centimetre storage is not centimetre accuracy."
    (source / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    write_plan(spec, local, turns)
    log(f"{spec['slug']}: {chosen['name']} {target:.1f} m (mapped {measured:.1f}, published {published}, scale {scale:.4f}) relief {relief:.1f} m turns {len(turns)} buildings {len(footprints)}")
    return record


def write_plan(spec, local, turns):
    folder = REVIEWS / spec["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    xs = [point[0] for point in local]
    ys = [point[1] for point in local]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1)
    def tx(point):
        return 40 + (point[0] - min_x) / span * 900
    def ty(point):
        return 940 - (point[1] - min_y) / span * 900
    path = " ".join(f"{tx(point):.1f},{ty(point):.1f}" for point in local)
    marks = []
    for turn in turns:
        point = local[min(len(local) - 1, int(turn["fraction"] * len(local)))]
        marks.append(f'<circle cx="{tx(point):.1f}" cy="{ty(point):.1f}" r="3" fill="#c4001a"/>')
    start = local[0]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="980" height="980">
<rect width="980" height="980" fill="#111"/>
<polyline points="{path} {tx(local[0]):.1f},{ty(local[0]):.1f}" fill="none" stroke="#f2f2f2" stroke-width="2"/>
<circle cx="{tx(start):.1f}" cy="{ty(start):.1f}" r="5" fill="#fff"/>
{''.join(marks)}
</svg>
'''
    (folder / "plan.svg").write_text(svg)


def emit_indexes(records):
    includes = []
    entries = []
    cases = []
    ini = []
    ready = [spec for spec in CIRCUITS if spec["slug"] in records]
    for spec in ready:
        record = records[spec["slug"]]
        prefix = spec["enum"]
        includes.append(f'#include "track_data/{spec["slug"]}_survey.inc"')
        grade = "{}"
        heading = "true" if record["heading_direction_test"] else "false"
        deck = "true" if spec.get("deck") else "false"
        description = spec["description"].replace('"', "")
        entries.append(f'''    {{TrackLayoutId::{prefix},
     "{spec["title"]}",
     "{spec["venue"]}",
     "{spec["country"]}",
     "{description}",
     "{spec["environment"]}",
     {record["target_m"]:.3f}f,
     {spec["turns"]},
     {format(1815.0 / record["target_m"], ".9f") if spec["slug"] == "lasvegas" else "0.0"}f,
     {record["relief_m"]:.3f}f,
     {"true" if record["clockwise"] else "false"},
     1.0f,
     true,
     k{prefix}Centerline,
     k{prefix}Elevation,
     k{prefix}Width,
     k{prefix}Bank,
     k{prefix}Runoff,
     {grade},
     "{spec["slug"]}",
     "{spec["folder"]}/Data",
     "/Game/Generated/{"LasVegas" if spec["slug"] == "lasvegas" else "Interlagos"}/Review",
     {record["aspect"]:.5f}f,
     {record["crossings"]},
     true,
     {heading},
     {deck},
     {spec["shoulder"]:.2f}f,
     k{prefix}Shoulder}},''')
        cases.append(f"        case TrackLayoutId::{prefix}: return k{prefix}Turns;")
        ini.append(f'+DirectoriesToAlwaysStageAsUFS=(Path="Generated/{spec["folder"]}/Data")')
    (TRACK_DATA / "generated_surveys.inc").write_text("\n".join(includes) + "\n")
    (TRACK_DATA / "generated_catalog.inc").write_text("\n".join(entries) + "\n")
    (TRACK_DATA / "generated_turn_cases.inc").write_text("\n".join(cases) + "\n")
    (TRACK_DATA / "generated_staging.ini").write_text("\n".join(ini) + "\n")
    lines = [
        "# Added circuits",
        "",
        "Nineteen layouts were built from OpenStreetMap raceway geometry and Copernicus GLO-90 elevations sampled on 2026-11-04. The driving length is the mapped plan, scaled to a published length only when the two already agreed within 1.5%. Shoulders use nearby OSM barriers where a vertex exists and a venue default where one does not.",
        "",
        "Suzuka is the only figure-eight. The back straight is the bridge over the Degner curves. Where the ground model falls into that underpass, the deck is filled to keep about 6.2 m of clearance and the lower road stays on the sampled ground. Its road profile is the Geospatial Information Authority of Japan 5 m mesh, not the earlier GLO-90 surface.",
        "",
        "Walls are continuous, including pit entry. That closure is for the game. Widths are typical asphalt figures, not a white-line survey. The initial generated circuits use GLO-90, a surface model with stated vertical uncertainty of 8 m on streets and 5 m on permanent circuits. Las Vegas has since been rebuilt with USGS 3DEP bare-earth terrain, a filtered road profile, native scenery and cockpit review. Its original footprint count in the table is superseded by [scenery.json](../Attribution/Sources/lasvegas/scenery.json); see [Las Vegas validation](lasvegas_validation.json) for evidence and limits.",
        "",
        "| Circuit | Mapped m | Published m | Scale | Relief m | Turns found | Buildings |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for spec in ready:
        record = records[spec["slug"]]
        lines.append(f"| {spec['title']} | {record['measured_m']:.1f} | {record['published_m']:.0f} | {record['uniform_scale']:.4f} | {record['relief_m']:.1f} | {record['turns_detected']} | {record['buildings']} |")
    lines.append("")
    lines.append("Hanoi is not in the game. OpenStreetMap's circuit relation there is two separate pieces, about 2.6 km and 2.3 km, and the roads around My Dinh do not join them into the published 5.607 km lap. Closing that gap would mean inventing roughly 600 m of circuit.")
    lines.append("")
    lines.append("Source notes for each venue are in `Attribution/Sources/<slug>/provenance.json`. Contact surfaces are regenerated with `make circuits`.")
    (ROOT / "docs" / "circuits.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    selected = set(args.only)
    records = {}
    for path in SOURCES.glob("*/reconstruction.json"):
        slug = path.parent.name
        if slug in {spec["slug"] for spec in CIRCUITS}:
            records[slug] = json.loads(path.read_text())
    failures = []
    for spec in CIRCUITS:
        if selected and spec["slug"] not in selected:
            continue
        try:
            records[spec["slug"]] = build(spec, refresh=args.refresh)
        except Exception as error:
            failures.append(f"{spec['slug']}: {error}")
            log(f"{spec['slug']}: FAILED {error}")
    missing = [spec["slug"] for spec in CIRCUITS if spec["slug"] not in records]
    if failures:
        log("failed: " + "; ".join(failures))
        return 1
    if missing:
        log("not built: " + ", ".join(missing))
    emit_indexes(records)
    log("wrote catalogue includes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
