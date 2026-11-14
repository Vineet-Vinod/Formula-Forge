"""Keep the public profile authoring path from restoring the old broad legal lane."""

from pathlib import Path
from shutil import copy2

import circuit_profiles
import pytest


def test_public_buddh_profiles_replay_without_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[1]
    source = Path("Attribution/Sources/buddh")
    native = Path("Source/FormulaForge/Native/track_data/buddh_survey.inc")
    catalogue = native.parent / "generated_catalog.inc"
    (tmp_path / source).mkdir(parents=True)
    (tmp_path / native.parent).mkdir(parents=True)
    for name in (
        "reconstruction.json", "environment-recipe.json", "elevation-corrections.json",
        "turn-registration.json", "start-line.json", "pit-lane.json",
        "shoulder-corrections.json", "first-sector.json", "first-sector-baseline.json",
    ):
        path = root / source / name
        if path.exists():
            copy2(path, tmp_path / source / name)
    copy2(root / native, tmp_path / native)
    copy2(root / catalogue, tmp_path / catalogue)
    expected = (root / native).read_bytes()
    expected_catalogue = (root / catalogue).read_bytes()
    monkeypatch.setattr(circuit_profiles, "ROOT", tmp_path)
    for _ in range(2):
        circuit_profiles.apply_racing("buddh")
        circuit_profiles.apply("buddh")
        assert (tmp_path / native).read_bytes() == expected
        assert (tmp_path / catalogue).read_bytes() == expected_catalogue
