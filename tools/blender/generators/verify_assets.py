"""Fast structural verification for generated Formula Buggy vehicle assets."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys


GAMEPLAY_CLIPS = {"idle", "accelerate", "brake", "turn_left", "turn_right"}
ASSETS = {
    "vehicles": {
        "joint_count": 9,
        "triangle_limit": 15_000,
        "slugs": ("tidebreaker", "sunskipper", "reefrunner", "boardwalk"),
    },
    "drivers": {
        "joint_count": 7,
        "triangle_limit": 12_000,
        "slugs": ("imani_reef", "dax_calder", "marina_quill", "niko_brass",
                  "sol_vega", "bea_torque"),
    },
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    require(len(header) == 24 and header[:8] == PNG_SIGNATURE,
            f"invalid PNG header: {path}")
    require(header[12:16] == b"IHDR", f"PNG has no IHDR first chunk: {path}")
    return struct.unpack(">II", header[16:24])


def read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    require(len(data) >= 20 and data[:4] == b"glTF", f"invalid GLB header: {path}")
    _, version, declared_length = struct.unpack_from("<4sII", data)
    require(version == 2, f"unsupported GLB version {version}: {path}")
    require(declared_length == len(data), f"incorrect GLB length: {path}")

    offset = 12
    document = None
    while offset < len(data):
        require(offset + 8 <= len(data), f"truncated GLB chunk header: {path}")
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        require(offset + length <= len(data), f"truncated GLB chunk: {path}")
        if chunk_type == 0x4E4F534A:
            require(document is None, f"multiple GLB JSON chunks: {path}")
            document = json.loads(data[offset:offset + length].decode("utf-8"))
        offset += length
    require(offset == len(data) and document is not None,
            f"missing GLB JSON document: {path}")
    return document


def validate_manifest(path: Path, kind: str, slug: str, triangle_limit: int) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(manifest.get("asset") == slug, f"asset id mismatch: {path}")
    require(manifest.get("type") == kind[:-1], f"asset type mismatch: {path}")
    require(manifest.get("units") == "meters", f"non-meter asset: {path}")

    bounds = manifest.get("measured_bounds_blender", {})
    dimensions = bounds.get("dimensions", [])
    require(len(dimensions) == 3 and all(isinstance(value, (int, float)) and value > 0
                                         for value in dimensions),
            f"invalid measured dimensions: {path}")
    targets = manifest.get("target_dimensions_m", {})
    require(len(targets) == 3 and all(isinstance(value, (int, float)) and value > 0
                                      for value in targets.values()),
            f"invalid target dimensions: {path}")
    errors = [abs(measured - target) / target * 100.0
              for measured, target in zip(dimensions, targets.values())]
    tolerance = manifest.get("verification", {}).get("dimension_tolerance_percent")
    require(isinstance(tolerance, (int, float)) and 0 < tolerance <= 8.0,
            f"invalid dimension tolerance: {path}")
    require(max(errors) <= tolerance + 0.01,
            f"dimension error {max(errors):.2f}% exceeds {tolerance:.2f}%: {path}")

    budget = manifest.get("runtime_budget", {})
    require(all(isinstance(budget.get(key), int) and budget[key] > 0
                for key in ("mesh_objects", "vertices", "triangles")),
            f"invalid runtime budget: {path}")
    require(budget["triangles"] <= triangle_limit,
            f"triangle budget {budget['triangles']} exceeds {triangle_limit}: {path}")
    require(set(manifest.get("animation_clips", {})) == GAMEPLAY_CLIPS,
            f"manifest gameplay clips mismatch: {path}")
    require(manifest.get("source") == f"{slug}.blend"
            and manifest.get("export") == f"{slug}.glb"
            and manifest.get("preview") == f"{slug}_preview.png",
            f"manifest filenames mismatch: {path}")
    return manifest


def validate_asset(root: Path, kind: str, slug: str, spec: dict) -> str:
    directory = root / kind / slug
    paths = {
        "blend": directory / f"{slug}.blend",
        "glb": directory / f"{slug}.glb",
        "json": directory / f"{slug}.json",
        "png": directory / f"{slug}_preview.png",
    }
    for label, path in paths.items():
        require(path.is_file() and path.stat().st_size > 0,
                f"missing or empty {label}: {path}")
    with paths["blend"].open("rb") as stream:
        blend_magic = stream.read(7)
        require(blend_magic == b"BLENDER" or blend_magic[:4] == b"\x28\xb5\x2f\xfd",
                f"invalid blend source: {paths['blend']}")

    manifest = validate_manifest(paths["json"], kind, slug, spec["triangle_limit"])
    require(read_png_dimensions(paths["png"]) == (720, 540),
            f"preview must be 720x540: {paths['png']}")

    glb = read_glb_json(paths["glb"])
    skins = glb.get("skins", [])
    require(len(skins) == 1, f"expected exactly one skin: {paths['glb']}")
    joints = skins[0].get("joints", [])
    require(len(joints) == spec["joint_count"],
            f"expected {spec['joint_count']} joints, got {len(joints)}: {paths['glb']}")
    action_counts = Counter(animation.get("name") for animation in glb.get("animations", []))
    require(action_counts == Counter({name: 1 for name in GAMEPLAY_CLIPS}),
            f"gameplay animations must occur exactly once, got {dict(action_counts)}: {paths['glb']}")
    require(all(animation.get("channels") for animation in glb["animations"]),
            f"empty animation channels: {paths['glb']}")

    node_names = {node.get("name") for node in glb.get("nodes", [])}
    missing_nodes = set(manifest.get("required_nodes", [])) - node_names
    require(not missing_nodes, f"missing required nodes {sorted(missing_nodes)}: {paths['glb']}")
    return (f"{kind[:-1]:7} {slug:14} dims={manifest['measured_bounds_blender']['dimensions']} "
            f"tris={manifest['runtime_budget']['triangles']:5} "
            f"skin=1 joints={len(joints)} clips=5 preview=720x540")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", type=Path,
                        default=Path(__file__).resolve().parents[3] / "assets_src")
    args = parser.parse_args()

    failures = []
    checked = 0
    for kind, spec in ASSETS.items():
        expected = set(spec["slugs"])
        kind_root = args.asset_root / kind
        present = {path.name for path in kind_root.iterdir() if path.is_dir()}
        if present != expected:
            failures.append(f"{kind} inventory mismatch: expected={sorted(expected)}, present={sorted(present)}")
            continue
        for slug in spec["slugs"]:
            try:
                print(validate_asset(args.asset_root, kind, slug, spec))
                checked += 1
            except (OSError, ValueError, VerificationError, json.JSONDecodeError) as error:
                failures.append(str(error))

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print(f"PASS: {checked} assets, {checked} skins, {checked * 5} exact gameplay clips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
