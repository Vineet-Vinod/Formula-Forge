---
name: map
description: Create or revise realistic racing circuits in Blender, using geographic references and validating their export and integration in the game.
---

# Circuit maps

Follow the requested scope: research, diagnosis or implementation. Preserve handling, speed, gears and core gameplay unless changes are explicitly authorized. Inspect the project's existing authoring, export and validation tools before choosing commands.

## Sources and accuracy

- Use FIA or circuit-operator documents for configuration, dimensions, turn numbering and escape/rejoin rules. Confirm road edges, kerbs, runoff and protective barriers against dated aerial imagery.
- Use OpenStreetMap (OSM) for initial geometry and surrounding roads, structures and vegetation. Resolve obscured features with Street View or other dated ground photographs where available.
- Obtain elevation from measured survey or terrain data when available. Label inferred heights and camber; do not attribute them to documents that contain only a plan view.
- Record source URLs, capture dates or revisions, coordinate transforms, attribution and uncertainty. Keep licensed source snapshots for reproducible offline builds.
- Prioritize accuracy inside the protective barriers; reconstruct the surroundings from available evidence. Preserve open escape routes. Do not infer a wall merely from a runoff polygon edge or a road offset.

## Blender construction

Use Blender's Python API through `uv` and the project's pinned dependencies. Maintain one local metre frame for road, runoff, barriers and scenery. Apply any scale correction consistently and check turn handedness after axis conversion.

Build and verify the road before scenery. Keep kerbs, runoff polygons and barrier paths explicit. Generate visible barriers and collision from the same geometry, including intentional openings, height and thickness.

Prevent overlapping asphalt, grass and kerb surfaces. Conform separate paint meshes to their supporting surface with a small positive clearance that survives export without looking raised. Check winding after mirroring, ground structures against terrain, and keep repeated-object placement deterministic.

Use documented braking-board positions where available. Otherwise follow the project's approach-length policy. Measure distances along the centreline to corner entry, group linked corners, and check visibility from the approaching car.

For revisions, update the source data or generator so changes survive rebuilding. Preserve manual edits before replacing a scene. Reapplying a repair should not accumulate offsets or duplicate geometry.

## Rendering diagnosis

Treat game screenshots as authoritative even when Blender looks correct. Record suspect object names, coordinates and bounds before modifying them.

Investigate depth conflicts first: duplicate faces/objects, coplanar sheets, paint clearance and intersecting runoff or kerbs. Then inspect normals, transforms, material indices, UVs, alpha behaviour, hidden export objects and LOD overlap. Use geometry queries to establish overlap; bounding boxes only identify candidates.

For floating geometry, inspect disconnected components and large faces extending from neighbouring areas. Compare failing geometry with a working counterpart. Use unique debug materials in a temporary export when identification is unclear. Correct the geometry or export defect rather than masking it with aesthetic changes.

## Export and integration

Match the engine's axis, origin, scale, road datum, material and index-limit conventions. Derive route data, surface classification and collision from the same source revision as the visible map. Verify alignment numerically.

Register the circuit and asset in the existing catalogue, loader and collision dispatch as needed. Check for legacy road-edge clamps that could block valid runoff. Exporting a model alone does not establish its collision or route integration. Rebuild the game after regenerating compiled track data.

Follow the project's asset layout. In Formula Forge, keep only `<slug>.blend`, `<slug>.glb`, `<slug>.json` and `<slug>_preview.png` under `assets/tracks/<slug>/`, with runtime textures embedded in the GLB. Retain required inputs beside the authoring tools; put disposable QA media and caches under `build/`. Export and validation must work without prior diagnostic output.

## Validation and handoff

Run relevant geometry, export, route-alignment and collision checks. Capture affected areas in the actual game renderer, then drive the changed sections. Test escape/rejoin paths, wall endpoints, contact against visible barriers, markings and sign readability at speed. Blender renders alone cannot establish that a game-rendering bug is fixed.

Keep the scene, runtime asset and generated game data consistent. Report what changed, what was actually tested and any unresolved uncertainty. Distinguish staged captures from driven testing; keep detailed logs under `build/`.
