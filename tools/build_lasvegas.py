"""Run through make lasvegas-assets; builds only /Game/Generated/LasVegas."""
from __future__ import annotations

import hashlib
import json

import unreal
from lasvegas_art import textures
from lasvegas_geometry import DATA, ROOT, SCRATCH, generate

ASSETS = '/Game/Generated/LasVegas'
LIBRARY = unreal.EditorAssetLibrary
EDIT = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def texture_material(name: str) -> unreal.Material:
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
    if name == 'Sphere':
        material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
        EDIT.connect_material_property(sample, 'RGB', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if name == 'Fence':
        material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_MASKED)
        material.set_editor_property('two_sided', True)
        EDIT.connect_material_property(sample, 'A', unreal.MaterialProperty.MP_OPACITY_MASK)
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
        EDIT.connect_material_property(rgb, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    value = EDIT.create_material_expression(material, unreal.MaterialExpressionConstant)
    value.r = roughness
    EDIT.connect_material_property(value, '', unreal.MaterialProperty.MP_ROUGHNESS)
    material.set_editor_property('two_sided', two_sided)
    EDIT.recompile_material(material)
    LIBRARY.save_loaded_asset(material)
    return material


def main() -> None:
    manifest = generate()
    textures(SCRATCH / 'art')
    materials = {name: texture_material(name) for name in
                 ['WallDark', 'WallGold', 'RaceSign', 'VegasSign', '50', '100', '150', 'CreamFacade',
                  'BlueFacade', 'BronzeFacade', 'Garage', 'Fence', 'Sphere', 'Bellagio', 'Venetian',
                  'Palazzo', 'Wynn', 'Paris', 'Cosmopolitan', 'Planet']}
    for name, color, roughness in [
        ('White', (.72, .73, .70), .82), ('Red', (.62, .025, .018), .8), ('Black', (.012, .015, .018), .8),
        ('Steel', (.24, .28, .30), .48), ('Cream', (.54, .49, .39), .8), ('Roof', (.12, .14, .15), .8),
        ('CityGround', (.17, .16, .135), .95), ('TowerSteel', (.27, .23, .15), .57),
        ('Trunk', (.16, .105, .055), .9), ('Leaves', (.045, .105, .025), .9),
        ('Lamp', (1.8, 1.8, 1.65), .4),
    ]:
        materials[name] = solid(name, color, roughness, emissive=name == 'Lamp', two_sided=name == 'Leaves')
    for name, path in {
        'Road': '/Game/Generated/Materials/rebuild_road_asphalt',
        'Runoff': '/Game/Generated/Materials/rebuild_runoff_asphalt',
        'Concrete': '/Game/Generated/Monza/Materials/Concrete',
        'Crowd': '/Game/Generated/Monza/Materials/circuit_original_spectators',
    }.items():
        materials[name] = unreal.load_asset(path)
        if materials[name] is None:
            raise RuntimeError(f'Missing material {path}')
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
        if name.startswith('Tile_Street'):
            ground_slots = [unreal.Name('Material_' + str(index)) for index, material in enumerate(record['materials'])
                            if material in ('Road', 'Runoff', 'CityGround', 'White', 'Red')]
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
        'artwork': 'Original geometry and procedural trackside textures; built-in image_gen produced original Sphere display artwork (art/sphere-display-v1.json). Existing licensed asphalt, concrete and original spectator atlas reused.',
        'estimates': 'OSM building tags give volume controls; missing heights use 3.4 m per level, default 3 levels. Facades, pit decks, temporary stands, palms and lighting furniture are original approximations, not a photogrammetric survey.',
    }
    (ROOT / 'Attribution/Sources/lasvegas/scenery.json').write_text(json.dumps(record, indent=2) + '\n')
    unreal.log(f'LASVEGAS_BUILT tiles={record["tiles"]} triangles={record["triangles"]}')


main()
