"""Apply registered road and shoulder controls without rebuilding the alignment."""

from __future__ import annotations

import argparse
import bisect
import itertools
import json
import math
import re
from pathlib import Path
from typing import Literal

from circuit_dataclasses import (
    AlignmentControls,
    BankingControls,
    ElevationControls,
    PitLane,
    RacingRecipe,
    ShoulderBaseline,
    ShoulderCorrection,
    ShoulderCorrections,
    TurnRegistrations,
)
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def native_profile(text: str, kind: Literal["Elevation", "Width", "Bank"]) -> list[tuple[float, float]]:
    """Read scalar station values; use native_bank_profile to retain quadratic banking."""
    match = re.search(rf"constexpr Track{kind}Point \w+\[\] = \{{(.*?)\n\}};", text, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing native {kind} profile")
    return [(float(a), float(b)) for a, b in re.findall(
        rf"\{{\s*({NUMBER})f,\s*({NUMBER})f(?:,\s*{NUMBER}f)*\s*\}}", match[1]
    )]


def native_bank_profile(text: str) -> list[tuple[float, float, float]]:
    match = re.search(r"constexpr TrackBankPoint \w+\[\] = \{(.*?)\n\};", text, re.DOTALL)
    if match is None:
        raise ValueError("Missing native Bank profile")
    return [(float(station), float(angle), float(quadratic or 0))
            for station, angle, quadratic in re.findall(
                rf"\{{\s*({NUMBER})f,\s*({NUMBER})f(?:,\s*({NUMBER})f)?(?:,\s*{NUMBER}f)*\s*\}}", match[1]
            )]


def native_bank_edges(text: str) -> list[tuple[float, float, float, float]]:
    match = re.search(r"constexpr TrackBankPoint \w+\[\] = \{(.*?)\n\};", text, re.DOTALL)
    if match is None:
        raise ValueError("Missing native Bank profile")
    result = []
    for body in re.findall(r"\{([^{}]+)\}", match[1]):
        values = [float(value) for value in re.findall(rf"({NUMBER})f", body)]
        if len(values) not in (2, 3, 6):
            raise ValueError("Native bank points require two, three or six values")
        result.append((values[0], values[3], values[4], values[5]) if len(values) == 6
                      else (values[0], 0.0, 0.0, 0.0))
    return result


def banking_rows(profile: BankingControls, length: float) -> list[tuple[float, float, float]]:
    for controls in (profile.controls, profile.quadratic_controls):
        if controls and (
            len(controls) < 2
            or not all(math.isfinite(value) for row in controls for value in row)
            or not all(b[0] > a[0] for a, b in itertools.pairwise(controls))
            or controls[0][0] != 0 or abs(controls[-1][0] - length) > .001
            or controls[0][1] != controls[-1][1]
        ):
            raise ValueError("Banking controls must be ordered and close the complete lap")

    def sample(controls: list[tuple[float, float]], station: float) -> float:
        if not controls:
            return 0.0
        positions = [row[0] for row in controls]
        index = max(0, min(len(controls) - 2, bisect.bisect_right(positions, station) - 1))
        a, b = controls[index], controls[index + 1]
        blend = (station - a[0]) / (b[0] - a[0])
        return a[1] + (b[1] - a[1]) * blend

    positions = sorted({row[0] for row in profile.controls + profile.quadratic_controls})
    return [(station, sample(profile.controls, station), sample(profile.quadratic_controls, station))
            for station in positions]


def banking_edge_rows(profile: BankingControls, length: float) -> list[tuple[float, float, float, float, float, float]]:
    bank = banking_rows(profile, length)
    edges = profile.edge_controls
    if (len(edges) < 2 or edges[0][0] != 0 or abs(edges[-1][0] - length) > .001
            or edges[0][1:] != edges[-1][1:]
            or not all(math.isfinite(value) for row in edges for value in row)
            or not all(b[0] > a[0] for a, b in itertools.pairwise(edges))
            or any(row[1] < 0 for row in edges)):
        raise ValueError("Bank-edge controls must be ordered, nonnegative and close the complete lap")
    positions = sorted({row[0] for row in bank} | {row[0] for row in edges})
    bank_positions = [row[0] for row in bank]
    edge_positions = [row[0] for row in edges]
    result = []
    for station in positions:
        i = max(0, min(len(bank) - 2, bisect.bisect_right(bank_positions, station) - 1))
        a, b = bank[i], bank[i + 1]
        t = (station - a[0]) / (b[0] - a[0])
        j = max(0, min(len(edges) - 2, bisect.bisect_right(edge_positions, station) - 1))
        c, d = edges[j], edges[j + 1]
        u = (station - c[0]) / (d[0] - c[0])
        result.append((station, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t,
                       c[1] + (d[1] - c[1]) * u, c[2] + (d[2] - c[2]) * u,
                       c[3] + (d[3] - c[3]) * u))
    return result


def replace_profile(
    text: str, kind: Literal["Elevation", "Width", "Bank"], controls: list[tuple[float, float]], length: float
) -> str:
    if (not all(math.isfinite(value) for row in controls for value in row)
            or not all(b[0] > a[0] for a, b in itertools.pairwise(controls))
            or abs(controls[0][0]) > 0.0001 or abs(controls[-1][0] - length) > 0.001
            or abs(controls[0][1] - controls[-1][1]) > 0.0001):
        raise ValueError(f"{kind} controls must be ordered and close the complete lap")
    if kind == "Width" and any(value <= 0 for _, value in controls):
        raise ValueError("Road widths must be positive")
    if kind == "Bank" and any(abs(value) >= 90 for _, value in controls):
        raise ValueError("Road banking must remain between -90 and 90 degrees")
    match = re.search(rf"constexpr Track{kind}Point \w+\[\] = \{{(.*?)\n\}};", text, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing native {kind} profile")
    body = "\n" + ",\n".join(f"    {{{station:.6f}f, {value:.6f}f}}" for station, value in controls)
    return text[:match.start(1)] + body + text[match.end(1):]


def apply_banking(slug: str) -> None:
    source = ROOT / "Attribution/Sources" / slug / "banking-corrections.json"
    profile = TypeAdapter(BankingControls).validate_json(source.read_bytes())
    path = ROOT / "Source/FormulaForge/Native/track_data" / f"{slug}_survey.inc"
    text = path.read_text()
    length = native_profile(text, "Width")[-1][0]
    updated = replace_profile(text, "Bank", profile.controls, length)
    if profile.edge_controls:
        rows_edge = banking_edge_rows(profile, length)
        match = re.search(r"constexpr TrackBankPoint \w+\[\] = \{(.*?)\n\};", updated, re.DOTALL)
        if match is None:
            raise ValueError("Missing native Bank profile")
        body = "\n" + ",\n".join("    {" + ", ".join(f"{value:.9f}f" for value in row) + "}"
                                 for row in rows_edge)
        updated = updated[:match.start(1)] + body + updated[match.end(1):]
    elif profile.quadratic_controls:
        rows = banking_rows(profile, length)
        match = re.search(r"constexpr TrackBankPoint \w+\[\] = \{(.*?)\n\};", updated, re.DOTALL)
        if match is None:
            raise ValueError("Missing native Bank profile")
        body = "\n" + ",\n".join(f"    {{{station:.6f}f, {angle:.6f}f, {q:.9f}f}}"
                                 for station, angle, q in rows)
        updated = updated[:match.start(1)] + body + updated[match.end(1):]
    path.write_text(updated)
    print(f"{slug}: applied registered banking; alignment, elevation and width unchanged")


def apply_racing(slug: str) -> None:
    source = ROOT / "Attribution/Sources" / slug
    path = ROOT / "Source/FormulaForge/Native/track_data" / f"{slug}_survey.inc"
    text = path.read_text()
    original_width = native_profile(text, "Width")
    length = original_width[-1][0]
    elevation_path = source / "elevation-corrections.json"
    if elevation_path.exists():
        profile = TypeAdapter(ElevationControls).validate_json(elevation_path.read_bytes())
        text = replace_profile(text, "Elevation", profile.controls, length)
    recipe = TypeAdapter(RacingRecipe).validate_json((source / "environment-recipe.json").read_bytes())
    if recipe.width_profile is not None:
        controls = recipe.width_profile.controls_m
        # Validate source controls before interpolating onto the retained station lattice.
        replace_profile(text, "Width", controls, length)
        positions = [row[0] for row in controls]
        stations = sorted(set([row[0] for row in original_width] + positions))
        widths = []
        for station in stations:
            i = max(0, min(len(controls) - 2, bisect.bisect_right(positions, station) - 1))
            a, b = controls[i], controls[i + 1]
            t = max(0.0, min(1.0, (station - a[0]) / (b[0] - a[0])))
            widths.append((station, a[1] + (b[1] - a[1]) * t * t * (3 - 2 * t)))
        text = replace_profile(text, "Width", widths, length)
    turns_path = source / "turn-registration.json"
    if turns_path.exists():
        turns = TypeAdapter(TurnRegistrations).validate_json(turns_path.read_bytes()).turns
        if (sorted(turn.official_turn for turn in turns) != list(range(1, len(turns) + 1))
                or any(not 0 <= turn.native_station_m < length for turn in turns)):
            raise ValueError(f"Invalid official turn registration: {slug}")
        match = re.search(r"constexpr TrackTurnExpectation \w+\[\] = \{(.*?)\n\};", text, re.DOTALL)
        if match is None:
            raise ValueError(f"Missing native turn expectations: {slug}")
        body = "\n" + ",\n".join(
            f'    {{"Turn {turn.official_turn}", {turn.native_station_m / length:.9f}f, TrackTurnDirection::{turn.direction.title()}}}'
            for turn in turns
        )
        text = text[:match.start(1)] + body + text[match.end(1):]
    path.write_text(text)
    catalogue = ROOT / "Source/FormulaForge/Native/track_data/generated_catalog.inc"
    entries = re.split(r"(?=    \{TrackLayoutId::)", catalogue.read_text())
    for index, entry in enumerate(entries):
        if f'     "{slug}",' not in entry:
            continue
        lines = entry.splitlines(keepends=True)
        if re.fullmatch(rf"\s+{NUMBER}f,\n", lines[9]) is None:
            raise ValueError(f"Unexpected native catalogue relief field: {slug}")
        heights = [height for _, height in native_profile(text, "Elevation")]
        lines[9] = f"     {max(heights) - min(heights):.6f}f,\n"
        start_line = source / "start-line.json"
        if start_line.exists():
            station = float(json.loads(start_line.read_text())["native_station_m"])
            if not math.isfinite(station) or not 0 <= station < length:
                raise ValueError(f"Invalid timing-line station: {slug}")
            if re.fullmatch(rf"\s+{NUMBER}f,\n", lines[8]) is None:
                raise ValueError(f"Unexpected native catalogue timing field: {slug}")
            lines[8] = f"     {station / length:.9f}f,\n"
        entries[index] = "".join(lines)
        break
    else:
        raise ValueError(f"Missing native catalogue entry: {slug}")
    catalogue.write_text("".join(entries))
    print(f"{slug}: applied retained racing controls; alignment, bank and protection unchanged")


def apply_alignment(slug: str) -> None:
    source = ROOT / "Attribution/Sources" / slug / "alignment-corrections.json"
    refinement = source.with_name("alignment-refinement.json")
    if refinement.exists():
        source = refinement
    profile = TypeAdapter(AlignmentControls).validate_json(source.read_bytes())
    path = ROOT / "Source/FormulaForge/Native/track_data" / f"{slug}_survey.inc"
    text = path.read_text()
    match = re.search(r"constexpr TrackControlPoint \w+\[\] = \{(.*?)\n\};", text, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing native alignment: {slug}")
    body = "\n" + ",\n".join(f"    {{{x:.6f}f, {y:.6f}f}}" for x, y in profile.controls_xy_m)
    path.write_text(text[:match.start(1)] + body + text[match.end(1):])
    print(f"{slug}: applied retained alignment; refresh exported surfaces and protection")


def pit_shoulders(
    rows: list[tuple[float, float, float]],
    length: float,
    profile: PitLane | ShoulderCorrection,
) -> list[tuple[float, float, float]]:
    positions = [row[0] for row in rows]

    def sample(station: float) -> tuple[float, float]:
        index = max(0, min(len(rows) - 2, bisect.bisect_right(positions, station) - 1))
        a, b = rows[index], rows[index + 1]
        t = (station - a[0]) / (b[0] - a[0])
        return a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t

    before = (profile.start_m - profile.transition_m) % length
    after = (profile.end_m + profile.transition_m) % length
    side = 0 if profile.side > 0 else 1
    before_width, after_width = sample(before)[side], sample(after)[side]
    span = (profile.end_m - profile.start_m) % length
    knots = sorted(set(positions + [before, profile.start_m, profile.end_m, after]))
    result = []
    for station in knots:
        widths = list(sample(station))
        progress = (station - profile.start_m) % length
        if progress <= span:
            widths[side] = profile.shoulder_m
        else:
            distance_before, distance_after = length - progress, progress - span
            if distance_before < profile.transition_m:
                t = 1 - distance_before / profile.transition_m
                widths[side] = before_width + (profile.shoulder_m - before_width) * t * t * (3 - 2 * t)
            elif distance_after < profile.transition_m:
                t = 1 - distance_after / profile.transition_m
                widths[side] = after_width + (profile.shoulder_m - after_width) * t * t * (3 - 2 * t)
        result.append((station, widths[0], widths[1]))
    return result


def section_shoulders(
    rows: list[tuple[float, float, float]], length: float, source: Path
) -> list[tuple[float, float, float]]:
    path = source / "shoulder-corrections.json"
    if path.exists():
        corrections = TypeAdapter(ShoulderCorrections).validate_json(path.read_bytes())
        for profile in corrections.sections:
            rows = pit_shoulders(rows, length, profile)
    return rows


def apply(slug: str) -> None:
    source = ROOT / "Attribution/Sources" / slug
    length = float(json.loads((source / "reconstruction.json").read_text())["target_m"])
    path = ROOT / "Source/FormulaForge/Native/track_data" / (slug + "_survey.inc")
    text = path.read_text()
    match = re.search(r"constexpr TrackShoulderPoint (\w+)\[\] = \{(.*?)\n\};", text, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing native shoulder profile: {slug}")
    rows = [tuple(float(value) for value in row) for row in
            re.findall(r"\{([\d.]+)f, ([\d.]+)f, ([\d.]+)f\}", match[2])]
    original = [(row[0], row[1], row[2]) for row in rows]
    baseline_path = source / "shoulder-baseline.json"
    if baseline_path.exists():
        original = TypeAdapter(ShoulderBaseline).validate_json(baseline_path.read_bytes()).controls
        if (abs(original[0][0]) > 0.001 or abs(original[-1][0] - length) > 0.001
                or original[0][1:] != original[-1][1:]
                or any(b[0] <= a[0] for a, b in itertools.pairwise(original))
                or any(left < 0 or right < 0 for _, left, right in original)):
            raise ValueError(f"Invalid retained shoulder baseline: {slug}")
    result = original
    pit_path = source / "pit-lane.json"
    if pit_path.exists():
        profile = TypeAdapter(PitLane).validate_json(pit_path.read_bytes())
        result = pit_shoulders(result, length, profile)
    result = section_shoulders(result, length, source)
    body = "\n" + ",\n".join(
        f"    {{{station:.3f}f, {left:.3f}f, {right:.3f}f}}"
        for station, left, right in result
    )
    path.write_text(text[:match.start(2)] + body + text[match.end(2):])
    print(f"{slug}: applied registered pit and local shoulder corrections")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--racing", action="store_true", help="Apply explicit elevation and width evidence")
    operation.add_argument("--alignment", action="store_true", help="Apply retained local alignment corrections")
    operation.add_argument("--banking", action="store_true", help="Apply registered lateral banking controls")
    parser.add_argument("circuits", nargs="+")
    arguments = parser.parse_args()
    for circuit in arguments.circuits:
        if arguments.banking:
            apply_banking(circuit)
        elif arguments.racing:
            apply_racing(circuit)
        elif arguments.alignment:
            apply_alignment(circuit)
        else:
            apply(circuit)
