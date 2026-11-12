"""Reconstruct mapped corner arcs while retaining the surrounding registered alignment."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
from circuit_dataclasses import (
    AlignmentRecipe,
    Catalogue,
    CornerFitProof,
    MappedCornerArc,
    RoadStation,
)
from numpy.typing import NDArray
from pydantic import TypeAdapter
from scipy.interpolate import CubicSpline

ROOT = Path(__file__).resolve().parents[1]


def fit_line(points: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if len(points) < 3:
        raise ValueError("A tangent fit needs at least three road observations")
    center = points.mean(axis=0)
    _, _, vectors = np.linalg.svd(points - center)
    direction = vectors[0]
    if np.dot(direction, points[-1] - points[0]) < 0:
        direction = -direction
    return center, direction


def refine(slug: str, sigma_m: float) -> None:
    source = ROOT / "Attribution/Sources" / slug
    retained = source / "alignment-refinement-base.csv.gz"
    if not retained.exists():
        road_path = ROOT / "build/circuits" / slug / "road.csv"
        retained.write_bytes(gzip.compress(road_path.read_bytes(), mtime=0))
    base = gzip.decompress(retained.read_bytes())
    rows = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(io.StringIO(base.decode()))))
    catalogue_path = ROOT / "build/circuits" / slug / "catalogue.json"
    length = TypeAdapter(Catalogue).validate_json(catalogue_path.read_bytes()).length_m
    positions = np.array([p.station for p in rows])
    spacing = length / len(rows)
    points = np.array([(p.x, p.y) for p in rows])
    offsets = np.arange(-math.ceil(4 * sigma_m / spacing), math.ceil(4 * sigma_m / spacing) + 1)
    weights = np.exp(-0.5 * (offsets * spacing / sigma_m) ** 2)
    weights /= weights.sum()
    smooth = np.zeros_like(points)
    for offset, weight in zip(offsets, weights, strict=True):
        smooth += np.roll(points, int(offset), axis=0) * weight
    movement = float(np.max(np.linalg.norm(smooth - points, axis=1)))
    if movement > 1.0:
        raise ValueError(f"{slug}: refinement {movement:.3f} m exceeds the 1 m registration allowance")
    spline = CubicSpline(np.append(positions, length), np.vstack((smooth, smooth[0])), bc_type="periodic")
    controls = spline(np.linspace(0, length, math.ceil(length), endpoint=False))
    record = {
        "schema_version": 1, "circuit": slug,
        "method": "Circular Gaussian denoising of dense registered XY samples, followed by periodic cubic resampling to 1 m controls. Removes short-wavelength Catmull interpolation ripples from the sparse mapped line; retains compound-corner shape instead of fitting a circle. Cubic resampling avoids reintroducing curvature discontinuities from linear sampling chords.",
        "source_road_file": retained.name,
        "source_road_sha256": hashlib.sha256(base).hexdigest(),
        "sigma_m": sigma_m, "maximum_displacement_m": movement,
        "registration_allowance_m": 1.0,
        "limitations": "Sub-metre authoring refinement within mapped alignment uncertainty, not surveyed edge data. Does not establish a correct route, race-event junction radius, width, elevation or banking. Re-export and check complete native curvature and protection after application.",
        "controls_xy_m": [[round(float(x), 6), round(float(y), 6)] for x, y in controls],
    }
    (source / "alignment-refinement.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{slug}: sigma {sigma_m:g} m, maximum XY refinement {movement:.3f} m", flush=True)


def reconstruct(slug: str) -> None:
    source = ROOT / "Attribution/Sources" / slug
    scratch = ROOT / "build/circuits" / slug
    catalogue = TypeAdapter(Catalogue).validate_json((scratch / "catalogue.json").read_bytes())
    arc_path = source / "alignment-arcs.json"
    arcs = TypeAdapter(list[MappedCornerArc]).validate_json(arc_path.read_bytes())
    retained = source / "alignment-base-road.csv.gz"
    if not retained.exists():
        retained.write_bytes(gzip.compress((scratch / "road.csv").read_bytes(), mtime=0))
    base = gzip.decompress(retained.read_bytes())
    rows = TypeAdapter(list[RoadStation]).validate_python(list(csv.DictReader(io.StringIO(base.decode()))))
    positions = np.array([p.station for p in rows])
    observed = np.array([(p.x, p.y) for p in rows])
    stations = np.arange(0, catalogue.length_m, 1.0)
    closed_stations = np.append(positions, catalogue.length_m)
    original = np.column_stack([
        np.interp(stations, closed_stations, np.append(observed[:, axis], observed[0, axis]))
        for axis in (0, 1)
    ])
    result = original.copy()
    allowances = np.zeros(len(stations))
    proofs = []
    for arc in arcs:
        start, end = arc.core_native_range_m
        entry, a = fit_line(observed[(positions > start - arc.incoming_fit_m[0])
                                    & (positions < start - arc.incoming_fit_m[1])])
        exit, b = fit_line(observed[(positions > end + arc.outgoing_fit_m[0])
                                   & (positions < end + arc.outgoing_fit_m[1])])
        turn = math.atan2(float(a[0] * b[1] - a[1] * b[0]), float(np.dot(a, b)))
        if not math.radians(15) < abs(turn) < math.radians(175):
            raise ValueError(f"{slug}/{arc.official_corner}: tangent observations do not define one arc")
        vertex = entry + a * np.linalg.solve(np.column_stack((a, -b)), exit - entry)[0]
        sign = math.copysign(1, turn)
        slope = -a * math.tan(abs(turn) / 2) + np.array([-a[1], a[0]]) * sign
        radius = float(np.dot(np.array(arc.circle_center_source_xy_m) - vertex, slope) / np.dot(slope, slope))
        if not 0.8 * arc.radius_m < radius < 1.2 * arc.radius_m:
            raise ValueError(f"{slug}/{arc.official_corner}: tangent radius disagrees with mapped arc")
        center = vertex + radius * slope
        entry_point = vertex - a * radius * math.tan(abs(turn) / 2)
        exit_point = vertex + b * radius * math.tan(abs(turn) / 2)
        angle_start = math.atan2(entry_point[1] - center[1], entry_point[0] - center[0])
        target = original.copy()
        mask = (stations > start - arc.blend_m) & (stations < end + arc.blend_m)
        for index in np.flatnonzero(mask):
            point = original[index]
            delta = point - center
            angle = ((math.atan2(delta[1], delta[0]) - angle_start) * sign) % (2 * math.pi)
            candidates = [entry_point + a * min(0, float(np.dot(point - entry_point, a))),
                          exit_point + b * max(0, float(np.dot(point - exit_point, b)))]
            if angle <= abs(turn):
                candidates.append(center + delta * radius / np.linalg.norm(delta))
            target[index] = min(candidates, key=lambda candidate: float(np.linalg.norm(candidate - point)))
        weight = np.minimum(np.clip((stations - start + arc.blend_m) / arc.blend_m, 0, 1),
                            np.clip((end + arc.blend_m - stations) / arc.blend_m, 0, 1))
        weight = weight**3 * (10 + weight * (-15 + 6 * weight))
        displacement = (target - original) * weight[:, None]
        maximum = float(np.max(np.linalg.norm(displacement, axis=1)))
        if maximum > arc.maximum_displacement_m:
            raise ValueError(f"{slug}/{arc.official_corner}: displacement {maximum:.3f} m exceeds source allowance")
        result += displacement
        allowances[weight > 0] = np.maximum(allowances[weight > 0], arc.maximum_displacement_m)
        before, after = result - np.roll(result, 1, axis=0), np.roll(result, -1, axis=0) - result
        angles = np.arctan2(before[:, 0] * after[:, 1] - before[:, 1] * after[:, 0], (before * after).sum(axis=1))
        curvature = np.abs(angles) / ((np.linalg.norm(before, axis=1) + np.linalg.norm(after, axis=1)) / 2)
        raw = np.array(arc.raw_controls_xy_native_m)[:, :2]
        error = float(np.max(np.abs(np.linalg.norm(raw - center, axis=1) - radius)))
        proof = CornerFitProof(arc.official_corner, arc.core_native_range_m, radius,
                               (float(center[0]), float(center[1])), 1 / float(np.max(curvature[mask])), maximum, error,
                               arc.evidence_kind, arc.radius_uncertainty_m)
        proofs.append(proof)
    total_movement = np.linalg.norm(result - original, axis=1)
    if np.any(total_movement > allowances + 0.000001):
        raise ValueError(f"{slug}: composed corner corrections exceed their source displacement allowance")
    before, after = result - np.roll(result, 1, axis=0), np.roll(result, -1, axis=0) - result
    angles = np.arctan2(before[:, 0] * after[:, 1] - before[:, 1] * after[:, 0], (before * after).sum(axis=1))
    curvature = np.abs(angles) / ((np.linalg.norm(before, axis=1) + np.linalg.norm(after, axis=1)) / 2)
    for proof_index, (arc, proof) in enumerate(zip(arcs, proofs, strict=True)):
        start, end = arc.core_native_range_m
        mask = (stations > start - arc.blend_m) & (stations < end + arc.blend_m)
        proofs[proof_index] = replace(proof, minimum_radius_m=1 / float(np.max(curvature[mask])))
        print(f"{slug}/{arc.official_corner}: radius {proof.radius_m:.2f} m, final minimum {proofs[proof_index].minimum_radius_m:.2f} m, movement {proof.maximum_displacement_m:.3f} m")
    recipe = AlignmentRecipe(1, slug,
        "Circular fillets tangent to retained mapped approaches/exits; fitted radius, quintic exterior joins and explicit 1 m controls. Source-map estimates, not surveyed kerbs.",
        hashlib.sha256(base).hexdigest(), hashlib.sha256(arc_path.read_bytes()).hexdigest(), proofs,
        [(round(float(x), 6), round(float(y), 6)) for x, y in result],
        maximum_composed_displacement_m=float(np.max(total_movement)))
    (source / "alignment-corrections.json").write_bytes(TypeAdapter(AlignmentRecipe).dump_json(recipe, indent=2) + b"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refine-sigma", type=float, help="Denoise retained native samples within a 1 m XY allowance")
    parser.add_argument("circuits", nargs="+")
    arguments = parser.parse_args()
    if arguments.refine_sigma is not None and not 0 < arguments.refine_sigma <= 3:
        parser.error("refinement sigma must be above zero and at most3m")
    for circuit in arguments.circuits:
        if arguments.refine_sigma is None:
            reconstruct(circuit)
        else:
            refine(circuit, arguments.refine_sigma)
