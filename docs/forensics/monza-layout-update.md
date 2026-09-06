# Monza layout update

Implemented 5 September 2026. The accepted accuracy target is correct barrier placement and open runoff connectivity at aerial-reference scale, not a centimetre survey. This supersedes the strict acquisition proposal in the earlier geodata exploration.

## What changed

`assets/tracks/monza/reconstruction/layout.json` records explicit barrier polylines, runoff polygons, source references, consultation-sheet bounds and confidence. The primary spatial reference is the regional AGEA 2024 aerial imagery. FIA competition notes corroborate the Rettifilo and Roggia escape-route connectivity. The existing OSM centreline, kerb station placements and surroundings remain the base map.

Ten barrier paths replace the old centreline-offset fence generator in the final scene. The first protection line surrounds the runoff, rather than following the bends of the racing line through an escape area. The pit separator now joins the adjacent inner barriers to close pit access, as requested on 6 September. This intentional departure from the aerial reference is recorded in the layout provenance. Reference polygons replace the inferred gravel/asphalt strips at the chicanes, Lesmos, Curva Grande and Alboreto. The approach/exit links between reference sheets are explicit points too; the builder does not close gaps automatically.

The game reads contact segments generated from the same applied Blender barrier coordinates and thicknesses. Swept rectangle contact preserves finite wall ends, checks vertical overlap and catches a car crossing a thin wall in one frame. Monza no longer uses the generic six-metre road-edge clamp for physical contact. Off-track Monza projection also searches the surrounding 300 m of track so a car using a chicane escape can reacquire the exit. The usual local projection remains in use on the racing surface. Other tracks keep their existing boundaries. Existing impact-response coefficients and vehicle tuning are retained. AI planning still uses its existing road-relative limits; it does not plan overtakes through the escape roads.

Runoff surface classification uses triangles exported from the actual runoff mesh. The grass sheets are cut away from these surfaces with a 2 mm numerical margin, and grass tuft instances are removed there. Two inferred marshal huts that occupied the revised runoff are moved behind the nearest outer barrier. The old offset-based impact tyre stacks are removed. Object names, original bounds and prop movements are recorded under `reconstruction/qa/layout_*.json`.

## Limits of this version

This is an aerial approximation. Vegetation obscures some barrier faces; small service openings, temporary event protection and detailed fence construction still need track-specific review. The geometry is based on the 2024 aerial arrangement with FIA-confirmed escape connectivity, not a claim to reproduce every 2026 event change. Temporary polystyrene-block routes are not solid collision walls.

The elevation and kerb cross sections remain the previous estimates. Public FIA event notes do not provide a full measured elevation model. The FIA source is not used as evidence for those heights. The road shape itself was preserved, including the existing normalization of the OSM coordinates to a 5,793 m lap. Buildings and other scenery outside the barriers remain best-effort OSM/procedural content.

## Rebuild and test

Run from the repository root:

```sh
uv run --no-sync python tools/blender/tracks/monza_layout.py
uv run --no-sync python tools/blender/tracks/verify_monza_layout.py --reapply
uv run --no-sync python tools/blender/tracks/export_monza_runtime.py
cmake --build build/game --parallel
uv run --no-sync python tools/blender/tracks/verify_monza_runtime.py
uv run --no-sync python tools/blender/tracks/verify_monza_rendering.py
uv run --no-sync python tools/blender/tracks/verify_monza_map_details.py
SDL_VIDEODRIVER=offscreen ctest --test-dir build/game -R 'authored_track_collision|monza_boundary_audit|collision_dynamics_audit' --output-on-failure
build/game/formula_forge --monza-runoff-test
```

The last command starts a solo session just before Rettifilo. Continue straight into the paved escape road, rejoin, and deliberately approach the visible outer rail. Normal Monza selection also loads the revised map. `--capture-monza-tour` produces 72 views in the actual game renderer under `build/playtest_frames/`.

The exporter refuses a scene whose saved layout hash differs from `layout.json`. The scene, runtime GLB, contact include and game executable must all be rebuilt together after boundary edits. `build_monza.py --phase finalize` applies the layout as its last geometry stage. The existing rendering repair/verification workflow remains necessary after a full foundation/environment rebuild.

The collision audit tests both chicane escapes beyond the old clamp and impacts against every exported barrier segment. The independent collision tests cover high-speed crossing, open endpoints, initial overlap, moving away and vertical separation. Layout verification checks upward runoff normals, grass overlap and geometric repeatability. Blender images are not used to certify the game renderer.

## Repeating the recipe for another track

1. Establish one local metre coordinate frame and retain the source transformation.
2. Use official circuit/event documents to identify the configuration and escape/rejoin rules. Record what they do not measure.
3. Corroborate the road, kerbs, runoff boundaries and first protection line with georeferenced aerial images. Use ground observations to resolve concealed features. Record unresolved sections explicitly.
4. Author open barrier paths and separate surface polygons. Do not infer walls from road offsets or polygon closure.
5. Generate display and contact from the same applied geometry. Export the source hash with both.
6. Verify road clearance, escape connectivity, wall ends and surfaces in the game; retain OSM for the surrounding area.

The optional `fetch_monza_layout_references.py` script reconstructs the consultation-sheet requests from the recorded bounds and survey transform. It writes images only under `build/`; no aerial images or Google content are packaged with the game.

## References

- [AGEA regional orthophoto WMS](https://www.cartografia.servizirl.it/arcgis5/services/BaseMap/Ortofoto2024/ImageServer/WMSServer)
- [FIA Italian GP competition notes V2](https://www.fia.com/system/files/decision-document/2026_italian_grand_prix_-_race_directors_competition_notes_v2.pdf)
- [FIA circuit map and pit-lane pack](https://www.fia.com/system/files/decision-document/2026_italian_grand_prix_-_competition_notes_-_circuit_map_pit_lane_drawing_emergency_exits_map_and_red_zone.pdf)
- Existing OSM snapshot: `assets/tracks/monza/reconstruction/references/monza.osm`; source hash and coordinate conversion are retained in `survey.json`.

## Verification recorded for this build

Seven targeted CTest audits passed: authored wall sweeps, Monza boundaries/rejoin, collision dynamics and surface penalties, vehicle dynamics, starting grids, track catalogue and runtime asset loading. The Blender geometry checks passed, including repeat application, upward sheets and zero grass/runoff overlap. The runtime route comparison found a maximum planar difference of 0.115 m from the preserved authoring road.

An actual game session drove straight through Rettifilo at 143 km/h without barrier contact, reacquired progress beyond the chicane, then deliberately hit the visible outside rail. The final contact frame and telemetry agree. Results and relative screenshot paths are recorded in `reconstruction/qa/layout_game_validation.json`; screenshots remain under `build/agent_play_frames/`. Both chicane escape paths are also checked by the collision audits. A complete manual lap remains useful for judging approximation errors.

## Map detail follow-up, 6 September 2026

The hovering incline before the driver-right Alta Velocità grandstands came from `Historic oval 1313097098` and the adjoining `Historic oval 19982933`. The environment generator had applied banking according to northing, including the straight approach, and left exposed thin edges above terrain. The repair flattens the straight approach, blends banking according to its direction, removes faces intersecting grandstand footprints and joins the exposed local perimeter to the ground. Original and resulting bounds are recorded in `qa/map_detail_repairs.json`.

Pit entry and exit now have continuous visible and collidable barriers. The straight-section kerbs, green apron and pit branch road/paint tapers have been removed. The central pit lane remains behind the wall. The collision regression includes attempts to cross both former openings while preserving the open chicane escapes.

Twenty braking boards follow the [shared distance-board policy](../track_braking_markers.md). Rettifilo, Roggia, Ascari and Alboreto get 200/150/100/50 m sequences. Each Lesmo gets 100/50 m. Distances refer to recorded corner entries, with board stations and orientation verified against the actual scene geometry.

`build/game/formula_forge --capture-monza-map-review` captures 16 driver views and seven additional views towards the right grandstands in the game renderer. Images are written under `build/playtest_frames/monza_map_review*.png`. Geometry, game audit and screenshot records for this follow-up are in `qa/map_detail_validation.json` and `qa/map_detail_game_validation.json`. The earlier driven-escape record above belongs to the 5 September build.
