from __future__ import annotations

import gzip
from pathlib import Path

from pydantic import TypeAdapter
from venues.baku_park_authoring import compile_ground
from venues.baku_park_authoring_dataclasses import ParkAuthoredGround


def test_authored_source_mesh_rebuilds_the_reviewed_native_patch_exactly() -> None:
    root = Path(__file__).resolve().parents[1] / "Attribution/Sources/baku/park-context"
    source = TypeAdapter(ParkAuthoredGround).validate_json(
        gzip.decompress((root / "authored-ground.json.gz").read_bytes())
    )
    rebuilt = compile_ground(source)
    assert len(source.vertices) == 38320
    assert len(source.faces) == 55257
    assert rebuilt == (root / "ground-delta.json.gz").read_bytes()
