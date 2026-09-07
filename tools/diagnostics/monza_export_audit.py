"""Inspect the existing GLB and compare affected source triangles by position."""

import io
import json
import struct
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/forensics/monza"


def read_glb(path):
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from("<III", raw)
    assert (magic, version, length) == (0x46546C67, 2, len(raw))
    size, kind = struct.unpack_from("<II", raw, 12)
    assert kind == 0x4E4F534A
    doc = json.loads(raw[20 : 20 + size])
    binary = raw[28 + size :]

    def read(i):
        a = doc["accessors"][i]
        v = doc["bufferViews"][a["bufferView"]]
        dtype = np.dtype(
            {5126: "<f4", 5123: "<u2", 5121: "u1", 5125: "<u4"}[a["componentType"]]
        )
        dim = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        return np.ndarray(
            (a["count"], dim),
            dtype,
            buffer=binary,
            offset=v.get("byteOffset", 0) + a.get("byteOffset", 0),
            strides=(v.get("byteStride", dim * dtype.itemsize), dtype.itemsize),
        )

    return doc, binary, read


def key(t):
    # Exact binary float32 coordinates for meshes with baked identity transforms.
    t = np.array(sorted(map(tuple, np.asarray(t, dtype="<f4"))), dtype="<f4")
    t[t == 0] = 0  # normalize signed zero after basis conversion
    return t.tobytes()


def main():
    doc, binary, read = read_glb(
        ROOT / "assets/tracks/monza/monza.glb"
    )
    scene = json.loads((OUT / "scene_audit.json").read_text())
    records = {r["name"]: r for r in scene["objects"]}
    names = json.loads((OUT / "triangle_objects.json").read_text())
    source = np.load(OUT / "triangles.npz")
    affected = [
        n
        for n in names
        if "kerb " in n
        or "Pit edge" in n
        or "edge line" in n
        or ("canopy" in n and n.startswith("Tribuna"))
        or n == "MONZA start bridge"
    ]
    lookup = {}
    comparison = {}
    for name in affected:
        i = names.index(name)
        p = source[f"p_{i}"]
        mi = source[f"m_{i}"]
        r = records[name]
        comparison[name] = {
            "source_triangles": len(p),
            "matched_positions": 0,
            "material_mismatches": 0,
            "normal_winding_mismatches": 0,
            "source_winding_mismatches": 0,
            "runtime_batches": set(),
        }
        for t, m in zip(p, mi):
            lookup[key(t)] = (name, t, r["materials"][m])
    issues = []
    normals = Counter()
    total = 0
    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            attrs = primitive["attributes"]
            pos = read(attrs["POSITION"])
            idx = read(primitive["indices"]).ravel()
            nn = read(attrs["NORMAL"])
            uv = read(attrs["TEXCOORD_0"])
            total += len(idx) // 3
            if not (
                np.isfinite(pos).all()
                and np.isfinite(nn).all()
                and np.isfinite(uv).all()
                and idx.max() < len(pos)
                and len(idx) % 3 == 0
                and len(pos) <= 65535
            ):
                issues.append(mesh["name"])
            p = pos[idx].reshape(-1, 3, 3)[:, :, [0, 2, 1]].copy()
            p[:, :, 1] *= -1
            n = nn[idx].reshape(-1, 3, 3)[:, :, [0, 2, 1]].copy()
            n[:, :, 1] *= -1
            mat = doc["materials"][primitive["material"]]["name"]
            for t, norm in zip(p, n):
                entry = lookup.get(key(t))
                if entry is None:
                    continue
                name, original, expected = entry
                r = comparison[name]
                r["matched_positions"] += 1
                r["material_mismatches"] += int(mat != expected)
                r["runtime_batches"].add(mesh["name"])
                geometric = np.cross(t[1] - t[0], t[2] - t[0])
                source_normal = np.cross(
                    original[1] - original[0], original[2] - original[0]
                )
                r["source_winding_mismatches"] += int(
                    np.dot(source_normal, geometric) < -1e-12
                )
                normals["compared"] += 1
                r["normal_winding_mismatches"] += int(
                    np.dot(geometric, norm[0]) < -1e-9
                )
    for r in comparison.values():
        r["runtime_batches"] = sorted(r["runtime_batches"])
    images = []
    for i, im in enumerate(doc["images"]):
        v = doc["bufferViews"][im["bufferView"]]
        data = binary[v.get("byteOffset", 0) : v.get("byteOffset", 0) + v["byteLength"]]
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        a = np.array(img)[:, :, 3]
        images.append(
            {
                "index": i,
                "size": list(img.size),
                "alpha_min": int(a.min()),
                "alpha_max": int(a.max()),
                "transparent_pixels": int((a < 255).sum()),
            }
        )
    report = {
        "meshes": len(doc["meshes"]),
        "triangles": total,
        "invalid_batches": issues,
        "materials": doc["materials"],
        "images": images,
        "samplers": doc["samplers"],
        "comparison": comparison,
        "nonidentity_nodes": [
            n
            for n in doc["nodes"]
            if any(k in n for k in ["matrix", "scale", "rotation", "translation"])
        ],
        "extensions": doc.get("extensionsUsed", []),
        "source_hash_matches": scene["hashes_before"][
            "assets/tracks/monza/monza.blend"
        ]
        == json.loads(
            (ROOT / "assets/tracks/monza/monza.json").read_text()
        )["source_sha256"],
    }
    (OUT / "export_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ["materials", "comparison"]},
            indent=2,
        )
    )
    for n, r in comparison.items():
        if (
            "Rettifilo" in n
            or r["source_triangles"] != r["matched_positions"]
            or r["material_mismatches"]
        ):
            print(n, r)


if __name__ == "__main__":
    main()
