"""Jeddah close walls must clear real kerbs without retaining detached spurs."""

from __future__ import annotations

import bisect
import itertools
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from circuit_dataclasses import ShoulderBaseline
from pydantic import TypeAdapter
from shapely.geometry import LinearRing
from venues.jeddah_boundary import load_recipe, usable_ring

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Attribution/Sources/jeddah"


def test_close_wall_profile_clears_kerbs_and_preserves_pit_divider() -> None:
    recipe = load_recipe()
    profile = TypeAdapter(ShoulderBaseline).validate_json(
        (SOURCE / "shoulder-baseline.json").read_bytes()
    )
    rows = profile.controls
    positions = [row[0] for row in rows]

    def gap(station: float, side: int) -> float:
        index = max(0, min(len(rows) - 2, bisect.bisect_right(positions, station) - 1))
        a, b = rows[index], rows[index + 1]
        column = 1 if side > 0 else 2
        t = (station - a[0]) / (b[0] - a[0])
        return a[column] + t * (b[column] - a[column]) + 0.15

    assert profile.includes_pit_registration
    assert rows[0][0] == 0 and rows[-1][0] == recipe.length_m
    assert rows[0][1:] == rows[-1][1:]
    assert all(b[0] > a[0] for a, b in itertools.pairwise(rows))
    for start, end, side in recipe.kerbs:
        for i in range(int(end - start) + 1):
            clearance = gap(start + i, side) - recipe.kerb_inner_offset_m - recipe.kerb_width_m
            assert clearance >= 0.30
    for station in (0, 50, 100, 6020, 6100, 6174):
        assert abs(gap(station, -1) - 1.05) < 1e-6
    for station in (700, 1100, 1900, 3200, 4500, 5800):
        assert 0.64 <= gap(station, 1) <= 1.41
        assert 0.64 <= gap(station, -1) <= 1.41
    margin = json.loads((SOURCE / "kerb-margins.json").read_text())
    assert margin["controls_m"] == [[0, 0.15], [recipe.length_m, 0.15]]


def test_retraced_wall_chain_is_rejected_but_real_narrow_island_remains() -> None:
    assert not usable_ring(LinearRing([(0, 0), (1, 0), (2, 0), (3, 0), (2, 0), (1, 0), (0, 0)]))
    assert usable_ring(LinearRing([(0, 0), (5, 0), (5, 0.1), (0, 0.1)]))


def test_native_profile_matches_literal_source_and_green_ribbons_are_removed() -> None:
    text = (ROOT / "Source/FormulaForge/Native/track_data/jeddah_survey.inc").read_text()
    match = re.search(r"constexpr TrackShoulderPoint kJeddahShoulder\[\] = \{(.*?)\n\};", text, re.DOTALL)
    assert match
    actual = [[float(value) for value in row] for row in re.findall(
        r"\{([\d.]+)f, ([\d.]+)f, ([\d.]+)f\}", match[1]
    )]
    expected = json.loads((SOURCE / "shoulder-baseline.json").read_text())["controls"]
    assert len(actual) == len(expected)
    assert max(abs(a - b) for ra, rb in zip(actual, expected) for a, b in zip(ra, rb)) <= 0.000501
    assert all(a.material == "Runoff" for a in load_recipe().apron_ranges)
    assert "RunoffGreen" not in (ROOT / "tools/venues/jeddah.py").read_text()


def test_high_wall_source_is_confined_to_t13_inside() -> None:
    from venues.jeddah_boundary import wall_height

    sections = load_recipe().high_walls
    assert wall_height(2277, -1, sections) == 2.85
    assert wall_height(2277, 1, sections) == 0.95
    assert wall_height(2170, -1, sections) == 0.95
    assert wall_height(2360, -1, sections) == 0.95


def test_render_uses_jeddah_physical_top_and_stacks_panels_only_there(tmp_path: Path) -> None:
    from circuit_dataclasses import BarrierPanel, Catalogue, Point, RoadStation
    from circuit_scene import CircuitScene

    class WallScene(CircuitScene):
        def __init__(self, slug: str) -> None:
            self.slug = slug
            self.length = 6174
            self.scratch = tmp_path
            self.catalogue = Catalogue(slug, slug + "/Meshes", 6174, 0, False)
            self.panels = [BarrierPanel(2180, 2350, -1, "PanelJeddahAramco")]
            self.overhead_soffits = []
            self.concrete: list[tuple[Point, Point, float | None]] = []
            self.banners: list[tuple[str, Point, Point, float, float]] = []

        def nearest(self, x: float, y: float) -> tuple[RoadStation, float]:
            return RoadStation(2277, 0, 0, 0, 1, 0, 6, 0), 0

        def beam(self, kind: str, material: str, a: Point, b: Point,
                 width: float, depth: float | None = None) -> None:
            if material == "Concrete":
                self.concrete.append((a, b, depth))

        def banner(self, a: Point, b: Point, height: float, material: str,
                   kind: str = "Tile_Detail", u0: float = 0, repeat: float = 1) -> None:
            self.banners.append((material, a, b, height, repeat))

    (tmp_path / "barriers.csv").write_text(
        "ax,ay,bx,by,bottom,top,radius\n0,7.4,2,7.4,0,2.85,0.15\n"
    )
    scene = WallScene("jeddah")
    scene.barriers(street=True)
    assert scene.concrete[0][2] == 2.85
    assert scene.concrete[0][0][2] == 1.425
    panels = [row for row in scene.banners if row[0] == "PanelJeddahAramco"]
    assert len(panels) == 3
    assert [round(row[1][2], 2) for row in panels] == [0.08, 1.03, 1.98]
    assert all(row[4] == 0.25 for row in panels)
    fence = next(row for row in scene.banners if row[0] == "Fence")
    assert fence[1][2] == 2.85 and fence[3] == 2.2
    accepted = WallScene("singapore")
    accepted.barriers(street=True)
    assert accepted.concrete[0][2] == 0.94
    assert len([r for r in accepted.banners if r[0] == "PanelJeddahAramco"]) == 1
    assert next(r for r in accepted.banners if r[0] == "Fence")[1][2] == 0.95
