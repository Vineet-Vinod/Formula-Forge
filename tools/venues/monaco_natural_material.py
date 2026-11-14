"""Mixed hillside finish using existing licensed textures; no reference-image pixels."""
from __future__ import annotations

import unreal
from circuit_materials import connect

EDIT = unreal.MaterialEditingLibrary


def build(material: unreal.Material) -> None:
    position = EDIT.create_material_expression(material, unreal.MaterialExpressionWorldPosition)
    coordinate = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    scale = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    scale.r = .00375
    connect(position, '', coordinate, 'A')
    connect(scale, '', coordinate, 'B')
    xy = EDIT.create_material_expression(material, unreal.MaterialExpressionComponentMask)
    xy.set_editor_property('r', True)
    xy.set_editor_property('g', True)
    xy.set_editor_property('b', False)
    xy.set_editor_property('a', False)
    connect(coordinate, '', xy, '')
    samples = []
    for path, tint in (
        ('/Game/Generated/Interlagos/Textures/infield_grass_color', (.70, .72, .51)),
        ('/Game/Generated/Monza/Textures/Concrete_color', (.38, .35, .24)),
    ):
        texture = unreal.load_asset(path)
        if not isinstance(texture, unreal.Texture2D):
            raise TypeError(f'Missing existing licensed texture {path}')
        sample = EDIT.create_material_expression(material, unreal.MaterialExpressionTextureSample)
        sample.texture = texture
        connect(xy, '', sample, 'UVs')
        color = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
        color.constant = unreal.LinearColor(*tint)
        tinted = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(sample, 'RGB', tinted, 'A')
        connect(color, '', tinted, 'B')
        samples.append(tinted)
    noise = EDIT.create_material_expression(material, unreal.MaterialExpressionNoise)
    noise.set_editor_property('scale', .002)
    noise.set_editor_property('levels', 2)
    noise.set_editor_property('quality', 1)
    noise.set_editor_property('output_min', 0.0)
    noise.set_editor_property('output_max', 1.0)
    connect(position, '', noise, 'World Position')
    mix = EDIT.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate)
    connect(samples[0], '', mix, 'A')
    connect(samples[1], '', mix, 'B')
    connect(noise, '', mix, 'Alpha')
    EDIT.connect_material_property(mix, '', unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    roughness.r = .98
    EDIT.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
