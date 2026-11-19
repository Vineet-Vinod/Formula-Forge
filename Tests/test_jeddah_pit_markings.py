"""Keep the reference fork and exit merge distinct from generic pit outlines."""

from __future__ import annotations

import struct
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from circuit_mesh import MeshScene
from circuit_route_assets import prepare
from circuit_scene import CircuitScene
from shapely.geometry import Polygon
from venues.jeddah_pit_markings import (
    emit_markings,
    load_recipe,
    paint_point,
    road_line_openings,
    strokes,
)
from venues.jeddah_pits import pit_route_source

ROOT = Path(__file__).resolve().parents[1]


def test_entry_lead_is_broken_and_fork_shares_one_tip() -> None:
    route = pit_route_source()
    lines = {line.name: line for line in load_recipe(route).lines}
    lead, inner, outer = (lines[name] for name in ('entry-dashed-lead', 'entry-pit-fork', 'entry-track-fork'))
    assert lead.dash_m > 0 and lead.gap_m > 0
    assert inner.controls[0][0] == outer.controls[0][0] == lead.controls[-1][0]
    road = CircuitScene('jeddah')
    assert paint_point(road, route, inner, inner.controls[0][0], 0) == paint_point(road, route, outer, outer.controls[0][0], 0)
    broken = strokes(lead)
    assert all(b[0] > a[1] for a, b in pairwise(broken))


def test_exit_has_one_guide_until_the_local_merge() -> None:
    route = pit_route_source()
    lines = {line.name: line for line in load_recipe(route).lines}
    for distance in (604, 680, 760, 800):
        active = [line.name for line in lines.values() if line.controls[0][0] <= distance <= line.controls[-1][0]]
        assert active == ['exit-left-guide']
    assert lines['exit-right-merge'].controls[0][0] >= 811
    assert lines['exit-merge-dashes'].dash_m == 1
    assert lines['exit-merge-dashes'].gap_m > 0
    road = CircuitScene('jeddah')
    line = lines['exit-left-guide']
    point = paint_point(road, route, line, line.controls[-1][0], 0)
    nearest, _ = road.nearest(*point[:2])
    assert abs((point[0] - nearest.x) * nearest.ty - (point[1] - nearest.y) * nearest.tx + nearest.half_width - .06) < .01


def test_only_white_paint_is_added_and_road_openings_are_finite() -> None:
    route = pit_route_source()
    scene = MeshScene()
    emit_markings(scene, route)
    assert scene.tiles and all(tile.materials == ['White'] for tile in scene.tiles.values())
    for opening in road_line_openings(route):
        shape = Polygon(opening.polygon_xy_m)
        assert shape.is_valid and shape.exterior.is_ccw
        assert abs(shape.convex_hull.area - shape.area) < 1e-7
        assert opening.top_m - opening.bottom_m < .18


def test_replacement_preserves_every_nonwhite_route_triangle_and_physical_file(tmp_path: Path) -> None:
    old = ROOT / 'build/reviews/jeddah-clearance-20261118/route-assets'
    import json

    old_manifest = json.loads((old / 'manifest.json').read_text())
    assets = prepare('jeddah', tmp_path, ROOT / 'Attribution/Sources/jeddah/pit-lane-reconstruction.json',
                     ROOT / 'build/reviews/jeddah-clearance-20261118/escape-overlay.json')

    def nonwhite(folder: Path, records: list[tuple[str, list[str]]]) -> Counter[tuple[str, bytes]]:
        result: Counter[tuple[str, bytes]] = Counter()
        for file, materials in records:
            raw = (folder / file).read_bytes()
            for offset in range(12, len(raw), 100):
                index = struct.unpack_from('<I', raw, offset)[0]
                if materials[index] != 'White':
                    result[(materials[index], raw[offset + 4:offset + 100])] += 1
        return result

    assert nonwhite(old, [(v['file'], v['materials']) for v in old_manifest['tiles']]) == nonwhite(tmp_path, [(v.file, v.materials) for v in assets.tiles])
    for file in ('pit_lane.bin', 'pit_barriers.bin', 'escape_surface.bin'):
        assert (tmp_path / file).read_bytes() == (ROOT / 'Content/Generated/Jeddah/Data' / file).read_bytes()
