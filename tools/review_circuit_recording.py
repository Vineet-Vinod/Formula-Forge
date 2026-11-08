"""Review packaged FFLapRecorder telemetry and retain unchanged station-selected images."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from circuit_dataclasses import (
    Catalogue,
    RecordingFrame,
    RecordingGap,
    RecordingRecipe,
    RecordingReview,
    RecordingReviewRequest,
    RecordingSelection,
    RecordingSession,
    RecordingTarget,
)
from pydantic import TypeAdapter, ValidationError

ROOT = Path(__file__).resolve().parents[1]
STATION_TARGETS = 125
MAXIMUM_TARGETS = 200
FRAME_ADAPTER = TypeAdapter(RecordingFrame)
INTERVAL_CAVEAT = (
    'Intervals use recorder time_s between captured viewport draws. GPU readback, '
    'image encoding, disk writes, recorder backpressure, startup and pauses can '
    'increase them. These are not uncaptured gameplay frame timings.'
)


def circular_distance(a: float, b: float, length: float) -> float:
    delta = abs(a - b) % length
    return min(delta, length - delta)


def image_path(recording: Path, image: str) -> Path:
    relative = Path(image)
    candidate = (recording / relative).resolve()
    if relative.is_absolute() or not candidate.is_relative_to(recording):
        raise ValueError(f'Image path escapes recording directory: {image}')
    return candidate


def station_targets(root: Path, slug: str, length: float) -> list[RecordingTarget]:
    targets = [RecordingTarget(i * length / STATION_TARGETS, 'uniform native station')
               for i in range(STATION_TARGETS)]
    recipe_path = root / 'Attribution/Sources' / slug / 'environment-recipe.json'
    if recipe_path.exists():
        recipe = TypeAdapter(RecordingRecipe).validate_json(recipe_path.read_bytes())
        for apex in recipe.braking_markers.approaches[:MAXIMUM_TARGETS - len(targets)]:
            targets.append(RecordingTarget(apex.apex_station_m % length,
                                           f'registered braking apex: {apex.name}'))
    return targets


def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = .95 * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def review_recording(recording_directory: Path, output_directory: Path,
                     slug: str, *, root: Path = ROOT) -> RecordingReview:
    recording, output = recording_directory.resolve(), output_directory.resolve()
    if output.is_relative_to(recording) or recording.is_relative_to(output):
        raise ValueError('Recording and output directories must not overlap')
    if not slug or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in slug):
        raise ValueError('Use a native circuit slug such as japan or portimao')
    catalogue_path = root / 'build/circuits' / slug / 'catalogue.json'
    catalogue = TypeAdapter(Catalogue).validate_json(catalogue_path.read_bytes())
    length = catalogue.length_m
    if (catalogue.slug != slug or not math.isfinite(length) or length <= 0
            or not math.isfinite(catalogue.start_station_m)
            or not 0 <= catalogue.start_station_m <= length):
        raise ValueError(f'Invalid native catalogue: {catalogue_path}')
    session_path = recording / 'session.json'
    session = TypeAdapter(RecordingSession).validate_json(session_path.read_bytes())
    circuit_name = ''.join(c for c in session.circuit.casefold() if c.isalnum())
    if circuit_name != ''.join(c for c in slug if c.isalnum()):
        raise ValueError(f'Session circuit {session.circuit!r} does not match {slug!r}')
    if not -.001 <= session.final_state.station_m <= length + .001:
        raise ValueError('Final session station is outside native lap')
    targets = station_targets(root, slug, length)
    candidates: list[tuple[RecordingFrame, int, float] | None] = [None] * len(targets)
    counts: Counter[str] = Counter()
    stations: set[float] = set()
    bins: set[int] = set()
    dimensions: set[tuple[int, int]] = set()
    percentages: list[float] = []
    intervals: list[float] = []
    minimum_tiles: int | None = None
    moving_tiles: int | None = None
    penetration = session.final_state.visual_penetration_m
    first: RecordingFrame | None = None
    previous: RecordingFrame | None = None
    warnings: list[str] = []
    frames_path = recording / 'frames.jsonl'
    with frames_path.open('rb') as journal:
        for line_number, raw in enumerate(journal, 1):
            try:
                frame = FRAME_ADAPTER.validate_json(raw)
            except ValidationError as error:
                raise ValueError(f'{frames_path}:{line_number}: {error}') from error
            if not -.001 <= frame.station_m <= length + .001:
                raise ValueError(f'{frames_path}:{line_number}: station outside native lap')
            if previous is not None:
                if frame.frame <= previous.frame or frame.time_s <= previous.time_s:
                    raise ValueError(f'{frames_path}:{line_number}: frame/time must increase')
                intervals.append((frame.time_s - previous.time_s) * 1000)
                counts['missing_frame_indices'] += frame.frame - previous.frame - 1
                counts['lap_counter_resets'] += frame.completed_laps < previous.completed_laps
            else:
                first = frame
                counts['missing_frame_indices'] += frame.frame
            previous = frame
            image = Path(frame.image)
            if (image.parent != Path('frames') or image.suffix not in ('.jpg', '.png')
                    or image.stem != f'{frame.frame:08d}'):
                raise ValueError(f'{frames_path}:{line_number}: image does not match recorder frame')
            path = image_path(recording, frame.image)
            counts['missing_images'] += not path.is_file()
            counts['frames'] += 1
            counts['contact'] += frame.barrier_contact
            counts['offtrack'] += not frame.on_track
            counts['airborne'] += not frame.grounded
            counts['invalid'] += frame.lap_invalid
            penetration = max(penetration, frame.visual_penetration_m)
            minimum_tiles = (frame.loaded_visual_tiles if minimum_tiles is None
                             else min(minimum_tiles, frame.loaded_visual_tiles))
            if abs(frame.speed_kph) > 1:
                moving_tiles = (frame.loaded_visual_tiles if moving_tiles is None
                                else min(moving_tiles, frame.loaded_visual_tiles))
            station = frame.station_m % length
            stations.add(station)
            bins.add(min(STATION_TARGETS - 1, int(station / length * STATION_TARGETS)))
            dimensions.add((frame.width, frame.height))
            percentages.append(frame.primary_screen_percentage_approx)
            for i, target in enumerate(targets):
                distance = circular_distance(station, target.station_m, length)
                candidate = candidates[i]
                if candidate is None or distance < candidate[2]:
                    candidates[i] = (frame, line_number, distance)
    if first is None or previous is None or minimum_tiles is None:
        raise ValueError(f'{frames_path}: no captured frames')
    final = session.final_state
    completed = final.completed_laps - first.completed_laps
    counter_reset = counts['lap_counter_resets'] > 0 or final.completed_laps < previous.completed_laps
    valid_lap = (completed > 0 and final.last_lap_valid and final.last_lap_s > 0
                 and not counter_reset and not session.presentation_only_replay)
    all_saved = (session.all_drawn_frames_saved and counts['frames'] == session.frames
                 and session.frames == session.rendered_frames
                 and counts['missing_frame_indices'] == 0)
    if session.state != 'stopped':
        warnings.append('Session is still recording; manifest may precede the journals.')
    if not all_saved:
        warnings.append('Manifest counts, frame indices or all_drawn_frames_saved are incomplete.')
    if counts['missing_images']:
        warnings.append(f"{counts['missing_images']} journal images are absent on disk.")
    if counter_reset:
        warnings.append('Completed-lap counter decreased; a clean continuous lap is not established.')
    if session.presentation_only_replay:
        warnings.append('Presentation replay carries source lap state; it is not a new live lap.')
    if len(bins) < STATION_TARGETS:
        warnings.append(f'Captured positions visit {len(bins)}/{STATION_TARGETS} native station bins.')
    ordered = sorted(stations)
    gaps = [RecordingGap(a, b % length, b - a)
            for a, b in zip(ordered, ordered[1:] + [ordered[0] + length], strict=True)]
    threshold = 2 * length / STATION_TARGETS
    clean = (valid_lap and session.state == 'stopped' and all_saved and len(bins) == STATION_TARGETS
             and not any(counts[key] for key in ('contact', 'offtrack', 'airborne', 'invalid', 'missing_images'))
             and final.on_track and final.grounded and not final.barrier_contact
             and not final.lap_invalid and penetration <= .001)
    output.mkdir(parents=True, exist_ok=True)
    telemetry = output / 'telemetry'
    telemetry.mkdir(exist_ok=True)
    archived = []
    for path in [session_path, *sorted(recording.glob('*.jsonl'))]:
        shutil.copy2(path, telemetry / path.name)
        archived.append(f'telemetry/{path.name}')
    shutil.copy2(catalogue_path, telemetry / 'native-catalogue.json')
    archived.append('telemetry/native-catalogue.json')
    selections = []
    copied: set[str] = set()
    for target, candidate in zip(targets, candidates, strict=True):
        assert candidate is not None
        frame, line_number, distance = candidate
        source_image = image_path(recording, frame.image)
        relative_image: str | None = None
        if source_image.is_file():
            relative_image = f'frames/{source_image.name}'
            if relative_image not in copied:
                destination = output / relative_image
                destination.parent.mkdir(exist_ok=True)
                shutil.copy2(source_image, destination)
                copied.add(relative_image)
        selections.append(RecordingSelection(target.station_m, target.reason, frame.frame,
                                             line_number, frame.station_m % length, distance,
                                             frame.time_s, str(source_image), relative_image))
    (output / 'index.json').write_text(json.dumps([asdict(s) for s in selections], indent=2,
                                                 allow_nan=False) + '\n')
    report = RecordingReview(
        circuit_slug=slug, recording_directory=str(recording), native_catalogue=str(catalogue_path),
        circuit_length_m=length, native_start_station_m=catalogue.start_station_m,
        session_state=session.state, stop_reason=session.stop_reason,
        presentation_only_replay=session.presentation_only_replay,
        completed_laps_during_recording=max(0, completed), valid_last_completed_live_lap=valid_lap,
        clean_live_recording=clean, frame_count=counts['frames'], manifest_saved_frames=session.frames,
        rendered_frames=session.rendered_frames, all_drawn_frames_saved=all_saved,
        contact_frames=counts['contact'], offtrack_frames=counts['offtrack'],
        airborne_frames=counts['airborne'], invalid_lap_frames=counts['invalid'],
        maximum_visual_penetration_m=penetration, minimum_loaded_tiles=minimum_tiles,
        minimum_moving_loaded_tiles=moving_tiles, dimensions=sorted(dimensions),
        primary_screen_percentage_range=(min(percentages), max(percentages)),
        frame_interval_median_ms=statistics.median(intervals) if intervals else None,
        frame_interval_p95_ms=percentile95(intervals), interval_caveat=INTERVAL_CAVEAT,
        station_bin_count=STATION_TARGETS, visited_station_bins=sorted(bins),
        station_bin_coverage_fraction=len(bins) / STATION_TARGETS,
        maximum_circular_frame_gap_m=max(gap.length_m for gap in gaps),
        station_gaps=[gap for gap in gaps if gap.length_m > threshold],
        gap_reporting_threshold_m=threshold, selected_image_count=len(copied),
        selected_target_count=len(selections), missing_image_files=counts['missing_images'],
        archived_journals=archived, warnings=warnings,
    )
    (output / 'summary.json').write_text(json.dumps(asdict(report), indent=2, allow_nan=False) + '\n')
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording_directory', type=Path)
    parser.add_argument('output_directory', type=Path)
    parser.add_argument('circuit_slug')
    arguments = TypeAdapter(RecordingReviewRequest).validate_python(vars(parser.parse_args()))
    try:
        report = review_recording(arguments.recording_directory, arguments.output_directory,
                                  arguments.circuit_slug)
    except (OSError, ValueError) as error:
        parser.exit(2, f'{error}\n')
    print(f'{report.circuit_slug}: valid live lap={report.valid_last_completed_live_lap}, '
          f'clean recording={report.clean_live_recording}, stop={report.stop_reason}, '
          f'coverage={report.station_bin_coverage_fraction:.1%}, '
          f'{report.selected_image_count} original images copied')
    print(arguments.output_directory / 'summary.json')


if __name__ == '__main__':
    main()
