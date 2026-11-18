"""Use the qualified raised-panel response for the separate STC bridge face."""

import hashlib
from pathlib import Path

import unreal


def build(assets: str) -> unreal.MaterialInterface:
    editor, library = unreal.MaterialEditingLibrary, unreal.EditorAssetLibrary
    path = assets + "/Materials/PanelJeddahPitBridgeStc"
    fingerprint = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    material = unreal.load_asset(path)
    if material is not None and library.get_metadata_tag(material, "JeddahBridgeSHA") == fingerprint:
        return material
    material = material or library.duplicate_asset(assets + "/Materials/PanelJeddahEntrySalesforce", path)
    if not isinstance(material, unreal.Material):
        raise TypeError("The raised STC face requires the qualified panel material")
    base = editor.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    texture = unreal.load_asset(assets + "/Textures/PanelStc")
    if not isinstance(base, unreal.MaterialExpressionTextureSample) or not isinstance(texture, unreal.Texture):
        raise TypeError("Unexpected raised-panel graph or missing original STC texture")
    base.texture = texture
    editor.recompile_material(material)
    library.set_metadata_tag(material, "JeddahBridgeSHA", fingerprint)
    if not library.save_loaded_asset(material):
        raise RuntimeError("Cannot save the private STC bridge face")
    return material
