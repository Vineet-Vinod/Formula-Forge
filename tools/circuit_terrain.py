"""Materialize retained ground or acquire scenery without replacing racing profiles."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import rasterio
from circuit_dataclasses import (
    Catalogue,
    Provenance,
    RetainedTerrainSource,
    RoadStation,
    TerrainGrid,
)
from pydantic import TypeAdapter
from rasterio.errors import RasterioIOError
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]


def materialize_retained_ground(source: Path, destination: Path) -> bool:
    manifest = source / "scenery-ground.json"
    if not manifest.exists():
        return False
    profile = TypeAdapter(RetainedTerrainSource).validate_json(manifest.read_bytes())
    grid_path = (source / profile.grid_file).resolve()
    if not grid_path.is_relative_to(source.resolve()):
        raise ValueError("Retained terrain grid must remain within its source directory")
    encoded = grid_path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != profile.grid_sha256:
        raise ValueError("Retained terrain grid hash does not match its source manifest")
    grid = TypeAdapter(TerrainGrid).validate_json(gzip.decompress(encoded))
    if (grid.columns < 2 or grid.rows < 2 or grid.step <= 0
            or len(grid.heights) != grid.columns * grid.rows
            or not all(math.isfinite(value) for value in (grid.x, grid.y, grid.step, *grid.heights))):
        raise ValueError("Retained terrain grid has invalid dimensions or nonfinite heights")
    horizontal_scale = 1.0
    if profile.grid_uniform_scale is not None:
        provenance = TypeAdapter(Provenance).validate_json((source / "provenance.json").read_bytes())
        horizontal_scale = provenance.route.uniform_scale / profile.grid_uniform_scale
    payload = (b"FFTRN1\0\0" + struct.pack("<ddfII", grid.x * horizontal_scale, grid.y * horizontal_scale,
                                          grid.step * horizontal_scale, grid.columns, grid.rows)
               + struct.pack(f"<{len(grid.heights)}f", *grid.heights))
    destination.write_bytes(payload)
    record = {
        "provider": profile.provider,
        "dataset": profile.dataset,
        "retained_window": str(profile.grid_file),
        "sha256": profile.grid_sha256,
        "grid_spacing_m": grid.step,
        "runtime_grid_spacing_m": grid.step * horizontal_scale,
        "horizontal_frame_correction": horizontal_scale,
        "grid_uniform_scale": profile.grid_uniform_scale,
        "relative_datum_m": profile.relative_datum_m,
        "road_join_distance_m": profile.road_join_distance_m,
        "source_manifest": manifest.name,
        "use": "Retained scenery-only ground grid. Heights already use the registered relative datum; racing profiles remain unchanged.",
        "terrain_sha256": hashlib.sha256(payload).hexdigest(),
    }
    (source / "scenery-terrain.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{source.name}: materialized retained {grid.columns}x{grid.rows} ground", flush=True)
    return True


def acquire(slug: str, rebase: bool = False) -> None:
    source = ROOT / "Attribution/Sources" / slug
    scratch = ROOT / "build/circuits" / slug
    provenance = TypeAdapter(Provenance).validate_json(
        (source / "provenance.json").read_bytes()
    )
    catalogue = TypeAdapter(Catalogue).validate_json(
        (scratch / "catalogue.json").read_bytes()
    )
    with (scratch / "road.csv").open() as handle:
        road = TypeAdapter(list[RoadStation]).validate_python(
            list(csv.DictReader(handle))
        )
    destination = ROOT / "Content/Generated" / catalogue.content_dir / "terrain.bin"
    if materialize_retained_ground(source, destination):
        return
    if destination.exists() and not rebase:
        print(f"{slug}: retaining existing terrain", flush=True)
        return
    origin = provenance.origin
    scale = provenance.route.uniform_scale
    factor_x = math.pi / 180 * 6378137 * math.cos(math.radians(origin.latitude)) * scale
    factor_y = math.pi / 180 * 6378137 * scale
    x0 = math.floor((min(p.x for p in road) - 650) / 12) * 12
    y0 = math.floor((min(p.y for p in road) - 650) / 12) * 12
    columns = math.ceil((max(p.x for p in road) + 650 - x0) / 12) + 1
    rows = math.ceil((max(p.y for p in road) + 650 - y0) / 12) + 1
    longitude = origin.longitude + (x0 + np.arange(columns) * 12) / factor_x
    latitude = origin.latitude + (y0 + np.arange(rows) * 12) / factor_y
    lat_tile, lon_tile = math.floor(origin.latitude), math.floor(origin.longitude)
    key = f"Copernicus_DSM_COG_10_{'N' if lat_tile >= 0 else 'S'}{abs(lat_tile):02d}_00_{'E' if lon_tile >= 0 else 'W'}{abs(lon_tile):03d}_00_DEM"
    url = f"https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/{key}/{key}.tif"
    retained = source / "elevation/scenery_dem.tif"
    retained.parent.mkdir(exist_ok=True)
    if retained.exists() and (source / "scenery-terrain.json").exists():
        url = json.loads((source / "scenery-terrain.json").read_text())["source_url"]
    if not retained.exists():
        with rasterio.Env(
            GDAL_CACHEMAX=32,
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        ):
            try:
                dataset = rasterio.open(url)
            except RasterioIOError:
                key = key.replace("COG_10_", "COG_30_")
                url = f"https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com/{key}/{key}.tif"
                dataset = rasterio.open(url)
            with dataset as raster:
                if (
                    min(longitude) < raster.bounds.left
                    or max(longitude) > raster.bounds.right
                    or min(latitude) < raster.bounds.bottom
                    or max(latitude) > raster.bounds.top
                ):
                    raise ValueError(
                        f"{slug}: landscape crosses tile boundary; acquire both windows explicitly"
                    )
                window = (
                    from_bounds(
                        float(min(longitude)) - 0.0005,
                        float(min(latitude)) - 0.0005,
                        float(max(longitude)) + 0.0005,
                        float(max(latitude)) + 0.0005,
                        raster.transform,
                    )
                    .round_offsets()
                    .round_lengths()
                )
                heights = raster.read(1, window=window)
                profile = raster.profile.copy()
                profile.update(
                    width=heights.shape[1],
                    height=heights.shape[0],
                    transform=raster.window_transform(window),
                    compress="deflate",
                    tiled=False,
                    blockysize=heights.shape[0],
                )
                with rasterio.open(retained, "w", **profile) as output:
                    output.write(heights, 1)
    with rasterio.open(retained) as raster:
        values = raster.read(1)
        transform = raster.transform
        cx = (longitude - transform.c) / transform.a - 0.5
        cy = (latitude - transform.f) / transform.e - 0.5
        c = np.clip(np.floor(cx).astype(int), 0, values.shape[1] - 2)
        r = np.clip(np.floor(cy).astype(int), 0, values.shape[0] - 2)
        tx, ty = np.clip(cx - c, 0, 1), np.clip(cy - r, 0, 1)
        grid = (
            values[r[:, None], c[None, :]] * (1 - tx)[None, :] * (1 - ty)[:, None]
            + values[r[:, None], c[None, :] + 1] * tx[None, :] * (1 - ty)[:, None]
            + values[r[:, None] + 1, c[None, :]] * (1 - tx)[None, :] * ty[:, None]
            + values[r[:, None] + 1, c[None, :] + 1] * tx[None, :] * ty[:, None]
        )
        differences = []
        for p in road[:: max(1, len(road) // 256)]:
            col = min(
                values.shape[1] - 1,
                max(
                    0,
                    round(
                        (origin.longitude + p.x / factor_x - transform.c) / transform.a
                        - 0.5
                    ),
                ),
            )
            row = min(
                values.shape[0] - 1,
                max(
                    0,
                    round(
                        (origin.latitude + p.y / factor_y - transform.f) / transform.e
                        - 0.5
                    ),
                ),
            )
            differences.append(float(values[row, col]) - p.z)
        datum = float(np.median(differences))
    payload = (
        b"FFTRN1\0\0"
        + struct.pack("<ddfII", x0, y0, 12.0, columns, rows)
        + (grid - datum).astype("<f4").tobytes()
    )
    destination.write_bytes(payload)
    record = {
        "provider": "Copernicus DEM, distributed through AWS Open Data",
        "dataset": "GLO-90 DSM" if "90m" in url else "GLO-30 DSM",
        "source_url": url,
        "source_info": "https://registry.opendata.aws/copernicus-dem/",
        "documentation": "https://copernicus-dem-90m.s3.amazonaws.com/readme.html",
        "retained_window": "elevation/scenery_dem.tif",
        "sha256": hashlib.sha256(retained.read_bytes()).hexdigest(),
        "grid_spacing_m": 12,
        "source_resolution_m": 90 if "90m" in url else 30,
        "relative_datum_m": datum,
        "datum_method": "Median offset to unchanged native road profile at 256 stations.",
        "use": "Surrounding landscape only, bilinearly resampled; not a racing-deck or bare-earth survey. Road-adjacent ground joins the existing road plane.",
        "terrain_sha256": hashlib.sha256(payload).hexdigest(),
    }
    (source / "scenery-terrain.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{slug}: retained {columns}x{rows} landscape, datum {datum:.2f}", flush=True)


if __name__ == "__main__":
    for venue in (argument for argument in sys.argv[1:] if argument != "--rebase"):
        acquire(venue, "--rebase" in sys.argv)
