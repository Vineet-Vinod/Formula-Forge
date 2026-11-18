"""Thin hospitality glazing with an explicit reflection of the authored night sky."""

from __future__ import annotations

import hashlib
from pathlib import Path

import unreal
from circuit_materials import connect


def build(assets: str) -> unreal.Material:
    library = unreal.EditorAssetLibrary
    editor = unreal.MaterialEditingLibrary
    cube = unreal.load_asset(assets + "/Environment/JeddahNightReflection")
    if not isinstance(cube, unreal.TextureCube):
        raise TypeError("Hospitality glazing requires the verified Jeddah night environment")
    fingerprint = hashlib.sha256(Path(__file__).read_bytes() +
        library.get_metadata_tag(cube, "JeddahEnvironmentSource").encode()).hexdigest()
    path = assets + "/Materials/JeddahHospitalityGlass"
    material = unreal.load_asset(path)
    if material is not None and not isinstance(material, unreal.Material):
        raise TypeError("Hospitality glass must retain its native material class")
    if material is not None and library.get_metadata_tag(material, "JeddahHospitalityGlazingSHA") == fingerprint:
        return material
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "JeddahHospitalityGlass", assets + "/Materials", unreal.Material, unreal.MaterialFactoryNew())
    if not isinstance(material, unreal.Material):
        raise TypeError("Cannot create the private hospitality glazing")
    editor.delete_all_material_expressions(material)
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("translucency_lighting_mode",
                                 unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    tint = editor.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    tint.constant = unreal.LinearColor(.045, .075, .105)
    editor.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    roughness.r = .13
    editor.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    specular = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    specular.r = .5
    editor.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)
    fresnel = editor.create_material_expression(material, unreal.MaterialExpressionFresnel)
    fresnel.set_editor_property("exponent", 5.0)
    fresnel.set_editor_property("base_reflect_fraction", .04)
    opacity = editor.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate)
    low = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    low.r = .08
    high = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    high.r = .78
    connect(low, "", opacity, "A")
    connect(high, "", opacity, "B")
    connect(fresnel, "", opacity, "Alpha")
    editor.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY)
    reflection = editor.create_material_expression(material, unreal.MaterialExpressionReflectionVectorWS)
    sky = editor.create_material_expression(material, unreal.MaterialExpressionTextureSample)
    sky.texture = cube
    sky.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    connect(reflection, "", sky, "UVs")
    reflected = editor.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(sky, "RGB", reflected, "A")
    connect(fresnel, "", reflected, "B")
    strength = editor.create_material_expression(material, unreal.MaterialExpressionConstant)
    strength.r = .65
    scaled = editor.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(reflected, "", scaled, "A")
    connect(strength, "", scaled, "B")
    # Translucent blending applies opacity afterward; preserve the reflected radiance.
    radiance = editor.create_material_expression(material, unreal.MaterialExpressionDivide)
    connect(scaled, "", radiance, "A")
    connect(opacity, "", radiance, "B")
    editor.connect_material_property(radiance, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    editor.recompile_material(material)
    library.set_metadata_tag(material, "JeddahHospitalityGlazingSHA", fingerprint)
    if not library.save_loaded_asset(material):
        raise RuntimeError("Cannot save the hospitality glass")
    return material
