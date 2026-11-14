from __future__ import annotations

import gzip
import struct
from pathlib import Path

import pytest
from circuit_dataclasses import MeshTile
from circuit_mesh import MeshScene
from pydantic import TypeAdapter
from venues.baku_museum_authoring import rebuild
from venues.baku_museum_dataclasses import MuseumSource
from venues.baku_museums import validate_support_rows

SOURCES = Path(__file__).resolve().parents[1] / "Attribution/Sources/baku"


def test_museum_ground_rebuild_uses_retained_original_planes(tmp_path: Path) -> None:
    delta = SOURCES / "museum-interior-ground-delta.json.gz"
    original = delta.read_bytes()
    output = tmp_path / "rebuilt.json.gz"
    rebuild(SOURCES / "museums.json.gz", delta, output)
    assert output.read_bytes() == original
    assert delta.read_bytes() == original


def test_museum_support_guard_rejects_changed_native_attributes() -> None:
    source = TypeAdapter(MuseumSource).validate_json(
        gzip.decompress((SOURCES / "museums.json.gz").read_bytes())
    )
    scene = MeshScene()
    for row in source.ground_supports:
        tile = scene.tiles.setdefault(row.tile, MeshTile())
        if row.material not in tile.materials:
            tile.materials.append(row.material)
        payload = struct.pack("<I", tile.materials.index(row.material)) + row.payload
        tile.triangles.extend(payload * row.copies)
    validate_support_rows(scene, source.ground_supports)
    first = scene.tiles[source.ground_supports[0].tile]
    first.triangles[99] ^= 1
    with pytest.raises(ValueError, match="supporting Ground changed"):
        validate_support_rows(scene, source.ground_supports)
