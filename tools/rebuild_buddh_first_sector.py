"""Rebuild the qualified Buddh width profile or its actual rendered contact planes."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from pydantic import TypeAdapter
from venues.buddh_first_sector import native_width_controls
from venues.buddh_first_sector_dataclasses import FirstSectorProposal, RetainedBaseline

ROOT = Path(__file__).resolve().parents[1]
TRACK_DATA = ROOT / "Source/FormulaForge/Native/track_data"


def literal(value: float) -> str:
    text = format(value, ".9g")
    if "." not in text and "e" not in text:
        text += ".0"
    return text + "f"


def width_profile(source: Path) -> str:
    proposal = TypeAdapter(FirstSectorProposal).validate_json(
        (source / "first-sector.json").read_bytes()
    )
    baseline = TypeAdapter(RetainedBaseline).validate_json(
        (source / "first-sector-baseline.json").read_bytes()
    )
    controls = native_width_controls(proposal, baseline)
    rows = [f"    {{{literal(s)}, {literal(w)}}}" for s, w in controls]
    return "constexpr TrackWidthPoint kBuddhWidth[] = {\n" + ",\n".join(rows) + "\n};"


def write_profile() -> None:
    source = ROOT / "Attribution/Sources/buddh"
    block = width_profile(source)
    survey = TRACK_DATA / "buddh_survey.inc"
    text, count = re.subn(
        r"constexpr TrackWidthPoint kBuddhWidth\[\] = \{.*?\n\};",
        lambda _match: block,
        survey.read_text(),
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("The retained Buddh survey must contain one width profile")
    survey.write_text(text)
    baseline = TypeAdapter(RetainedBaseline).validate_json(
        (source / "first-sector-baseline.json").read_bytes()
    )
    retained = [
        f"    {{{literal(s)}, {literal(w)}}}" for s, w in baseline.width_controls
    ]
    (TRACK_DATA / "buddh_first_sector_profile.inc").write_text(
        "// Retained width for unchanged protection reach and fallback field.\n"
        "// Rebuild with tools/rebuild_buddh_first_sector.py profile.\n"
        "constexpr TrackWidthPoint kBuddhFirstSectorRetainedWidth[] = {\n"
        + ",\n".join(retained) + "\n};\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=("profile", "contact"))
    arguments = parser.parse_args()
    if arguments.part == "profile":
        write_profile()
    else:
        from generate_circuit_scene import generate

        generate("buddh", write_native_contact=True)


if __name__ == "__main__":
    main()
