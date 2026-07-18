"""Shared deterministic Blender helpers for Formula Buggy authored assets."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path
from typing import Iterable, Sequence

import bpy
from mathutils import Vector


ASSET_PROP = "formula_buggy_asset"


def reset_scene() -> None:
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                       bpy.data.cameras, bpy.data.lights, bpy.data.armatures,
                       bpy.data.actions):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.context.scene.render.film_transparent = False


def mark_asset(obj: bpy.types.Object) -> bpy.types.Object:
    obj[ASSET_PROP] = True
    return obj


def parent(child: bpy.types.Object, owner: bpy.types.Object) -> bpy.types.Object:
    child.parent = owner
    return child


def empty(name: str, location=(0.0, 0.0, 0.0), owner=None,
          display="PLAIN_AXES") -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_type = display
    obj.empty_display_size = 0.18
    obj.location = location
    mark_asset(obj)
    if owner:
        parent(obj, owner)
    return obj


def material(name: str, color: Sequence[float], *, metallic=0.0,
             roughness=0.48, emission=None, emission_strength=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color[:3], color[3] if len(color) > 3 else 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = mat.diffuse_color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission[:3], 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def _finish_mesh(obj, name, mat=None, owner=None, smooth=False):
    obj.name = name
    obj.data.name = f"{name}_mesh"
    mark_asset(obj)
    if mat:
        obj.data.materials.append(mat)
    if owner:
        parent(obj, owner)
    if smooth:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def cube(name: str, location, scale, mat=None, owner=None, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = _finish_mesh(bpy.context.object, name, mat, owner)
    obj.scale = (scale[0] / 2.0, scale[1] / 2.0, scale[2] / 2.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = obj.modifiers.new("soft_edges", "BEVEL")
        mod.width = min(bevel, min(scale) * 0.22)
        mod.segments = 3
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def sphere(name: str, location, scale, mat=None, owner=None, segments=24,
           rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings,
                                        location=location)
    obj = _finish_mesh(bpy.context.object, name, mat, owner, smooth=True)
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def cylinder(name: str, location, radius, depth, mat=None, owner=None,
             rotation=(0.0, 0.0, 0.0), vertices=24, bevel=0.025):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=depth, location=location,
                                        rotation=rotation)
    obj = _finish_mesh(bpy.context.object, name, mat, owner, smooth=True)
    if bevel > 0:
        mod = obj.modifiers.new("edge_round", "BEVEL")
        mod.width = min(bevel, radius * 0.2, depth * 0.1)
        mod.segments = 2
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cone(name: str, location, radius1, radius2, depth, mat=None, owner=None,
         rotation=(0.0, 0.0, 0.0), vertices=24):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1,
                                    radius2=radius2, depth=depth,
                                    location=location, rotation=rotation)
    return _finish_mesh(bpy.context.object, name, mat, owner, smooth=True)


def bar(name: str, start, end, radius, mat=None, owner=None):
    start_v, end_v = Vector(start), Vector(end)
    midpoint = (start_v + end_v) * 0.5
    direction = end_v - start_v
    obj = cylinder(name, midpoint, radius, direction.length, mat, owner,
                   vertices=16, bevel=radius * 0.35)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    return obj


def torus(name: str, location, major_radius, minor_radius, mat=None, owner=None,
          rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major_radius,
                                     minor_radius=minor_radius,
                                     major_segments=28, minor_segments=10,
                                     location=location, rotation=rotation)
    return _finish_mesh(bpy.context.object, name, mat, owner, smooth=True)


def add_wheel(pivot_name, location, radius, width, owner, tire_mat, hub_mat):
    pivot = empty(pivot_name, location, owner)
    # Cylinders are Z-aligned by default; rotate so the axle runs along X.
    tire = cylinder(f"{pivot_name}_tire", (0, 0, 0), radius, width,
                    tire_mat, pivot, rotation=(0, math.pi / 2, 0), bevel=0.04)
    cylinder(f"{pivot_name}_hub", (0, 0, 0), radius * 0.48, width * 1.04,
             hub_mat, pivot, rotation=(0, math.pi / 2, 0), bevel=0.025)
    outer_face = math.copysign(width * 0.53, location[0])
    torus(f"{pivot_name}_rim", (outer_face, 0, 0), radius * 0.72,
          radius * 0.10, hub_mat, pivot, rotation=(0, math.pi / 2, 0))
    for index in range(5):
        angle = index * math.tau / 5.0
        bar(f"{pivot_name}_spoke_{index}", (outer_face, 0, 0),
            (outer_face, radius * 0.56 * math.cos(angle),
             radius * 0.56 * math.sin(angle)),
            radius * 0.045, hub_mat, pivot)
    return pivot, tire


def animate_transform(obj, data_path: str, frames_and_values, action_name: str,
                      index=None):
    for frame, value in frames_and_values:
        if index is None:
            setattr(obj, data_path, value)
            obj.keyframe_insert(data_path=data_path, frame=frame)
        else:
            target = getattr(obj, data_path)
            target[index] = value
            obj.keyframe_insert(data_path=data_path, index=index, frame=frame)
    if obj.animation_data and obj.animation_data.action:
        obj.animation_data.action.name = action_name


def build_rigid_rig(name: str, bone_specs: dict, objects: Iterable[bpy.types.Object],
                    root_owner=None, group_for_object=None):
    """Create an armature and rigid-weight every mesh to one named bone.

    Rigid vertex groups keep authored prop meshes cheap and make the exported
    GLB a real skin, which raylib requires before it will import animations.
    """
    armature = bpy.data.armatures.new(f"{name}_data")
    rig = bpy.data.objects.new(name, armature)
    bpy.context.scene.collection.objects.link(rig)
    mark_asset(rig)
    if root_owner:
        parent(rig, root_owner)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones = {}
    for bone_name, spec in bone_specs.items():
        bone = armature.edit_bones.new(bone_name)
        bone.head = spec["head"]
        bone.tail = spec.get("tail", (spec["head"][0], spec["head"][1], spec["head"][2] + 0.2))
        bone.use_deform = spec.get("deform", True)
        parent_name = spec.get("parent")
        if parent_name:
            bone.parent = bones[parent_name]
        bones[bone_name] = bone
    bpy.ops.object.mode_set(mode="OBJECT")

    valid_bones = set(bone_specs)
    for obj in objects:
        if obj.type != "MESH":
            continue
        bone_name = group_for_object(obj) if group_for_object else next(iter(valid_bones))
        if bone_name not in valid_bones:
            bone_name = next(iter(valid_bones))
        group = obj.vertex_groups.new(name=bone_name)
        group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
        modifier = obj.modifiers.new("runtime_skin", "ARMATURE")
        modifier.object = rig
        modifier.use_vertex_groups = True
        # glTF requires the armature to be the direct parent of every skinned
        # mesh. Preserve the fully composed authored transform while replacing
        # the construction-only empty hierarchy.
        world_transform = obj.matrix_world.copy()
        obj.parent = rig
        obj.matrix_world = world_transform
    return rig


def create_rig_action(rig: bpy.types.Object, name: str, frame_range,
                      channels: Sequence[dict]):
    """Author and retain one skeletal clip as a same-named NLA track."""
    rig.animation_data_create()
    action = bpy.data.actions.new(name)
    rig.animation_data.action = action
    for channel in channels:
        bone = rig.pose.bones[channel["bone"]]
        bone.rotation_mode = channel.get("rotation_mode", "XYZ")
        path = channel.get("path", "rotation_euler")
        index = channel.get("index")
        for frame, value in channel["keys"]:
            if index is None:
                setattr(bone, path, value)
                bone.keyframe_insert(data_path=path, frame=frame,
                                     group=channel["bone"])
            else:
                getattr(bone, path)[index] = value
                bone.keyframe_insert(data_path=path, index=index, frame=frame,
                                     group=channel["bone"])
    action.frame_start, action.frame_end = frame_range
    rig.animation_data.action = None
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, int(frame_range[0]), action)
    strip.name = name
    strip.action_frame_start, strip.action_frame_end = frame_range
    return action


def configure_preview(asset_name: str, bounds, preview_path: Path,
                      camera_location=(6.4, -7.2, 4.6), target=(0, 0, 0.8)):
    ground_mat = material("preview_ground", (0.045, 0.075, 0.075, 1),
                          roughness=0.82)
    bpy.ops.mesh.primitive_plane_add(size=30,
                                     location=(0, 0, bounds["min"][2] - 0.015))
    ground = bpy.context.object
    ground.name = "PREVIEW_ground"
    ground.data.materials.append(ground_mat)

    bpy.ops.object.light_add(type="AREA", location=(4.5, -4.0, 7.0))
    key = bpy.context.object
    key.name = "PREVIEW_key"
    key.data.energy = 1100
    key.data.shape = "DISK"
    key.data.size = 5.0
    key.rotation_euler = (math.radians(22), 0, math.radians(38))
    bpy.ops.object.light_add(type="AREA", location=(-4.0, -1.0, 3.2))
    fill = bpy.context.object
    fill.name = "PREVIEW_fill"
    fill.data.energy = 650
    fill.data.color = (0.34, 0.58, 1.0)
    fill.data.size = 4.0
    bpy.ops.object.light_add(type="AREA", location=(1.0, 4.5, 4.5))
    rim = bpy.context.object
    rim.name = "PREVIEW_rim"
    rim.data.energy = 900
    rim.data.color = (1.0, 0.34, 0.13)
    rim.data.size = 3.0

    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    camera.name = "PREVIEW_camera"
    camera.data.lens = 57
    camera.data.sensor_width = 36
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    # The standalone bpy wheel exposes Eevee Next under the legacy enum.
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(preview_path)
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.world.color = (0.012, 0.020, 0.030)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.image_settings.color_depth = "8"
    scene.frame_set(1)
    bpy.ops.render.render(write_still=True)


def asset_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.get(ASSET_PROP)]


def measured_bounds(objects: Iterable[bpy.types.Object]):
    points = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        points.extend(evaluated.matrix_world @ vertex.co for vertex in evaluated.data.vertices)
    if not points:
        return {"min": [0, 0, 0], "max": [0, 0, 0], "dimensions": [0, 0, 0]}
    minimum = [min(point[i] for point in points) for i in range(3)]
    maximum = [max(point[i] for point in points) for i in range(3)]
    return {
        "min": [round(v, 4) for v in minimum],
        "max": [round(v, 4) for v in maximum],
        "dimensions": [round(maximum[i] - minimum[i], 4) for i in range(3)],
    }


def mesh_statistics(objects: Iterable[bpy.types.Object]):
    meshes = [obj for obj in objects if obj.type == "MESH"]
    triangles = 0
    vertices = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
        vertices += len(obj.data.vertices)
    return {"mesh_objects": len(meshes), "vertices": vertices,
            "triangles": triangles}


def inspect_glb(path: Path):
    """Read enough of a GLB to verify runtime-facing names and skin data."""
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise RuntimeError(f"Invalid GLB header: {path}")
    _, version, total_length = struct.unpack_from("<4sII", data, 0)
    if version != 2 or total_length != len(data):
        raise RuntimeError(f"Invalid GLB v2 length: {path}")
    json_length, json_type = struct.unpack_from("<II", data, 12)
    if json_type != 0x4E4F534A:
        raise RuntimeError(f"GLB JSON chunk missing: {path}")
    document = json.loads(data[20:20 + json_length].decode("utf-8"))
    return {
        "nodes": sorted(node.get("name", "") for node in document.get("nodes", [])),
        "actions": sorted(animation.get("name", "")
                          for animation in document.get("animations", [])),
        "action_channel_counts": {
            animation.get("name", ""): len(animation.get("channels", []))
            for animation in document.get("animations", [])
        },
        "skins": len(document.get("skins", [])),
        "meshes": len(document.get("meshes", [])),
    }


def export_asset(output_dir: Path, slug: str, metadata: dict,
                 required_nodes: Sequence[str], camera_location, target):
    output_dir.mkdir(parents=True, exist_ok=True)
    blend_path = output_dir / f"{slug}.blend"
    glb_path = output_dir / f"{slug}.glb"
    preview_path = output_dir / f"{slug}_preview.png"
    manifest_path = output_dir / f"{slug}.json"
    objects = asset_objects()
    bounds = measured_bounds(objects)
    stats = mesh_statistics(objects)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path), export_format="GLB", use_selection=True,
        export_apply=True, export_yup=True, export_cameras=False,
        export_lights=False, export_extras=True, export_animations=True,
    )

    glb = inspect_glb(glb_path)
    expected_actions = sorted(metadata.get("animation_clips", {}).keys())
    missing_nodes = sorted(set(required_nodes) - set(glb["nodes"]))
    missing_actions = sorted(set(expected_actions) - set(glb["actions"]))
    extra_actions = sorted(set(glb["actions"]) - set(expected_actions))
    target_dimensions = metadata.get("target_dimensions_m", {})
    target_values = list(target_dimensions.values())
    measured_values = bounds["dimensions"]
    dimension_error = {
        axis: round(abs(measured - target) / target * 100.0, 2)
        for axis, measured, target in zip(target_dimensions, measured_values, target_values)
    }
    max_dimension_error = max(dimension_error.values(), default=0.0)
    if (missing_nodes or missing_actions or extra_actions or glb["skins"] < 1
            or max_dimension_error > 8.0):
        raise RuntimeError(
            f"{slug} GLB verification failed: missing_nodes={missing_nodes}, "
            f"missing_actions={missing_actions}, extra_actions={extra_actions}, "
            f"skins={glb['skins']}, dimension_error={dimension_error}"
        )

    configure_preview(slug, bounds, preview_path, camera_location, target)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)

    result = {
        "schema_version": 1,
        "asset": slug,
        "units": "meters",
        "axes_blender": {"right": "+X", "front": "-Y", "up": "+Z"},
        "measured_bounds_blender": bounds,
        "runtime_budget": stats,
        "verification": {
            "status": "passed",
            "required_nodes_present": True,
            "named_actions_present": expected_actions,
            "action_channel_counts": glb["action_channel_counts"],
            "skin_count": glb["skins"],
            "exported_meshes": glb["meshes"],
            "dimension_error_percent": dimension_error,
            "dimension_tolerance_percent": 8.0,
        },
        "required_nodes": list(required_nodes),
        "source": blend_path.name,
        "export": glb_path.name,
        "preview": preview_path.name,
        **metadata,
    }
    manifest_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return blend_path, glb_path, preview_path, manifest_path
