import csv
from pathlib import Path

import unreal

levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assets = unreal.AssetToolsHelpers.get_asset_tools()
materials = unreal.MaterialEditingLibrary


def surface(name: str, color: tuple[float, float, float], roughness: float, emissive: bool = False) -> unreal.Material:
    path = '/Game/FrontendArt/' + name
    material = unreal.load_asset(path)
    if material is None:
        material = assets.create_asset(name, '/Game/FrontendArt', unreal.Material, unreal.MaterialFactoryNew())
    materials.delete_all_material_expressions(material)
    tint = materials.create_material_expression(material, unreal.MaterialExpressionConstant3Vector)
    tint.set_editor_property('constant', unreal.LinearColor(*color, 1.0))
    materials.connect_material_property(tint, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR if emissive else unreal.MaterialProperty.MP_BASE_COLOR)
    value = materials.create_material_expression(material, unreal.MaterialExpressionConstant)
    value.set_editor_property('r', roughness)
    materials.connect_material_property(value, '', unreal.MaterialProperty.MP_ROUGHNESS)
    materials.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def mesh(label: str, asset: str, location: tuple[float, float, float], scale: tuple[float, float, float], material: unreal.Material | None = None) -> unreal.StaticMeshActor:
    actor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*location))
    actor.set_actor_label('Garage_' + label)
    component = actor.static_mesh_component
    component.set_static_mesh(unreal.load_asset(asset))
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    if material is not None:
        component.set_material(0, material)
    return actor


if not unreal.EditorAssetLibrary.does_asset_exist('/Game/Frontend'):
    levels.new_level('/Game/Frontend')
else:
    levels.load_level('/Game/Frontend')
for actor in actors.get_all_level_actors():
    if actor.get_actor_label().startswith('Garage_'):
        actors.destroy_actor(actor)

floor = surface('Floor', (.024, .026, .032), .30)
wall = surface('Wall', (.011, .013, .019), .55)
platform = surface('Platform', (.045, .048, .058), .27)
red = surface('RedLight', (5.0, .025, .045), .3, True)
cube = '/Engine/BasicShapes/Cube'
cylinder = '/Engine/BasicShapes/Cylinder'
mesh('Floor', cube, (0, 0, -30), (35, 35, .3), floor)
mesh('PodiumEdge', cylinder, (0, 0, -12), (8.85, 8.85, .08), red)
mesh('Podium', cylinder, (0, 0, -6), (8.7, 8.7, .12), platform)
mesh('BackWall', cube, (-650, 0, 430), (.3, 32, 9), wall)
for index, y in enumerate(range(-1200, 1201, 300)):
    mesh(f'Panel{index}', cube, (-626, y, 390), (.12, 2.85, 7.4), platform)
    mesh(f'Strip{index}', cube, (-616, y - 110, 450), (.025, .045, 6.4), red)
mesh('FloorStrip', cube, (-570, 0, -13), (.05, 30, .03), red)
mesh('Car', '/Game/Generated/Car/Body', (0, 0, 0), (1, 1, 1))
mounts = Path(unreal.Paths.project_content_dir()) / 'Generated/Data/wheel_mounts.csv'
with mounts.open() as source:
    for name, row in zip(('WheelFL', 'WheelFR', 'WheelRL', 'WheelRR'), csv.reader(source)):
        mesh(name, '/Game/Generated/Car/' + name, tuple(float(value) for value in row), (1, 1, 1))

for label, position, intensity, color in (
    ('Key', (350, -350, 850), 18000, (1.0, .94, .90)),
    ('Fill', (100, 650, 500), 12000, (.80, .88, 1.0)),
    ('Rim', (-450, -150, 500), 8000, (1.0, .025, .04)),
):
    light = actors.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(*position))
    light.set_actor_label('Garage_' + label)
    light.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*position), unreal.Vector(0, 0, 35)), False)
    component = light.get_component_by_class(unreal.SpotLightComponent)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_intensity(intensity)
    component.set_light_color(unreal.LinearColor(*color, 1.0))
    component.set_editor_property('attenuation_radius', 3000)
    component.set_editor_property('inner_cone_angle', 45)
    component.set_editor_property('outer_cone_angle', 70)
    component.set_editor_property('source_radius', 50)

sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 600))
sky.set_actor_label('Garage_SoftFill')
component = sky.get_component_by_class(unreal.SkyLightComponent)
component.set_mobility(unreal.ComponentMobility.MOVABLE)
component.set_editor_property('source_type', unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
component.set_editor_property('cubemap', unreal.load_asset('/Game/Generated/Environment/Daylight'))
component.set_intensity(.35)

key = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 900), unreal.Rotator(-40, 140, 0))
key.set_actor_label('Garage_Overhead')
component = key.get_component_by_class(unreal.DirectionalLightComponent)
component.set_mobility(unreal.ComponentMobility.MOVABLE)
component.set_intensity(2.8)
component.set_light_color(unreal.LinearColor(1.0, .96, .93, 1.0))

camera = actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(1050, -1300, 650))
camera.set_actor_label('Garage_Camera')
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(), unreal.Vector(-260, -200, 70)), False)
camera.camera_component.set_field_of_view(44)
camera.camera_component.set_editor_property('constrain_aspect_ratio', False)
post = actors.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector())
post.set_actor_label('Garage_Exposure')
post.set_editor_property('unbound', True)
settings = post.get_editor_property('settings')
for key, value in {'override_auto_exposure_method': True, 'auto_exposure_method': unreal.AutoExposureMethod.AEM_MANUAL,
                   'override_auto_exposure_apply_physical_camera_exposure': True, 'auto_exposure_apply_physical_camera_exposure': False,
                   'override_bloom_intensity': True, 'bloom_intensity': .12,
                   'override_vignette_intensity': True, 'vignette_intensity': .25}.items():
    settings.set_editor_property(key, value)
post.set_editor_property('settings', settings)
levels.save_current_level()
print('Native Unreal Ferrari garage ready')
