#!/usr/bin/env python3
"""Crop the Clark County bare-earth DEM onto the Las Vegas survey frame.

The retained grid is the circuit extent plus a margin, in the same local
metres as the generated centreline. Full county tiles stay in build/tmp.
"""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path

import tifffile

ROOT = Path(__file__).resolve().parents[1]
EARTH = 6378137.0
LAT0 = 36.11468849381722
LON0 = -115.17298826588483
SCALE = 0.998518
TIE_E = 659993.9996937403
TIE_N = 4000005.999994392
STEP = 4.0
MARGIN = 160.0


def utm11(lat: float, lon: float) -> tuple[float, float]:
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    lon0 = math.radians(-117.0)
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    lat_r, lon_r = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(lat_r) ** 2)
    t = math.tan(lat_r) ** 2
    c = ep2 * math.cos(lat_r) ** 2
    aa = (lon_r - lon0) * math.cos(lat_r)
    m = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat_r
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat_r)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat_r)
        - (35 * e2**3 / 3072) * math.sin(6 * lat_r)
    )
    east = k0 * n * (aa + (1 - t + c) * aa**3 / 6 + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * aa**5 / 120) + 500000.0
    north = k0 * (m + n * math.tan(lat_r) * (aa * aa / 2 + (5 - t + 9 * c + 4 * c * c) * aa**4 / 24
                                              + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * aa**6 / 720))
    return east, north


def local_to_latlon(x: float, y: float) -> tuple[float, float]:
    x, y = x / SCALE, y / SCALE
    lat = LAT0 + math.degrees(y / EARTH)
    lon = LON0 + math.degrees(x / (EARTH * math.cos(math.radians(LAT0))))
    return lat, lon


def main() -> None:
    survey = (ROOT / "Source/FormulaForge/Native/track_data/lasvegas_survey.inc").read_text()
    points = [(float(x), float(y)) for x, y in re.findall(r"\{(-?[0-9.]+)f, (-?[0-9.]+)f\}", survey.split("kLasVegasElevation")[0])]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    origin_x = math.floor((min(xs) - MARGIN) / STEP) * STEP
    origin_y = math.floor((min(ys) - MARGIN) / STEP) * STEP
    cols = int(math.ceil((max(xs) + MARGIN - origin_x) / STEP)) + 1
    rows = int(math.ceil((max(ys) + MARGIN - origin_y) / STEP)) + 1
    easts, norths = [], []
    for row in range(rows):
        for col in range(cols):
            lat, lon = local_to_latlon(origin_x + col * STEP, origin_y + row * STEP)
            east, north = utm11(lat, lon)
            easts.append(east)
            norths.append(north)
    col0 = max(0, int(math.floor(min(easts) - TIE_E)) - 2)
    col1 = int(math.ceil(max(easts) - TIE_E)) + 3
    row0 = max(0, int(math.floor(TIE_N - max(norths))) - 2)
    row1 = int(math.ceil(TIE_N - min(norths))) + 3
    print(f"grid {cols}x{rows} window rows {row0}:{row1} cols {col0}:{col1}", flush=True)
    with tifffile.TiffFile(ROOT / "build/tmp/lasvegas-dem/x66y400.tif") as tif:
        raster = tif.pages[0].asarray()
        window = raster[row0:row1, col0:col1]
        del raster
    heights = []
    missing = 0
    for index, (east, north) in enumerate(zip(easts, norths)):
        col = east - TIE_E - col0
        row = TIE_N - north - row0
        c0, r0 = int(math.floor(col)), int(math.floor(row))
        if not (0 <= r0 < window.shape[0] - 1 and 0 <= c0 < window.shape[1] - 1):
            heights.append(float("nan"))
            missing += 1
            continue
        tx, ty = col - c0, row - r0
        value = (
            window[r0, c0] * (1 - tx) * (1 - ty)
            + window[r0, c0 + 1] * tx * (1 - ty)
            + window[r0 + 1, c0] * (1 - tx) * ty
            + window[r0 + 1, c0 + 1] * tx * ty
        )
        if value < -1000:
            heights.append(float("nan"))
            missing += 1
        else:
            heights.append(float(value))
    finite = [value for value in heights if value == value]
    print(f"samples {len(heights)} missing {missing} absolute {min(finite):.2f}..{max(finite):.2f} relief {max(finite) - min(finite):.2f}", flush=True)
    out = ROOT / "Attribution/Sources/lasvegas/elevation"
    out.mkdir(parents=True, exist_ok=True)
    blob = bytearray(b"FFDEM1\0\0")
    blob += struct.pack("<ddfII", origin_x, origin_y, STEP, cols, rows)
    blob += struct.pack(f"<{len(heights)}f", *heights)
    (out / "bare_earth.bin").write_bytes(blob)
    print(f"wrote {out / 'bare_earth.bin'} {len(blob)} bytes", flush=True)


if __name__ == "__main__":
    main()
