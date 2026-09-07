"""Audit the exported glTF and compare the game's sampled route with Blender's survey."""

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import build_monza as B
import numpy as np

ROOT = B.ROOT


def verify(folder=None):
    folder = Path(folder or B.OUT / "runtime")
    raw = (folder / "monza.glb").read_bytes()
    magic, version, size = struct.unpack_from("<III", raw)
    assert (magic, version, size) == (0x46546C67, 2, len(raw))
    n, kind = struct.unpack_from("<II", raw, 12)
    assert kind == 0x4E4F534A
    doc = json.loads(raw[20 : 20 + n])
    binary = raw[28 + n :]
    metadata = json.loads((folder / "monza.json").read_text())
    assert metadata["source_sha256"] == hashlib.sha256(B.BLEND.read_bytes()).hexdigest()
    components = {5126: "<f4", 5123: "<u2", 5121: "u1"}
    sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}

    def read(index):
        a = doc["accessors"][index]
        v = doc["bufferViews"][a["bufferView"]]
        return np.frombuffer(
            binary,
            dtype=components[a["componentType"]],
            count=a["count"] * sizes[a["type"]],
            offset=v.get("byteOffset", 0) + a.get("byteOffset", 0),
        ).reshape(a["count"], sizes[a["type"]])

    triangles = 0
    for mesh in doc["meshes"]:
        for p in mesh["primitives"]:
            coords = read(p["attributes"]["POSITION"])
            indices = read(p["indices"])
            assert np.isfinite(coords).all()
            assert len(coords) <= 65535 and int(indices.max()) < len(coords)
            assert np.isfinite(read(p["attributes"]["NORMAL"])).all()
            assert np.isfinite(read(p["attributes"]["TEXCOORD_0"])).all()
            assert len(indices) % 3 == 0
            triangles += len(indices) // 3
    assert triangles == metadata["triangles"] and len(raw) < 104_000_000
    trees = sum(v for k, v in metadata["instances"].items() if k.startswith("LIB_Tree"))
    assert trees == 14958
    assert len(metadata["grid_slots"]) == 11
    checks = {
        "glb_valid": True,
        "index_limit": 65535,
        "triangles": triangles,
        "meshes": len(doc["meshes"]),
        "bytes": len(raw),
        "tree_instances": trees,
        "grid_slots": 11,
        "source_hash_matches": True,
    }
    binary_path = ROOT / "build/game/formula_forge"
    if binary_path.exists():
        route = np.array(
            json.loads(
                subprocess.check_output(
                    [str(binary_path), "--dump-monza-route"], cwd=ROOT
                )
            )
        )
        reference = np.array([B.station_point(float(row[0]))[0] for row in route])
        planar = np.linalg.norm(route[:, 1:3] - reference[:, :2], axis=1)
        vertical = np.abs(route[:, 3] - reference[:, 2])
        widths = np.abs(
            route[:, 4] - np.array([B.width(float(row[0])) for row in route])
        )
        assert planar.max() < 0.15, planar.max()
        assert vertical.max() < 0.003, vertical.max()
        assert widths.max() < 0.002, widths.max()
        checks["native_route"] = {
            "samples": len(route),
            "max_planar_error_m": float(planar.max()),
            "max_vertical_error_m": float(vertical.max()),
            "max_width_error_m": float(widths.max()),
        }
    else:
        checks["native_route"] = (
            "Build the game to run the native alignment comparison."
        )
    (folder / "validation.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path)
    verify(parser.parse_args().runtime)
