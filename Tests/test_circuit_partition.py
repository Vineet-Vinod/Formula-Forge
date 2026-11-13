from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from circuit_partition import MAGIC, mesh_rows, partition_city
from circuit_partition_dataclasses import CityPartitionRecipe, SceneManifest, SceneTile
from pydantic import TypeAdapter


def test_city_partition_preserves_materials_duplicates_and_residency(tmp_path: Path) -> None:
    def triangle(x: float, material: int) -> bytes:
        return struct.pack("<I", material) + b"".join(
            struct.pack("<8f", x + dx, dy, z, 0, 0, 1, u, v)
            for dx, dy, z, u, v in ((0, 0, 0, .1, .2), (80, 0, 20, .3, .4), (0, 80, 40, .5, .6))
        )

    a, b = triangle(-15_000, 0), triangle(15_000, 1)
    bounds = (-30_000., -30_000., -100., 30_000., 30_000., 30_000.)
    records = []
    for name, rows in (("Building_City_00_00", a + b + a),
                       ("Building_Crowd_00_00", b), ("Tile_Street_00_00", a)):
        payload = MAGIC + struct.pack("<I", len(rows) // 100) + rows
        path = tmp_path / (name + ".mesh")
        path.write_bytes(payload)
        records.append(SceneTile(name, path.name, ["Glass", "Steel"], bounds,
                                 len(rows) // 100, hashlib.sha256(payload).hexdigest()))
    adapter = TypeAdapter(SceneManifest)
    manifest = SceneManifest("baku", "Baku/Data", records)
    (tmp_path / "manifest.json").write_bytes(adapter.dump_json(manifest))
    assert partition_city(tmp_path, CityPartitionRecipe(120)) == 4
    result = adapter.validate_json((tmp_path / "manifest.json").read_bytes())
    city = [tile for tile in result.tiles if tile.source_parent is not None]
    assert len(city) == 2
    assert all(tile.bounds == bounds and tile.materials == ["Glass", "Steel"] for tile in city)
    assert sorted(mesh_rows(tmp_path / tile.file, tile) for tile in city) == sorted([a + a, b])
    assert result.tiles[-2:] == records[-2:]
    assert result.city_partition is not None
    assert result.city_partition.parents[0].triangle_multiset_equal
    assert result.city_partition.superseded_assets == [records[0].name]
