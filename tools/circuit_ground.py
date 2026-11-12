"""Derive racing profiles and bounded scenery grids from retained classified ground."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import struct
from pathlib import Path

import numpy as np
from circuit_dataclasses import (
    Catalogue,
    ClassifiedGroundSource,
    Provenance,
    RetainedTerrainSource,
    RoadStation,
    TerrainGrid,
)
from numpy.typing import NDArray
from pydantic import TypeAdapter
from rasterio.warp import transform
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]


def interpolate_ground(
    points: NDArray[np.float64], tree: cKDTree, targets: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    distances, indices = tree.query(targets, k=8, workers=1)
    near = points[indices]
    heights = np.full(len(targets), np.nan)
    best = np.full(len(targets), np.inf)
    # Containing local triangles avoid extrapolating a plane through nearly collinear observations.
    for first, second, third in itertools.combinations(range(8), 3):
        a, b, c = near[:, first], near[:, second], near[:, third]
        determinant = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        valid = np.abs(determinant) > 0.000001
        wa = np.divide((b[:, 1] - c[:, 1]) * (targets[:, 0] - c[:, 0])
                       + (c[:, 0] - b[:, 0]) * (targets[:, 1] - c[:, 1]),
                       determinant, out=np.zeros(len(targets)), where=valid)
        wb = np.divide((c[:, 1] - a[:, 1]) * (targets[:, 0] - c[:, 0])
                       + (a[:, 0] - c[:, 0]) * (targets[:, 1] - c[:, 1]),
                       determinant, out=np.zeros(len(targets)), where=valid)
        wc = 1 - wa - wb
        score = (distances[:, [first, second, third]] ** 2).sum(axis=1)
        use = valid & (wa >= -1e-8) & (wb >= -1e-8) & (wc >= -1e-8) & (score < best)
        heights[use] = (a[:, 2] * wa + b[:, 2] * wb + c[:, 2] * wc)[use]
        best[use] = score[use]
    measured_hull = np.isfinite(heights)
    weights = 1 / np.maximum(distances, 0.001) ** 2
    fallback = (near[:, :, 2] * weights).sum(axis=1) / weights.sum(axis=1)
    heights[~measured_hull] = fallback[~measured_hull]
    return heights, distances[:, 0], measured_hull


def geographic_targets(
    xy: NDArray[np.float64], provenance: Provenance, crs: str
) -> NDArray[np.float64]:
    origin, scale = provenance.origin, provenance.route.uniform_scale
    factor = math.pi / 180 * 6378137 * scale
    longitude = origin.longitude + xy[:, 0] / (factor * math.cos(math.radians(origin.latitude)))
    latitude = origin.latitude + xy[:, 1] / factor
    east, north = transform("EPSG:4326", crs, longitude.tolist(), latitude.tolist())
    return np.column_stack((east, north))


def generate(slug: str) -> None:
    source = ROOT / "Attribution/Sources" / slug
    scratch = ROOT / "build/circuits" / slug
    cloud = TypeAdapter(ClassifiedGroundSource).validate_json((source / "classified-ground.json").read_bytes())
    point_file = (source / cloud.point_file).resolve()
    if not point_file.is_relative_to(source.resolve()) or hashlib.sha256(point_file.read_bytes()).hexdigest() != cloud.point_sha256:
        raise ValueError("Classified point source does not match its retained manifest")
    with np.load(point_file) as archive:
        points = np.asarray(archive["xyz"], dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 8 or not np.isfinite(points).all():
        raise ValueError("Ground points must contain finite XYZ observations")
    tree = cKDTree(points[:, :2])
    provenance = TypeAdapter(Provenance).validate_json((source / "provenance.json").read_bytes())
    catalogue = TypeAdapter(Catalogue).validate_json((scratch / "catalogue.json").read_bytes())
    with (scratch / "road.csv").open() as handle:
        road = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(handle)))
    xy = np.array([(p.x, p.y) for p in road])
    alignment_path = source / "alignment-corrections.json"
    refinement_path = source / "alignment-refinement.json"
    if refinement_path.exists():
        alignment_path = refinement_path
    if alignment_path.exists():
        first = json.loads(alignment_path.read_text())["controls_xy_m"][0]
        if math.dist(first, xy[0]) > 0.1:
            raise ValueError("Apply and export the corrected alignment before sampling ground")
    heights, distances, containing = interpolate_ground(points, tree, geographic_targets(xy, provenance, cloud.crs))
    spacing = catalogue.length_m / len(road)
    sigma_m = 2.0
    offsets = np.arange(-math.ceil(4 * sigma_m / spacing), math.ceil(4 * sigma_m / spacing) + 1)
    weights = np.exp(-0.5 * (offsets * spacing / sigma_m) ** 2)
    weights /= weights.sum()
    smooth = np.zeros(len(road))
    for offset, weight in zip(offsets, weights, strict=True):
        smooth += np.roll(heights, int(offset)) * weight
    datum = float(smooth.min())
    controls = [[float(p.station), round(float(z - datum), 6)] for p, z in zip(road, smooth, strict=True)]
    controls.append([catalogue.length_m, controls[0][1]])
    grades = (np.roll(smooth, -1) - smooth) / spacing
    report = {
        "schema_version": 1, "circuit": slug, "provider": cloud.provider, "dataset": cloud.dataset,
        "point_manifest": "classified-ground.json", "point_sha256": cloud.point_sha256,
        "vertical_datum": cloud.vertical_datum, "relative_datum_m": datum,
        "relief_m": float(smooth.max() - smooth.min()), "controls": controls,
        "interpolation": "Closest containing triangle among eight nearest retained class2 observations; bounded inverse-distance fallback outside their local convex hull.",
        "smoothing": "Circular Gaussian sigma2m to remove point/export noise; no height or grade rescaling/clipping.",
        "maximum_filter_change_m": float(np.max(np.abs(smooth - heights))),
        "nearest_ground_p95_m": float(np.quantile(distances, 0.95)), "nearest_ground_max_m": float(distances.max()),
        "road_local_triangle_fraction": float(containing.mean()),
        "maximum_rise_percent": float(grades.max() * 100), "maximum_fall_percent": float(-grades.min() * 100),
        "vertical_uncertainty_m": cloud.vertical_uncertainty_m,
        "road_registration_note": "Mapped racing alignment adds horizontal uncertainty to the published ground-survey accuracy. Dense controls do not imply engineering survey precision.",
        "source_road_sha256": hashlib.sha256((scratch / "road.csv").read_bytes()).hexdigest(),
    }
    raw = {"station_m": [p.station for p in road], "absolute_ground_m": heights.tolist(),
           "nearest_point_m": distances.tolist(), "containing_triangle": containing.tolist()}
    (source / "elevation/road-ground-samples.json.gz").write_bytes(gzip.compress(json.dumps(raw).encode(), mtime=0))
    (source / "elevation-corrections.json").write_text(json.dumps(report, indent=2) + "\n")
    for step in (4.0, 12.0):
        x0 = math.floor((float(xy[:, 0].min()) - 650) / step) * step
        y0 = math.floor((float(xy[:, 1].min()) - 650) / step) * step
        columns = math.ceil((float(xy[:, 0].max()) + 650 - x0) / step) + 1
        rows = math.ceil((float(xy[:, 1].max()) + 650 - y0) / step) + 1
        gx, gy = np.meshgrid(x0 + np.arange(columns) * step, y0 + np.arange(rows) * step)
        targets = geographic_targets(np.column_stack((gx.ravel(), gy.ravel())), provenance, cloud.crs)
        values = np.empty(len(targets))
        for start in range(0, len(targets), 8192):
            values[start:start + 8192] = interpolate_ground(points, tree, targets[start:start + 8192])[0]
        if step == 4:
            payload = b"FFDEM1\0\0" + struct.pack("<ddfII", x0, y0, step, columns, rows) + values.astype("<f4").tobytes()
            (source / "elevation/bare_earth.bin").write_bytes(payload)
        else:
            grid = TerrainGrid(x0, y0, step, columns, rows, tuple(float(z - datum) for z in values))
            encoded = gzip.compress(TypeAdapter(TerrainGrid).dump_json(grid), mtime=0)
            grid_file = Path("elevation/classified-scenery-grid.json.gz")
            (source / grid_file).write_bytes(encoded)
            manifest = RetainedTerrainSource(grid_file, hashlib.sha256(encoded).hexdigest(), cloud.provider,
                                            cloud.dataset, datum, 20, provenance.route.uniform_scale)
            (source / "scenery-ground.json").write_bytes(TypeAdapter(RetainedTerrainSource).dump_json(manifest, indent=2) + b"\n")
    print(f"{slug}: classified ground relief {report['relief_m']:.3f} m, grades +{report['maximum_rise_percent']:.2f}/-{report['maximum_fall_percent']:.2f}%, nearest ground p95 {report['nearest_ground_p95_m']:.3f} m", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("circuit")
    generate(parser.parse_args().circuit)
