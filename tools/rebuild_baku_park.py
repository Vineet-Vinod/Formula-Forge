"""Repack the authored Baku public-ground control mesh without refitting terrain."""

from __future__ import annotations

import argparse
from pathlib import Path

from venues.baku_park_authoring import rebuild


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("Attribution/Sources/baku/park-context/authored-ground.json.gz"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Attribution/Sources/baku/park-context/ground-delta.json.gz"),
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    source: Path = arguments.source
    output: Path = arguments.output
    check: bool = arguments.check
    rebuild(source, output, check=check)


if __name__ == "__main__":
    main()
