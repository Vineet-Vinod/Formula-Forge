"""World-aligned rock detail for Monaco's finite photographed natural masks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import unreal
from circuit_materials import connect

EDIT = unreal.MaterialEditingLibrary
LIBRARY = unreal.EditorAssetLibrary
MAPS = (
    ("diff", "c66de7f7b48ef1ba542c17af780787ca6d43da2160a46ff3544dd9fcdf65ca30"),
    ("rough", "63bb4105e6f60b5968da785afc292b94026a5afa6f18388e98b00232e9e2c433"),
    ("nor_dx", "d95f1b4972e7d83ab4b02688b28661b60b60f8991b50d4ea6e989e3221d01f47"),
)


def import_textures(root: Path, assets: str) -> dict[str, unreal.Texture2D]:
    textures: dict[str, unreal.Texture2D] = {}
    for suffix, expected in MAPS:
        name = "rock_boulder_dry_" + suffix
        source = root / "Attribution/Sources/monaco/textures/rock-boulder-dry" / (name + "_2k.jpg")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"The licensed rock texture changed: {source.name}")
        path = assets + "/Textures/" + name
        texture = unreal.load_asset(path)
        if texture is None or LIBRARY.get_metadata_tag(texture, "CircuitSourceSHA256") != expected:
            task = unreal.AssetImportTask()
            task.filename = str(source)
            task.destination_path = assets + "/Textures"
            task.destination_name = name
            task.automated = True
            task.replace_existing = True
            task.save = False
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            texture = unreal.load_asset(path)
        if not isinstance(texture, unreal.Texture2D):
            raise TypeError(f"Rock appearance requires a Texture2D: {path}")
        texture.set_editor_property("srgb", suffix == "diff")
        if suffix != "diff":
            compression = (unreal.TextureCompressionSettings.TC_NORMALMAP if suffix == "nor_dx"
                           else unreal.TextureCompressionSettings.TC_MASKS)
            texture.set_editor_property("compression_settings", compression)
        LIBRARY.set_metadata_tag(texture, "CircuitSourceSHA256", expected)
        LIBRARY.save_loaded_asset(texture)
        textures[suffix] = texture
    return textures


def constant(material: unreal.Material, value: float) -> unreal.MaterialExpression:
    node = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    node.r = value
    return node


def vector(material: unreal.Material, value: tuple[float, float, float]) -> unreal.MaterialExpression:
    node = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    node.constant = unreal.LinearColor(*value)
    return node


def world_sample(material: unreal.Material, texture: unreal.Texture2D,
                 size_cm: float, normal: bool = False) -> unreal.MaterialExpression:
    obj = EDIT.create_material_expression(material, unreal.MaterialExpressionTextureObject)
    obj.texture = texture
    if normal:
        sampler = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
    elif texture.get_editor_property("compression_settings") == unreal.TextureCompressionSettings.TC_MASKS:
        sampler = unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
    else:
        sampler = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
    obj.set_editor_property("sampler_type", sampler)
    call = EDIT.create_material_expression(material, unreal.MaterialExpressionMaterialFunctionCall)
    name = "WorldAlignedNormal" if normal else "WorldAlignedTexture"
    function = unreal.load_asset("/Engine/Functions/Engine_MaterialFunctions01/Texturing/" + name)
    if not isinstance(function, unreal.MaterialFunction):
        raise TypeError(f"Missing engine material function {name}")
    call.set_material_function(function)
    connect(obj, "", call, "TextureObject")
    connect(vector(material, (size_cm, size_cm, size_cm)), "", call, "TextureSize")
    if normal:
        flag = EDIT.create_material_expression(material, unreal.MaterialExpressionStaticBool)
        flag.set_editor_property("value", True)
        connect(flag, "", call, "WorldSpace")
    return call


def build(material: unreal.Material, textures: dict[str, unreal.Texture2D], mixed: bool) -> None:
    material.set_editor_property("tangent_space_normal", False)
    rock = world_sample(material, textures["diff"], 180)
    rough = world_sample(material, textures["rough"], 180)
    normal = world_sample(material, textures["nor_dx"], 180, normal=True)
    if mixed:
        texture = unreal.load_asset("/Game/Generated/Interlagos/Textures/infield_grass_color")
        if not isinstance(texture, unreal.Texture2D):
            raise TypeError("Missing accepted licensed grass texture")
        grass = world_sample(material, texture, 240)
        tinted = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(grass, "XYZ Texture", tinted, "A")
        connect(vector(material, (.72, .75, .56)), "", tinted, "B")
        position = EDIT.create_material_expression(material, unreal.MaterialExpressionWorldPosition)
        noise = EDIT.create_material_expression(material, unreal.MaterialExpressionNoise)
        noise.set_editor_property("scale", .003)
        noise.set_editor_property("levels", 2)
        noise.set_editor_property("quality", 1)
        noise.set_editor_property("output_min", 0.)
        noise.set_editor_property("output_max", 1.)
        connect(position, "", noise, "World Position")
        vertex_normal = EDIT.create_material_expression(material, unreal.MaterialExpressionVertexNormalWS)
        z = EDIT.create_material_expression(material, unreal.MaterialExpressionComponentMask)
        z.set_editor_property("r", False)
        z.set_editor_property("g", False)
        z.set_editor_property("b", True)
        connect(vertex_normal, "", z, "")
        slope = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(z, "", slope, "A")
        connect(z, "", slope, "B")
        vegetation = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(noise, "", vegetation, "A")
        connect(slope, "", vegetation, "B")
        color = EDIT.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate)
        connect(rock, "XYZ Texture", color, "A")
        connect(tinted, "", color, "B")
        connect(vegetation, "", color, "Alpha")
        EDIT.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
        normals = EDIT.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate)
        connect(normal, "XYZ Texture", normals, "A")
        connect(vertex_normal, "", normals, "B")
        connect(vegetation, "", normals, "Alpha")
        normalized = EDIT.create_material_expression(material, unreal.MaterialExpressionNormalize)
        connect(normals, "", normalized, "VectorInput")
        EDIT.connect_material_property(normalized, "", unreal.MaterialProperty.MP_NORMAL)
        EDIT.connect_material_property(constant(material, .96), "", unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        EDIT.connect_material_property(rock, "XYZ Texture", unreal.MaterialProperty.MP_BASE_COLOR)
        EDIT.connect_material_property(rough, "XYZ Texture", unreal.MaterialProperty.MP_ROUGHNESS)
        EDIT.connect_material_property(normal, "XYZ Texture", unreal.MaterialProperty.MP_NORMAL)
    EDIT.connect_material_property(constant(material, .18), "", unreal.MaterialProperty.MP_SPECULAR)
