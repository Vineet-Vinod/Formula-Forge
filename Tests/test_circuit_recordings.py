"""A completed lap claim must survive recorder faults, missing evidence and station wrapping."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_circuit_recording import review_recording


def frame(index: int, station: float, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        'frame': index, 'time_s': index * .04, 'simulation_s': index * .04,
        'station_m': station, 'speed_kph': 100, 'barrier_contact': False,
        'on_track': True, 'grounded': True, 'lap_invalid': False,
        'completed_laps': 0, 'last_lap_valid': False, 'last_lap_s': 0,
        'visual_penetration_m': 0, 'loaded_visual_tiles': 40,
        'primary_screen_percentage_approx': 100,
        'image': f'frames/{index:08d}.jpg', 'width': 1600, 'height': 900,
    }
    record.update(changes)
    return record


def recording(root: Path, frames: list[dict[str, object]], *,
              replay: bool = False, missing_image: int | None = None) -> tuple[Path, Path]:
    catalogue = root / 'build/circuits/fixture/catalogue.json'
    catalogue.parent.mkdir(parents=True)
    catalogue.write_text(json.dumps({'slug': 'fixture', 'content_dir': 'Fixture/Data',
                                     'length_m': 100, 'start_station_m': 98.1,
                                     'deck_separation': False}))
    source = root / 'recording'
    (source / 'frames').mkdir(parents=True)
    session = {'schema_version': 1, 'state': 'stopped', 'stop_reason': 'lap_complete',
               'circuit': 'Fixture', 'frames': len(frames), 'rendered_frames': len(frames),
               'all_drawn_frames_saved': True, 'duration_s': 10,
               'presentation_only_replay': replay, 'final_state': frames[-1]}
    (source / 'session.json').write_text(json.dumps(session))
    (source / 'frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
    for name in ['inputs.jsonl', 'ticks.jsonl', 'steps.jsonl']:
        (source / name).write_bytes(b'{"original_journal":true}\n')
    for i, row in enumerate(frames):
        if i != missing_image:
            image = row['image']
            assert isinstance(image, str)
            (source / image).write_bytes(b'unchanged original image bytes\x00' + bytes([i % 256]))
    return source, root / 'review'


def test_full_lap_selects_across_native_wrap_and_preserves_original_evidence(tmp_path: Path) -> None:
    frames = [frame(i, (98.1 + .8 * i) % 100) for i in range(126)]
    frames[-1].update(completed_laps=1, last_lap_valid=True, last_lap_s=5)
    source, output = recording(tmp_path, frames)
    recipe = tmp_path / 'Attribution/Sources/fixture/environment-recipe.json'
    recipe.parent.mkdir(parents=True)
    recipe.write_text(json.dumps({'braking_markers': {'approaches': [
        {'official_corner': 'Hairpin', 'apex_station_m': 99.9}]}}))

    result = review_recording(source, output, 'fixture', root=tmp_path)

    assert result.valid_last_completed_live_lap
    assert result.clean_live_recording
    assert result.station_bin_coverage_fraction == 1
    assert result.maximum_circular_frame_gap_m == pytest.approx(.8)
    assert result.station_gaps == []
    assert result.selected_target_count == 126
    assert result.selected_image_count == 125
    index = json.loads((output / 'index.json').read_text())
    assert index[0]['target_station_m'] == 0
    assert index[0]['station_m'] == pytest.approx(99.7)
    assert index[0]['station_error_m'] == pytest.approx(.3)
    assert index[-1]['reason'] == 'registered braking apex: Hairpin'
    for item in index:
        assert (output / item['copied_image']).read_bytes() == Path(item['source_image']).read_bytes()
    for name in ['session.json', 'frames.jsonl', 'inputs.jsonl', 'ticks.jsonl', 'steps.jsonl']:
        assert (output / 'telemetry' / name).read_bytes() == (source / name).read_bytes()
    assert len(list((source / 'frames').iterdir())) == len(frames)


def test_faults_and_partial_wrap_gaps_remain_visible(tmp_path: Path) -> None:
    frames = [frame(0, 98), frame(1, 99, time_s=.1, barrier_contact=True),
              frame(2, 1, time_s=.4, on_track=False, grounded=False,
                    visual_penetration_m=.2, loaded_visual_tiles=0,
                    primary_screen_percentage_approx=80),
              frame(3, 2, time_s=.6, completed_laps=1, lap_invalid=True)]
    source, output = recording(tmp_path, frames, missing_image=2)

    result = review_recording(source, output, 'fixture', root=tmp_path)

    assert not result.valid_last_completed_live_lap
    assert not result.clean_live_recording
    assert (result.contact_frames, result.offtrack_frames, result.airborne_frames,
            result.invalid_lap_frames) == (1, 1, 1, 1)
    assert result.maximum_visual_penetration_m == .2
    assert result.minimum_loaded_tiles == result.minimum_moving_loaded_tiles == 0
    assert result.primary_screen_percentage_range == (80, 100)
    assert result.dimensions == [(1600, 900)]
    assert result.missing_image_files == 1
    assert result.frame_interval_median_ms == pytest.approx(200)
    assert result.frame_interval_p95_ms == pytest.approx(290)
    assert 'not uncaptured gameplay' in result.interval_caveat
    assert result.maximum_circular_frame_gap_m == 96
    wrap_gap = next(gap for gap in result.station_gaps if gap.start_station_m == 99)
    assert (wrap_gap.end_station_m, wrap_gap.length_m) == (1, 2)


@pytest.mark.parametrize('replay,initial_laps', [(True, 0), (False, 1)])
def test_replayed_or_previously_completed_laps_are_not_new_live_laps(
    tmp_path: Path, replay: bool, initial_laps: int,
) -> None:
    frames = [frame(0, 98, completed_laps=initial_laps),
              frame(1, 99, completed_laps=1, last_lap_valid=True, last_lap_s=70)]
    source, output = recording(tmp_path, frames, replay=replay)
    assert not review_recording(source, output, 'fixture', root=tmp_path).valid_last_completed_live_lap


@pytest.mark.parametrize('changes,error', [
    ({'station_m': float('nan')}, 'finite'),
    ({'station_m': 101}, 'outside native lap'),
    ({'grounded': 'false'}, 'boolean'),
    ({'width': 0}, 'greater than'),
    ({'time_s': 0}, 'frame/time must increase'),
])
def test_bad_telemetry_is_rejected_before_copying(
    tmp_path: Path, changes: dict[str, object], error: str,
) -> None:
    source, output = recording(tmp_path, [frame(0, 98), frame(1, 99, **changes)])
    original = (source / 'frames.jsonl').read_bytes()
    with pytest.raises(ValueError, match=error):
        review_recording(source, output, 'fixture', root=tmp_path)
    assert not output.exists()
    assert (source / 'frames.jsonl').read_bytes() == original


def test_wrong_circuit_and_overlapping_output_are_rejected(tmp_path: Path) -> None:
    source, output = recording(tmp_path, [frame(0, 98)])
    session = json.loads((source / 'session.json').read_text())
    session['circuit'] = 'Another Circuit'
    (source / 'session.json').write_text(json.dumps(session))
    with pytest.raises(ValueError, match='does not match'):
        review_recording(source, output, 'fixture', root=tmp_path)
    with pytest.raises(ValueError, match='must not overlap'):
        review_recording(source, source / 'review', 'fixture', root=tmp_path)
