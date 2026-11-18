"""A private blue-hour sky material for the floodlit Jeddah scene."""

from __future__ import annotations

import unreal
from circuit_materials import connect


def build_sky(path: str, recipe_hash: str) -> None:
    library = unreal.EditorAssetLibrary
    editor = unreal.MaterialEditingLibrary
    existing = unreal.load_asset(path)
    if existing is not None:
        if library.get_metadata_tag(existing, "CircuitMaterialRecipe") == recipe_hash:
            return
        if not library.delete_asset(path):
            raise RuntimeError(f"Cannot refresh Jeddah sky {path}")
    directory, name = path.rsplit("/", 1)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, directory, unreal.Material, unreal.MaterialFactoryNew()
    )
    material.set_editor_property("two_sided", True)
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("is_sky", True)
    view = editor.create_material_expression(material, unreal.MaterialExpressionCameraVectorWS)
    elevation = editor.create_material_expression(material, unreal.MaterialExpressionComponentMask)
    elevation.set_editor_property("r", False)
    elevation.set_editor_property("g", False)
    elevation.set_editor_property("b", True)
    connect(view, "", elevation, "")
    negative = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    negative.r = -1.0
    inverse = editor.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(elevation, "", inverse, "A")
    connect(negative, "", inverse, "B")
    clamp = editor.create_material_expression(material, unreal.MaterialExpressionClamp)
    connect(inverse, "", clamp, "")
    power = editor.create_material_expression(material, unreal.MaterialExpressionPower)
    exponent = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    exponent.r = .45
    connect(clamp, "", power, "Base")
    connect(exponent, "", power, "Exp")
    horizon = editor.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    horizon.constant = unreal.LinearColor(.040, .075, .130)
    zenith = editor.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    zenith.constant = unreal.LinearColor(.020, .045, .100)
    gradient = editor.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate)
    connect(horizon, "", gradient, "A")
    connect(zenith, "", gradient, "B")
    connect(power, "", gradient, "Alpha")
    editor.connect_material_property(gradient, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    editor.recompile_material(material)
    library.set_metadata_tag(material, "CircuitMaterialRecipe", recipe_hash)
    library.save_loaded_asset(material)
