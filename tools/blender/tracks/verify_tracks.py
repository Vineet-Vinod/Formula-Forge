"""Validate generated Formula Forge track artifacts and glTF scene contracts."""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import bpy

from generate_tracks import (ASPHALT_MAX_LUMINANCE, ASPHALT_MIN_LUMINANCE,
                             RUNOFF_TRANSITION_METERS, SAMPLES, TERRAIN_REACH_METERS,
                             TRACKS as TRACK_SPECS, cpp_pairs, dense_closed,
                             active_zone, bank_height, canonical_runoff_zones,
                             cpp_runoff_zones, find_crossover, length_closed,
                             load_course_design, loop_pose, pair_digest,
                             resample_closed, sample_stations,
                             shoulder_ground_z, spa_road_width,
                             transform_bounds_blender_to_gltf)


REPO = Path(__file__).resolve().parents[3]
TRACK_NAMES = ("spa", "suzuka", "silverstone", "monza", "interlagos")
EXPECTED_SOURCE_PLAN_Y_REFLECTION = {
    "spa": False,
    "suzuka": True,
    "silverstone": True,
    "monza": True,
    "interlagos": True,
}


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
    banks = cpp_pairs(source, spec["bank_profile"]) if spec.get("bank_profile") else []
    centerline, road_widths, bank_angles = [], [], []
    for index,(x,y) in enumerate(runtime_plan):
        distance = target*index/SAMPLES
        elevation = sample_stations(elevations,distance,target,0.0)
        centerline.append((x,-y,elevation))
        road_widths.append(spa_road_width(index/SAMPLES) if slug == "spa" else
                           sample_stations(widths,distance,target,spec.get("width",13.0)))
        bank_angles.append(sample_stations(banks,distance,target,0.0))
    return centerline, road_widths, bank_angles, raw_controls, elevations, widths, banks


def glb_json(path: Path):
    with path.open("rb") as handle:
        magic, version, _ = struct.unpack("<4sII", handle.read(12))
        if magic != b"glTF" or version != 2:
            raise ValueError(f"{path}: not glTF 2.0")
        size, kind = struct.unpack("<I4s", handle.read(8))
        if kind != b"JSON":
            raise ValueError(f"{path}: first chunk is not JSON")
        return json.loads(handle.read(size).decode("utf-8"))


def mesh_has_edge(mesh, first: int, second: int) -> bool:
    wanted = {first, second}
    for polygon in mesh.polygons:
        vertices = list(polygon.vertices)
        for index, vertex in enumerate(vertices):
            if {vertex, vertices[(index+1) % len(vertices)]} == wanted:
                return True
    return False


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
    if not (16 <= geometry["mesh_objects"] <= 36 and geometry["vertices"] < 70000 and geometry["materials"] >= 24):
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
    expected, expected_widths, expected_banks, raw_controls, elevations, widths, banks = expected_centerline(slug)
    spec = TRACK_SPECS[slug]
    source = REPO / spec["source_file"]
    source_meta = meta["source_centerline"]
    hashes = (("control_sha256",pair_digest(raw_controls)),
              ("elevation_sha256",pair_digest(elevations) if elevations else None),
              ("width_sha256",pair_digest(widths) if widths else None),
              ("bank_sha256",pair_digest(banks) if banks else None))
    for key,value in hashes:
        if source_meta[key] != value:
            raise ValueError(f"{slug}: stale source hash {key}")
    surface = bpy.data.objects["track_surface"]
    if len(surface.data.vertices) != SAMPLES*2:
        raise ValueError(f"{slug}: track_surface vertex contract changed")
    max_error, max_width_error, max_bank_error = 0.0, 0.0, 0.0
    surface_offset = meta["runtime_alignment"]["road_surface_offset_above_centerline_asset_units"]
    for index,wanted in enumerate(expected):
        left = surface.data.vertices[index*2].co
        right = surface.data.vertices[index*2+1].co
        actual = ((left.x+right.x)*0.5,(left.y+right.y)*0.5,
                  (left.z+right.z)*0.5-surface_offset)
        max_error = max(max_error,math.dist(actual,wanted))
        planar_width = math.hypot(left.x-right.x,left.y-right.y)
        max_width_error = max(max_width_error,abs(planar_width-expected_widths[index]))
        wanted_crossfall = bank_height(expected_widths[index], expected_banks[index])
        max_bank_error = max(max_bank_error, abs((left.z-right.z)-wanted_crossfall))
    if max_error > 0.002:
        raise ValueError(f"{slug}: road centerline/catalog error {max_error:.6f}")
    if max_width_error > 0.002:
        raise ValueError(f"{slug}: road width/catalog error {max_width_error:.6f}")
    if max_bank_error > 0.002:
        raise ValueError(f"{slug}: road bank/catalog error {max_bank_error:.6f}")

    presentation = meta["presentation_contract"]
    asphalt = bpy.data.materials["asphalt"]
    asphalt_color = tuple(asphalt.diffuse_color)
    luminance = 0.2126*asphalt_color[0] + 0.7152*asphalt_color[1] + 0.0722*asphalt_color[2]
    if not ASPHALT_MIN_LUMINANCE <= luminance <= ASPHALT_MAX_LUMINANCE:
        raise ValueError(f"{slug}: asphalt luminance {luminance:.4f} is not readable")
    if abs(luminance-presentation["asphalt_relative_luminance"]) > 0.002:
        raise ValueError(f"{slug}: asphalt luminance metadata is stale")
    gltf_asphalt = next(material for material in gltf["materials"] if material.get("name") == "asphalt")
    gltf_color = gltf_asphalt["pbrMetallicRoughness"]["baseColorFactor"]
    if max(abs(gltf_color[index]-asphalt_color[index]) for index in range(4)) > 0.002:
        raise ValueError(f"{slug}: GLB asphalt color differs from BLEND")

    barrier = bpy.data.objects["continuous_safety_barriers"]
    fence = bpy.data.objects["continuous_catch_fence"]
    limits = bpy.data.objects["track_limit_lines"]
    grid_slots = bpy.data.objects["starting_grid_slots"]
    if (len(barrier.data.vertices), len(barrier.data.polygons)) != (SAMPLES*8, SAMPLES*6):
        raise ValueError(f"{slug}: continuous barrier topology changed")
    fence_posts = (SAMPLES//16)*2
    expected_fence_topology = (SAMPLES*12 + fence_posts*8,
                               SAMPLES*6 + fence_posts*6)
    if (len(fence.data.vertices), len(fence.data.polygons)) != expected_fence_topology:
        raise ValueError(f"{slug}: continuous fence topology changed")
    if (len(limits.data.vertices), len(limits.data.polygons)) != (SAMPLES*4, SAMPLES*2):
        raise ValueError(f"{slug}: track-limit line topology changed")
    if (len(grid_slots.data.vertices), len(grid_slots.data.polygons)) != (6*16, 6*4):
        raise ValueError(f"{slug}: starting grid slot topology changed")
    if grid_slots.get("slot_count") != 6 or not grid_slots.get("before_start_finish"):
        raise ValueError(f"{slug}: starting grid slot contract is stale")
    car_length = 83.6 / 17.0
    first_center_inset = car_length * 0.5 + 1.0
    row_spacing = car_length + 3.0
    start_index = int(spec["start_phase"] * SAMPLES) % SAMPLES
    max_grid_alignment_error = 0.0
    for slot in range(6):
        distance_behind = first_center_inset + slot * row_spacing
        index = int(round(start_index - distance_behind * SAMPLES / target_length)) % SAMPLES
        point = expected[index]
        _, tangent = loop_pose(expected, index/SAMPLES)
        normal = (-tangent[1], tangent[0])
        lane = (-1 if slot % 2 == 0 else 1) * min(expected_widths[index]*0.5*0.28, 2.0)
        wanted = (point[0] + normal[0]*lane, point[1] + normal[1]*lane)
        authored = grid_slots.data.vertices[slot*16:(slot+1)*16]
        actual = (sum(vertex.co.x for vertex in authored)/len(authored),
                  sum(vertex.co.y for vertex in authored)/len(authored))
        max_grid_alignment_error = max(max_grid_alignment_error, math.dist(actual,wanted))
    if max_grid_alignment_error > 0.002:
        raise ValueError(f"{slug}: starting grid slots miss runtime spawn centers by "
                         f"{max_grid_alignment_error:.6f}")
    if not presentation["barriers_continuous"] or presentation["barrier_samples_per_side"] != SAMPLES:
        raise ValueError(f"{slug}: barrier continuity metadata is stale")
    for side in range(2):
        barrier_start = side*SAMPLES*4
        if not mesh_has_edge(barrier.data, barrier_start, barrier_start+(SAMPLES-1)*4):
            raise ValueError(f"{slug}: safety barrier side {side} has an open seam")
        limit_start = side*SAMPLES*2
        if not mesh_has_edge(limits.data, limit_start, limit_start+(SAMPLES-1)*2):
            raise ValueError(f"{slug}: track-limit side {side} has an open seam")
        fence_side_stride = SAMPLES*6 + (SAMPLES//16)*8
        fence_side_start = side*fence_side_stride
        for rail in range(3):
            rail_start = fence_side_start + rail*SAMPLES*2
            if not mesh_has_edge(fence.data, rail_start, rail_start+(SAMPLES-1)*2):
                raise ValueError(f"{slug}: catch-fence side {side} rail {rail} has an open seam")

    detail_scale = 1.0
    grounding = meta["grounding_contract"]
    tolerance = grounding["tolerance_asset_units"]
    if (grounding["runoff_transition_asset_units"] != RUNOFF_TRANSITION_METERS or
            grounding["terrain_reach_asset_units"] != TERRAIN_REACH_METERS or
            not grounding["outer_edge_follows_local_centerline"]):
        raise ValueError(f"{slug}: terrain height contract is stale")
    if grounding["barrier_samples"] != SAMPLES*2:
        raise ValueError(f"{slug}: barrier grounding sample count changed")
    max_barrier_ground_error = 0.0
    course_design = load_course_design(slug)
    runtime_runoff = cpp_runoff_zones(REPO / spec["source_file"],
                                      spec["runtime_runoff_profile"])
    if canonical_runoff_zones(runtime_runoff) != canonical_runoff_zones(course_design["runoff_zones"]):
        raise ValueError(f"{slug}: Blender and runtime runoff profiles differ")
    for side_index, side in enumerate((-1, 1)):
        side_start = side_index * SAMPLES * 4
        for index, point in enumerate(expected):
            distance = target_length * index / SAMPLES
            zone = active_zone(course_design["barrier_zones"], distance, side, target_length)
            offset = float(zone.get("offset_m", 6.0)) if zone else 6.0
            lateral = expected_widths[index]*0.5 + offset*detail_scale
            wanted_z = shoulder_ground_z(point[2], expected_widths[index]*0.5,
                                         side*lateral, detail_scale, expected_banks[index])
            actual_z = barrier.data.vertices[side_start + index*4].co.z
            max_barrier_ground_error = max(max_barrier_ground_error, abs(actual_z-wanted_z))
    if max_barrier_ground_error > tolerance:
        raise ValueError(f"{slug}: safety barrier floats by {max_barrier_ground_error:.6f}")

    embankment = bpy.data.objects["track_embankment"]
    max_embankment_ground_error = 0.0
    for side_index, side in enumerate((-1, 1)):
        side_start = side_index * SAMPLES * 2
        for index, point in enumerate(expected):
            half_width = expected_widths[index] * 0.5
            for vertex_offset, distance in ((0, half_width + RUNOFF_TRANSITION_METERS),
                                            (1, half_width + TERRAIN_REACH_METERS)):
                wanted_z = shoulder_ground_z(point[2], half_width, side * distance,
                                             detail_scale, expected_banks[index])
                actual_z = embankment.data.vertices[side_start + index*2 + vertex_offset].co.z
                max_embankment_ground_error = max(max_embankment_ground_error,
                                                   abs(actual_z - wanted_z))
    if max_embankment_ground_error > tolerance:
        raise ValueError(f"{slug}: terrain shoulder differs from contact plane by "
                         f"{max_embankment_ground_error:.6f}")

    object_groups = {
        "vegetation": ("palm_groves", "park_trees", "coastal_rocks"),
        "grandstand": ("formula_grandstands",),
        "marshal": ("marshal_posts",),
        "pit": ("pit_buildings",),
    }
    max_prop_ground_error = 0.0
    for instance in grounding["instances"]:
        index = instance["station"]
        point = expected[index]
        half_width = expected_widths[index]*0.5
        lateral = instance["lateral"]
        side = instance["side"]
        expected_z = shoulder_ground_z(point[2], half_width, side*lateral, detail_scale,
                                       expected_banks[index])
        if abs(expected_z-instance["base_z"]) > tolerance:
            raise ValueError(f"{slug}: stale grounded {instance['kind']} metadata at station {index}")
        _, tangent = loop_pose(expected, index/SAMPLES)
        normal = (-tangent[1], tangent[0])
        expected_x = point[0] + normal[0]*side*lateral
        expected_y = point[1] + normal[1]*side*lateral
        candidate_errors = []
        search_radius = 4.0*detail_scale if instance["kind"] == "vegetation" else 25.0*detail_scale
        for object_name in object_groups[instance["kind"]]:
            for vertex in bpy.data.objects[object_name].data.vertices:
                if math.hypot(vertex.co.x-expected_x, vertex.co.y-expected_y) <= search_radius:
                    candidate_errors.append(abs(vertex.co.z-expected_z))
        if not candidate_errors:
            raise ValueError(f"{slug}: no grounded geometry near {instance['kind']} station {index}")
        max_prop_ground_error = max(max_prop_ground_error, min(candidate_errors))
    if max_prop_ground_error > tolerance:
        raise ValueError(f"{slug}: scenery floats by {max_prop_ground_error:.6f}")

    bridge_meta = meta["bridge_contract"]
    forbidden_landforms = [name for name in scene_names
                           if "mountain" in name.lower() or "tunnel" in name.lower()]
    if forbidden_landforms:
        raise ValueError(f"{slug}: circuit world contains obstructive landforms {forbidden_landforms}")
    if slug == "suzuka":
        if not bridge_meta:
            raise ValueError("suzuka: missing bridge contract")
        crossing = find_crossover(expected)
        if crossing["planar_distance"] > 3.0:
            raise ValueError(f"suzuka: crossover centerlines miss by {crossing['planar_distance']:.3f}m")
        for key in ("lower_station", "upper_station"):
            if bridge_meta[key] != crossing[key]:
                raise ValueError(f"suzuka: stale bridge {key}")
        bridge = bpy.data.objects["suzuka_bridge_structure"]
        upper, lower = crossing["upper_station"], crossing["lower_station"]
        catalog_bridge = spec["bridge_crossing"]
        station_tolerance = target_length/SAMPLES*1.5
        if abs(lower*target_length/SAMPLES-catalog_bridge["lower_distance_m"]) > station_tolerance:
            raise ValueError("suzuka: lower crossover station differs from catalog declaration")
        if abs(upper*target_length/SAMPLES-catalog_bridge["upper_distance_m"]) > station_tolerance:
            raise ValueError("suzuka: upper crossover station differs from catalog declaration")
        actual_clearance = ((expected[upper][2] + surface_offset - 0.62*detail_scale) -
                            (expected[lower][2] + surface_offset))
        if actual_clearance < catalog_bridge["minimum_clearance_m"]*detail_scale:
            raise ValueError(f"suzuka: bridge clearance is only {actual_clearance:.3f}")
        if abs(actual_clearance-bridge_meta["clearance_asset_units"]) > tolerance:
            raise ValueError("suzuka: bridge clearance metadata is stale")
        if not bridge.get("open_underpass") or abs(bridge["clearance_asset_units"]-actual_clearance) > tolerance:
            raise ValueError("suzuka: bridge object contract is stale")
        bridge_station_set = set(bridge_meta["embankment_open_stations"])
        if len(bridge_station_set) != 29 or upper not in bridge_station_set:
            raise ValueError("suzuka: bridge embankment opening changed")
    elif bridge_meta is not None or "suzuka_bridge_structure" in scene_names:
        raise ValueError(f"{slug}: only Suzuka may contain a crossover bridge")
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
    expected_reflection = EXPECTED_SOURCE_PLAN_Y_REFLECTION[slug]
    if bool(spec.get("runtime_mirror_y")) != expected_reflection:
        raise ValueError(f"{slug}: source-plan reflection would invert driver-visible turns")
    if alignment["source_plan_y_reflected"] != expected_reflection:
        raise ValueError(f"{slug}: source-plan reflection metadata is stale")
    expected_scale = spec["cpp_simulation_units_per_asset_unit"]*0.085
    if abs(alignment["recommended_glb_uniform_scale"]-expected_scale) > 1e-8:
        raise ValueError(f"{slug}: C++ world scale metadata is stale")
    if alignment["blender_to_gltf_matrix_row_major"] != [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]:
        raise ValueError(f"{slug}: Blender/glTF basis contract changed")
    layers = alignment["opaque_layer_elevations_asset_units"]
    layer_values = [layers[name] for name in ("outskirts","verge","infield")]
    if not all(a < b for a,b in zip(layer_values,layer_values[1:])):
        raise ValueError(f"{slug}: opaque terrain layers are not strictly separated")
    for object_name,layer_name in (("terrain_outskirts","outskirts"),("terrain_verge","verge"),
                                   ("terrain_infield","infield")):
        layer_mesh = bpy.data.objects[object_name].data
        z_values = [vertex.co.z for vertex in layer_mesh.vertices]
        if max(abs(value-layers[layer_name]) for value in z_values) > 0.002:
            raise ValueError(f"{slug}: {object_name} elevation differs from layer contract")
        expected_topology = (9,8) if object_name == "terrain_infield" else (16,16)
        if ((len(layer_mesh.vertices),len(layer_mesh.polygons)) != expected_topology or
                any(len(face.vertices) != 3 for face in layer_mesh.polygons)):
            raise ValueError(f"{slug}: {object_name} explicit non-overlap topology changed")
    unit = meta["coordinate_unit"]
    print(f"PASS {slug:12} length={target_length:7.1f} {unit} "
          f"surface={meta['measured_surface_centerline_asset_units']:7.1f} "
          f"meshes={geometry['mesh_objects']:2} verts={geometry['vertices']:5} "
          f"materials={geometry['materials']:2} align_error={max_error:.6f} width_error={max_width_error:.6f} "
          f"ground_error={max(max_barrier_ground_error,max_prop_ground_error,max_embankment_ground_error):.6f} "
          f"tarmac_luma={luminance:.3f} "
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
