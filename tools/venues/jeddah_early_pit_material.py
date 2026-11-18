"""Private source-sized STC faces and asphalt paint for the open pit approach."""

import hashlib
from pathlib import Path

import unreal

NAMES = ("PanelJeddahPitBridgeStc", "PanelJeddahPitStc", "JeddahPitEntryPaint")


def build(assets: str, name: str) -> unreal.MaterialInterface:
    editor, library = unreal.MaterialEditingLibrary, unreal.EditorAssetLibrary
    if name not in NAMES:
        raise ValueError(name)
    path = assets + "/Materials/" + name
    fingerprint = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    material = unreal.load_asset(path)
    if material is not None and library.get_metadata_tag(material, "JeddahBridgeSHA") == fingerprint:
        return material
    source = "Runoff" if name == "JeddahPitEntryPaint" else "PanelJeddahEntrySalesforce"
    material = material or library.duplicate_asset(assets + "/Materials/" + source, path)
    if name == "JeddahPitEntryPaint":
        if not isinstance(material, unreal.MaterialInstanceConstant):
            raise TypeError("Paint must retain the qualified asphalt parent")
        editor.set_material_instance_vector_parameter_value(material, "Tint", unreal.LinearColor(.48, .025, .17))
        editor.set_material_instance_scalar_parameter_value(material, "Roughness", .86)
    else:
        if not isinstance(material, unreal.Material):
            raise TypeError("The raised STC face requires the qualified panel material")
        base = editor.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
        texture = unreal.load_asset(assets + "/Textures/PanelStc")
        if not isinstance(base, unreal.MaterialExpressionTextureSample) or not isinstance(texture, unreal.Texture):
            raise TypeError("Unexpected raised-panel graph or missing original STC texture")
        base.texture = texture
        coordinate = editor.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate)
        red = editor.create_material_expression(material, unreal.MaterialExpressionComponentMask)
        for channel in ("r", "g", "b", "a"):
            red.set_editor_property(channel, channel == "r")
        green = editor.create_material_expression(material, unreal.MaterialExpressionComponentMask)
        for channel in ("r", "g", "b", "a"):
            green.set_editor_property(channel, channel == "g")
        fraction = editor.create_material_expression(material, unreal.MaterialExpressionFrac)
        axes = editor.create_material_expression(material, unreal.MaterialExpressionAppendVector)
        scale = editor.create_material_expression(material, unreal.MaterialExpressionConstant2Vector)
        scale.set_editor_property("r", .2)
        scale.set_editor_property("g", .7)
        offset = editor.create_material_expression(material, unreal.MaterialExpressionConstant2Vector)
        offset.set_editor_property("r", .4)
        offset.set_editor_property("g", .15)
        product = editor.create_material_expression(material, unreal.MaterialExpressionMultiply)
        shifted = editor.create_material_expression(material, unreal.MaterialExpressionAdd)
        connect = editor.connect_material_expressions
        for target in (red, green):
            connect(coordinate, "", target, "Input")
        connect(red, "", fraction, "Input")
        connect(fraction, "", axes, "A")
        connect(green, "", axes, "B")
        connect(axes, "", product, "A")
        connect(scale, "", product, "B")
        connect(product, "", shifted, "A")
        connect(offset, "", shifted, "B")
        connect(shifted, "", base, "UVs")
        editor.recompile_material(material)
    library.set_metadata_tag(material, "JeddahBridgeSHA", fingerprint)
    if not library.save_loaded_asset(material):
        raise RuntimeError("Cannot save private pit approach material")
    return material
