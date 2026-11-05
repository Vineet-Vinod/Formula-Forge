"""Run through make lasvegas-assets; builds only /Game/Generated/LasVegas."""
from __future__ import annotations

import hashlib
import json

import unreal
from lasvegas_art import lightfield
from lasvegas_geometry import DATA, ROOT, SCRATCH, generate

ASSETS = '/Game/Generated/LasVegas'
LIBRARY = unreal.EditorAssetLibrary
EDIT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def connect(source: unreal.MaterialExpression, output: str, target: unreal.MaterialExpression, input_name: str) -> None:
    if not EDIT.connect_material_expressions(source, output, target, input_name):
        inputs = EDIT.get_material_expression_input_names(target)
        raise RuntimeError(f'Cannot connect {target.get_class().get_name()}.{input_name}; inputs={inputs}')


def import_texture(name: str) -> unreal.Texture:
    task = unreal.AssetImportTask()
    task.filename = str(SCRATCH / 'art' / f'{name}.png')
    task.destination_path = ASSETS + '/Textures'
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    TOOLS.import_asset_tasks([task])
    texture = unreal.load_asset(ASSETS + '/Textures/' + name)
    if name == 'Sphere':
        texture.set_editor_property('power_of_two_mode', unreal.TexturePowerOfTwoSetting.STRETCH_TO_POWER_OF_TWO)
    texture.set_editor_property('lod_group', unreal.TextureGroup.TEXTUREGROUP_WORLD)
    LIBRARY.save_loaded_asset(texture)
    return texture


def texture_material(name: str) -> unreal.Material:
    texture = import_texture(name)
    material = unreal.load_asset(ASSETS + '/Materials/' + name)
    if material is None:
        material = TOOLS.create_asset(name, ASSETS + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(material)
    sample = EDIT.create_material_expression(material, unreal.MaterialExpressionTextureSample)
    sample.texture = texture
    EDIT.connect_material_property(sample, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR)
    roughness = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    roughness.r = .55 if 'Facade' in name else .82
    EDIT.connect_material_property(roughness, '', unreal.MaterialProperty.MP_ROUGHNESS)
    if name in ('Sphere', 'LightHalo'):
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
        EDIT.connect_material_property(sample, 'RGB', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if 'Facade' in name or name == 'Garage':
        mask = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(sample, 'RGB', mask, 'A')
        connect(sample, 'A', mask, 'B')
        EDIT.connect_material_property(mask, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    elif name not in ('Sphere', 'Fence', 'Rubber', 'LightHalo'):
        glow = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        strength = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
        strength.r = .22 if not name.startswith('Wall') else .025
        connect(strength, '', glow, 'B')
        connect(sample, 'RGB', glow, 'A')
        EDIT.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if name in ('Fence', 'Rubber'):
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
        material.set_editor_property('two_sided', name == 'Fence')
        EDIT.connect_material_property(sample, 'A', unreal.MaterialProperty.MP_OPACITY_MASK)
    if name == 'Sphere':
        scale = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
        scale.r = .65
        display = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(sample, 'RGB', display, 'A')
        connect(scale, '', display, 'B')
        EDIT.connect_material_property(display, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if name == 'LightHalo':
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_ADDITIVE)
        material.set_editor_property('two_sided', True)
        view = EDIT.create_material_expression(material, unreal.MaterialExpressionCameraVectorWS)
        normal = EDIT.create_material_expression(material, unreal.MaterialExpressionPixelNormalWS)
        facing = EDIT.create_material_expression(material, unreal.MaterialExpressionDotProduct)
        connect(view, '', facing, 'A')
        connect(normal, '', facing, 'B')
        absolute = EDIT.create_material_expression(material, unreal.MaterialExpressionAbs)
        connect(facing, '', absolute, '')
        power = EDIT.create_material_expression(material, unreal.MaterialExpressionPower)
        connect(absolute, '', power, 'Base')
        exponent = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
        exponent.r = 4
        connect(exponent, '', power, 'Exp')
        tint = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
        tint.constant = unreal.LinearColor(.045, .042, .036)
        emission = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
        connect(power, '', emission, 'A')
        connect(tint, '', emission, 'B')
        EDIT.connect_material_property(emission, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        EDIT.connect_material_property(sample, 'A', unreal.MaterialProperty.MP_OPACITY)
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)
    return material


def solid(name: str, color: tuple[float, float, float], roughness: float = .8,
          emissive: bool = False, two_sided: bool = False) -> unreal.Material:
    material = unreal.load_asset(ASSETS + '/Materials/' + name)
    if material is None:
        material = TOOLS.create_asset(name, ASSETS + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    EDIT.delete_all_material_expressions(material)
    rgb = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    rgb.constant = unreal.LinearColor(*color)
    EDIT.connect_material_property(rgb, '', unreal.MaterialProperty.MP_BASE_COLOR)
    if emissive:
        if name == 'Canopy':
            glow = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
            glow.constant = unreal.LinearColor(*(channel * .18 for channel in color))
            EDIT.connect_material_property(glow, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        else:
            EDIT.connect_material_property(rgb, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    value = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    value.r = roughness
    EDIT.connect_material_property(value, '', unreal.MaterialProperty.MP_ROUGHNESS)
    material.set_editor_property('two_sided', two_sided)
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)
    return material


def night_sky() -> None:
    material = solid('NightSky', (.004, .005, .006), emissive=True, two_sided=True)
    EDIT.delete_all_material_expressions(material)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    view = EDIT.create_material_expression(material, unreal.MaterialExpressionCameraVectorWS)
    vertical = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    vertical.constant = unreal.LinearColor(0, 0, 1)
    dot = EDIT.create_material_expression(material, unreal.MaterialExpressionDotProduct)
    connect(view, '', dot, 'A')
    connect(vertical, '', dot, 'B')
    absolute = EDIT.create_material_expression(material, unreal.MaterialExpressionAbs)
    connect(dot, '', absolute, '')
    inverse = EDIT.create_material_expression(material, unreal.MaterialExpressionOneMinus)
    connect(absolute, '', inverse, '')
    falloff = EDIT.create_material_expression(material, unreal.MaterialExpressionPower)
    exponent = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    exponent.r = 8
    connect(inverse, '', falloff, 'Base')
    connect(exponent, '', falloff, 'Exp')
    tint = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    tint.constant = unreal.LinearColor(.025, .028, .029)
    glow = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(falloff, '', glow, 'A')
    connect(tint, '', glow, 'B')
    base = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    base.constant = unreal.LinearColor(.004, .005, .006)
    total = EDIT.create_material_expression(material, unreal.MaterialExpressionAdd)
    connect(base, '', total, 'A')
    connect(glow, '', total, 'B')
    EDIT.connect_material_property(total, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)


def lighting_texture() -> unreal.Texture:
    texture = import_texture('FloodlightField')
    texture.set_editor_property('srgb', False)
    texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
    texture.set_editor_property('address_x', unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)
    LIBRARY.save_loaded_asset(texture)
    return texture


def field_nodes(material: unreal.Material, bounds: tuple[float, float, float, float],
                texture: unreal.Texture) -> unreal.MaterialExpression:
    position = EDIT.create_material_expression(material, unreal.MaterialExpressionWorldPosition)
    scale = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    scale.constant = unreal.LinearColor(1 / bounds[2], 1 / bounds[3], 1 / 6400)
    scaled = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(position, '', scaled, 'A')
    connect(scale, '', scaled, 'B')
    offset = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    offset.constant = unreal.LinearColor(-bounds[0] / bounds[2], -bounds[1] / bounds[3], .5)
    coordinate = EDIT.create_material_expression(material, unreal.MaterialExpressionAdd)
    connect(scaled, '', coordinate, 'A')
    connect(offset, '', coordinate, 'B')
    xy = EDIT.create_material_expression(material, unreal.MaterialExpressionComponentMask)
    xy.set_editor_property('r', True)
    xy.set_editor_property('g', True)
    xy.set_editor_property('b', False)
    xy.set_editor_property('a', False)
    connect(coordinate, '', xy, '')
    sample = EDIT.create_material_expression(material, unreal.MaterialExpressionTextureSample)
    sample.texture = texture
    sample.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
    connect(xy, '', sample, 'UVs')
    z = EDIT.create_material_expression(material, unreal.MaterialExpressionComponentMask)
    z.set_editor_property('r', False)
    z.set_editor_property('g', False)
    z.set_editor_property('b', True)
    z.set_editor_property('a', False)
    connect(coordinate, '', z, '')
    above = EDIT.create_material_expression(material, unreal.MaterialExpressionSubtract)
    connect(z, '', above, 'A')
    connect(sample, 'G', above, 'B')
    fade_scale = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    fade_scale.r = 3.2
    fade = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(above, '', fade, 'A')
    connect(fade_scale, '', fade, 'B')
    inverse = EDIT.create_material_expression(material, unreal.MaterialExpressionOneMinus)
    connect(fade, '', inverse, '')
    clamp = EDIT.create_material_expression(material, unreal.MaterialExpressionClamp)
    connect(inverse, '', clamp, '')
    output = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(sample, 'R', output, 'A')
    connect(clamp, '', output, 'B')
    floor = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    floor.r = .06
    total = EDIT.create_material_expression(material, unreal.MaterialExpressionAdd)
    connect(output, '', total, 'A')
    connect(floor, '', total, 'B')
    return total


def shade(material: unreal.Material, bounds: tuple[float, float, float, float], texture: unreal.Texture) -> None:
    source = EDIT.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    output = EDIT.get_material_property_input_node_output_name(material, unreal.MaterialProperty.MP_BASE_COLOR)
    if source is None:
        raise RuntimeError(f'Missing base color in {material.get_path_name()}')
    multiply = EDIT.create_material_expression(material, unreal.MaterialExpressionMultiply)
    connect(source, output, multiply, 'A')
    connect(field_nodes(material, bounds, texture), '', multiply, 'B')
    EDIT.connect_material_property(multiply, '', unreal.MaterialProperty.MP_BASE_COLOR)
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)


def night_copy(name: str, source: unreal.MaterialInterface, bounds: tuple[float, float, float, float],
               texture: unreal.Texture) -> unreal.MaterialInterface:
    path = ASSETS + '/Materials/Night_' + name
    result = unreal.load_asset(path)
    if result is None:
        result = TOOLS.duplicate_asset('Night_' + name, ASSETS + '/Materials', source)
        if isinstance(result, unreal.MaterialInstanceConstant):
            parent = night_copy(source.parent.get_name(), source.parent, bounds, texture)
            EDIT.set_material_instance_parent(result, parent)
        elif isinstance(result, unreal.Material):
            shade(result, bounds, texture)
        else:
            raise RuntimeError(f'Cannot copy material {source.get_path_name()}')
        LIBRARY.save_loaded_asset(result)
    return result


def main() -> None:
    manifest = generate()
    bounds = lightfield(SCRATCH / 'art')
    field = lighting_texture()
    if '-FFLasVegasReuseMaterials' in unreal.SystemLibrary.get_command_line():
        materials = {}
        for tile in manifest['tiles']:
            for name in tile['materials']:
                asset = 'Night_' + name if name in ('Road', 'Runoff', 'Concrete', 'Crowd') else name
                materials[name] = unreal.load_asset(ASSETS + '/Materials/' + asset)
                if materials[name] is None:
                    raise RuntimeError(f'Missing material {asset}; run make lasvegas-assets first')
    else:
        materials = {name: texture_material(name) for name in
                     ['WallDark', 'WallBlue', 'WallPink', 'WallGold', 'RaceSign', 'VegasSign', '50', '100', '150', 'CreamFacade',
                      'BlueFacade', 'BronzeFacade', 'Garage', 'Fence', 'Rubber', 'LightHalo', 'Sphere', 'Bellagio', 'Venetian',
                      'Palazzo', 'Wynn', 'Paris', 'Cosmopolitan', 'Planet']}
        for name, color, roughness in [
            ('Glass', (.055, .085, .105), .25), ('White', (.72, .73, .70), .82), ('Red', (.62, .025, .018), .8), ('Black', (.012, .015, .018), .8),
            ('Steel', (.24, .28, .30), .48), ('Cream', (.54, .49, .39), .8), ('Roof', (.12, .14, .15), .8),
            ('CityGround', (.17, .16, .135), .95), ('TowerSteel', (.27, .23, .15), .57),
            ('Trunk', (.16, .105, .055), .9), ('Leaves', (.045, .105, .025), .9),
            ('Brick', (.34, .16, .08), .85), ('Copper', (.055, .22, .17), .7),
            ('Canopy', (.65, .66, .62), .8), ('IlluminatedCream', (.55, .41, .23), .7),
            ('WheelLight', (1.8, .6, 3.0), .5),
            ('Lamp', (12, 12, 11), .4),
        ]:
            materials[name] = solid(name, color, roughness, emissive=name in ('Lamp', 'IlluminatedCream', 'TowerSteel', 'Canopy', 'WheelLight'), two_sided=name == 'Leaves')
        night_sky()
        for name, path in {
            'Road': '/Game/Generated/Materials/rebuild_road_asphalt',
            'Runoff': '/Game/Generated/Materials/rebuild_runoff_asphalt',
            'Concrete': '/Game/Generated/Monza/Materials/Concrete',
            'Crowd': '/Game/Generated/Monza/Materials/circuit_original_spectators',
        }.items():
            source = unreal.load_asset(path)
            if source is None:
                raise RuntimeError(f'Missing material {path}')
            materials[name] = night_copy(name, source, bounds, field)
        for name, material in materials.items():
            if name not in ('Sphere', 'Lamp', 'WheelLight', 'LightHalo') and isinstance(material, unreal.Material) and not material.get_name().startswith('Night_'):
                shade(material, bounds, field)
    lines = []
    for record in manifest['tiles']:
        name = record['name']
        path = ASSETS + '/Track/' + name
        mesh = unreal.load_asset(path) if LIBRARY.does_asset_exist(path) else None
        if mesh is None or LIBRARY.get_metadata_tag(mesh, 'LasVegasSourceSHA256') != record['sha256']:
            mesh = unreal.FFLasVegasMeshLibrary.build_tile(str(SCRATCH / record['file']), path,
                                                         [materials[key] for key in record['materials']])
        if mesh is None:
            raise RuntimeError(f'Failed to build {name}')
        for index, key in enumerate(record['materials']):
            mesh.set_material(index, materials[key])
        if name.startswith('Tile_Street'):
            ground_slots = [unreal.Name('Material_' + str(index)) for index, material in enumerate(record['materials'])
                            if material in ('Road', 'Runoff', 'CityGround', 'White', 'Red', 'Rubber', 'Black', 'Steel', 'Lamp', 'LightHalo')]
            unreal.FFMeshBuildLibrary.suppress_ground_shadow_sections(mesh, ground_slots)
        LIBRARY.set_metadata_tag(mesh, 'LasVegasSourceSHA256', record['sha256'])
        LIBRARY.save_loaded_asset(mesh)
        lines.append(name + ',' + ','.join(f'{bound:.3f}' for bound in record['bounds']))
        unreal.log(f'LASVEGAS_TILE {name} triangles={record["triangles"]}')
    (DATA / 'render_tiles.csv').write_text('\n'.join(lines) + '\n')
    # Las Vegas owns its level. Scenery is streamed by FFPresentation from the manifest.
    level_path = ASSETS + '/Review'
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not LIBRARY.does_asset_exist(level_path):
        levels.new_level(level_path)
    else:
        levels.load_level(level_path)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode', unreal.load_class(None, '/Script/FormulaForge.FormulaTrialGameMode'))
    levels.save_current_level()
    record = {
        'recipe': 'make lasvegas-assets', 'scope': ASSETS, 'source_manifest': 'scenery_sources.json',
        'road_sha256': hashlib.sha256((DATA / 'drive_surface.bin').read_bytes()).hexdigest(),
        'terrain_sha256': hashlib.sha256((DATA / 'terrain.bin').read_bytes()).hexdigest(),
        'tiles': len(manifest['tiles']), 'triangles': sum(tile['triangles'] for tile in manifest['tiles']),
        'landmarks': manifest['landmarks'],
        'artwork': 'Original geometry and typeset signs; original built-in image_gen facade and Sphere artwork with retained prompts. See facade-art.json and art/sphere-display-v1.json. Existing licensed asphalt, concrete and original spectator atlas reused through Las Vegas-only material copies.',
        'night_lighting': {'fixture_count': len((DATA / 'night_lights.csv').read_text().splitlines()),
                           'field_resolution': 2048, 'height_fade_m': 20,
                           'method': 'Static diffuse falloff field in Las Vegas surface materials, with directional shading, specular and vehicle shadows. Venue lighting is an approximation; not a path-traced or surveyed light installation.'},
        'estimates': 'OSM building tags give volume controls; missing heights use 3.4 m per level, default 3 levels. Facades, pit decks, temporary stands, palms and lighting furniture are original approximations, not a photogrammetric survey.',
    }
    (ROOT / 'Attribution/Sources/lasvegas/scenery.json').write_text(json.dumps(record, indent=2) + '\n')
    unreal.log(f'LASVEGAS_BUILT tiles={record["tiles"]} triangles={record["triangles"]}')


if __name__ == '__main__':
    main()
