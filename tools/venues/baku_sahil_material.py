"""A separate Sahil leaf material; accepted foliage assets remain source inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal

from venues.baku_sahil_dataclasses import SahilMaterialSource

EDIT = unreal.MaterialEditingLibrary
LIBRARY = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
RECIPE_SHA256 = "466160b01970c2fa3d2cee89595ac87915344fa1226ed44f87360636d7a85378"
PARAMETER_ARRAYS = (
    "scalar_parameter_values",
    "vector_parameter_values",
    "double_vector_parameter_values",
    "texture_parameter_values",
    "texture_collection_parameter_values",
    "parameter_collection_parameter_values",
    "runtime_virtual_texture_parameter_values",
    "sparse_volume_texture_parameter_values",
    "font_parameter_values",
    "user_scene_texture_overrides",
)


def instance_state(instance: unreal.MaterialInstanceConstant) -> dict[str, str]:
    for name in PARAMETER_ARRAYS[:-1]:
        for parameter in instance.get_editor_property(name):
            info = parameter.get_editor_property("parameter_info")
            if info.association != unreal.MaterialParameterAssociation.GLOBAL_PARAMETER:
                raise ValueError(
                    "Sahil accepted foliage unexpectedly has layer-scoped parameters"
                )
    state = {
        name: json.dumps(
            [value.export_text() for value in instance.get_editor_property(name)]
        )
        for name in PARAMETER_ARRAYS
    }
    for name in (
        "base_property_overrides",
        "lightmass_settings",
        "nanite_override_material",
    ):
        state[name] = instance.get_editor_property(name).export_text()
    for name in (
        "phys_material",
        "phys_material_mask",
        "subsurface_profile",
        "override_subsurface_profile",
        "override_specular_profile",
        "override_toon_profile",
        "override_phys_material",
        "override_blendable_location",
        "override_blendable_priority",
        "blendable_location_override",
        "blendable_priority_override",
    ):
        value = instance.get_editor_property(name)
        state[name] = (
            value.get_path_name() if isinstance(value, unreal.Object) else str(value)
        )
    for name in ("override_specular_profile", "override_toon_profile"):
        if instance.get_editor_property(name):
            raise ValueError(
                "Sahil accepted foliage unexpectedly overrides a lighting profile"
            )
    state["effective_static_switches"] = json.dumps(
        {
            str(name): EDIT.get_material_instance_static_switch_parameter_value(
                instance, name
            )
            for name in EDIT.get_static_switch_parameter_names(instance)
        },
        sort_keys=True,
    )
    return state


def validate_parent(source: unreal.Material, target: unreal.Material) -> None:
    if target.get_editor_property("tangent_space_normal"):
        raise ValueError("Sahil canopy requires world-space shading normals")
    node = EDIT.get_material_property_input_node(
        target, unreal.MaterialProperty.MP_NORMAL
    )
    if not isinstance(node, unreal.MaterialExpressionVertexNormalWS):
        raise TypeError("Sahil canopy Normal must use VertexNormalWS")
    for name in (
        "two_sided",
        "blend_mode",
        "shading_model",
        "opacity_mask_clip_value",
        "cast_ray_traced_shadows",
        "cast_dynamic_shadow_as_masked",
    ):
        if target.get_editor_property(name) != source.get_editor_property(name):
            raise ValueError(f"Sahil canopy changed accepted material property {name}")
    properties = [
        name
        for name in dir(unreal.MaterialProperty)
        if name.startswith("MP_") and name not in ("MP_NORMAL", "MP_MAX")
    ]
    if not properties:
        raise RuntimeError("Unreal material property inventory is unavailable")
    for name in properties:
        prop = getattr(unreal.MaterialProperty, name)
        old = EDIT.get_material_property_input_node(source, prop)
        new = EDIT.get_material_property_input_node(target, prop)
        old_output = EDIT.get_material_property_input_node_output_name(source, prop)
        new_output = EDIT.get_material_property_input_node_output_name(target, prop)
        if ((old.get_name() if old else None), old_output) != (
            (new.get_name() if new else None),
            new_output,
        ):
            raise ValueError(f"Sahil canopy changed accepted connection {name}")


def build(root: Path, assets: str) -> unreal.MaterialInstanceConstant:
    if assets != "/Game/Generated/Baku":
        raise ValueError("The Sahil canopy material is scoped to Baku")
    recipe = (
        root / "Attribution/Sources/baku/khagani/canopy-material.json"
    ).read_bytes()
    if hashlib.sha256(recipe).hexdigest() != RECIPE_SHA256:
        raise ValueError("Sahil material recipe needs renewed source qualification")
    # The source generator validates this hash-bound authored recipe with Pydantic.
    source = SahilMaterialSource(**json.loads(recipe))
    protected = (
        (source.accepted_parent_asset, source.parent_sha256),
        (source.accepted_instance_asset, source.instance_sha256),
        (source.accepted_atlas_asset, source.atlas_sha256),
        (source.neutral_normal_asset, source.normal_sha256),
    )
    for asset, expected in protected:
        path = root / "Content" / (asset.removeprefix("/Game/") + ".uasset")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Sahil accepted material input changed: {asset}")
    parent = unreal.load_asset(source.accepted_parent_asset)
    accepted = unreal.load_asset(source.accepted_instance_asset)
    actual = unreal.load_asset(source.actual_instance_asset)
    if (
        not isinstance(parent, unreal.Material)
        or not isinstance(accepted, unreal.MaterialInstanceConstant)
        or not isinstance(actual, unreal.MaterialInstanceConstant)
    ):
        raise TypeError(
            "Sahil canopy requires its versioned accepted material and instances"
        )
    for instance in (accepted, actual):
        if instance.get_editor_property("parent") != parent:
            raise ValueError("Sahil accepted leaf instance parent changed")
    state = instance_state(actual)
    if state != instance_state(accepted):
        raise ValueError(
            "Actual Baku foliage parameter arrays/base overrides differ from accepted source"
        )
    actual_path = (
        root
        / "Content"
        / (source.actual_instance_asset.removeprefix("/Game/") + ".uasset")
    )
    actual_sha = hashlib.sha256(actual_path.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256(recipe + Path(__file__).read_bytes()).hexdigest()
    folder = assets + "/Materials"
    material_path = folder + "/" + source.target_instance_name
    parent_path = folder + "/" + source.target_parent_name
    material = unreal.load_asset(material_path)
    private_parent = unreal.load_asset(parent_path)
    if (
        material is not None
        and LIBRARY.get_metadata_tag(material, "BakuSahilMaterialRecipe") != fingerprint
    ):
        if not LIBRARY.delete_asset(material_path):
            raise RuntimeError("Cannot refresh the private Sahil leaf instance")
        material = None
    if (
        private_parent is not None
        and LIBRARY.get_metadata_tag(private_parent, "BakuSahilMaterialRecipe")
        != fingerprint
    ):
        if material is not None:
            raise ValueError("Sahil material and private parent receipts disagree")
        if not LIBRARY.delete_asset(parent_path):
            raise RuntimeError("Cannot refresh the private Sahil leaf parent")
        private_parent = None
    if private_parent is None:
        private_parent = TOOLS.duplicate_asset(
            source.target_parent_name, folder, parent
        )
        if not isinstance(private_parent, unreal.Material):
            raise TypeError("Cannot duplicate the accepted Sahil parent")
        private_parent.set_editor_property("tangent_space_normal", False)
        normal = EDIT.create_material_expression(
            private_parent, unreal.MaterialExpressionVertexNormalWS
        )
        if not EDIT.connect_material_property(
            normal, "", unreal.MaterialProperty.MP_NORMAL
        ):
            raise RuntimeError("Cannot connect Sahil world-space crown normals")
        EDIT.recompile_material(private_parent)
    if not isinstance(private_parent, unreal.Material):
        raise TypeError("Invalid private Sahil leaf parent")
    validate_parent(parent, private_parent)
    if material is None:
        material = TOOLS.duplicate_asset(source.target_instance_name, folder, actual)
        if not isinstance(material, unreal.MaterialInstanceConstant):
            raise TypeError("Cannot duplicate actual accepted Baku leaf instance")
        EDIT.set_material_instance_parent(material, private_parent)
    if not isinstance(material, unreal.MaterialInstanceConstant):
        raise TypeError("Invalid Sahil leaf instance")
    if (
        material.get_editor_property("parent") != private_parent
        or instance_state(material) != state
    ):
        raise ValueError(
            "Sahil leaf instance did not preserve complete accepted parameter arrays"
        )
    for asset in (private_parent, material):
        if LIBRARY.get_metadata_tag(asset, "BakuSahilMaterialRecipe") != fingerprint:
            LIBRARY.set_metadata_tag(asset, "BakuSahilMaterialRecipe", fingerprint)
            LIBRARY.save_loaded_asset(asset)
    if hashlib.sha256(actual_path.read_bytes()).hexdigest() != actual_sha:
        raise ValueError("Sahil material construction changed accepted Baku foliage")
    for asset, expected in protected:
        path = root / "Content" / (asset.removeprefix("/Game/") + ".uasset")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                f"Sahil material construction changed accepted input: {asset}"
            )
    return material
