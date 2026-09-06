# Building and validating circuit maps

Use this workflow for new circuits and map revisions in Formula Forge. Monza is the worked example. Commands below run from the repository root and use the existing Monza tools; another circuit needs its own source data and integration.

The accuracy target is the road, kerbs, runoff and first protective barrier at aerial-reference scale. If a chicane escape has no barrier, keep it open. Reconstruct the surroundings beyond the barriers as closely as the available sources allow. Record estimates and deliberate game-specific exceptions, such as Monza's closed pit access.

Follow [AGENTS.md](AGENTS.md). Map work must not silently retune handling, speed, gears, drivability or core gameplay. Fix geometry and export problems at their source. Keep generated assets reproducible and commit the source changes with their exports.

## 1. Gather and record sources

Start with official circuit documents, confirm the visible layout against aerial images, then use OSM for additional geographic detail. Choose a documented configuration; it does not have to be the newest year. Record imagery capture dates and document revisions so conflicting observations can be explained.

| Source | Use it for | Limits |
| --- | --- | --- |
| FIA event documents, circuit maps and race director notes | Configuration, numbered turns, pit layout, escape/rejoin routes, event-specific barriers and instructions | A schematic map is not a surveyed drawing. Event notes do not necessarily supply elevation or camber. |
| Circuit operator and official championship pages | Lap length, direction, named corners, published dimensions and rebuilding history | Check whether dimensions describe the selected configuration. |
| Regional or national orthophotos, GIS portals and WMS imagery | Road edges, kerb extents, gravel/asphalt/grass boundaries, first protection lines and structure footprints | Trees and shadows can conceal barriers. Pixel size does not establish positional accuracy. |
| Google Maps aerial views and Street View, or dated ground photographs | Confirm ambiguous openings, barrier types, bridge clearance, stand orientation and visible construction | Coverage and dates vary. Perspective images do not directly measure terrain height. Record the specific observation and location. |
| OpenStreetMap API snapshots and relations | Initial centreline, roads, buildings, grandstands, woods, service paths and historic layouts | Missing features are not evidence of absence. Do not generate all runoff and barriers from OSM road offsets. |
| Published engineering survey, terrain model or LiDAR | Elevation, grade separation and terrain where the data resolves them | Inspect vertical datum, resolution and capture date. A broad terrain model may not resolve road crown or kerb profiles. |

FIA documents plus confirmatory aerial imagery are the normal starting point for layout accuracy. Supplement them where a specific feature remains unresolved. Do not claim that a height came from FIA documentation unless that document actually measures it. Monza's current elevation, crossfall and several construction dimensions remain estimates.

For Monza, use these recorded references:

- [Implemented layout and source links](docs/forensics/monza-layout-update.md), including FIA competition notes and the regional AGEA 2024 orthophotos.
- [Layout source manifest](assets/tracks/monza/reconstruction/layout.json), including reference-region bounds, barrier provenance and pit-closure exceptions.
- [Survey sources](assets/tracks/monza/reconstruction/references/SOURCES.md) and the checked-in [OSM snapshot](assets/tracks/monza/reconstruction/references/monza.osm).
- [Earlier geodata investigation](docs/forensics/monza-geodata-exploration.md) for alternatives when coverage is missing. Its engineering-survey acquisition proposal is historical; it is not a prerequisite for this aerial-scale workflow.

For every source, retain its URL or dataset identifier, document revision or capture date, retrieval date, geographic bounds, coordinate system, attribution, and which features it supports. Hash downloaded inputs. Distinguish observed, inferred and deliberately modified features. Keep uncertain sections identifiable by name and coordinates.

Use downloaded snapshots for normal builds. Fetching changing online data belongs in an explicit source-refresh step. Preserve source attribution and record whether imagery is only consulted or can be redistributed. Do not bundle reference images as game textures by default.

The existing optional Monza image-fetch command reconstructs consultation requests from the recorded bounds and writes under `build/`:

```sh
uv sync --frozen
uv run --no-sync python tools/blender/tracks/fetch_monza_layout_references.py
```

## 2. Establish the coordinate and layout contract

Use one local coordinate frame in metres for all imported sources, scene geometry and exported contact geometry. Record the geographic origin, projection and any scale correction. Apply the same transformation to road, barriers, runoff and surroundings. Do not independently stretch the road to match a lap length while leaving everything else behind.

Monza uses Blender X east, Y north and Z up. Its [survey](assets/tracks/monza/reconstruction/survey.json) records the origin and uniform plan correction. Along-track stations are metres from the control line, wrapping at the lap length. Driver-left/right must be checked after every axis reflection.

Author these separately:

- A closed centreline, road widths, elevation and crossfall, with known corner entries and exits.
- Kerb segments with an explicit side and station range, verified against references.
- Runoff polygons with a surface type and evidence for their boundaries.
- Open barrier polylines with height and thickness. Join endpoints only where a barrier actually continues or a recorded game requirement closes access.
- Escape/rejoin test paths that a car must be able to traverse.
- Buildings, stands, service roads, woodland and historic structures outside the racing area.

The first protection line goes around the available runoff. It must not follow a centreline offset through a chicane escape. A runoff polygon edge does not automatically imply a wall. Use [Monza's layout file](assets/tracks/monza/reconstruction/layout.json) as the example data structure.

## 3. Build the Blender scene

Use the Blender Python API through `uv`, with the dependencies pinned by `uv.lock`. Store authoring scripts under `tools/blender/tracks/` and editable assets under `assets/tracks/<slug>/`. Keep survey inputs, layout data, the `.blend`, runtime metadata and QA reports distinct.

Build the racing surface and reference curves first. Check lap closure, turn direction, dimensions and coordinate alignment before adding scenery. Work through named sections, with separate collections for track, runoff, barriers, fencing, signage, stands, buildings and vegetation. Give objects descriptive names that can be matched to a screenshot and a diagnostic report.

Partition asphalt, gravel, grass and kerb aprons so they do not occupy the same area and plane. Conform independent road paint to the actual asphalt triangles with a small positive clearance. The Monza repair uses a nominal 8 mm clearance and verifies more than 5 mm after float conversion. Apply the same principle to separate kerb paint. An offset must solve a measured depth conflict without becoming a visible raised strip.

Check winding after mirroring strips or swapping left and right. Ground stands, embankments and exposed structure edges against local terrain. Trace surprising geometry back to its source feature; Monza's hovering incline was part of the historic oval extending into the grandstand area. Do not hide a geometry defect with colour or lighting changes.

Use shared meshes or instances for repeated scenery. Keep placement deterministic. Material nodes, instances and visibility settings must have an explicit representation in the runtime exporter.

Add distance boards using the [braking-marker policy](docs/track_braking_markers.md) and [shared planner](tools/blender/tracks/braking_markers.py). Measure usable approach length from the previous complex's exit to the next braking corner's entry. Long approaches receive 200/150/100/50 m boards; shorter ones receive fewer. Linked turns share a sequence, and flat bends do not automatically receive boards. Record the station and side, face digits towards traffic, and preserve sightlines and escape routes.

### Update the saved Monza scene

For a layout or map-detail revision, edit the source data or generator first, then apply it to the saved scene:

```sh
uv sync --frozen
uv run --no-sync python tools/blender/tracks/monza_layout.py
```

This applies explicit barriers and runoff, trims conflicting scenery, repairs the historic-oval/pit details and generates distance boards. It saves the Blender scene and writes contact data. [monza_map_details.py](tools/blender/tracks/monza_map_details.py) retains source meshes for repeatable local repairs; account for those cached originals when intentionally replacing a repaired object's source geometry.

Use [repair_monza_rendering.py](tools/blender/tracks/repair_monza_rendering.py) when the scene needs its existing normal, paint-clearance, apron or stand-foundation repairs. It saves the scene. This is a repair operation, not a read-only diagnostic:

```sh
uv run --no-sync python tools/blender/tracks/repair_monza_rendering.py
```

### Rebuild Monza from source

Preserve manual scene edits before running `foundation`; it replaces the authored scene. Normal map-detail revisions do not need a foundation rebuild.

```sh
uv sync --frozen
uv run --no-sync python tools/blender/tracks/survey_monza.py
uv run --no-sync python tools/blender/tracks/build_monza.py --phase foundation
uv run --no-sync python tools/blender/tracks/build_monza.py --phase environment --section 0
```

Inspect section 0, then run the environment command for sections 1 through 9 in order, reviewing each section. The generator rejects duplicate or out-of-order sections. Finish with:

```sh
uv run --no-sync python tools/blender/tracks/build_monza.py --phase finalize
uv run --no-sync python tools/blender/tracks/verify_monza_reconstruction.py
```

Finalization applies the layout and rendering repairs before saving. Blender driver and elevated renders help inspect placement; they do not certify the game renderer. Optional full-scene review commands are documented in the [authoring README](assets/tracks/monza/reconstruction/README.md).

## 4. Diagnose and validate before export

Treat gameplay screenshots as evidence even when Blender looks correct. For a reported artifact, capture its track station, side, view direction and nearby landmarks. Preserve a before image and record suspicious object names, world-space bounds, dimensions and coordinates before modification.

Investigate depth conflicts first. Use Python geometry queries, projected polygon intersections and triangle-height comparisons rather than relying only on renders. A bounding-box overlap identifies candidates; it does not prove that their surfaces overlap.

| Audit | What to inspect |
| --- | --- |
| Duplicate and overlapping geometry | Duplicate faces and objects, objects repeated across collections, coplanar meshes, very small surface separation, internal faces, overlapping roof panels and mirrored copies |
| Road paint and kerbs | Paint/asphalt clearance, kerb colour/base overlap, grass or runoff crossing kerbs, upward normals, material indices and actual supporting triangles |
| Topology | Degenerate or unusually large triangles, disconnected islands, non-manifold edges and thin surfaces that only work from one side. Open sheet boundaries can be intentional; classify them before repairing. |
| Transforms and extent | Unapplied transforms, negative scale, axis reflection, extreme coordinates, implausible dimensions and incorrect parent transforms |
| Materials and UVs | Face material-slot indices, finite UV coordinates, texture mapping, alpha blending, texture transparency, backface culling and unsupported shader nodes |
| Export selection | Hidden objects that still export, source-library meshes exported twice, evaluated instances, unintended LOD overlap and disconnected geometry within otherwise valid objects |

Compare one correctly rendering kerb with one failing kerb, including topology, winding, material indices, UVs, transforms, underlying surfaces, hierarchy and exporter flags. Looking similar in Blender is not evidence that their exports are equivalent.

For a floating surface, search nearby objects and disconnected mesh components. Also search large triangles whose vertices lie outside the visible problem area. On a temporary diagnostic copy, assign unique opaque debug materials and export to the game so the offending object can be identified. Keep debug materials out of the final asset.

The current Monza checks are:

```sh
uv run --no-sync python tools/blender/tracks/verify_monza_layout.py --reapply
uv run --no-sync python tools/blender/tracks/verify_monza_rendering.py
uv run --no-sync python tools/blender/tracks/verify_monza_map_details.py
```

These check layout/scene hashes, escape clearance, grass/runoff overlap, runoff and sheet normals, paint clearance, apron self-overlap, repair repeatability, the grounded historic approach, removed pit kerbs, and marker stations/facing. They do not implement every general audit in the table. Add targeted diagnostics for new failure modes.

`verify_monza_layout.py --reapply` rebuilds in memory and compares geometry; it does not save that scene. It does write QA reports and regenerate the contact include. Run mutating or regenerating steps sequentially. A second application should not drift geometry or accumulate objects.

## 5. Export and integrate into the game

Export the saved scene and derive road data, visible barriers and collision from the same coordinate contract. Material conversion must target the actual game shader. Bake or simplify unsupported effects deliberately, preserve opaque/cutout behaviour, and validate thin geometry after triangulation.

Monza's exporter uses spatial mesh batches and foliage cards, converts to glTF, and enforces the runtime's 16-bit mesh-index limit. It records the source scene hash and refuses a layout whose hash differs from the applied scene.

```sh
uv run --no-sync python tools/blender/tracks/export_monza_runtime.py
make
uv run --no-sync python tools/blender/tracks/verify_monza_runtime.py
```

`make` configures and builds the game through the repository's dependency workflow. With an already configured build, `cmake --build build/game --parallel 4` is sufficient. Rebuild after export because export rewrites C++ includes. `generate_tracks.py --track monza` delegates to the runtime exporter; it does not rebuild the source Blender scene.

| Integration point | Current Monza example |
| --- | --- |
| Editable scene | `assets/tracks/monza/reconstruction/monza_reconstruction.blend` |
| Runtime asset and metadata | `assets/tracks/monza/reconstruction/runtime/monza.glb` and `monza.json` |
| Route, width, elevation and bank samples | `src/track_data/monza_survey.inc`, generated from survey/builder data |
| Wall contact segments and runoff triangles | `src/track_data/monza_boundaries.inc`, generated from applied Blender geometry |
| Circuit ID and route catalogue | [track_types.hpp](src/track_types.hpp) and [track_catalog.cpp](src/track_catalog.cpp) |
| GLB path, scale and expected dimensions | `TrackAssetSpec` entries in [arcade_render.cpp](src/arcade_render.cpp) |
| Circuit selection and collision dispatch | [game.cpp](src/game.cpp) |
| Shared wall-contact implementation | [authored_track_collision.hpp](src/authored_track_collision.hpp) |

Monza maps Blender `(x, y, z)` to glTF `(x, z, -y)`, then uses a uniform render scale of `1.445`. This corresponds to 17 simulation units per metre and a render scale of `0.085`. Load the asset at the agreed origin and yaw. Preserve the road-datum convention, including the existing `0.06 m` surface offset. Use asset metadata and native alignment checks instead of eyeballing the scale.

For another circuit, register its ID, catalogue data, menu entry, asset specification and relevant array/count changes. Extend generator/validator dispatch and add authored boundary dispatch where needed. Monza's authored wall path is currently selected explicitly in game code; exporting another GLB alone will not activate it for a new track. Inspect and replace any road-edge clamp that would create an invisible wall across intended runoff, within the authorized map-collision scope.

Keep visible wall position, thickness and height consistent with contact geometry. Collision must respect finite wall ends and vertical separation, and catch a car crossing a thin wall between frames. Runoff surface classification must match the exported surface polygons. Preserve escape connectivity and support progress reacquisition after a legitimate rejoin.

Manual Blender centreline edits do not automatically update the route include. Reflect route changes in the survey/builder source, regenerate the scene and exports, and verify minimap, grids, turn direction and progress against the new geometry. Do not hand-edit generated includes.

## 6. Validate in the game

Run the relevant automated checks against the rebuilt executable:

```sh
SDL_VIDEODRIVER=offscreen ctest --test-dir build/game -R '^(authored_track_collision|monza_boundary_audit|collision_dynamics_audit|arcade_vehicle_audit|race_grid_alignment_audit|track_catalog_audit|authored_asset_audit)$' --output-on-failure
```

These are the current targeted Monza checks. They cover wall contact, closed pit openings, open chicane escapes and rejoin, surface/collision behaviour, vehicle regression, grids, catalogue and asset loading. Adapt track-specific probes for another circuit. Run broader route, AI, race and performance checks when the change affects those systems. Report failures without changing vehicle tuning or weakening assertions to make a map pass.

Capture actual game views, then drive the revision:

```sh
build/game/formula_forge --capture-monza-map-review
build/game/formula_forge --capture-monza-tour
build/game/formula_forge --monza-runoff-test
```

The first command saves 16 driver views and seven right-facing grandstand views. The tour saves 72 circuit checkpoints. Images go under `build/playtest_frames/`. These are staged captures, not driven laps. The last command starts a solo session before Rettifilo; normal Monza selection loads the same asset.

Inspect road markings, both sides of kerbs, roofs, signs, transparent foliage, stand foundations, bridge clearances and distant surfaces. Match before/after viewpoints for reported defects. Test signs while approaching at speed, including whether scenery conceals a board.

Drive through intended chicane escapes and rejoin. Approach actual visible barriers and verify where contact occurs. Attempt to enter deliberately closed branches, including Monza's pit entry and exit. Check that a car can reach the real wall without an invisible road-edge clamp stopping it early. Cover wall endpoints, high-speed crossings and elevated structures with automated probes where manual driving is hard to repeat.

A valid Blender render, a valid GLB, staged game captures and a driven lap establish different things. Record which checks were completed. Never describe screenshot coverage or seven targeted tests as a full gameplay-suite pass.

## 7. Save the handoff

Keep source observations, changed object names and coordinates, layout/scene/export hashes, QA results, test commands and screenshot paths with the revision. Monza's [map-detail validation record](assets/tracks/monza/reconstruction/qa/map_detail_game_validation.json) is an example. Historical reports belong to their recorded hashes; do not present their measurements as results for a new build.

Before handing the map over, confirm that the saved `.blend`, runtime GLB, generated route/contact includes and executable belong to the same revision. Commit the generator/data changes, saved scene, required runtime assets and QA metadata together. State what changed, what was actually verified, any unresolved approximation or defect, and how to launch the build for testing.
