"""Validate generated Formula Buggy track artifacts and glTF scene contracts."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import bpy

from generate_tracks import (SAMPLES, TRACKS as TRACK_SPECS, cpp_pairs, dense_closed,
                             length_closed, loop_pose, pair_digest,
                             resample_closed, sample_stations,
                             spa_road_width, sunset_elevation, sunset_road_width,
                             transform_bounds_blender_to_gltf)


REPO = Path(__file__).resolve().parents[3]
TRACK_NAMES = ("sunset_cove", "spa", "suzuka", "silverstone", "monza", "interlagos")


def expected_centerline(slug: str):
    spec = TRACK_SPECS[slug]
    source = REPO / spec["source_file"]
    raw_controls = cpp_pairs(source, spec["centerline"])
    source_scale = spec.get("source_scale", 1.0)
    runtime_mirror = -1.0 if spec.get("runtime_mirror_y") else 1.0
    runtime_controls = [(x*source_scale, y*source_scale*runtime_mirror)
                        for x,y in raw_controls]
    dense = dense_closed(runtime_controls)
    authored_length = length_closed(dense)
    target = spec["target_length"] or authored_length
    scale = target/authored_length
    runtime_plan = resample_closed([(x*scale,y*scale) for x,y in dense], SAMPLES)
    elevations = cpp_pairs(source, spec["elevation"]) if spec.get("elevation") else []
    widths = cpp_pairs(source, spec["width_profile"]) if spec.get("width_profile") else []
    centerline, road_widths = [], []
    for index,(x,y) in enumerate(runtime_plan):
        distance = target*index/SAMPLES
        elevation = (sunset_elevation(index/SAMPLES) if slug == "sunset_cove" else
                     sample_stations(elevations,distance,target,0.0))
        centerline.append((x,-y,elevation))
        road_widths.append(sunset_road_width(index/SAMPLES) if slug == "sunset_cove" else
                           spa_road_width(index/SAMPLES) if slug == "spa" else
                           sample_stations(widths,distance,target,spec.get("width",13.0)))
    return centerline, road_widths, raw_controls, elevations, widths


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
    gltf_materials = {material.get("name") for material in gltf.get("materials", [])}
    required_materials = set(meta["required_materials"])
    if gltf_materials != required_materials:
        raise ValueError(f"{slug}: GLB materials differ: {sorted(gltf_materials ^ required_materials)}")
    non_opaque = [material.get("name") for material in gltf.get("materials", [])
                  if material.get("alphaMode", "OPAQUE") != "OPAQUE"]
    if non_opaque:
        raise ValueError(f"{slug}: world materials must remain opaque: {non_opaque}")
    target_length = meta["target_lap_length"]["value"]
    length_error = abs(meta["measured_planar_centerline_asset_units"] - target_length)
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
    root = bpy.data.objects["map_root"]
    if math.dist(tuple(root.location),(0.0,0.0,0.0)) > 1e-8 or any(abs(v) > 1e-8 for v in root.rotation_euler):
        raise ValueError(f"{slug}: map_root must remain at catalog origin with zero rotation")
    expected, expected_widths, raw_controls, elevations, widths = expected_centerline(slug)
    spec = TRACK_SPECS[slug]
    source = REPO / spec["source_file"]
    source_meta = meta["source_centerline"]
    hashes = (("control_sha256",pair_digest(raw_controls)),
              ("elevation_sha256",pair_digest(elevations) if elevations else None),
              ("width_sha256",pair_digest(widths) if widths else None))
    for key,value in hashes:
        if source_meta[key] != value:
            raise ValueError(f"{slug}: stale source hash {key}")
    surface = bpy.data.objects["track_surface"]
    if len(surface.data.vertices) != SAMPLES*2:
        raise ValueError(f"{slug}: track_surface vertex contract changed")
    max_error, max_width_error = 0.0, 0.0
    surface_offset = meta["runtime_alignment"]["road_surface_offset_above_centerline_asset_units"]
    for index,wanted in enumerate(expected):
        left = surface.data.vertices[index*2].co
        right = surface.data.vertices[index*2+1].co
        actual = ((left.x+right.x)*0.5,(left.y+right.y)*0.5,
                  (left.z+right.z)*0.5-surface_offset)
        max_error = max(max_error,math.dist(actual,wanted))
        max_width_error = max(max_width_error,abs(math.dist(left,right)-expected_widths[index]))
    if max_error > 0.002:
        raise ValueError(f"{slug}: road centerline/catalog error {max_error:.6f}")
    if max_width_error > 0.002:
        raise ValueError(f"{slug}: road width/catalog error {max_width_error:.6f}")
    width_meta = meta["road_width_asset_units"]
    if abs(width_meta["min"]-min(expected_widths)) > 0.002 or abs(width_meta["max"]-max(expected_widths)) > 0.002:
        raise ValueError(f"{slug}: road width metadata is stale")
    start_expected,forward_expected = loop_pose(expected,spec["start_phase"])
    start = meta["runtime_alignment"]["start"]
    if math.dist(start["position_blender"],start_expected) > 0.002:
        raise ValueError(f"{slug}: metadata start position is stale")
    if math.dist(start["forward_blender"],forward_expected) > 0.002:
        raise ValueError(f"{slug}: metadata start forward is stale")
    if math.dist(tuple(bpy.data.objects["start_gantry"].location),start_expected) > 0.002:
        raise ValueError(f"{slug}: gantry is not at runtime start phase")
    calculated_gltf_bounds = transform_bounds_blender_to_gltf(meta["measured_bounds_blender"])
    if calculated_gltf_bounds != meta["measured_bounds_gltf_y_up"]:
        raise ValueError(f"{slug}: glTF bounds transform metadata is stale")
    alignment = meta["runtime_alignment"]
    expected_scale = spec["cpp_simulation_units_per_asset_unit"]*0.085
    if abs(alignment["recommended_glb_uniform_scale"]-expected_scale) > 1e-8:
        raise ValueError(f"{slug}: C++ world scale metadata is stale")
    if alignment["blender_to_gltf_matrix_row_major"] != [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]:
        raise ValueError(f"{slug}: Blender/glTF basis contract changed")
    layers = alignment["opaque_layer_elevations_asset_units"]
    layer_values = [layers[name] for name in ("ocean","sand","vegetation","embankment_outer")]
    if not all(a < b for a,b in zip(layer_values,layer_values[1:])):
        raise ValueError(f"{slug}: opaque terrain layers are not strictly separated")
    for object_name,layer_name in (("ocean","ocean"),("sand_island","sand"),
                                   ("island_vegetation","vegetation")):
        layer_mesh = bpy.data.objects[object_name].data
        z_values = [vertex.co.z for vertex in layer_mesh.vertices]
        if max(abs(value-layers[layer_name]) for value in z_values) > 0.002:
            raise ValueError(f"{slug}: {object_name} elevation differs from layer contract")
        if len(layer_mesh.vertices) != 9 or len(layer_mesh.polygons) != 8 or any(len(face.vertices) != 3 for face in layer_mesh.polygons):
            raise ValueError(f"{slug}: {object_name} must remain an explicit shared-center triangle fan")
    unit = meta["coordinate_unit"]
    print(f"PASS {slug:12} length={target_length:7.1f} {unit} "
          f"surface={meta['measured_surface_centerline_asset_units']:7.1f} "
          f"meshes={geometry['mesh_objects']:2} verts={geometry['vertices']:5} "
          f"materials={geometry['materials']:2} align_error={max_error:.6f} width_error={max_width_error:.6f} "
          f"preview={paths['_preview.png'].stat().st_size//1024:4}KiB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO / "assets_src" / "tracks")
    parser.add_argument("--track", choices=["all", *TRACK_NAMES], default="all")
    args = parser.parse_args()
    forbidden = [path for path in args.root.resolve().parent.rglob("*")
                 if path.name == "__pycache__" or path.suffix in (".pyc",".blend1",".blend2")]
    forbidden += [path for path in (REPO/"tools"/"blender"/"tracks").rglob("*")
                  if path.name == "__pycache__" or path.suffix in (".pyc",".blend1",".blend2")]
    if forbidden:
        raise ValueError(f"forbidden generated artifacts: {[str(path) for path in forbidden]}")
    targets = TRACK_NAMES if args.track == "all" else (args.track,)
    for slug in targets:
        verify(args.root.resolve(), slug)


if __name__ == "__main__":
    main()
