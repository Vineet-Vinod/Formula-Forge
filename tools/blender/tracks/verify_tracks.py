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
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from generate_tracks import (ASPHALT_MAX_LUMINANCE, ASPHALT_MIN_LUMINANCE,
                             EMBANKMENT_UNDERLAY_GAP_METERS,
                             GROUND_RADIAL_STEP_METERS,
                             OFFROAD_VISUAL_CLEARANCE_METERS,
                             RUNOFF_TRANSITION_METERS, SAMPLES, TERRAIN_REACH_METERS,
                             TRACKS as TRACK_SPECS, cpp_pairs, dense_closed,
                             active_zone, bank_height, canonical_runoff_zones,
                             cpp_runoff_zones, find_crossover, length_closed,
                             interpolated_track_frame, load_course_design, loop_pose, pair_digest,
                             resample_closed, sample_stations,
                             shoulder_ground_z, spa_road_width, track_frame,
                             transform_bounds_blender_to_gltf)

# The rendered surface is piecewise planar while runtime banking is evaluated
# continuously; five centimetres is the maximum accepted approximation error.
VISIBLE_CONTACT_TOLERANCE_METERS = 0.05


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
        # A positive Blender lateral offset becomes a negative runtime lane
        # after the exported basis transform.
        bank_angles.append(-sample_stations(banks,distance,target,0.0))
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


def audit_visible_contact_surface(meta, expected, expected_widths, expected_banks,
                                  target_length, surface_offset):
    """Ray-test every longitudinal meter and every lateral meter a car can reach."""
    def projected_ground(x, y, hint):
        best = None
        for offset in range(-6, 7):
            station = (hint + offset) % SAMPLES
            next_station = (station + 1) % SAMPLES
            point, nxt = expected[station], expected[next_station]
            dx, dy = nxt[0] - point[0], nxt[1] - point[1]
            length_squared = max(0.000001, dx * dx + dy * dy)
            blend = max(0.0, min(1.0, ((x - point[0]) * dx + (y - point[1]) * dy) /
                                      length_squared))
            center_x = point[0] + dx * blend
            center_y = point[1] + dy * blend
            distance_squared = (x - center_x) ** 2 + (y - center_y) ** 2
            if best is not None and distance_squared >= best[0]:
                continue
            inverse_length = 1.0 / math.sqrt(length_squared)
            normal = (-dy * inverse_length, dx * inverse_length)
            lane = (x - center_x) * normal[0] + (y - center_y) * normal[1]
            center_z = point[2] + (nxt[2] - point[2]) * blend
            half_width = 0.5 * (expected_widths[station] +
                                (expected_widths[next_station] - expected_widths[station]) * blend)
            bank = expected_banks[station] + (
                expected_banks[next_station] - expected_banks[station]) * blend
            best = (distance_squared,
                    shoulder_ground_z(center_z, half_width, lane, 1.0, bank))
        return best[1]

    surface_names = {
        "track_surface", "track_runoff", "track_embankment",
        "terrain_infield", "terrain_verge", "terrain_outskirts",
        "gravel_runoff_zones", "grass_runoff_zones", "asphalt_runoff_zones",
    }
    vertices, polygons, owners = [], [], []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or obj.name not in surface_names:
            continue
        base = len(vertices)
        vertices.extend(tuple(obj.matrix_world @ vertex.co) for vertex in obj.data.vertices)
        for polygon in obj.data.polygons:
            polygons.append(tuple(base + index for index in polygon.vertices))
            material = (obj.data.materials[polygon.material_index].name
                        if polygon.material_index < len(obj.data.materials) else "")
            owners.append((obj.name, material))
    if not polygons:
        raise ValueError("track has no visible contact surfaces")
    bvh = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
    ray_top = max(vertex[2] for vertex in vertices) + 5.0
    ray_bottom = min(vertex[2] for vertex in vertices) - 5.0
    bridge = meta.get("bridge_contract")
    max_overburden = 0.0
    worst = None
    max_road_tessellation_error = 0.0
    grass_on_road = []
    meters_checked = int(math.ceil(target_length))
    for meter in range(meters_checked):
        phase = meter / target_length
        center, tangent = loop_pose(expected, phase)
        normal = (-tangent[1], tangent[0])
        sample = phase * SAMPLES
        index = int(math.floor(sample)) % SAMPLES
        blend = sample - math.floor(sample)
        next_index = (index + 1) % SAMPLES
        width = expected_widths[index] + (expected_widths[next_index] - expected_widths[index]) * blend
        bank = expected_banks[index] + (expected_banks[next_index] - expected_banks[index]) * blend
        half_width = width * 0.5
        lane_min = math.floor(-half_width - 5.5)
        lane_max = math.ceil(half_width + 5.5)
        for lane in range(lane_min, lane_max + 1):
            x = center[0] + normal[0] * lane
            y = center[1] + normal[1] * lane
            expected_z = surface_offset + projected_ground(x, y, index)
            origin_z = ray_top
            hit = None
            while origin_z > ray_bottom:
                location, _, polygon_index, _ = bvh.ray_cast(
                    Vector((x, y, origin_z)), Vector((0.0, 0.0, -1.0)),
                    origin_z - ray_bottom)
                if location is None:
                    break
                owner = owners[polygon_index]
                # Suzuka's lower figure-eight road legitimately passes beneath
                # the bridge deck. Ignore that known high surface and continue
                # down to the lower tire-contact plane.
                at_lower_bridge = (bridge and
                    abs(((meter - bridge["lower_distance_m"] + target_length * 0.5) %
                         target_length) - target_length * 0.5) <= 45.0)
                if at_lower_bridge and location.z - expected_z > 5.0:
                    origin_z = location.z - 0.01
                    continue
                hit = (location.z, owner)
                break
            if hit is None:
                raise ValueError(f"visible terrain hole at {meter}m lane {lane}m")
            overburden = hit[0] - expected_z
            if hit[1][0] == "track_surface":
                max_road_tessellation_error = max(max_road_tessellation_error, overburden)
            elif overburden > max_overburden:
                max_overburden = overburden
                worst = (meter, lane, hit[1][0], hit[1][1])
            if (abs(lane) <= half_width - 0.25 and hit[1][0] != "track_surface" and
                    overburden >= -0.01):
                grass_on_road.append((meter, lane, hit[1][0], hit[1][1], overburden))
    return {
        "meters_checked": meters_checked,
        "max_overburden": max_overburden,
        "max_road_tessellation_error": max_road_tessellation_error,
        "worst": worst,
        "grass_on_road": grass_on_road,
    }


def audit_road_boundary_intersections(meta, expected, expected_widths):
    """Reject folded road boundaries, except Suzuka's declared grade-separated crossover."""
    segments = []
    for side in (-1, 1):
        edge = []
        for index, point in enumerate(expected):
            _, _, normal = track_frame(expected, index)
            lateral = side * expected_widths[index] * 0.5
            edge.append((point[0] + normal[0] * lateral,
                         point[1] + normal[1] * lateral))
        segments.extend((side, index, edge[index], edge[(index + 1) % SAMPLES])
                        for index in range(SAMPLES))

    cell_size = 20.0
    buckets = {}
    for segment_index, (_, _, first, second) in enumerate(segments):
        x0, x1 = sorted((first[0], second[0]))
        y0, y1 = sorted((first[1], second[1]))
        for cell_x in range(math.floor(x0 / cell_size), math.floor(x1 / cell_size) + 1):
            for cell_y in range(math.floor(y0 / cell_size), math.floor(y1 / cell_size) + 1):
                buckets.setdefault((cell_x, cell_y), []).append(segment_index)

    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def proper_intersection(a, b, c, d):
        ab_c, ab_d = orientation(a, b, c), orientation(a, b, d)
        cd_a, cd_b = orientation(c, d, a), orientation(c, d, b)
        epsilon = 1.0e-7
        return ((ab_c > epsilon and ab_d < -epsilon) or
                (ab_c < -epsilon and ab_d > epsilon)) and (
                (cd_a > epsilon and cd_b < -epsilon) or
                (cd_a < -epsilon and cd_b > epsilon))

    bridge = meta.get("bridge_contract")
    checked = set()
    for candidates in buckets.values():
        for offset, first_index in enumerate(candidates):
            first = segments[first_index]
            for second_index in candidates[offset + 1:]:
                pair = (min(first_index, second_index), max(first_index, second_index))
                if pair in checked:
                    continue
                checked.add(pair)
                second = segments[second_index]
                station_distance = min(abs(first[1] - second[1]),
                                       SAMPLES - abs(first[1] - second[1]))
                if station_distance <= 2:
                    continue
                if bridge:
                    lower, upper = bridge["lower_station"], bridge["upper_station"]
                    first_lower = min(abs(first[1] - lower), SAMPLES - abs(first[1] - lower)) <= 30
                    first_upper = min(abs(first[1] - upper), SAMPLES - abs(first[1] - upper)) <= 30
                    second_lower = min(abs(second[1] - lower), SAMPLES - abs(second[1] - lower)) <= 30
                    second_upper = min(abs(second[1] - upper), SAMPLES - abs(second[1] - upper)) <= 30
                    if (first_lower and second_upper) or (first_upper and second_lower):
                        continue
                if proper_intersection(first[2], first[3], second[2], second[3]):
                    return (first[0], first[1], second[0], second[1])
    return None


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
    if not (16 <= geometry["mesh_objects"] <= 36 and geometry["vertices"] < 450000 and
            geometry["triangles"] < 650000 and geometry["materials"] >= 24):
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
    start_progress = spec["start_phase"] * target_length
    exact_grid_alignment = grid_slots.get("runtime_distance_alignment") == "exact_progress"
    max_grid_alignment_error = 0.0
    for slot in range(6):
        distance_behind = first_center_inset + slot * row_spacing
        if exact_grid_alignment:
            point, _, normal, index, blend = interpolated_track_frame(
                expected, start_progress - distance_behind, target_length)
            nxt_index = (index + 1) % SAMPLES
            width = expected_widths[index] + (expected_widths[nxt_index] - expected_widths[index]) * blend
            lane = (-1 if slot % 2 == 0 else 1) * min(width*0.5*0.28, 2.0)
        else:
            start_index = int(spec["start_phase"] * SAMPLES) % SAMPLES
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
    grid_alignment_tolerance = 0.05 if exact_grid_alignment else 0.002
    if max_grid_alignment_error > grid_alignment_tolerance:
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
    if (grounding["profiled_runoff_surface_offset_asset_units"] != surface_offset or
            not grounding["nearest_section_projection"] or
            grounding["blender_lateral_to_runtime_sign"] != -1 or
            not grounding["nearest_branch_bisector_clipping"] or
            grounding["branch_reach_probe_step_asset_units"] != 0.25 or
            grounding["radial_step_asset_units"] != GROUND_RADIAL_STEP_METERS or
            grounding["offroad_visual_clearance_asset_units"] != OFFROAD_VISUAL_CLEARANCE_METERS or
            ("embankment_underlay_gap_asset_units" in grounding and
             grounding["embankment_underlay_gap_asset_units"] != EMBANKMENT_UNDERLAY_GAP_METERS) or
            grounding["runoff_transition_asset_units"] != RUNOFF_TRANSITION_METERS or
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
    generic_runoff = bpy.data.objects["track_runoff"]
    runoff_rows = int(round(RUNOFF_TRANSITION_METERS / GROUND_RADIAL_STEP_METERS)) + 1
    expected_runoff_faces = SAMPLES * 2 * (runoff_rows - 1)
    if (len(generic_runoff.data.vertices) != SAMPLES * 2 * runoff_rows or
            not expected_runoff_faces * 0.90 <= len(generic_runoff.data.polygons) <= expected_runoff_faces or
            not generic_runoff.get("nearest_section_grounding")):
        raise ValueError(f"{slug}: generic runoff tessellation contract changed")
    for surface_name in ("gravel", "grass", "asphalt"):
        object_name = f"{surface_name}_runoff_zones"
        if object_name in bpy.data.objects:
            runoff = bpy.data.objects[object_name]
            if (not runoff.get("nearest_section_grounding") or
                    runoff.get("radial_step_m") != GROUND_RADIAL_STEP_METERS):
                raise ValueError(f"{slug}: {object_name} grounding contract changed")
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
    embankment_rows = int(math.ceil((TERRAIN_REACH_METERS - RUNOFF_TRANSITION_METERS) /
                                    GROUND_RADIAL_STEP_METERS)) + 1
    if (len(embankment.data.vertices) != SAMPLES * 2 * embankment_rows or
            not embankment.get("nearest_section_grounding") or
            embankment.get("radial_step_m") != GROUND_RADIAL_STEP_METERS):
        raise ValueError(f"{slug}: terrain shoulder tessellation contract changed")
    max_embankment_span = spec.get("max_embankment_longitudinal_span_m")
    if grounding.get("max_embankment_longitudinal_span_asset_units") != max_embankment_span:
        raise ValueError(f"{slug}: embankment span metadata is stale")
    if max_embankment_span is not None:
        if embankment.get("max_longitudinal_span_m") != max_embankment_span:
            raise ValueError(f"{slug}: embankment span clipping contract is stale")
        for polygon in embankment.data.polygons:
            vertices = list(polygon.vertices)
            longitudinal_span = max(
                math.dist(embankment.data.vertices[vertices[0]].co,
                          embankment.data.vertices[vertices[1]].co),
                math.dist(embankment.data.vertices[vertices[2]].co,
                          embankment.data.vertices[vertices[3]].co))
            if longitudinal_span > max_embankment_span + tolerance:
                raise ValueError(f"{slug}: grass embankment contains a {longitudinal_span:.3f}m span")
    if ("embankment_underlay_gap_asset_units" in grounding and
            embankment.get("underlay_gap_m") != EMBANKMENT_UNDERLAY_GAP_METERS):
        raise ValueError(f"{slug}: terrain underlay can z-fight with runoff surfaces")
    if "embankment_underlay_gap_asset_units" in grounding:
        minimum_runoff_separation = float("inf")
        separation_samples = 0
        for surface_name in ("gravel", "grass", "asphalt"):
            object_name = f"{surface_name}_runoff_zones"
            if object_name not in bpy.data.objects:
                continue
            runoff = bpy.data.objects[object_name]
            stride = max(1, len(runoff.data.polygons) // 400)
            for polygon_index in range(0, len(runoff.data.polygons), stride):
                polygon = runoff.data.polygons[polygon_index]
                center = polygon.center
                hit, location, _, _ = embankment.ray_cast(
                    center + Vector((0.0, 0.0, 1.0)), Vector((0.0, 0.0, -1.0)),
                    distance=3.0)
                if hit:
                    minimum_runoff_separation = min(
                        minimum_runoff_separation, center.z - location.z)
                    separation_samples += 1
        if (separation_samples == 0 or
                minimum_runoff_separation < EMBANKMENT_UNDERLAY_GAP_METERS - 0.015):
            raise ValueError(
                f"{slug}: profiled runoff overlaps the grass underlay "
                f"({minimum_runoff_separation:.4f}m separation)")
    max_embankment_ground_error = 0.0

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
        if (instance["kind"] == "vegetation" and
                "vegetation_canopy_clearance_asset_units" in grounding and
                instance.get("road_edge_clearance", -1.0) + tolerance <
                grounding["vegetation_canopy_clearance_asset_units"]):
            raise ValueError(
                f"{slug}: vegetation canopy intrudes on the road near station {index}")
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
    boundary_intersection = audit_road_boundary_intersections(meta, expected, expected_widths)
    if boundary_intersection is not None:
        raise ValueError(f"{slug}: folded/intersecting road boundary {boundary_intersection}")
    contact_audit = audit_visible_contact_surface(
        meta, expected, expected_widths, expected_banks, target_length, surface_offset)
    if contact_audit["grass_on_road"]:
        raise ValueError(f"{slug}: non-asphalt surface covers the racing surface; "
                         f"first={contact_audit['grass_on_road'][0]} "
                         f"count={len(contact_audit['grass_on_road'])} "
                         f"max_overburden={contact_audit['max_overburden']:.4f} "
                         f"worst={contact_audit['worst']}")
    if contact_audit["max_overburden"] > VISIBLE_CONTACT_TOLERANCE_METERS:
        raise ValueError(f"{slug}: visible terrain can cover the car by "
                         f"{contact_audit['max_overburden']:.4f}m at "
                         f"{contact_audit['worst']}")
    unit = meta["coordinate_unit"]
    print(f"PASS {slug:12} length={target_length:7.1f} {unit} "
          f"surface={meta['measured_surface_centerline_asset_units']:7.1f} "
          f"meshes={geometry['mesh_objects']:2} verts={geometry['vertices']:5} "
          f"materials={geometry['materials']:2} align_error={max_error:.6f} width_error={max_width_error:.6f} "
          f"ground_error={max(max_barrier_ground_error,max_prop_ground_error,max_embankment_ground_error):.6f} "
          f"contact_meters={contact_audit['meters_checked']} "
          f"edge_intersections=0 "
          f"overburden={contact_audit['max_overburden']:.6f} "
          f"road_tessellation={contact_audit['max_road_tessellation_error']:.6f} "
          f"tarmac_luma={luminance:.3f} "
          f"preview={paths['_preview.png'].stat().st_size//1024:4}KiB")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO / "assets" / "tracks")
    parser.add_argument("--track", choices=["all", *TRACK_NAMES], default="all")
    args = parser.parse_args()
    forbidden = [path for path in args.root.resolve().parent.rglob("*")
                 if path.suffix in (".blend1", ".blend2")]
    if forbidden:
        raise ValueError(f"forbidden generated artifacts: {[str(path) for path in forbidden]}")
    targets = TRACK_NAMES if args.track == "all" else (args.track,)
    for slug in targets:
        verify(args.root.resolve(), slug)


if __name__ == "__main__":
    main()
