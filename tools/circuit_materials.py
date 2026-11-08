"""Private venue irradiance materials, using the accepted diffuse-field shader recipe."""

from __future__ import annotations

import unreal

EDIT = unreal.MaterialEditingLibrary
LIBRARY = unreal.EditorAssetLibrary


def connect(
    source: unreal.MaterialExpression,
    output: str,
    target: unreal.MaterialExpression,
    input_name: str,
) -> None:
    if not EDIT.connect_material_expressions(source, output, target, input_name):
        inputs = EDIT.get_material_expression_input_names(target)
        raise RuntimeError(
            f"Cannot connect {target.get_class().get_name()}.{input_name}; inputs={inputs}"
        )


def field_nodes(
    material: unreal.Material,
    bounds: tuple[float, float, float, float],
    texture: unreal.Texture,
) -> unreal.MaterialExpression:
    position = EDIT.create_material_expression(
        material, unreal.MaterialExpressionWorldPosition
    )
    scale = EDIT.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector
    )
    scale.constant = unreal.LinearColor(1 / bounds[2], 1 / bounds[3], 1 / 6400)
    scaled = EDIT.create_material_expression(
        material, unreal.MaterialExpressionMultiply
    )
    connect(position, "", scaled, "A")
    connect(scale, "", scaled, "B")
    offset = EDIT.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector
    )
    offset.constant = unreal.LinearColor(
        -bounds[0] / bounds[2], -bounds[1] / bounds[3], 0.5
    )
    coordinate = EDIT.create_material_expression(material, unreal.MaterialExpressionAdd)
    connect(scaled, "", coordinate, "A")
    connect(offset, "", coordinate, "B")
    xy = EDIT.create_material_expression(
        material, unreal.MaterialExpressionComponentMask
    )
    xy.set_editor_property("r", True)
    xy.set_editor_property("g", True)
    xy.set_editor_property("b", False)
    xy.set_editor_property("a", False)
    connect(coordinate, "", xy, "")
    sample = EDIT.create_material_expression(
        material, unreal.MaterialExpressionTextureSample
    )
    sample.texture = texture
    sample.set_editor_property(
        "sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
    )
    connect(xy, "", sample, "UVs")
    z = EDIT.create_material_expression(
        material, unreal.MaterialExpressionComponentMask
    )
    z.set_editor_property("r", False)
    z.set_editor_property("g", False)
    z.set_editor_property("b", True)
    z.set_editor_property("a", False)
    connect(coordinate, "", z, "")
    above = EDIT.create_material_expression(material, unreal.MaterialExpressionSubtract)
    connect(z, "", above, "A")
    connect(sample, "G", above, "B")
    fade_scale = EDIT.create_material_expression(
        material, unreal.MaterialExpressionConstant
    )
    fade_scale.r = 3.2
    fade = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(above, "", fade, "A")
    connect(fade_scale, "", fade, "B")
    inverse = EDIT.create_material_expression(
        material, unreal.MaterialExpressionOneMinus
    )
    connect(fade, "", inverse, "")
    clamp = EDIT.create_material_expression(material, unreal.MaterialExpressionClamp)
    connect(inverse, "", clamp, "")
    output = EDIT.create_material_expression(
        material, unreal.MaterialExpressionMultiply
    )
    connect(sample, "R", output, "A")
    connect(clamp, "", output, "B")
    floor = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    floor.r = (
        0.35
        if "Facade" in material.get_name()
        else 0.05
        if "PresentationSurface" in material.get_name()
        else 0.12
    )
    total = EDIT.create_material_expression(material, unreal.MaterialExpressionAdd)
    connect(output, "", total, "A")
    connect(floor, "", total, "B")
    return total


def shade(
    material: unreal.Material,
    bounds: tuple[float, float, float, float],
    texture: unreal.Texture,
) -> None:
    source = EDIT.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_BASE_COLOR
    )
    output = EDIT.get_material_property_input_node_output_name(
        material, unreal.MaterialProperty.MP_BASE_COLOR
    )
    if source is None:
        raise RuntimeError(f"Missing base color in {material.get_path_name()}")
    multiply = EDIT.create_material_expression(
        material, unreal.MaterialExpressionMultiply
    )
    connect(source, output, multiply, "A")
    connect(field_nodes(material, bounds, texture), "", multiply, "B")
    EDIT.connect_material_property(multiply, "", unreal.MaterialProperty.MP_BASE_COLOR)
    if any(
        word in material.get_name()
        for word in ("PresentationSurface", "SurfaceMasked", "Pavement", "TreeCanopy")
    ):
        strength = EDIT.create_material_expression(
            material, unreal.MaterialExpressionConstant
        )
        strength.r = (
            1.8
            if "PresentationSurface" in material.get_name()
            else 0.3
            if "SurfaceMasked" in material.get_name()
            else 0.07
        )
        bounce = EDIT.create_material_expression(
            material, unreal.MaterialExpressionMultiply
        )
        connect(multiply, "", bounce, "A")
        connect(strength, "", bounce, "B")
        EDIT.connect_material_property(
            bounce, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
        )
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)
