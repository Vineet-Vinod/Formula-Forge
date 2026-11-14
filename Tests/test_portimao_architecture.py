"""The cantilever stand must retain its source envelope and backed seating."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from circuit_dataclasses import Point
from circuit_scene import CircuitScene
from shapely import covers, points
from shapely.geometry import Polygon
from venues.portimao import circuit_edges
from venues.portimao_stand import main_grandstand

Face = tuple[str, str, Point, Point, Point]


@pytest.fixture(scope='module')
def stand() -> tuple[CircuitScene, list[Face]]:
    scene = CircuitScene('portimao')
    records: list[Face] = []

    def capture(kind: str, material: str, a: Point, b: Point, c: Point,
                uv: tuple[tuple[float, float], ...] = ((0, 0), (1, 0), (1, 1)),
                normals: tuple[Point, ...] | None = None) -> None:
        records.append((kind, material, a, b, c))

    scene.triangle = capture
    scene.road_surfaces()
    circuit_edges(scene)
    records.clear()
    grid, road = scene.grid, tuple(scene.road)
    cutouts = tuple(shape.wkb for shape in scene.terrain_cutouts)
    main_grandstand(scene)
    assert scene.grid == grid and tuple(scene.road) == road
    assert tuple(shape.wkb for shape in scene.terrain_cutouts) == cutouts
    return scene, records


def test_structure_keeps_source_canopy_plan_and_racing_clearance(
    stand: tuple[CircuitScene, list[Face]],
) -> None:
    scene, records = stand
    roof = Polygon(scene.footprint(38166697).ring)
    assert roof.is_valid and roof.convex_hull.area == pytest.approx(roof.area, abs=1e-6)
    assert roof.disjoint(scene.road_mask.buffer(1.0))
    vertices = points([p[:2] for kind, _material, *face in records
                       if not kind.startswith('Building_Crowd') for p in face])
    assert all(covers(roof.buffer(.04), vertices))


def surface_height(face: Face, x: float, y: float) -> float | None:
    _kind, _material, a, b, c = face
    determinant = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
    if abs(determinant) < 1e-9:
        return None
    u = ((b[1]-c[1])*(x-c[0]) + (c[0]-b[0])*(y-c[1]))/determinant
    v = ((c[1]-a[1])*(x-c[0]) + (a[0]-c[0])*(y-c[1]))/determinant
    if min(u, v, 1-u-v) < -1e-8:
        return None
    return u*a[2] + v*b[2] + (1-u-v)*c[2]


def test_upper_seating_has_both_concrete_soffit_and_tread(
    stand: tuple[CircuitScene, list[Face]],
) -> None:
    _scene, records = stand
    soffits = [face for face in records if face[0] == 'Building_PortimaoTierSoffit']
    assert soffits
    upper_z = max(face[2][2] for face in soffits)
    upper = [face for face in soffits if abs(face[2][2]-upper_z) < 1e-8]
    concrete = [face for face in records if face[1] == 'Concrete' and
                face[0] in {'Building_PortimaoTierSoffit', 'Building_PortimaoStandTread'}]
    for face in upper[::40]:
        x = sum(p[0] for p in face[2:])/3
        y = sum(p[1] for p in face[2:])/3
        hits = sorted({round(z, 7) for candidate in concrete
                       if (z := surface_height(candidate, x, y)) is not None})
        assert len(hits) == 2
        assert hits[0] == pytest.approx(upper_z, abs=1e-6)
        assert hits[1] > hits[0] + .20
