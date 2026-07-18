"""Validate generated Formula Buggy track artifacts and glTF scene contracts."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import bpy


REPO = Path(__file__).resolve().parents[3]
TRACKS = ("sunset_cove", "spa", "suzuka", "silverstone", "monza", "interlagos")


def glb_json(path: Path):
    with path.open("rb") as handle:
        magic, version, _ = struct.unpack("<4sII", handle.read(12))
        if magic != b"glTF" or version != 2:
            raise ValueError(f"{path}: not glTF 2.0")
        size, kind = struct.unpack("<I4s", handle.read(8))
        if kind != b"JSON":
            raise ValueError(f"{path}: first chunk is not JSON")
        return json.loads(handle.read(size).decode("utf-8"))


def verify(root: Path, slug: str):
    folder = root / slug
    paths = {ext: folder / f"{slug}{ext}" for ext in (".json", ".glb", ".blend", "_preview.png")}
    missing = [str(path) for path in paths.values() if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise ValueError(f"{slug}: missing/empty artifacts: {missing}")
    meta = json.loads(paths[".json"].read_text(encoding="utf-8"))
    gltf = glb_json(paths[".glb"])
    node_names = {node.get("name") for node in gltf.get("nodes", [])}
    absent = set(meta["required_nodes"]) - node_names
    if absent:
        raise ValueError(f"{slug}: GLB missing nodes {sorted(absent)}")
    length_error = abs(meta["measured_planar_centerline_m"] - meta["target_lap_length_m"])
    # The exported ribbon is a 1,024-sample render mesh; exact authored target
    # length remains in metadata while chord approximation stays below 2 m.
    if length_error > 2.0:
        raise ValueError(f"{slug}: planar length error {length_error:.3f}m")
    geometry = meta["runtime_geometry"]
    if not (8 <= geometry["mesh_objects"] <= 20 and geometry["vertices"] < 30000 and geometry["materials"] >= 10):
        raise ValueError(f"{slug}: unexpected geometry budget {geometry}")
    if paths["_preview.png"].stat().st_size < 20000:
        raise ValueError(f"{slug}: preview appears blank or trivial")
    with paths["_preview.png"].open("rb") as preview:
        signature = preview.read(24)
    if signature[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", signature[16:24]) != (1024, 768):
        raise ValueError(f"{slug}: preview is not the authored 1024x768 PNG")
    bpy.ops.wm.open_mainfile(filepath=str(paths[".blend"]), load_ui=False)
    scene_names = {obj.name for obj in bpy.context.scene.objects}
    if absent := set(meta["required_nodes"]) - scene_names:
        raise ValueError(f"{slug}: BLEND missing nodes {sorted(absent)}")
    blend_meshes = [obj for obj in bpy.context.scene.objects
                    if obj.type == "MESH" and not obj.name.startswith("PREVIEW_")]
    if len(blend_meshes) != geometry["mesh_objects"]:
        raise ValueError(f"{slug}: BLEND mesh count differs from metadata")
    if bpy.context.scene.unit_settings.system != "METRIC":
        raise ValueError(f"{slug}: BLEND does not use metric units")
    print(f"PASS {slug:12} length={meta['target_lap_length_m']:7.1f}m "
          f"surface={meta['measured_surface_centerline_m']:7.1f}m "
          f"meshes={geometry['mesh_objects']:2} verts={geometry['vertices']:5} "
          f"materials={geometry['materials']:2} preview={paths['_preview.png'].stat().st_size//1024:4}KiB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO / "assets_src" / "tracks")
    parser.add_argument("--track", choices=["all", *TRACKS], default="all")
    args = parser.parse_args()
    targets = TRACKS if args.track == "all" else (args.track,)
    for slug in targets:
        verify(args.root.resolve(), slug)


if __name__ == "__main__":
    main()
