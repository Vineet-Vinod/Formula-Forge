"""Apply reference-registered pit-wall offsets to native shoulder profiles."""

from __future__ import annotations

import bisect
import json
import re
import sys
from pathlib import Path

from circuit_dataclasses import PitLane, ShoulderCorrection, ShoulderCorrections
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]


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
    for circuit in sys.argv[1:]:
        apply(circuit)
