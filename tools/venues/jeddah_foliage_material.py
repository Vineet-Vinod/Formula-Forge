"""Private Jeddah leaf response; preserve the accepted shared foliage assets."""

from __future__ import annotations

import hashlib
from pathlib import Path

import unreal

COLORS = {
    "JeddahPalmLeaf": (.065, .16, .035),
    "JeddahPalmLeafLight": (.105, .20, .05),
    "JeddahPalmLeafShade": (.043, .105, .025),
    "JeddahPalmBark": (.19, .135, .08),
    "JeddahPalmBarkLight": (.25, .19, .12),
}


def build(assets: str, name: str) -> unreal.MaterialInterface:
    editor, library = unreal.MaterialEditingLibrary, unreal.EditorAssetLibrary
    path = assets + "/Materials/" + name
    fingerprint = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    existing = unreal.load_asset(path)
    if existing is not None and library.get_metadata_tag(existing, "JeddahFoliageSHA") == fingerprint:
        return existing
    if name == "JeddahTreeCanopy":
        material = existing or library.duplicate_asset(assets + "/Materials/TreeCanopy", path)
        if isinstance(material, unreal.MaterialInstanceConstant):
            source_parent = material.get_editor_property("parent")
            if not isinstance(source_parent, unreal.Material):
                raise TypeError("Expected a direct canopy material parent")
            parent_path = assets + "/Materials/JeddahTreeCanopyBase"
            parent = unreal.load_asset(parent_path) or library.duplicate_asset(source_parent.get_path_name(), parent_path)
            if not isinstance(parent, unreal.Material):
                raise TypeError("Cannot create the private canopy parent")
            editor.set_material_instance_parent(material, parent)
        elif isinstance(material, unreal.Material):
            parent = material
        else:
            raise TypeError("Cannot duplicate Jeddah's canopy")
        parent.set_editor_property("tangent_space_normal", False)
        parent.set_editor_property("two_sided", True)
        normal = editor.create_material_expression(parent, unreal.MaterialExpressionVertexNormalWS)
        editor.connect_material_property(normal, "", unreal.MaterialProperty.MP_NORMAL)
        editor.recompile_material(parent)
        library.save_loaded_asset(parent)
    else:
        material = existing or unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, assets + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
        if not isinstance(material, unreal.Material):
            raise TypeError(name)
        editor.delete_all_material_expressions(material)
        color = editor.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
        color.constant = unreal.LinearColor(*COLORS[name])
        editor.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
        roughness = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
        roughness.r = .64 if "Leaf" in name else .9
        editor.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
        specular = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
        specular.r = .24
        editor.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)
        if "Leaf" in name:
            material.set_editor_property("two_sided", True)
            material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
            scattering = editor.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
            scattering.constant = unreal.LinearColor(.045, .085, .018)
            editor.connect_material_property(scattering, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
        editor.recompile_material(material)
    library.set_metadata_tag(material, "JeddahFoliageSHA", fingerprint)
    if not library.save_loaded_asset(material):
        raise RuntimeError("Cannot save " + path)
    return material
