"""Apply bounded native route edits, retaining original material and vertex data."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = unreal.EditorAssetLibrary
EDIT = unreal.MaterialEditingLibrary
match = re.search(r'-FFRoutePlan=(?:"([^"]+)"|(\S+))', unreal.SystemLibrary.get_command_line())
if match is None:
    raise ValueError('Pass -FFRoutePlan=<repository build plan>')
plan_path = Path(match[1] or match[2])
plan = json.loads(plan_path.read_text())
validation = json.loads(plan_path.with_suffix('.validated.json').read_text())
assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == validation['plan_sha256']
receipts = []


def material(prefix: str, slug: str, name: str) -> unreal.MaterialInterface:
    if slug == 'jeddah' and name == 'PanelJeddahPitBridgeStc':
        from venues.jeddah_early_pit_material import build

        return build(prefix)
    alias = {'Runoff': 'Lit_Runoff', 'Concrete': 'Lit_Concrete'} if slug == 'lasvegas' else {}
    paths = [prefix + '/Materials/' + alias.get(name, name), prefix + '/Materials/Route_' + name]
    for path in paths:
        found = unreal.load_asset(path)
        if isinstance(found, unreal.MaterialInterface):
            return found
    source_paths = {
        'Runoff': '/Game/Generated/Materials/rebuild_runoff_asphalt',
        'Concrete': '/Game/Generated/Monza/Materials/Concrete',
        'Fence': '/Game/Generated/Monza/Materials/Monza_main_straight_wire',
        'White': '/Game/Generated/Baku/Materials/White',
        'Steel': '/Game/Generated/Baku/Materials/Steel',
    }
    source = unreal.load_asset(source_paths[name])
    if not isinstance(source, unreal.MaterialInterface):
        raise TypeError('Missing verified route material: ' + name)
    copied = LIBRARY.duplicate_asset(source.get_path_name().split('.')[0], paths[1])
    if not isinstance(copied, unreal.MaterialInterface):
        raise TypeError('Cannot create local route material: ' + paths[1])
    if isinstance(copied, unreal.MaterialInstanceConstant):
        for parameter in EDIT.get_static_switch_parameter_names(copied):
            if str(parameter) in ('UseBakedAO', 'UseVertexColor'):
                EDIT.set_material_instance_static_switch_parameter_value(copied, parameter, False)
    LIBRARY.save_loaded_asset(copied)
    return copied


def overlaps(bounds, portals) -> bool:
    for portal in portals:
        xs = [-point[1] * 100 for point in portal['polygon_xy_m']]
        ys = [-point[0] * 100 for point in portal['polygon_xy_m']]
        if not (bounds[3] < min(xs) or bounds[0] > max(xs) or bounds[4] < min(ys) or bounds[1] > max(ys)
                or bounds[5] < portal['bottom_m'] * 100 or bounds[2] > portal['top_m'] * 100):
            return True
    return False


def clear_escape_trunks(slug: str) -> list[dict]:
    if slug != 'singapore':
        return []
    path = ROOT / 'Attribution/Sources/singapore/escape-obstacle-clearance.json'
    recipe = json.loads(path.read_text())
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    mesh = unreal.load_asset(recipe['asset'])
    if not isinstance(mesh, unreal.StaticMesh):
        raise TypeError('Missing qualified escape obstacle asset ' + recipe['asset'])
    if LIBRARY.get_metadata_tag(mesh, 'CircuitEscapeObstacleRecipe') == fingerprint:
        return []
    selected = []
    for expected in recipe['material_slots']:
        slots = [slot for slot in mesh.get_editor_property('static_materials')
                 if str(slot.material_slot_name) == expected['slot']]
        if len(slots) != 1 or slots[0].material_interface is None or slots[0].material_interface.get_path_name() != expected['material']:
            raise ValueError('Qualified escape tree slot changed')
        selected.append(unreal.Name(expected['slot']))
    count = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, True)
    if count != recipe['expected_source_facets']:
        raise ValueError('Qualified escape trunk count changed: ' + str(count))
    affected = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, False)
    if affected != count:
        raise ValueError('Escape trunk edit differs from dry-run')
    LIBRARY.set_metadata_tag(mesh, 'CircuitEscapeObstacleRecipe', fingerprint)
    assert LIBRARY.save_loaded_asset(mesh)
    unreal.log('ESCAPE_TRUNK_CLEARED ' + slug + ' ' + str(affected))
    return [{'asset': recipe['asset'], 'affected_source_triangles': affected,
             'recipe_sha256': fingerprint, 'material_slots': recipe['material_slots']}]


def open_jeddah_pit_exit(slug: str, route_fingerprint: str) -> list[dict]:
    if slug != 'jeddah':
        return []
    path = ROOT / 'Attribution/Sources/jeddah/pit-exit-architecture-opening.json'
    if not path.exists():
        return []
    recipe = json.loads(path.read_text())
    if recipe['asset'] != '/Game/Generated/Jeddah/Track/Building_City_m1_00':
        raise ValueError('Jeddah pit opening asset changed')
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    mesh = unreal.load_asset(recipe['asset'])
    if not isinstance(mesh, unreal.StaticMesh):
        raise TypeError('Missing Jeddah covered-exit mesh')
    if recipe.get('application_mode') == 'source_reconstructed_open_exit':
        source_path = ROOT / recipe['source_reconstruction_file']
        source = json.loads(source_path.read_text())
        if source_path != ROOT / 'Attribution/Sources/jeddah/pit-exit-reconstruction.json' or source['osm_id'] != 1257884698 or source['mode'] != 'open_sky_reference_variant':
            raise ValueError('Jeddah regenerated open-exit source ownership changed')
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        module_hash = hashlib.sha256((ROOT / 'tools/venues/jeddah_pit_exit.py').read_bytes()).hexdigest()
        scenery = json.loads((ROOT / 'Attribution/Sources/jeddah/scenery.json').read_text())
        qualified = [record for record in scenery['landmarks']
                     if record.get('osm_id') == 1257884698
                     and record.get('exit_roof_state') == 'open_sky_reference_variant'
                     and record.get('source_open_exit_recipe_sha256') == source_hash
                     and record.get('source_open_exit_module_sha256') == module_hash]
        if len(qualified) != 1 or not 0 < qualified[0]['removed_eastern_tip_m2'] < qualified[0]['original_footprint_m2'] * .25:
            raise ValueError('Jeddah scene lacks the finite regenerated open-exit qualification')
        manifest_folder = ROOT / 'build/circuits/jeddah'
        manifest = json.loads((manifest_folder / 'manifest.json').read_text())
        tile = next(record for record in manifest['tiles'] if record['name'] == 'Building_City_m1_00')
        packed_hash = hashlib.sha256((manifest_folder / tile['file']).read_bytes()).hexdigest()
        if packed_hash != tile['sha256'] or LIBRARY.get_metadata_tag(mesh, 'CircuitSourceSHA256') != packed_hash:
            raise ValueError('Jeddah open-exit source was not imported into the current native asset')
        return [{'asset': recipe['asset'], 'source_reconstructed_open_exit': True,
                 'recipe_sha256': fingerprint, 'source_reconstruction_sha256': source_hash,
                 'imported_source_sha256': packed_hash, 'legacy_white_cut_applied': False}]
    expected = recipe['material_slots']
    if expected != [{'slot': 'Material_3', 'material': '/Game/Generated/Jeddah/Materials/White.White'}]:
        raise ValueError('Jeddah pit opening material whitelist changed')
    slots = [slot for slot in mesh.get_editor_property('static_materials')
             if str(slot.material_slot_name) == expected[0]['slot']]
    if len(slots) != 1 or slots[0].material_interface is None or slots[0].material_interface.get_path_name() != expected[0]['material']:
        raise ValueError('Jeddah pit opening White slot changed')
    selected = [unreal.Name(expected[0]['slot'])]
    source_file = ROOT / recipe['source_asset_file']
    previous = LIBRARY.get_metadata_tag(mesh, 'CircuitJeddahPitExitRecipe')
    count = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, True)
    if previous == fingerprint:
        if count != 0:
            raise ValueError('Jeddah pit opening is not idempotent')
        return [{'asset': recipe['asset'], 'affected_source_triangles': recipe['expected_source_facets'],
                 'recipe_sha256': fingerprint, 'material_slots': expected, 'already_applied': True,
                 'sha256': hashlib.sha256(source_file.read_bytes()).hexdigest()}]
    if hashlib.sha256(source_file.read_bytes()).hexdigest() != recipe['source_asset_sha256']:
        raise ValueError('Jeddah covered-exit source asset changed')
    if count != recipe['expected_source_facets'] or count <= 0:
        raise ValueError('Jeddah pit opening dry-run count changed: ' + str(count))
    affected = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, False)
    if affected != count or unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, True) != 0:
        raise ValueError('Jeddah pit opening differs from dry-run or leaves obstructing faces')
    LIBRARY.set_metadata_tag(mesh, 'CircuitJeddahPitExitRecipe', fingerprint)
    LIBRARY.set_metadata_tag(mesh, 'CircuitRouteRecipe', route_fingerprint)
    assert LIBRARY.save_loaded_asset(mesh)
    unreal.log('JEDDAH_PIT_EXIT_OPENED ' + str(affected))
    return [{'asset': recipe['asset'], 'affected_source_triangles': affected,
             'recipe_sha256': fingerprint, 'material_slots': expected,
             'sha256': hashlib.sha256(source_file.read_bytes()).hexdigest()}]


def clear_monaco_pit_floor(slug: str) -> list[dict]:
    if slug != 'monaco':
        return []
    path = ROOT / 'Attribution/Sources/monaco/pit-floor-clearance.json'
    recipe = json.loads(path.read_text())
    if recipe['asset'] != '/Game/Generated/Monaco/Track/Building_City_00_m1' or recipe['material_slots'] != [
            {'slot': 'Material_4', 'material': '/Game/Generated/Monaco/Materials/Concrete.Concrete'}]:
        raise ValueError('Monaco pit floor asset or material whitelist changed')
    mesh = unreal.load_asset(recipe['asset'])
    if not isinstance(mesh, unreal.StaticMesh):
        raise TypeError('Missing Monaco pit floor mesh')
    expected = recipe['material_slots'][0]
    slots = [slot for slot in mesh.get_editor_property('static_materials') if str(slot.material_slot_name) == expected['slot']]
    if len(slots) != 1 or slots[0].material_interface is None or slots[0].material_interface.get_path_name() != expected['material']:
        raise ValueError('Monaco Concrete slot changed')
    selected = [unreal.Name(expected['slot'])]
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    source_file = ROOT / recipe['source_asset_file']
    count = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, True)
    if LIBRARY.get_metadata_tag(mesh, 'CircuitMonacoPitFloorRecipe') == fingerprint:
        return [{'asset': recipe['asset'], 'recipe_sha256': fingerprint, 'already_applied': True,
                 'remaining_boundary_intersections': count,
                 'sha256': hashlib.sha256(source_file.read_bytes()).hexdigest()}]
    if hashlib.sha256(source_file.read_bytes()).hexdigest() != recipe['source_asset_sha256']:
        raise ValueError('Monaco pit floor source asset changed')
    if not 0 < count <= recipe['maximum_affected_source_facets']:
        raise ValueError('Monaco pit floor dry-run count is outside the qualified scope: ' + str(count))
    affected = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, False)
    if affected != count:
        raise ValueError('Monaco pit floor cut differs from dry-run')
    remaining = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(path), selected, True)
    LIBRARY.set_metadata_tag(mesh, 'CircuitMonacoPitFloorRecipe', fingerprint)
    assert LIBRARY.save_loaded_asset(mesh)
    return [{'asset': recipe['asset'], 'affected_source_triangles': affected, 'recipe_sha256': fingerprint,
             'remaining_boundary_intersections': remaining,
             'material_slots': recipe['material_slots'], 'sha256': hashlib.sha256(source_file.read_bytes()).hexdigest()}]


for entry in plan['circuits']:
    manifest_path = ROOT / entry['manifest']
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == validation['manifest_sha256'][entry['manifest']]
    manifest = json.loads(manifest_path.read_text())
    folder = manifest_path.parent
    slug = manifest['circuit']
    fingerprint = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    directory = entry['content_dir'].removesuffix('/Data')
    directory = '' if directory == 'Data' else directory
    prefix = '/Game/Generated/' + (directory + '/' if directory else '')
    data = ROOT / 'Content/Generated' / directory / 'Data'
    index = json.loads((ROOT / entry['index']).read_text())
    materials = {name: material(prefix.rstrip('/'), slug, name) for tile in manifest['tiles'] for name in tile['materials']}
    portals = json.loads((folder / 'portals.json').read_text())['portals']
    visual_portals = json.loads((folder / 'portals.json').read_text())['portals']
    if any('native-wave1/' in source for source in manifest['source_sha256']):
        for portal in visual_portals:
            if '-pit-' in portal['id']:
                portal['top_m'] += 0.5
    visual_portal_path = folder / 'visual-portals.json'
    visual_portal_path.write_text(json.dumps({'portals': visual_portals}, indent=2) + '\n')
    cosmetic_portals = manifest.get('cosmetic_portals', [])
    cosmetic_portal_path = folder / 'exit-support-portals.json'
    if cosmetic_portals:
        cosmetic_portal_path.write_text(json.dumps({'portals': cosmetic_portals}, indent=2) + '\n')
    changed = []
    protected = {'Road', 'Asphalt', 'AsphaltLight', 'White', 'Red', 'Yellow', 'Green', 'Black', 'Water',
                 'TreeCanopy', 'Trunk', 'Leaves', 'Lit_Road', 'Canopy', 'Lamp', 'LightHalo', 'JeddahWorkingAsphalt'}
    cosmetic = {'Grass', 'Gravel', 'Ground', 'Soil', 'Pavement', 'CityGround', 'Runoff', 'Lit_Runoff',
                'RunoffGreen', 'Limestone', 'MonacoRockGround', 'MonacoNaturalGround', 'MonacoGardenLawn', 'MonacoIvyGround'}
    for record in index['assets']:
        relevant = overlaps(record['bounds'], portals)
        cosmetic_relevant = overlaps(record['bounds'], cosmetic_portals)
        paint = [p for p in manifest['paint_domains'] if overlaps(record['bounds'], [
            {'polygon_xy_m': p['polygon_xy_m'], 'bottom_m': p['bottom_m'], 'top_m': p['top_m']}])]
        if not relevant and not paint and not cosmetic_relevant:
            continue
        mesh = unreal.load_asset(record['asset'])
        if not isinstance(mesh, unreal.StaticMesh):
            raise TypeError(record['asset'])
        if LIBRARY.get_metadata_tag(mesh, 'CircuitRouteRecipe') == fingerprint:
            del mesh
            unreal.SystemLibrary.collect_garbage()
            continue
        selected = []
        for slot in record['slots']:
            if slot['material'] is None:
                raise ValueError('A native route candidate has an empty material')
            label = slot['material'].rsplit('/', 1)[-1].split('.')[0]
            lower = label.lower()
            barrier = any(word in lower for word in ('concrete', 'fence', 'steel', 'armco', 'wall', 'panel', 'rubber', 'tyre', 'racesign'))
            if label not in protected and (barrier or label in cosmetic):
                selected.append(unreal.Name(slot['slot']))
        count = 0
        if relevant and selected:
            count = unreal.FFMeshBuildLibrary.cut_tile_portals(mesh, str(visual_portal_path), selected, False)
            if count < 0:
                raise ValueError('Native portal clipping rejected ' + record['asset'])
        if cosmetic_relevant:
            terrain_slots = [unreal.Name(slot['slot']) for slot in record['slots']
                if slot['material'] is not None and
                slot['material'].rsplit('/', 1)[-1].split('.')[0] in cosmetic]
            if terrain_slots:
                affected = unreal.FFMeshBuildLibrary.cut_tile_portals(
                    mesh, str(cosmetic_portal_path), terrain_slots, False)
                if affected < 0:
                    raise ValueError('Cosmetic pit support clipping rejected ' + record['asset'])
                count += affected
        for source_name in sorted({p['source_material'] for p in paint}):
            domains = [p for p in paint if p['source_material'] == source_name]
            slots = [unreal.Name(s['slot']) for s in record['slots'] if s['material'].rsplit('/', 1)[-1].split('.')[0] == source_name]
            if not slots:
                continue
            paint_path = folder / ('paint-' + source_name + '.json')
            paint_path.write_text(json.dumps({'portals': domains}, indent=2) + '\n')
            target = material(prefix.rstrip('/'), slug, domains[0]['target_material'])
            affected = unreal.FFMeshBuildLibrary.reclassify_tile_portals(mesh, str(paint_path), slots, target, False)
            if affected < 0:
                raise ValueError('Native material correction rejected ' + record['asset'])
            count += affected
        if count:
            LIBRARY.set_metadata_tag(mesh, 'CircuitRouteRecipe', fingerprint)
            assert LIBRARY.save_loaded_asset(mesh)
            changed.append({'asset': record['asset'], 'affected_source_triangles': count})
            unreal.log('ROUTE_CLIPPED ' + slug + ' ' + record['name'] + ' ' + str(count))
        del mesh
        unreal.SystemLibrary.collect_garbage()
    rows = [line for line in (data / 'render_tiles.csv').read_text().splitlines()
            if not line.split(',')[0].startswith('Tile_Route_')]
    for tile in manifest['tiles']:
        raw_path = folder / tile['file']
        assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == tile['sha256']
        asset = prefix + 'Track/' + tile['name']
        mesh = unreal.FFLasVegasMeshLibrary.build_tile(str(raw_path), asset, [materials[name] for name in tile['materials']])
        if not isinstance(mesh, unreal.StaticMesh):
            raise TypeError('Cannot build route mesh ' + asset)
        unreal.FFMeshBuildLibrary.suppress_ground_shadow_sections(mesh, [unreal.Name('Material_' + str(i))
            for i, name in enumerate(tile['materials']) if name in ('Runoff', 'White')], 0)
        LIBRARY.set_metadata_tag(mesh, 'CircuitRouteRecipe', fingerprint)
        assert LIBRARY.save_loaded_asset(mesh)
        rows.append(tile['name'] + ',' + ','.join(f'{value:.6f}' for value in tile['bounds']))
    for filename in (manifest['pit_lane_file'], manifest['protection_file'], manifest['escape_surface_file']):
        if filename:
            shutil.copyfile(folder / filename, data / filename)
    (data / 'render_tiles.csv').write_text('\n'.join(rows) + '\n')
    trunk_edits = clear_escape_trunks(slug)
    pit_exit_edits = open_jeddah_pit_exit(slug, fingerprint)
    pit_floor_edits = clear_monaco_pit_floor(slug)
    retained_edits = []
    for record in index['assets']:
        if not overlaps(record['bounds'], portals) and not overlaps(record['bounds'], manifest['paint_domains']) and not overlaps(record['bounds'], cosmetic_portals):
            continue
        mesh = unreal.load_asset(record['asset'])
        if isinstance(mesh, unreal.StaticMesh) and LIBRARY.get_metadata_tag(mesh, 'CircuitRouteRecipe') == fingerprint:
            asset_file = ROOT / 'Content' / (record['asset'].removeprefix('/Game/') + '.uasset')
            retained_edits.append({'asset': record['asset'], 'triangles': mesh.get_num_triangles(0),
                                   'sha256': hashlib.sha256(asset_file.read_bytes()).hexdigest()})
        del mesh
        unreal.SystemLibrary.collect_garbage()
    (data / 'route_overlay.json').write_text(json.dumps({'version': 1, 'circuit': slug,
        'manifest_sha256': fingerprint, 'source_sha256': manifest['source_sha256'],
        'cosmetic_portal_count': len(cosmetic_portals),
        'native_edits': retained_edits, 'pit_architecture_edits': pit_exit_edits, 'pit_floor_edits': pit_floor_edits, 'added_route_meshes': [p['name'] for p in manifest['tiles']],
        'note': 'Finite pit/escape overlays; base authoring manifests describe the retained pre-overlay scene.'}, indent=2) + '\n')
    receipts.append({'circuit': slug, 'manifest_sha256': fingerprint, 'native_edits': changed,
                     'escape_trunk_edits': trunk_edits, 'pit_architecture_edits': pit_exit_edits, 'pit_floor_edits': pit_floor_edits,
                     'added_route_meshes': [p['name'] for p in manifest['tiles']], 'visual_acceptance': 'pending'})
    unreal.log('ROUTE_IMPORT_COMPLETE ' + slug)
    unreal.SystemLibrary.collect_garbage()
(ROOT / plan['receipt']).write_text(json.dumps({'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    'circuits': receipts, 'scope': 'Finite native portal/material edits and new route-only meshes/data. Main road data and unrelated native assets remain subject to exact delta proof and live review.'}, indent=2) + '\n')
