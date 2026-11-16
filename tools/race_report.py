"""Build a standalone replay and measurement report from the native runner's CSVs."""

import argparse
import csv
import html
import json
from pathlib import Path


def build_report(directory: Path, template: Path) -> Path:
    frames: dict[str, list[list[float]]] = {}
    with (directory / "race.csv").open() as stream:
        for row in csv.DictReader(stream):
            frames.setdefault(row["time_s"], []).append(
                [
                    float(row[key])
                    for key in (
                        "car",
                        "x_m",
                        "y_m",
                        "heading",
                        "speed_mps",
                        "line",
                        "target",
                    )
                ]
            )
    lines: dict[str, list[list[float]]] = {}
    with (directory / "trajectories.csv").open() as stream:
        for row in csv.DictReader(stream):
            lines.setdefault(row["line"], []).append(
                [float(row["x_m"]), float(row["y_m"])]
            )
    summary = (directory / "summary.json").read_text()
    rows: list[str] = []
    for result in sorted(directory.parent.glob("*/summary.json")):
        rows.append(
            f"<details><summary>{html.escape(result.parent.name)}</summary><pre>{html.escape(result.read_text())}</pre></details>"
        )
    data = {
        "times": [float(time) for time in frames],
        "frames": list(frames.values()),
        "lines": list(lines.values()),
    }
    document = template.read_text().replace(
        "__RACE_DATA__", json.dumps(data, separators=(",", ":"))
    )
    document = document.replace("__SUMMARY__", html.escape(summary)).replace(
        "__RESULTS__", "\n".join(rows)
    )
    destination = directory / "report.html"
    destination.write_text(document)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    directory: Path = args.directory
    print(build_report(directory, Path(__file__).with_name("race_report.html")))


if __name__ == "__main__":
    main()
